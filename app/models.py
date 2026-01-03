"""
Database models for Azure GenAI Accelerator.

Uses SQLModel for ORM with Pydantic validation.
Generic models for any AI-powered analysis use case.
"""

from datetime import datetime
from typing import Optional, List

from pydantic import field_validator
from sqlmodel import Field, SQLModel, Relationship, JSON, Column


class Request(SQLModel, table=True):
    """
    Represents an input request to be analyzed.
    
    Generic model that can hold any text input with optional context.
    """
    __tablename__ = "requests"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    input_text: str = Field(max_length=5000, description="Primary input text for analysis")
    context: Optional[str] = Field(default=None, max_length=2000, description="Additional context")
    
    # ABAC fields for access control
    region: str = Field(default="Global", max_length=20, description="Geographic region for ABAC")
    created_by_user_id: Optional[str] = Field(default=None, max_length=50, description="User who created this request")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship to analysis results
    results: list["AnalysisResult"] = Relationship(back_populates="request")


class AnalysisResult(SQLModel, table=True):
    """
    AI-generated analysis result for a request.
    
    Contains the LLM analysis results including score and categories.
    Includes observability fields for evaluation and improvement.
    """
    __tablename__ = "analysis_results"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    request_id: int = Field(foreign_key="requests.id", index=True)
    
    # Analysis output - generic fields
    score: int = Field(ge=0, le=100, description="Analysis score from 0 to 100")
    categories: list[str] = Field(default=[], sa_column=Column(JSON), description="Identified categories/tags")
    summary: str = Field(description="LLM summary/reasoning")
    processed_content: Optional[str] = Field(default=None, description="Processed/transformed content")
    
    model_version: str = Field(max_length=50, description="Model used for analysis")
    
    # ABAC fields for access control (denormalized for query performance)
    region: str = Field(default="Global", max_length=20, description="Region (copied from request)")
    analyzed_by_user_id: Optional[str] = Field(default=None, max_length=50, description="User who triggered analysis")
    
    # OBSERVABILITY FIELDS - LLM Tracing
    llm_trace: dict = Field(default={}, sa_column=Column(JSON), description="Full trace: input, tools, output")
    
    # EVALUATION FIELDS - Human Feedback Loop
    human_feedback: Optional[bool] = Field(default=None, description="Human verdict: True=correct, False=incorrect")
    feedback_comment: Optional[str] = Field(default=None, max_length=500, description="Optional feedback details")
    feedback_by_user_id: Optional[str] = Field(default=None, max_length=50, description="User who provided feedback")
    feedback_at: Optional[datetime] = Field(default=None, description="When feedback was provided")
    
    # VALIDATION FLAGS - Automated safety checks
    validation_status: str = Field(default="PASS", max_length=30, description="PASS, FAIL_LOW_QUALITY, etc.")
    validation_details: Optional[str] = Field(default=None, max_length=500, description="Details if validation failed")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship back to request
    request: Optional[Request] = Relationship(back_populates="results")


# Pydantic models for API/Service layer (not stored in DB)

class RequestCreate(SQLModel):
    """Input model for creating a new request."""
    input_text: str = Field(max_length=5000)
    context: Optional[str] = Field(default=None, max_length=2000)
    region: str = Field(default="Global", max_length=20)


class AnalysisOutput(SQLModel):
    """Output model from LLM analysis."""
    score: int = Field(ge=0, le=100)
    categories: list[str]
    summary: str
    processed_content: Optional[str] = None
