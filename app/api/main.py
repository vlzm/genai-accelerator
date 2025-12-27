"""
FastAPI Application for KYC/AML Analyzer.

REST API for programmatic access to transaction analysis.
Designed for integration with external systems and microservices.

Run with: uvicorn app.api.main:app --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, get_session
from app.models import TransactionCreate
from app.services.risk_engine import RiskEngine
from app.services.auth_mock import get_current_user, UserProfile, Permission
from app.services.secret_manager import get_settings
from app.api.schemas import (
    TransactionAnalyzeRequest,
    FeedbackRequest,
    AnalysisResponse,
    TransactionResponse,
    RiskReportResponse,
    FeedbackResponse,
    FeedbackStatsResponse,
    HealthResponse,
    ErrorResponse,
    SimilarCaseResponse,
    SimilarCasesResponse,
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
    title="KYC/AML Analyzer API",
    description="""
## Secure KYC/AML Transaction Risk Analysis API

This API provides programmatic access to AI-powered AML/KYC risk analysis.

### Features
- **Transaction Analysis**: Submit transactions for risk assessment
- **Risk Reports**: Retrieve and filter risk reports
- **Human Feedback**: Submit feedback for model improvement
- **Evaluation Metrics**: Access model quality statistics

### Security
- RBAC/ABAC access control via user headers
- All endpoints require authentication (simulated via X-User-Key header)
- Designed for Azure Managed Identity in production

### Observability
- Full LLM tracing available on reports
- Guardrail status for safety checks
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
        "name": "KYC/AML Analyzer API",
        "version": API_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


# ============ Transaction Analysis Endpoints ============

@app.post(
    "/transactions/analyze",
    response_model=AnalysisResponse,
    tags=["Transactions"],
    summary="Analyze a transaction for AML/KYC risk",
    responses={
        403: {"model": ErrorResponse, "description": "User lacks ANALYZE_TRANSACTIONS permission"},
    },
)
async def analyze_transaction(
    request: TransactionAnalyzeRequest,
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Submit a transaction for AI-powered risk analysis.
    
    The analysis includes:
    - Sanctions list checking
    - PEP (Politically Exposed Person) verification
    - Amount threshold validation
    - Risk scoring and factor identification
    
    **Required Permission**: ANALYZE_TRANSACTIONS
    
    **ABAC**: Transaction will be tagged with user's region if not specified.
    """
    try:
        with get_session() as session:
            engine = RiskEngine(session, user=user)
            
            transaction_data = TransactionCreate(
                comment=request.comment,
                amount=request.amount,
                currency=request.currency,
                sender_id=request.sender_id,
                receiver_id=request.receiver_id,
                region=request.region,
            )
            
            transaction, report = engine.process_transaction(transaction_data)
            
            return AnalysisResponse(
                transaction=TransactionResponse(
                    id=transaction.id,
                    sender_id=transaction.sender_id,
                    receiver_id=transaction.receiver_id,
                    amount=transaction.amount,
                    currency=transaction.currency,
                    comment=transaction.comment,
                    region=transaction.region,
                    created_at=transaction.created_at,
                ),
                report=RiskReportResponse(
                    id=report.id,
                    transaction_id=report.transaction_id,
                    risk_score=report.risk_score,
                    risk_level=report.risk_level,
                    risk_factors=report.risk_factors,
                    reasoning=report.llm_reasoning,
                    model_version=report.model_version,
                    region=report.region,
                    guardrail_status=report.guardrail_status,
                    guardrail_details=report.guardrail_details,
                    human_feedback=report.human_feedback,
                    created_at=report.created_at,
                    llm_trace=report.llm_trace,
                ),
            )
            
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/reports",
    response_model=list[RiskReportResponse],
    tags=["Reports"],
    summary="Get risk reports",
)
async def get_reports(
    limit: int = Query(default=20, ge=1, le=100, description="Max reports to return"),
    min_score: Optional[int] = Query(default=None, ge=0, le=100, description="Filter by minimum risk score"),
    region: Optional[str] = Query(default=None, description="Filter by region"),
    include_trace: bool = Query(default=False, description="Include LLM trace in response"),
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Retrieve risk reports with optional filtering.
    
    **ABAC Applied**: Users only see reports from their accessible regions
    and within their clearance level.
    
    **Required Permission**: VIEW_TRANSACTIONS
    """
    try:
        with get_session() as session:
            engine = RiskEngine(session, user=user)
            
            if min_score is not None:
                reports = engine.get_high_risk_transactions(min_score=min_score, limit=limit)
            elif region:
                reports = engine.get_reports_by_region(region, limit=limit)
            else:
                reports = engine.get_recent_reports(limit=limit)
            
            return [
                RiskReportResponse(
                    id=r.id,
                    transaction_id=r.transaction_id,
                    risk_score=r.risk_score,
                    risk_level=r.risk_level,
                    risk_factors=r.risk_factors,
                    reasoning=r.llm_reasoning,
                    model_version=r.model_version,
                    region=r.region,
                    guardrail_status=r.guardrail_status,
                    guardrail_details=r.guardrail_details,
                    human_feedback=r.human_feedback,
                    created_at=r.created_at,
                    llm_trace=r.llm_trace if include_trace else None,
                )
                for r in reports
            ]
            
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Failed to fetch reports")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/reports/{report_id}",
    response_model=RiskReportResponse,
    tags=["Reports"],
    summary="Get a specific report by ID",
)
async def get_report(
    report_id: int,
    include_trace: bool = Query(default=True, description="Include LLM trace"),
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Retrieve a specific risk report by ID.
    
    **ABAC Applied**: Access denied if report is outside user's region/clearance.
    """
    try:
        with get_session() as session:
            engine = RiskEngine(session, user=user)
            
            # Get all reports and find by ID (simple approach)
            reports = engine.get_recent_reports(limit=1000)
            report = next((r for r in reports if r.id == report_id), None)
            
            if not report:
                raise HTTPException(
                    status_code=404,
                    detail=f"Report {report_id} not found or not accessible",
                )
            
            return RiskReportResponse(
                id=report.id,
                transaction_id=report.transaction_id,
                risk_score=report.risk_score,
                risk_level=report.risk_level,
                risk_factors=report.risk_factors,
                reasoning=report.llm_reasoning,
                model_version=report.model_version,
                region=report.region,
                guardrail_status=report.guardrail_status,
                guardrail_details=report.guardrail_details,
                human_feedback=report.human_feedback,
                created_at=report.created_at,
                llm_trace=report.llm_trace if include_trace else None,
            )
            
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Failed to fetch report")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/reports/{report_id}/similar",
    response_model=SimilarCasesResponse,
    tags=["Reports"],
    summary="Find similar historical cases (RAG)",
)
async def get_similar_cases(
    report_id: int,
    limit: int = Query(default=3, ge=1, le=10, description="Max similar cases"),
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Find similar historical cases using RAG vector search.
    
    Uses pgvector for semantic similarity search to find past transactions
    with similar patterns. Helps compliance officers make informed decisions.
    
    **Feature Toggle**: Set RAG_ENABLED=false to disable.
    
    **ABAC Applied**: Results filtered by user's accessible regions.
    """
    try:
        with get_session() as session:
            engine = RiskEngine(session, user=user)
            
            # Check if RAG is enabled
            if not engine.is_rag_enabled():
                return SimilarCasesResponse(
                    query_report_id=report_id,
                    similar_cases=[],
                    rag_enabled=False,
                    message="RAG is disabled. Set RAG_ENABLED=true to enable.",
                )
            
            # Find the report
            reports = engine.get_recent_reports(limit=1000)
            report = next((r for r in reports if r.id == report_id), None)
            
            if not report:
                raise HTTPException(
                    status_code=404,
                    detail=f"Report {report_id} not found or not accessible",
                )
            
            # Find similar cases
            similar = engine.find_similar_cases(report, limit=limit)
            
            return SimilarCasesResponse(
                query_report_id=report_id,
                similar_cases=[
                    SimilarCaseResponse(
                        report_id=s.id,
                        risk_score=s.risk_score,
                        risk_level=s.risk_level,
                        risk_factors=s.risk_factors,
                        region=s.region,
                        created_at=s.created_at,
                    )
                    for s in similar
                ],
                rag_enabled=True,
                message=f"Found {len(similar)} similar cases",
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to find similar cases")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Feedback Endpoints ============

@app.post(
    "/feedback",
    response_model=FeedbackResponse,
    tags=["Feedback"],
    summary="Submit human feedback for a report",
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
    
    **Required Permission**: VIEW_TRANSACTIONS (to access the report)
    """
    try:
        with get_session() as session:
            engine = RiskEngine(session, user=user)
            
            report = engine.submit_feedback(
                report_id=request.report_id,
                feedback=request.feedback,
                comment=request.comment,
            )
            
            if not report:
                raise HTTPException(
                    status_code=404,
                    detail=f"Report {request.report_id} not found or not accessible",
                )
            
            feedback_type = "positive" if request.feedback else "negative"
            return FeedbackResponse(
                report_id=request.report_id,
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
    - Guardrail failure breakdown
    
    **ABAC Applied**: Statistics are scoped to user's accessible data.
    """
    try:
        with get_session() as session:
            engine = RiskEngine(session, user=user)
            stats = engine.get_feedback_stats()
            
            return FeedbackStatsResponse(**stats)
            
    except Exception as e:
        logger.exception("Failed to fetch feedback stats")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/reports/needs-review",
    response_model=list[RiskReportResponse],
    tags=["Feedback"],
    summary="Get reports needing human review",
)
async def get_reports_needing_review(
    limit: int = Query(default=20, ge=1, le=100),
    user: UserProfile = Depends(get_user_from_header),
):
    """
    Get prioritized queue of reports needing human review.
    
    Priority order:
    1. Reports with guardrail failures
    2. High-risk reports without feedback
    3. Recent reports without feedback
    """
    try:
        with get_session() as session:
            engine = RiskEngine(session, user=user)
            reports = engine.get_reports_needing_review(limit=limit)
            
            return [
                RiskReportResponse(
                    id=r.id,
                    transaction_id=r.transaction_id,
                    risk_score=r.risk_score,
                    risk_level=r.risk_level,
                    risk_factors=r.risk_factors,
                    reasoning=r.llm_reasoning,
                    model_version=r.model_version,
                    region=r.region,
                    guardrail_status=r.guardrail_status,
                    guardrail_details=r.guardrail_details,
                    human_feedback=r.human_feedback,
                    created_at=r.created_at,
                    llm_trace=r.llm_trace,
                )
                for r in reports
            ]
            
    except Exception as e:
        logger.exception("Failed to fetch reports needing review")
        raise HTTPException(status_code=500, detail=str(e))

