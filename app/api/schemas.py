"""
Pydantic schemas for API request/response validation.

These are separate from database models to maintain clean API contracts.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


# ============ Request Schemas ============

class TransactionAnalyzeRequest(BaseModel):
    """Request to analyze a transaction for AML/KYC risk."""
    sender_id: str = Field(..., max_length=100, description="Sender identifier")
    receiver_id: str = Field(..., max_length=100, description="Receiver identifier")
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(default="USD", max_length=3, description="Currency code")
    comment: str = Field(..., max_length=2000, description="Transaction comment to analyze")
    region: str = Field(default="Global", max_length=20, description="Geographic region")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sender_id": "ACC-123456",
                    "receiver_id": "ACC-789012",
                    "amount": 50000.00,
                    "currency": "USD",
                    "comment": "Payment for consulting services to Ahmed Hassan",
                    "region": "EMEA",
                }
            ]
        }
    }


class FeedbackRequest(BaseModel):
    """Request to submit human feedback for a risk report."""
    report_id: int = Field(..., description="ID of the risk report")
    feedback: bool = Field(..., description="True = correct, False = incorrect")
    comment: Optional[str] = Field(None, max_length=500, description="Optional explanation")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "report_id": 1,
                    "feedback": False,
                    "comment": "Risk score too high, this is a known customer",
                }
            ]
        }
    }


# ============ Response Schemas ============

class TransactionResponse(BaseModel):
    """Transaction details in API response."""
    id: int
    sender_id: str
    receiver_id: str
    amount: Decimal
    currency: str
    comment: str
    region: str
    created_at: datetime


class RiskReportResponse(BaseModel):
    """Risk report details in API response."""
    id: int
    transaction_id: int
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: str
    risk_factors: list[str]
    reasoning: str
    model_version: str
    region: str
    guardrail_status: str
    guardrail_details: Optional[str]
    human_feedback: Optional[bool]
    created_at: datetime
    
    # Observability - optional, only if requested
    llm_trace: Optional[dict] = None


class AnalysisResponse(BaseModel):
    """Response from transaction analysis."""
    transaction: TransactionResponse
    report: RiskReportResponse
    message: str = "Analysis completed successfully"


class FeedbackResponse(BaseModel):
    """Response from feedback submission."""
    report_id: int
    feedback_recorded: bool
    message: str


class FeedbackStatsResponse(BaseModel):
    """Model evaluation statistics."""
    total_reports: int
    with_feedback: int
    positive_feedback: int
    negative_feedback: int
    pending_feedback: int
    feedback_rate: float
    accuracy_estimate: Optional[float]
    guardrail_failures: dict[str, int]


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


class SimilarCaseResponse(BaseModel):
    """A similar historical case from RAG search."""
    report_id: int
    risk_score: int
    risk_level: str
    risk_factors: list[str]
    region: str
    created_at: datetime


class SimilarCasesResponse(BaseModel):
    """Response from similar cases search."""
    query_report_id: int
    similar_cases: list[SimilarCaseResponse]
    rag_enabled: bool
    message: str

