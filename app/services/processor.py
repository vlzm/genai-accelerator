"""
Processor - Core Business Logic Layer.

Orchestrates the request processing workflow:
1. Receives input data
2. Calls LLM service for analysis (with observability tracing)
3. Runs validation checks for safety
4. Stores results in database with trace and validation status
5. Returns structured response

Implements RBAC/ABAC access control:
- RBAC: Role-based permission checks
- ABAC: Region and clearance level filtering

Implements Observability & Human Feedback Loop:
- LLM Tracing: Full trace of input, tool calls, and output
- Validation: Automated safety checks (quality, consistency)
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
    Request,
    RequestCreate,
    AnalysisResult,
)
from app.services.llm_service import get_llm_service, LLMResponse
from app.services.auth_mock import (
    UserProfile,
    Permission,
    check_permission,
    Region,
)
from app.services.validation import run_all_validations

logger = logging.getLogger(__name__)


class Processor:
    """
    Core business logic for input processing and analysis.
    
    Handles the full workflow from request creation
    to analysis result generation and storage.
    
    All methods that access data enforce ABAC policies based on
    the current user's region and clearance level.
    """
    
    def __init__(self, session: Session, user: Optional[UserProfile] = None):
        """
        Initialize Processor.
        
        Args:
            session: Database session
            user: Current user for access control. If None, no filtering applied.
        """
        self.session = session
        self.user = user
        self.llm_service = get_llm_service()
    
    def _check_analyze_permission(self) -> None:
        """Verify user can analyze requests (RBAC)."""
        if self.user:
            check_permission(self.user, Permission.ANALYZE_TRANSACTIONS)
    
    def _check_view_permission(self) -> None:
        """Verify user can view requests (RBAC)."""
        if self.user:
            check_permission(self.user, Permission.VIEW_TRANSACTIONS)
    
    def create_request(
        self,
        data: RequestCreate,
    ) -> Request:
        """
        Creates and persists a new request.
        
        The request is tagged with the user's region for ABAC.
        
        Args:
            data: Request creation data
            
        Returns:
            Persisted Request with ID
        """
        # Determine region from user or data
        region = data.region
        if self.user and data.region == "Global":
            # If user has a specific region, use it for new requests
            if self.user.region != Region.GLOBAL:
                region = self.user.region.value
        
        request = Request(
            input_text=data.input_text,
            context=data.context,
            region=region,
            created_by_user_id=self.user.id if self.user else None,
            created_at=datetime.utcnow(),
        )
        
        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)
        
        logger.info(f"Created request {request.id} in region {region}")
        return request
    
    def analyze_request(self, request: Request) -> AnalysisResult:
        """
        Performs LLM-based analysis on a request.
        
        Requires ANALYZE permission.
        
        Includes observability features:
        - Full LLM trace (input, tool calls, output)
        - Validation checks (quality, consistency)
        - Fields for human feedback collection
        
        Args:
            request: Request to analyze
            
        Returns:
            Persisted AnalysisResult with results, trace, and validation status
            
        Raises:
            PermissionError: If user lacks ANALYZE permission
        """
        # RBAC check
        self._check_analyze_permission()
        
        # Call LLM service for analysis
        llm_response: LLMResponse = self.llm_service.analyze(
            input_text=request.input_text,
            context=request.context,
        )
        
        # Build summary with tool info if applicable
        summary = llm_response.reasoning
        if llm_response.tools_used:
            summary += f"\n\n[Tools used: {', '.join(llm_response.tools_used)}]"
        
        # Run validation checks (automated safety checks)
        validation_result = run_all_validations(
            response_text=summary,
            score=llm_response.score,
            categories=llm_response.categories,
        )
        
        if not validation_result.passed:
            logger.warning(
                f"Validation failed for request {request.id}: "
                f"{validation_result.status} - {validation_result.details}"
            )
        
        # Create analysis result with ABAC metadata and observability fields
        result = AnalysisResult(
            request_id=request.id,
            score=llm_response.score,
            categories=llm_response.categories,
            summary=summary,
            processed_content=llm_response.processed_content,
            model_version=self.llm_service.get_model_version(),
            region=request.region,  # Copy region for ABAC queries
            analyzed_by_user_id=self.user.id if self.user else None,
            # Observability: LLM trace
            llm_trace=llm_response.trace or {},
            # Validation status
            validation_status=validation_result.status,
            validation_details=validation_result.details,
            # Human feedback fields initialized as None (pending feedback)
            human_feedback=None,
            feedback_comment=None,
            feedback_by_user_id=None,
            feedback_at=None,
            created_at=datetime.utcnow(),
        )
        
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        
        logger.info(
            f"Created analysis result {result.id} for request {request.id}: "
            f"score={result.score}, region={result.region}, "
            f"validation={validation_result.status}"
        )
        
        return result
    
    def process_request(
        self,
        data: RequestCreate,
    ) -> tuple[Request, AnalysisResult]:
        """
        Full workflow: create request and analyze it.
        
        This is the main entry point for the UI layer.
        Requires ANALYZE permission.
        
        Args:
            data: Request creation data
            
        Returns:
            Tuple of (Request, AnalysisResult)
        """
        self._check_analyze_permission()
        request = self.create_request(data)
        result = self.analyze_request(request)
        return request, result
    
    def _apply_abac_filter(self, statement):
        """
        Applies ABAC filters to a query based on user attributes.
        
        Filters:
        1. Region: Users only see their region (unless VIEW_ALL_REGIONS)
        2. Score: Users without VIEW_HIGH_RISK can't see high scores
        """
        if not self.user:
            return statement
        
        conditions = []
        
        # Region filter (ABAC)
        if not self.user.has_permission(Permission.VIEW_ALL_REGIONS):
            if self.user.region != Region.GLOBAL:
                conditions.append(AnalysisResult.region == self.user.region.value)
        
        # Score filter (ABAC based on clearance)
        if not self.user.has_permission(Permission.VIEW_HIGH_RISK):
            max_score = self.user.get_max_visible_risk_score()
            conditions.append(AnalysisResult.score <= max_score)
        
        if conditions:
            statement = statement.where(and_(*conditions))
        
        return statement
    
    def get_request_with_results(
        self,
        request_id: int,
    ) -> Optional[Request]:
        """
        Retrieves a request with its analysis results.
        
        ABAC: Checks if user can access this request's region.
        
        Args:
            request_id: ID of request to retrieve
            
        Returns:
            Request with loaded results or None
        """
        self._check_view_permission()
        
        statement = select(Request).where(Request.id == request_id)
        request = self.session.exec(statement).first()
        
        if request and self.user:
            # ABAC check: can user access this region?
            if not self.user.can_access_region(request.region):
                logger.warning(
                    f"User {self.user.username} denied access to request "
                    f"{request_id} (region: {request.region})"
                )
                return None
        
        return request
    
    def get_recent_results(self, limit: int = 10) -> list[AnalysisResult]:
        """
        Retrieves recent analysis results for dashboard display.
        
        ABAC: Filters by user's region and clearance level.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of recent AnalysisResults, newest first
        """
        self._check_view_permission()
        
        statement = (
            select(AnalysisResult)
            .order_by(AnalysisResult.created_at.desc())
        )
        
        # Apply ABAC filters
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(limit)
        
        return list(self.session.exec(statement).all())
    
    def get_high_score_results(
        self,
        min_score: int = 50,
        limit: int = 20,
    ) -> list[AnalysisResult]:
        """
        Retrieves high-score results for review.
        
        ABAC: Filters by user's region. Requires VIEW_HIGH_RISK for scores >= 70.
        
        Args:
            min_score: Minimum score threshold
            limit: Maximum number of results to return
            
        Returns:
            List of high-score AnalysisResults
        """
        self._check_view_permission()
        
        # Adjust min_score based on user's clearance
        effective_min_score = min_score
        if self.user and not self.user.has_permission(Permission.VIEW_HIGH_RISK):
            # Users without VIEW_HIGH_RISK can only see up to score 69
            max_allowed = self.user.get_max_visible_risk_score()
            if min_score > max_allowed:
                # They can't see any high-score results
                return []
        
        statement = (
            select(AnalysisResult)
            .where(AnalysisResult.score >= effective_min_score)
            .order_by(AnalysisResult.score.desc())
        )
        
        # Apply ABAC filters
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(limit)
        
        return list(self.session.exec(statement).all())
    
    def get_results_by_region(self, region: str, limit: int = 20) -> list[AnalysisResult]:
        """
        Retrieves results for a specific region.
        
        ABAC: User must have access to the requested region.
        
        Args:
            region: Region to filter by
            limit: Maximum number of results
            
        Returns:
            List of AnalysisResults for the region
        """
        self._check_view_permission()
        
        # ABAC check
        if self.user and not self.user.can_access_region(region):
            raise PermissionError(
                f"Access denied. User '{self.user.username}' cannot access region '{region}'."
            )
        
        statement = (
            select(AnalysisResult)
            .where(AnalysisResult.region == region)
            .order_by(AnalysisResult.created_at.desc())
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
        
        results = self.get_recent_results(limit=100)
        
        if not results:
            return {
                "total_analyzed": 0,
                "high_score_count": 0,
                "critical_count": 0,
                "average_score": 0,
                "regions_visible": [],
            }
        
        high_score = [r for r in results if r.score >= 50]
        critical = [r for r in results if r.score >= 76]
        regions = list(set(r.region for r in results))
        
        return {
            "total_analyzed": len(results),
            "high_score_count": len(high_score),
            "critical_count": len(critical),
            "average_score": sum(r.score for r in results) / len(results),
            "regions_visible": regions,
        }

    def submit_feedback(
        self,
        result_id: int,
        feedback: bool,
        comment: Optional[str] = None,
    ) -> Optional[AnalysisResult]:
        """
        Submits human feedback for an analysis result.
        
        This implements the Human-in-the-Loop evaluation loop.
        Collected feedback enables:
        - Building a "Golden Dataset" for model evaluation
        - Error analysis to understand model failures
        - Fine-tuning data collection
        
        Args:
            result_id: ID of the analysis result to provide feedback for
            feedback: True = correct verdict, False = incorrect verdict
            comment: Optional explanation of why the verdict was wrong
            
        Returns:
            Updated AnalysisResult or None if not found/not accessible
        """
        self._check_view_permission()
        
        # Fetch the result with ABAC check
        statement = select(AnalysisResult).where(AnalysisResult.id == result_id)
        statement = self._apply_abac_filter(statement)
        result = self.session.exec(statement).first()
        
        if not result:
            logger.warning(f"Result {result_id} not found or not accessible")
            return None
        
        # Update feedback fields
        result.human_feedback = feedback
        result.feedback_comment = comment
        result.feedback_by_user_id = self.user.id if self.user else None
        result.feedback_at = datetime.utcnow()
        
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        
        feedback_type = "positive" if feedback else "negative"
        logger.info(
            f"Feedback submitted for result {result_id}: {feedback_type} "
            f"by {self.user.username if self.user else 'anonymous'}"
        )
        
        return result
    
    def get_feedback_stats(self) -> dict:
        """
        Gets feedback statistics for model evaluation.
        
        Returns breakdown of:
        - Total results with feedback
        - Positive vs negative feedback ratio
        - Validation failure counts
        
        This data is essential for model quality monitoring.
        
        Returns:
            Dict with feedback and validation statistics
        """
        self._check_view_permission()
        
        # Get all visible results
        statement = select(AnalysisResult)
        statement = self._apply_abac_filter(statement)
        results = list(self.session.exec(statement).all())
        
        if not results:
            return {
                "total_results": 0,
                "with_feedback": 0,
                "positive_feedback": 0,
                "negative_feedback": 0,
                "pending_feedback": 0,
                "feedback_rate": 0.0,
                "accuracy_estimate": None,
                "validation_failures": {},
            }
        
        total = len(results)
        with_feedback = [r for r in results if r.human_feedback is not None]
        positive = [r for r in with_feedback if r.human_feedback is True]
        negative = [r for r in with_feedback if r.human_feedback is False]
        pending = total - len(with_feedback)
        
        # Validation failure breakdown
        validation_failures = {}
        for r in results:
            if r.validation_status and r.validation_status != "PASS":
                validation_failures[r.validation_status] = (
                    validation_failures.get(r.validation_status, 0) + 1
                )
        
        return {
            "total_results": total,
            "with_feedback": len(with_feedback),
            "positive_feedback": len(positive),
            "negative_feedback": len(negative),
            "pending_feedback": pending,
            "feedback_rate": len(with_feedback) / total if total > 0 else 0.0,
            "accuracy_estimate": (
                len(positive) / len(with_feedback)
                if len(with_feedback) > 0 else None
            ),
            "validation_failures": validation_failures,
        }
    
    def get_results_needing_review(self, limit: int = 20) -> list[AnalysisResult]:
        """
        Gets results that need human review.
        
        Prioritizes:
        1. Results with validation failures
        2. Results without feedback
        3. High-score results
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of AnalysisResults prioritized for review
        """
        self._check_view_permission()
        
        # Get results with validation failures first
        statement = (
            select(AnalysisResult)
            .where(AnalysisResult.validation_status != "PASS")
            .order_by(AnalysisResult.created_at.desc())
        )
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(limit)
        
        validation_failed = list(self.session.exec(statement).all())
        
        remaining = limit - len(validation_failed)
        if remaining <= 0:
            return validation_failed
        
        # Get high-score results without feedback
        existing_ids = [r.id for r in validation_failed]
        statement = (
            select(AnalysisResult)
            .where(
                and_(
                    AnalysisResult.human_feedback.is_(None),
                    AnalysisResult.validation_status == "PASS",
                    AnalysisResult.score >= 50,
                    AnalysisResult.id.notin_(existing_ids) if existing_ids else True,
                )
            )
            .order_by(AnalysisResult.score.desc())
        )
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(remaining)
        
        high_score = list(self.session.exec(statement).all())
        
        return validation_failed + high_score


def get_processor(session: Session, user: Optional[UserProfile] = None) -> Processor:
    """Factory function for Processor with dependency injection."""
    return Processor(session, user)

