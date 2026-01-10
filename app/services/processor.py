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
- ABAC: Group-based filtering

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
    Group,
)
from app.services.validation import run_all_validations
from app.services.rag_service import RAGService, SimilarCaseResult, RAGTrace

logger = logging.getLogger(__name__)


class Processor:
    """
    Core business logic for input processing and analysis.
    
    Handles the full workflow from request creation
    to analysis result generation and storage.
    
    All methods that access data enforce ABAC policies based on
    the current user's group and permissions.
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
        self.rag_service = RAGService(session)
    
    def _check_analyze_permission(self) -> None:
        """Verify user can analyze requests (RBAC)."""
        if self.user:
            check_permission(self.user, Permission.ANALYZE)
    
    def _check_view_permission(self) -> None:
        """Verify user can view requests (RBAC)."""
        if self.user:
            check_permission(self.user, Permission.VIEW)
    
    def create_request(
        self,
        data: RequestCreate,
    ) -> Request:
        """
        Creates and persists a new request.
        
        The request is tagged with the user's group for ABAC.
        
        Args:
            data: Request creation data
            
        Returns:
            Persisted Request with ID
        """
        # Determine group from user or data
        group = data.group
        if self.user and data.group == "default":
            # If user has a specific group, use it for new requests
            if self.user.group != Group.DEFAULT:
                group = self.user.group.value
        
        request = Request(
            input_text=data.input_text,
            context=data.context,
            group=group,
            created_by_user_id=self.user.id if self.user else None,
            created_at=datetime.utcnow(),
        )
        
        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)
        
        logger.info(f"Created request {request.id} in group {group}")
        return request
    
    def analyze_request(self, request: Request, mode: str = "analysis") -> AnalysisResult:
        """
        Performs LLM-based analysis on a request.
        
        Requires ANALYZE permission.
        
        Supports two modes:
        - "analysis": Full scoring mode with score, categories, and summary
        - "chat": Conversational mode - returns only a text response (no score)
        
        Includes observability features:
        - Full LLM trace (input, tool calls, output)
        - Validation checks (quality, consistency) - only in analysis mode
        - Fields for human feedback collection
        
        Args:
            request: Request to analyze
            mode: "analysis" or "chat"
            
        Returns:
            Persisted AnalysisResult with results, trace, and validation status
            
        Raises:
            PermissionError: If user lacks ANALYZE permission
        """
        # RBAC check
        self._check_analyze_permission()
        
        # Call LLM service for analysis (using agent mode with tools)
        llm_response: LLMResponse = self.llm_service.analyze_with_tools(
            input_text=request.input_text,
            context=request.context,
            mode=mode,
        )
        
        # Build summary with tool info if applicable
        summary = llm_response.reasoning
        if llm_response.tools_used:
            summary += f"\n\n[Tools used: {', '.join(llm_response.tools_used)}]"
        
        # Run validation checks only in analysis mode (chat mode skips validation)
        if mode == "analysis" and llm_response.score is not None:
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
        else:
            # Chat mode - skip validation (ValidationResult is a dataclass)
            from app.services.validation import ValidationResult
            validation_result = ValidationResult(
                status="PASS",
                details="Chat mode - validation skipped",
            )
        
        # Create analysis result with ABAC metadata and observability fields
        result = AnalysisResult(
            request_id=request.id,
            result_type=mode,  # "analysis" or "chat"
            score=llm_response.score,  # None in chat mode
            categories=llm_response.categories,  # Empty in chat mode
            summary=summary,
            processed_content=llm_response.processed_content,
            model_version=self.llm_service.get_model_version(),
            group=request.group,  # Copy group for ABAC queries
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
        
        # Generate embedding for RAG (if enabled) - for both modes
        if self.rag_service.is_enabled:
            try:
                self.rag_service.embed_result(result, request.input_text)
                self.session.commit()
            except Exception as e:
                logger.warning(f"Failed to generate embedding for result {result.id}: {e}")
                # Don't fail the whole operation if embedding fails
        
        log_score = result.score if result.score is not None else "N/A"
        logger.info(
            f"Created {mode} result {result.id} for request {request.id}: "
            f"score={log_score}, group={result.group}, "
            f"validation={validation_result.status}"
        )
        
        return result
    
    def process_request(
        self,
        data: RequestCreate,
        mode: str = "analysis",
    ) -> tuple[Request, AnalysisResult]:
        """
        Full workflow: create request and analyze/chat.
        
        This is the main entry point for the UI layer.
        Requires ANALYZE permission.
        
        Args:
            data: Request creation data
            mode: "analysis" for scoring mode, "chat" for conversational mode
            
        Returns:
            Tuple of (Request, AnalysisResult)
        """
        self._check_analyze_permission()
        request = self.create_request(data)
        result = self.analyze_request(request, mode=mode)
        return request, result
    
    def _apply_abac_filter(self, statement):
        """
        Applies ABAC filters to a query based on user attributes.
        
        Filters:
        1. Group: Users only see their group (unless VIEW_ALL_GROUPS)
        2. Score: Users without VIEW_SENSITIVE can't see high scores
           (Note: Chat results with score=None are always visible)
        """
        from sqlmodel import or_
        
        if not self.user:
            return statement
        
        conditions = []
        
        # Group filter (ABAC)
        if not self.user.has_permission(Permission.VIEW_ALL_GROUPS):
            if self.user.group != Group.DEFAULT:
                conditions.append(AnalysisResult.group == self.user.group.value)
        
        # Score filter (ABAC based on permissions)
        # Chat results (score=None) are always visible regardless of permissions
        if not self.user.has_permission(Permission.VIEW_SENSITIVE):
            max_score = self.user.get_max_visible_score()
            # Allow: score <= max_score OR score IS NULL (chat mode)
            conditions.append(
                or_(
                    AnalysisResult.score <= max_score,
                    AnalysisResult.score.is_(None)
                )
            )
        
        if conditions:
            statement = statement.where(and_(*conditions))
        
        return statement
    
    def get_request_with_results(
        self,
        request_id: int,
    ) -> Optional[Request]:
        """
        Retrieves a request with its analysis results.
        
        ABAC: Checks if user can access this request's group.
        
        Args:
            request_id: ID of request to retrieve
            
        Returns:
            Request with loaded results or None
        """
        self._check_view_permission()
        
        statement = select(Request).where(Request.id == request_id)
        request = self.session.exec(statement).first()
        
        if request and self.user:
            # ABAC check: can user access this group?
            if not self.user.can_access_group(request.group):
                logger.warning(
                    f"User {self.user.username} denied access to request "
                    f"{request_id} (group: {request.group})"
                )
                return None
        
        return request
    
    def get_recent_results(self, limit: int = 10) -> list[AnalysisResult]:
        """
        Retrieves recent analysis results for dashboard display.
        
        ABAC: Filters by user's group and permissions.
        
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
        
        ABAC: Filters by user's group. Requires VIEW_SENSITIVE for scores >= 70.
        
        Args:
            min_score: Minimum score threshold
            limit: Maximum number of results to return
            
        Returns:
            List of high-score AnalysisResults
        """
        self._check_view_permission()
        
        # Adjust min_score based on user's permissions
        effective_min_score = min_score
        if self.user and not self.user.has_permission(Permission.VIEW_SENSITIVE):
            # Users without VIEW_SENSITIVE can only see up to score 69
            max_allowed = self.user.get_max_visible_score()
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
    
    def get_results_by_group(self, group: str, limit: int = 20) -> list[AnalysisResult]:
        """
        Retrieves results for a specific group.
        
        ABAC: User must have access to the requested group.
        
        Args:
            group: Group to filter by
            limit: Maximum number of results
            
        Returns:
            List of AnalysisResults for the group
        """
        self._check_view_permission()
        
        # ABAC check
        if self.user and not self.user.can_access_group(group):
            raise PermissionError(
                f"Access denied. User '{self.user.username}' cannot access group '{group}'."
            )
        
        statement = (
            select(AnalysisResult)
            .where(AnalysisResult.group == group)
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
                "chat_count": 0,
                "high_score_count": 0,
                "critical_count": 0,
                "average_score": 0,
                "groups_visible": [],
            }
        
        # Separate analysis and chat results (score can be None for chat)
        analysis_results = [r for r in results if r.score is not None]
        chat_results = [r for r in results if r.score is None]
        
        high_score = [r for r in analysis_results if r.score >= 50]
        critical = [r for r in analysis_results if r.score >= 76]
        groups = list(set(r.group for r in results))
        
        # Calculate average only for analysis results with scores
        avg_score = (
            sum(r.score for r in analysis_results) / len(analysis_results)
            if analysis_results else 0
        )
        
        return {
            "total_analyzed": len(results),
            "chat_count": len(chat_results),
            "high_score_count": len(high_score),
            "critical_count": len(critical),
            "average_score": avg_score,
            "groups_visible": groups,
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
        Gets ALL results for the Evaluation page with ABAC/RBAC filtering.
        
        Results are prioritized:
        1. Results with validation failures (first priority - need immediate attention)
        2. Results without feedback (pending review)
        3. Results with feedback (already reviewed)
        
        All results remain visible - nothing disappears after feedback.
        ABAC filtering ensures users only see results they have access to.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of AnalysisResults prioritized for review
        """
        self._check_view_permission()
        
        # Priority 1: Results with validation failures
        statement = (
            select(AnalysisResult)
            .where(AnalysisResult.validation_status != "PASS")
            .order_by(AnalysisResult.created_at.desc())
        )
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(limit)
        
        validation_failed = list(self.session.exec(statement).all())
        collected_ids = [r.id for r in validation_failed]
        
        remaining = limit - len(validation_failed)
        if remaining <= 0:
            return validation_failed
        
        # Priority 2: Results without feedback (pending review)
        statement = (
            select(AnalysisResult)
            .where(
                and_(
                    AnalysisResult.human_feedback.is_(None),
                    AnalysisResult.validation_status == "PASS",
                    AnalysisResult.id.notin_(collected_ids) if collected_ids else True,
                )
            )
            .order_by(AnalysisResult.created_at.desc())
        )
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(remaining)
        
        pending_feedback = list(self.session.exec(statement).all())
        collected_ids.extend([r.id for r in pending_feedback])
        
        remaining = remaining - len(pending_feedback)
        if remaining <= 0:
            return validation_failed + pending_feedback
        
        # Priority 3: Results WITH feedback (already reviewed - still shown for reference)
        statement = (
            select(AnalysisResult)
            .where(
                and_(
                    AnalysisResult.human_feedback.is_not(None),
                    AnalysisResult.validation_status == "PASS",
                    AnalysisResult.id.notin_(collected_ids) if collected_ids else True,
                )
            )
            .order_by(AnalysisResult.created_at.desc())
        )
        statement = self._apply_abac_filter(statement)
        statement = statement.limit(remaining)
        
        reviewed = list(self.session.exec(statement).all())
        
        return validation_failed + pending_feedback + reviewed

    def find_similar_cases(
        self,
        result: AnalysisResult,
        limit: int = 3,
        min_similarity: float = 0.3,
    ) -> tuple[list[SimilarCaseResult], RAGTrace]:
        """
        Finds similar historical cases using RAG.
        
        This helps users make informed decisions by showing
        how similar cases were handled in the past.
        
        Args:
            result: Current AnalysisResult to find similar cases for
            limit: Maximum number of similar cases to return
            min_similarity: Minimum similarity threshold (0.0-1.0, default 30%)
            
        Returns:
            Tuple of (list of SimilarCaseResult with scores, RAGTrace for debugging)
        """
        trace = RAGTrace(enabled=self.rag_service.is_enabled)
        
        if not self.rag_service.is_enabled:
            return [], trace
        
        self._check_view_permission()
        
        try:
            similar, trace = self.rag_service.find_similar_to_result(
                result, 
                limit=limit,
                min_similarity=min_similarity,
            )
            
            # Apply ABAC filter to results
            if self.user:
                filtered = [
                    s for s in similar
                    if self.user.can_access_group(s.result.group)
                ]
                trace.results_after_filter = len(filtered)
                return filtered, trace
            
            return similar, trace
        except Exception as e:
            trace.search_error = str(e)
            logger.warning(f"Similar case search failed: {e}")
            return [], trace
    
    def is_rag_enabled(self) -> bool:
        """Check if RAG feature is enabled."""
        return self.rag_service.is_enabled


def get_processor(session: Session, user: Optional[UserProfile] = None) -> Processor:
    """Factory function for Processor with dependency injection."""
    return Processor(session, user)
