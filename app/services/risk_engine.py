"""
Risk Engine - Business Logic Layer.

Orchestrates the risk analysis workflow:
1. Receives transaction data
2. Calls LLM service for analysis
3. Stores results in database
4. Returns structured response

This separation allows the business logic to be easily tested
and reused across different interfaces (Streamlit, FastAPI).
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from app.models import (
    Transaction,
    TransactionCreate,
    RiskReport,
    RiskAnalysisResult,
)
from app.services.llm_service import get_llm_service, LLMResponse

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Core business logic for transaction risk analysis.
    
    Handles the full workflow from transaction creation
    to risk report generation and storage.
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.llm_service = get_llm_service()
    
    def create_transaction(self, data: TransactionCreate) -> Transaction:
        """
        Creates and persists a new transaction.
        
        Args:
            data: Transaction creation data
            
        Returns:
            Persisted Transaction with ID
        """
        transaction = Transaction(
            comment=data.comment,
            amount=data.amount,
            currency=data.currency,
            sender_id=data.sender_id,
            receiver_id=data.receiver_id,
            created_at=datetime.utcnow(),
        )
        
        self.session.add(transaction)
        self.session.commit()
        self.session.refresh(transaction)
        
        logger.info(f"Created transaction {transaction.id}")
        return transaction
    
    def analyze_transaction(self, transaction: Transaction) -> RiskReport:
        """
        Performs LLM-based risk analysis on a transaction.
        
        Args:
            transaction: Transaction to analyze
            
        Returns:
            Persisted RiskReport with analysis results
        """
        # Call LLM service
        llm_response: LLMResponse = self.llm_service.analyze_transaction(
            comment=transaction.comment,
            amount=float(transaction.amount),
            sender_id=transaction.sender_id,
            receiver_id=transaction.receiver_id,
        )
        
        # Create risk report
        report = RiskReport(
            transaction_id=transaction.id,
            risk_score=llm_response.risk_score,
            risk_level=llm_response.risk_level,
            risk_factors=llm_response.risk_factors,
            llm_reasoning=llm_response.reasoning,
            model_version=self.llm_service.get_model_version(),
            created_at=datetime.utcnow(),
        )
        
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        
        logger.info(
            f"Created risk report {report.id} for transaction {transaction.id}: "
            f"score={report.risk_score}, level={report.risk_level}"
        )
        
        return report
    
    def process_transaction(
        self,
        data: TransactionCreate,
    ) -> tuple[Transaction, RiskReport]:
        """
        Full workflow: create transaction and analyze it.
        
        This is the main entry point for the UI layer.
        
        Args:
            data: Transaction creation data
            
        Returns:
            Tuple of (Transaction, RiskReport)
        """
        transaction = self.create_transaction(data)
        report = self.analyze_transaction(transaction)
        return transaction, report
    
    def get_transaction_with_reports(
        self,
        transaction_id: int,
    ) -> Optional[Transaction]:
        """
        Retrieves a transaction with its risk reports.
        
        Args:
            transaction_id: ID of transaction to retrieve
            
        Returns:
            Transaction with loaded risk_reports or None
        """
        statement = select(Transaction).where(Transaction.id == transaction_id)
        return self.session.exec(statement).first()
    
    def get_recent_reports(self, limit: int = 10) -> list[RiskReport]:
        """
        Retrieves recent risk reports for dashboard display.
        
        Args:
            limit: Maximum number of reports to return
            
        Returns:
            List of recent RiskReports, newest first
        """
        statement = (
            select(RiskReport)
            .order_by(RiskReport.created_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement).all())
    
    def get_high_risk_transactions(
        self,
        min_score: int = 50,
        limit: int = 20,
    ) -> list[RiskReport]:
        """
        Retrieves high-risk transactions for compliance review.
        
        Args:
            min_score: Minimum risk score threshold
            limit: Maximum number of reports to return
            
        Returns:
            List of high-risk RiskReports
        """
        statement = (
            select(RiskReport)
            .where(RiskReport.risk_score >= min_score)
            .order_by(RiskReport.risk_score.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement).all())


def get_risk_engine(session: Session) -> RiskEngine:
    """Factory function for RiskEngine with dependency injection."""
    return RiskEngine(session)

