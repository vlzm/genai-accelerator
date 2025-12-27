"""
Risk Engine - Business Logic Layer.

Orchestrates the risk analysis workflow:
1. Receives transaction data
2. Calls LLM service for analysis (with observability tracing)
3. Runs guardrails for safety checks
4. Stores results in database with trace and guardrail status
5. Returns structured response

Implements RBAC/ABAC access control:
- RBAC: Role-based permission checks
- ABAC: Region and clearance level filtering

Implements Observability & Human Feedback Loop:
- LLM Tracing: Full trace of input, tool calls, and output
- Guardrails: Automated safety checks (PII leakage, consistency)
- Human Feedback: Binary feedback collection for model improvement

This separation allows the business logic to be easily tested
and reused across different interfaces (Streamlit, FastAPI).
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select, and_

from app.models import (
    Transaction,
    TransactionCreate,
    RiskReport,
    RiskAnalysisResult,
)
from app.services.llm_service import get_llm_service, LLMResponse
from app.services.auth_mock import (
    UserProfile,
    Permission,
    check_permission,
    Region,
)
from app.services.guardrails import run_all_guardrails
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Core business logic for transaction risk analysis.
    
    Handles the full workflow from transaction creation
    to risk report generation and storage.
    
    All methods that access data enforce ABAC policies based on
    the current user's region and clearance level.
    """
    
    def __init__(self, session: Session, user: Optional[UserProfile] = None):
        """
        Initialize RiskEngine.
        
        Args:
            session: Database session
            user: Current user for access control. If None, no filtering applied.
        """
        self.session = session
        self.user = user
        self.llm_service = get_llm_service()
        self.rag_service = RAGService(session)
    
    def _check_analyze_permission(self) -> None:
        """Verify user can analyze transactions (RBAC)."""
        if self.user:
            check_permission(self.user, Permission.ANALYZE_TRANSACTIONS)
    
    def _check_view_permission(self) -> None:
        """Verify user can view transactions (RBAC)."""
        if self.user:
            check_permission(self.user, Permission.VIEW_TRANSACTIONS)
    
    def create_transaction(
        self,
        data: TransactionCreate,
    ) -> Transaction:
        """
        Creates and persists a new transaction.
        
        The transaction is tagged with the user's region for ABAC.
        
        Args:
            data: Transaction creation data
            
        Returns:
            Persisted Transaction with ID
        """
        # Determine region from user or data
        region = data.region
        if self.user and data.region == "Global":
            # If user has a specific region, use it for new transactions
            if self.user.region != Region.GLOBAL:
                region = self.user.region.value
        
        transaction = Transaction(
            comment=data.comment,
            amount=data.amount,
            currency=data.currency,
            sender_id=data.sender_id,
            receiver_id=data.receiver_id,
            region=region,
            created_by_user_id=self.user.id if self.user else None,
            created_at=datetime.utcnow(),
        )
        
        self.session.add(transaction)
        self.session.commit()
        self.session.refresh(transaction)
        
        logger.info(f"Created transaction {transaction.id} in region {region}")
        return transaction
    
    def analyze_transaction(self, transaction: Transaction) -> RiskReport:
        """
        Performs LLM-based risk analysis on a transaction.
        
        Requires ANALYZE_TRANSACTIONS permission.
        
        Uses agent mode with tool calling for grounded analysis:
        - Checks entities against sanctions lists
        - Validates amounts against reporting thresholds
        - Checks for PEP status
        
        Includes observability features:
        - Full LLM trace (input, tool calls, output)
        - Guardrail checks (PII leakage, consistency)
        - Fields for human feedback collection
        
        Args:
            transaction: Transaction to analyze
            
        Returns:
            Persisted RiskReport with analysis results, trace, and guardrail status
            
        Raises:
            PermissionError: If user lacks ANALYZE_TRANSACTIONS permission
        """
        # RBAC check
        self._check_analyze_permission()
        
        # Call LLM service with tool support (agent mode)
        # This returns response with full trace for observability
        llm_response: LLMResponse = self.llm_service.analyze_with_tools(
            comment=transaction.comment,
            amount=float(transaction.amount),
            currency=transaction.currency,
            sender_id=transaction.sender_id,
            receiver_id=transaction.receiver_id,
        )
        
        # Build enhanced reasoning with tool info
        reasoning = llm_response.reasoning
        if llm_response.tools_used:
            reasoning += f"\n\n[Tools used: {', '.join(llm_response.tools_used)}]"
        if llm_response.compliance_actions:
            reasoning += f"\n[Compliance actions: {', '.join(llm_response.compliance_actions)}]"
        
        # Run guardrails (automated safety checks)
        guardrail_result = run_all_guardrails(
            response_text=reasoning,
            risk_score=llm_response.risk_score,
            risk_level=llm_response.risk_level,
            risk_factors=llm_response.risk_factors,
        )
        
        if not guardrail_result.passed:
            logger.warning(
                f"Guardrail failed for transaction {transaction.id}: "
                f"{guardrail_result.status} - {guardrail_result.details}"
            )
        
        # Create risk report with ABAC metadata and observability fields
        report = RiskReport(
            transaction_id=transaction.id,
            risk_score=llm_response.risk_score,
            risk_level=llm_response.risk_level,
            risk_factors=llm_response.risk_factors,
            llm_reasoning=reasoning,
            model_version=self.llm_service.get_model_version(),
            region=transaction.region,  # Copy region for ABAC queries
            analyzed_by_user_id=self.user.id if self.user else None,
            # Observability: LLM trace
            llm_trace=llm_response.trace or {},
            # Evaluation: Guardrail status
            guardrail_status=guardrail_result.status,
            guardrail_details=guardrail_result.details,
            # Human feedback fields initialized as None (pending feedback)
            human_feedback=None,
            feedback_comment=None,
            feedback_by_user_id=None,
            feedback_at=None,
            created_at=datetime.utcnow(),
        )
        
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        
        # Generate embedding for RAG (if enabled)
        # Done after commit to ensure report has ID
        if self.rag_service.is_enabled:
            try:
                self.rag_service.embed_report(report, transaction.comment)
                self.session.commit()
            except Exception as e:
                logger.warning(f"Failed to generate embedding for report {report.id}: {e}")
                # Don't fail the whole operation if embedding fails
        
        logger.info(
            f"Created risk report {report.id} for transaction {transaction.id}: "
            f"score={report.risk_score}, level={report.risk_level}, "
            f"region={report.region}, tools_used={llm_response.tools_used}, "
            f"guardrail={guardrail_result.status}"
        )
        
        return report
    
    def process_transaction(
        self,
        data: TransactionCreate,
    ) -> tuple[Transaction, RiskReport]:
        """
        Full workflow: create transaction and analyze it.
        
        This is the main entry point for the UI layer.
        Requires ANALYZE_TRANSACTIONS permission.
        
        Args:
            data: Transaction creation data
            
        Returns:
            Tuple of (Transaction, RiskReport)
        """
        self._check_analyze_permission()
        transaction = self.create_transaction(data)
        report = self.analyze_transaction(transaction)
        return transaction, report
    
    def _apply_abac_filter(self, statement):
        """
        Applies ABAC filters to a query based on user attributes.
        
        Filters:
        1. Region: Users only see their region (unless VIEW_ALL_REGIONS)
        2. Risk Score: Users without VIEW_HIGH_RISK can't see high scores
        """
        if not self.user:
            return statement
        
        conditions = []
        
        # Region filter (ABAC)
        if not self.user.has_permission(Permission.VIEW_ALL_REGIONS):
            if self.user.region != Region.GLOBAL:
                conditions.append(RiskReport.region == self.user.region.value)
        
        # Risk score filter (ABAC based on clearance)
        if not self.user.has_permission(Permission.VIEW_HIGH_RISK):
            max_score = self.user.get_max_visible_risk_score()
            conditions.append(RiskReport.risk_score <= max_score)
        
        if conditions:
            statement = statement.where(and_(*conditions))
        
        return statement
    
    def get_transaction_with_reports(
        self,
        transaction_id: int,
    ) -> Optional[Transaction]:
        """
        Retrieves a transaction with its risk reports.
        
        ABAC: Checks if user can access this transaction's region.
        
        Args:
            transaction_id: ID of transaction to retrieve
            
        Returns:
            Transaction with loaded risk_reports or None
        """
        self._check_view_permission()
        
        statement = select(Transaction).where(Transaction.id == transaction_id)
        transaction = self.session.exec(statement).first()
        
        if transaction and self.user:
            # ABAC check: can user access this region?
            if not self.user.can_access_region(transaction.region):
                logger.warning(
                    f"User {self.user.username} denied access to transaction "
                    f"{transaction_id} (region: {transaction.region})"
                )
                return None
        
        return transaction
    
    def get_recent_reports(self, limit: int = 10) -> list[RiskReport]:
        """
        Retrieves recent risk reports for dashboard display.
        
        ABAC: Filters by user's region and clearance level.
        
        Args:
            limit: Maximum number of reports to return
            
        Returns:
            List of recent RiskReports, newest first
        """
        self._check_view_permission()
        
        statement = (
            select(RiskReport)
            .order_by(RiskReport.created_at.desc())
        )
        
        # Apply ABAC filters
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(limit)
        
        return list(self.session.exec(statement).all())
    
    def get_high_risk_transactions(
        self,
        min_score: int = 50,
        limit: int = 20,
    ) -> list[RiskReport]:
        """
        Retrieves high-risk transactions for compliance review.
        
        ABAC: Filters by user's region. Requires VIEW_HIGH_RISK for scores >= 70.
        
        Args:
            min_score: Minimum risk score threshold
            limit: Maximum number of reports to return
            
        Returns:
            List of high-risk RiskReports
        """
        self._check_view_permission()
        
        # Adjust min_score based on user's clearance
        effective_min_score = min_score
        if self.user and not self.user.has_permission(Permission.VIEW_HIGH_RISK):
            # Users without VIEW_HIGH_RISK can only see up to score 69
            max_allowed = self.user.get_max_visible_risk_score()
            if min_score > max_allowed:
                # They can't see any high-risk transactions
                return []
        
        statement = (
            select(RiskReport)
            .where(RiskReport.risk_score >= effective_min_score)
            .order_by(RiskReport.risk_score.desc())
        )
        
        # Apply ABAC filters
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(limit)
        
        return list(self.session.exec(statement).all())
    
    def get_reports_by_region(self, region: str, limit: int = 20) -> list[RiskReport]:
        """
        Retrieves reports for a specific region.
        
        ABAC: User must have access to the requested region.
        
        Args:
            region: Region to filter by
            limit: Maximum number of reports
            
        Returns:
            List of RiskReports for the region
        """
        self._check_view_permission()
        
        # ABAC check
        if self.user and not self.user.can_access_region(region):
            raise PermissionError(
                f"Access denied. User '{self.user.username}' cannot access region '{region}'."
            )
        
        statement = (
            select(RiskReport)
            .where(RiskReport.region == region)
            .order_by(RiskReport.created_at.desc())
            .limit(limit)
        )
        
        return list(self.session.exec(statement).all())
    
    def get_dashboard_stats(self) -> dict:
        """
        Get dashboard statistics respecting ABAC.
        
        Returns:
            Dict with counts and statistics
        """
        self._check_view_permission()
        
        reports = self.get_recent_reports(limit=100)
        
        if not reports:
            return {
                "total_analyzed": 0,
                "high_risk_count": 0,
                "critical_count": 0,
                "average_score": 0,
                "regions_visible": [],
            }
        
        high_risk = [r for r in reports if r.risk_score >= 50]
        critical = [r for r in reports if r.risk_level == "CRITICAL"]
        regions = list(set(r.region for r in reports))
        
        return {
            "total_analyzed": len(reports),
            "high_risk_count": len(high_risk),
            "critical_count": len(critical),
            "average_score": sum(r.risk_score for r in reports) / len(reports),
            "regions_visible": regions,
        }


    def submit_feedback(
        self,
        report_id: int,
        feedback: bool,
        comment: Optional[str] = None,
    ) -> Optional[RiskReport]:
        """
        Submits human feedback for a risk report.
        
        This implements the Human-in-the-Loop evaluation loop.
        Collected feedback enables:
        - Building a "Golden Dataset" for model evaluation
        - Error analysis to understand model failures
        - Fine-tuning data collection
        
        Args:
            report_id: ID of the risk report to provide feedback for
            feedback: True = correct verdict, False = incorrect verdict
            comment: Optional explanation of why the verdict was wrong
            
        Returns:
            Updated RiskReport or None if not found/not accessible
        """
        self._check_view_permission()
        
        # Fetch the report with ABAC check
        statement = select(RiskReport).where(RiskReport.id == report_id)
        statement = self._apply_abac_filter(statement)
        report = self.session.exec(statement).first()
        
        if not report:
            logger.warning(f"Report {report_id} not found or not accessible")
            return None
        
        # Update feedback fields
        report.human_feedback = feedback
        report.feedback_comment = comment
        report.feedback_by_user_id = self.user.id if self.user else None
        report.feedback_at = datetime.utcnow()
        
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        
        feedback_type = "positive" if feedback else "negative"
        logger.info(
            f"Feedback submitted for report {report_id}: {feedback_type} "
            f"by {self.user.username if self.user else 'anonymous'}"
        )
        
        return report
    
    def get_feedback_stats(self) -> dict:
        """
        Gets feedback statistics for model evaluation.
        
        Returns breakdown of:
        - Total reports with feedback
        - Positive vs negative feedback ratio
        - Guardrail failure counts
        
        This data is essential for "Enlightened Dictator" decision-making.
        
        Returns:
            Dict with feedback and guardrail statistics
        """
        self._check_view_permission()
        
        # Get all visible reports
        statement = select(RiskReport)
        statement = self._apply_abac_filter(statement)
        reports = list(self.session.exec(statement).all())
        
        if not reports:
            return {
                "total_reports": 0,
                "with_feedback": 0,
                "positive_feedback": 0,
                "negative_feedback": 0,
                "pending_feedback": 0,
                "feedback_rate": 0.0,
                "accuracy_estimate": None,
                "guardrail_failures": {},
            }
        
        total = len(reports)
        with_feedback = [r for r in reports if r.human_feedback is not None]
        positive = [r for r in with_feedback if r.human_feedback is True]
        negative = [r for r in with_feedback if r.human_feedback is False]
        pending = total - len(with_feedback)
        
        # Guardrail failure breakdown
        guardrail_failures = {}
        for r in reports:
            if r.guardrail_status and r.guardrail_status != "PASS":
                guardrail_failures[r.guardrail_status] = (
                    guardrail_failures.get(r.guardrail_status, 0) + 1
                )
        
        return {
            "total_reports": total,
            "with_feedback": len(with_feedback),
            "positive_feedback": len(positive),
            "negative_feedback": len(negative),
            "pending_feedback": pending,
            "feedback_rate": len(with_feedback) / total if total > 0 else 0.0,
            "accuracy_estimate": (
                len(positive) / len(with_feedback)
                if len(with_feedback) > 0 else None
            ),
            "guardrail_failures": guardrail_failures,
        }
    
    def get_reports_needing_review(self, limit: int = 20) -> list[RiskReport]:
        """
        Gets reports that need human review.
        
        Prioritizes:
        1. Reports with guardrail failures
        2. Reports without feedback
        3. High-risk reports
        
        Args:
            limit: Maximum number of reports to return
            
        Returns:
            List of RiskReports prioritized for review
        """
        self._check_view_permission()
        
        # Get reports with guardrail failures first
        statement = (
            select(RiskReport)
            .where(RiskReport.guardrail_status != "PASS")
            .order_by(RiskReport.created_at.desc())
        )
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(limit)
        
        guardrail_failed = list(self.session.exec(statement).all())
        
        remaining = limit - len(guardrail_failed)
        if remaining <= 0:
            return guardrail_failed
        
        # Get high-risk reports without feedback
        existing_ids = [r.id for r in guardrail_failed]
        statement = (
            select(RiskReport)
            .where(
                and_(
                    RiskReport.human_feedback.is_(None),
                    RiskReport.guardrail_status == "PASS",
                    RiskReport.risk_score >= 50,
                    RiskReport.id.notin_(existing_ids) if existing_ids else True,
                )
            )
            .order_by(RiskReport.risk_score.desc())
        )
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(remaining)
        
        high_risk = list(self.session.exec(statement).all())
        
        return guardrail_failed + high_risk


    def find_similar_cases(
        self,
        report: RiskReport,
        limit: int = 3,
    ) -> list[RiskReport]:
        """
        Finds similar historical cases using RAG.
        
        This helps compliance officers make informed decisions
        by showing how similar cases were handled in the past.
        
        Args:
            report: Current RiskReport to find similar cases for
            limit: Maximum number of similar cases to return
            
        Returns:
            List of similar RiskReports (empty if RAG disabled)
        """
        if not self.rag_service.is_enabled:
            return []
        
        self._check_view_permission()
        
        try:
            similar = self.rag_service.find_similar_to_report(report, limit=limit)
            
            # Apply ABAC filter to results
            if self.user:
                similar = [
                    r for r in similar
                    if self.user.can_access_region(r.region)
                ]
            
            return similar
        except Exception as e:
            logger.warning(f"Similar case search failed: {e}")
            return []
    
    def is_rag_enabled(self) -> bool:
        """Check if RAG feature is enabled."""
        return self.rag_service.is_enabled


def get_risk_engine(session: Session, user: Optional[UserProfile] = None) -> RiskEngine:
    """Factory function for RiskEngine with dependency injection."""
    return RiskEngine(session, user)
