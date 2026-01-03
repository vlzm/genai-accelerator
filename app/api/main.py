"""
FastAPI Application for Azure GenAI Accelerator.

REST API for programmatic access to AI-powered analysis.
Designed for integration with external systems and microservices.

Run with: uvicorn app.api.main:app --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, get_session
from app.models import RequestCreate
from app.services.processor import Processor
from app.services.auth_mock import get_current_user, UserProfile, Permission
from app.services.secret_manager import get_settings
from app.api.schemas import (
    AnalyzeRequest,
    FeedbackRequest,
    AnalyzeResponse,
    RequestResponse,
    AnalysisResultResponse,
    FeedbackResponse,
    FeedbackStatsResponse,
    HealthResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

# App version
API_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("Initializing database...")
    init_db()
    logger.info("FastAPI started successfully")
    yield
    # Shutdown
    logger.info("FastAPI shutting down")


app = FastAPI(
    title="Azure GenAI Accelerator API",
    description="""
## Azure GenAI Accelerator - REST API

This API provides programmatic access to AI-powered analysis.

### Features
- **Analysis**: Submit data for AI analysis
- **Results**: Retrieve and filter analysis results
- **Human Feedback**: Submit feedback for model improvement
- **Evaluation Metrics**: Access model quality statistics

### Security
- RBAC/ABAC access control via user headers
- All endpoints require authentication (simulated via X-User-Key header)
- Designed for Azure Managed Identity in production

### Observability
- Full LLM tracing available on results
- Validation status for quality checks
- Human feedback collection for model evaluation
    """,
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    },
    lifespan=lifespan,
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Dependencies ============

def get_user_from_header(
    x_user_key: str = Header(
        default="officer_south",
        description="Mock user key for RBAC/ABAC (e.g., admin_global, officer_south)",
    )
) -> UserProfile:
    """
    Extract user from request header.
    
    In production, this would validate Azure AD token and extract claims.
    For local development, we use a mock user key.
    """
    try:
        return get_current_user(x_user_key)
    except KeyError:
        raise HTTPException(
            status_code=401,
            detail=f"Unknown user key: {x_user_key}. Use one of: admin_global, senior_global, officer_south, officer_north, viewer_south",
        )


# ============ Health & Info Endpoints ============

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
)
async def health_check():
    """
    Check API health and dependencies.
    
    Returns status of database connection and LLM provider.
    """
    settings = get_settings()
    
    # Check database
    db_status = "healthy"
    try:
        with get_session() as session:
            session.exec("SELECT 1")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        llm_provider=settings.llm_provider,
        version=API_VERSION,
    )


@app.get(
    "/",
    tags=["System"],
    summary="API root",
)
async def root():
    """API root with documentation links."""
    return {
        "name": "Azure GenAI Accelerator API",
        "version": API_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


# ============ Analysis Endpoints ============

@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
    tags=["Analysis"],
    summary="Analyze input data with AI",
    responses={
        403: {"model": ErrorResponse, "description": "User lacks ANALYZE permission"},
    },
)
async def analyze(
    request: AnalyzeRequest,
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Submit input data for AI-powered analysis.
    
    The analysis includes:
    - Content processing and categorization
    - Score assignment based on significance
    - Summary generation
    
    **Required Permission**: ANALYZE_TRANSACTIONS
    
    **ABAC**: Request will be tagged with user's region if not specified.
    """
    try:
        with get_session() as session:
            processor = Processor(session, user=user)
            
            request_data = RequestCreate(
                input_text=request.input_text,
                context=request.context,
                region=request.region,
            )
            
            req, result = processor.process_request(request_data)
            
            return AnalyzeResponse(
                request=RequestResponse(
                    id=req.id,
                    input_text=req.input_text,
                    context=req.context,
                    region=req.region,
                    created_at=req.created_at,
                ),
                result=AnalysisResultResponse(
                    id=result.id,
                    request_id=result.request_id,
                    score=result.score,
                    categories=result.categories,
                    summary=result.summary,
                    processed_content=result.processed_content,
                    model_version=result.model_version,
                    region=result.region,
                    validation_status=result.validation_status,
                    validation_details=result.validation_details,
                    human_feedback=result.human_feedback,
                    created_at=result.created_at,
                    llm_trace=result.llm_trace,
                ),
            )
            
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/results",
    response_model=list[AnalysisResultResponse],
    tags=["Results"],
    summary="Get analysis results",
)
async def get_results(
    limit: int = Query(default=20, ge=1, le=100, description="Max results to return"),
    min_score: Optional[int] = Query(default=None, ge=0, le=100, description="Filter by minimum score"),
    region: Optional[str] = Query(default=None, description="Filter by region"),
    include_trace: bool = Query(default=False, description="Include LLM trace in response"),
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Retrieve analysis results with optional filtering.
    
    **ABAC Applied**: Users only see results from their accessible regions
    and within their clearance level.
    
    **Required Permission**: VIEW_TRANSACTIONS
    """
    try:
        with get_session() as session:
            processor = Processor(session, user=user)
            
            if min_score is not None:
                results = processor.get_high_score_results(min_score=min_score, limit=limit)
            elif region:
                results = processor.get_results_by_region(region, limit=limit)
            else:
                results = processor.get_recent_results(limit=limit)
            
            return [
                AnalysisResultResponse(
                    id=r.id,
                    request_id=r.request_id,
                    score=r.score,
                    categories=r.categories,
                    summary=r.summary,
                    processed_content=r.processed_content,
                    model_version=r.model_version,
                    region=r.region,
                    validation_status=r.validation_status,
                    validation_details=r.validation_details,
                    human_feedback=r.human_feedback,
                    created_at=r.created_at,
                    llm_trace=r.llm_trace if include_trace else None,
                )
                for r in results
            ]
            
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Failed to fetch results")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/results/{result_id}",
    response_model=AnalysisResultResponse,
    tags=["Results"],
    summary="Get a specific result by ID",
)
async def get_result(
    result_id: int,
    include_trace: bool = Query(default=True, description="Include LLM trace"),
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Retrieve a specific analysis result by ID.
    
    **ABAC Applied**: Access denied if result is outside user's region/clearance.
    """
    try:
        with get_session() as session:
            processor = Processor(session, user=user)
            
            # Get all results and find by ID (simple approach)
            results = processor.get_recent_results(limit=1000)
            result = next((r for r in results if r.id == result_id), None)
            
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail=f"Result {result_id} not found or not accessible",
                )
            
            return AnalysisResultResponse(
                id=result.id,
                request_id=result.request_id,
                score=result.score,
                categories=result.categories,
                summary=result.summary,
                processed_content=result.processed_content,
                model_version=result.model_version,
                region=result.region,
                validation_status=result.validation_status,
                validation_details=result.validation_details,
                human_feedback=result.human_feedback,
                created_at=result.created_at,
                llm_trace=result.llm_trace if include_trace else None,
            )
            
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Failed to fetch result")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Feedback Endpoints ============

@app.post(
    "/feedback",
    response_model=FeedbackResponse,
    tags=["Feedback"],
    summary="Submit human feedback for a result",
)
async def submit_feedback(
    request: FeedbackRequest,
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Submit human feedback for model evaluation.
    
    This enables the Human-in-the-Loop data flywheel:
    - Builds "Golden Dataset" for model evaluation
    - Enables error analysis when model makes mistakes
    - Collects data for potential fine-tuning
    
    **Required Permission**: VIEW_TRANSACTIONS (to access the result)
    """
    try:
        with get_session() as session:
            processor = Processor(session, user=user)
            
            result = processor.submit_feedback(
                result_id=request.result_id,
                feedback=request.feedback,
                comment=request.comment,
            )
            
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail=f"Result {request.result_id} not found or not accessible",
                )
            
            feedback_type = "positive" if request.feedback else "negative"
            return FeedbackResponse(
                result_id=request.result_id,
                feedback_recorded=True,
                message=f"Feedback recorded as {feedback_type}. Thank you for improving the model!",
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to submit feedback")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/feedback/stats",
    response_model=FeedbackStatsResponse,
    tags=["Feedback"],
    summary="Get feedback statistics for model evaluation",
)
async def get_feedback_stats(
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Get model evaluation statistics based on human feedback.
    
    Returns:
    - Feedback counts (positive/negative/pending)
    - Estimated accuracy based on human verdicts
    - Validation failure breakdown
    
    **ABAC Applied**: Statistics are scoped to user's accessible data.
    """
    try:
        with get_session() as session:
            processor = Processor(session, user=user)
            stats = processor.get_feedback_stats()
            
            return FeedbackStatsResponse(**stats)
            
    except Exception as e:
        logger.exception("Failed to fetch feedback stats")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/results/needs-review",
    response_model=list[AnalysisResultResponse],
    tags=["Feedback"],
    summary="Get results needing human review",
)
async def get_results_needing_review(
    limit: int = Query(default=20, ge=1, le=100),
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Get prioritized queue of results needing human review.
    
    Priority order:
    1. Results with validation failures
    2. High-score results without feedback
    3. Recent results without feedback
    """
    try:
        with get_session() as session:
            processor = Processor(session, user=user)
            results = processor.get_results_needing_review(limit=limit)
            
            return [
                AnalysisResultResponse(
                    id=r.id,
                    request_id=r.request_id,
                    score=r.score,
                    categories=r.categories,
                    summary=r.summary,
                    processed_content=r.processed_content,
                    model_version=r.model_version,
                    region=r.region,
                    validation_status=r.validation_status,
                    validation_details=r.validation_details,
                    human_feedback=r.human_feedback,
                    created_at=r.created_at,
                    llm_trace=r.llm_trace,
                )
                for r in results
            ]
            
    except Exception as e:
        logger.exception("Failed to fetch results needing review")
        raise HTTPException(status_code=500, detail=str(e))
