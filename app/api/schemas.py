"""
Pydantic schemas for API request/response validation.

These are separate from database models to maintain clean API contracts.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============ Request Schemas ============

class AnalyzeRequest(BaseModel):
    """Request to analyze input data."""
    input_text: str = Field(..., max_length=5000, description="Primary input text to analyze")
    context: Optional[str] = Field(None, max_length=2000, description="Additional context")
    region: str = Field(default="Global", max_length=20, description="Geographic region")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "input_text": "Analyze this text for any interesting patterns or insights.",
                    "context": "This is a sample input for demonstration purposes.",
                    "region": "EMEA",
                }
            ]
        }
    }


class FeedbackRequest(BaseModel):
    """Request to submit human feedback for an analysis result."""
    result_id: int = Field(..., description="ID of the analysis result")
    feedback: bool = Field(..., description="True = correct, False = incorrect")
    comment: Optional[str] = Field(None, max_length=500, description="Optional explanation")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "result_id": 1,
                    "feedback": False,
                    "comment": "Score was too high for this input",
                }
            ]
        }
    }


# ============ Response Schemas ============

class RequestResponse(BaseModel):
    """Request details in API response."""
    id: int
    input_text: str
    context: Optional[str]
    region: str
    created_at: datetime


class AnalysisResultResponse(BaseModel):
    """Analysis result details in API response."""
    id: int
    request_id: int
    score: int = Field(..., ge=0, le=100)
    categories: list[str]
    summary: str
    processed_content: Optional[str]
    model_version: str
    region: str
    validation_status: str
    validation_details: Optional[str]
    human_feedback: Optional[bool]
    created_at: datetime
    
    # Observability - optional, only if requested
    llm_trace: Optional[dict] = None


class AnalyzeResponse(BaseModel):
    """Response from analysis endpoint."""
    request: RequestResponse
    result: AnalysisResultResponse
    message: str = "Analysis completed successfully"


class FeedbackResponse(BaseModel):
    """Response from feedback submission."""
    result_id: int
    feedback_recorded: bool
    message: str


class FeedbackStatsResponse(BaseModel):
    """Model evaluation statistics."""
    total_results: int
    with_feedback: int
    positive_feedback: int
    negative_feedback: int
    pending_feedback: int
    feedback_rate: float
    accuracy_estimate: Optional[float]
    validation_failures: dict[str, int]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    database: str
    llm_provider: str
    version: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
