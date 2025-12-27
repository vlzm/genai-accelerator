"""
Database models for KYC/AML Analyzer.

Uses SQLModel for ORM with Pydantic validation.
Supports optional RAG with pgvector for similarity search.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any

from pydantic import field_validator
from sqlmodel import Field, SQLModel, Relationship, JSON, Column

# Import pgvector only if available (RAG feature)
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None  # type: ignore


class Transaction(SQLModel, table=True):
    """
    Represents a financial transaction to be analyzed.
    
    The comment field may contain PII and should be handled securely.
    """
    __tablename__ = "transactions"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    comment: str = Field(max_length=2000, description="Transaction comment (may contain PII)")
    amount: Decimal = Field(decimal_places=2, description="Transaction amount")
    currency: str = Field(default="USD", max_length=3)
    sender_id: str = Field(max_length=100, description="Sender identifier")
    receiver_id: str = Field(max_length=100, description="Receiver identifier")
    
    # ABAC fields for access control
    region: str = Field(default="Global", max_length=20, description="Geographic region for ABAC")
    created_by_user_id: Optional[str] = Field(default=None, max_length=50, description="User who created this transaction")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship to risk reports
    risk_reports: list["RiskReport"] = Relationship(back_populates="transaction")
    
    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.upper()


class RiskReport(SQLModel, table=True):
    """
    AI-generated risk assessment for a transaction.
    
    Contains the LLM analysis results including risk score and factors.
    Includes observability fields for evaluation and improvement.
    """
    __tablename__ = "risk_reports"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transactions.id", index=True)
    risk_score: int = Field(ge=0, le=100, description="Risk score from 0 (safe) to 100 (critical)")
    risk_level: str = Field(max_length=20, description="LOW, MEDIUM, HIGH, CRITICAL")
    risk_factors: list[str] = Field(default=[], sa_column=Column(JSON))
    llm_reasoning: str = Field(description="LLM explanation of the risk assessment")
    model_version: str = Field(max_length=50, description="Model used for analysis")
    
    # ABAC fields for access control (denormalized for query performance)
    region: str = Field(default="Global", max_length=20, description="Region (copied from transaction)")
    analyzed_by_user_id: Optional[str] = Field(default=None, max_length=50, description="User who triggered analysis")
    
    # OBSERVABILITY FIELDS - LLM Tracing
    llm_trace: dict = Field(default={}, sa_column=Column(JSON), description="Full trace: input, tools, output")
    
    # EVALUATION FIELDS - Human Feedback Loop
    human_feedback: Optional[bool] = Field(default=None, description="Human verdict: True=correct, False=incorrect")
    feedback_comment: Optional[str] = Field(default=None, max_length=500, description="Optional feedback details")
    feedback_by_user_id: Optional[str] = Field(default=None, max_length=50, description="User who provided feedback")
    feedback_at: Optional[datetime] = Field(default=None, description="When feedback was provided")
    
    # GUARDRAIL FLAGS - Automated safety checks
    guardrail_status: str = Field(default="PASS", max_length=30, description="PASS, FAIL_PII_LEAKAGE, FAIL_LOW_QUALITY, etc.")
    guardrail_details: Optional[str] = Field(default=None, max_length=500, description="Details if guardrail failed")
    
    # RAG / VECTOR SEARCH - Embedding for similarity search
    # Note: Only populated when RAG_ENABLED=true, otherwise null
    # Using raw List[float] - the actual Vector type is applied via sa_column
    embedding: Optional[List[float]] = Field(
        default=None,
        sa_column=Column(Vector(1536)) if PGVECTOR_AVAILABLE else None,
        description="Vector embedding for similarity search (1536 dimensions for text-embedding-3-small)"
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship back to transaction
    transaction: Optional[Transaction] = Relationship(back_populates="risk_reports")
    
    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        allowed = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"risk_level must be one of {allowed}")
        return v_upper


# Pydantic models for API/Service layer (not stored in DB)

class TransactionCreate(SQLModel):
    """Input model for creating a new transaction."""
    comment: str = Field(max_length=2000)
    amount: Decimal = Field(decimal_places=2)
    currency: str = Field(default="USD", max_length=3)
    sender_id: str = Field(max_length=100)
    receiver_id: str = Field(max_length=100)
    region: str = Field(default="Global", max_length=20)


class RiskAnalysisResult(SQLModel):
    """Output model from LLM risk analysis."""
    risk_score: int = Field(ge=0, le=100)
    risk_level: str
    risk_factors: list[str]
    reasoning: str

