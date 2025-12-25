"""
Database models for KYC/AML Analyzer.

Uses SQLModel for ORM with Pydantic validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel, Relationship, JSON, Column


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


class RiskAnalysisResult(SQLModel):
    """Output model from LLM risk analysis."""
    risk_score: int = Field(ge=0, le=100)
    risk_level: str
    risk_factors: list[str]
    reasoning: str

