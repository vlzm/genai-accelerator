"""
Validation - Automated Safety Checks.

Provides real-time validation of LLM outputs to catch critical errors.
These are deterministic evaluators that run synchronously.

For complex evaluation (LLM-as-a-Judge), run asynchronously in batch mode
to avoid slowing down the UI.
"""

import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    status: str  # PASS, FAIL_LOW_QUALITY, FAIL_INCONSISTENT, etc.
    details: Optional[str] = None
    
    @property
    def passed(self) -> bool:
        return self.status == "PASS"


# Keywords that indicate low quality or uncertainty
LOW_QUALITY_INDICATORS = [
    "i don't know",
    "i'm not sure",
    "unable to determine",
    "cannot assess",
    "error",
    "failed",
    "unknown",
    "n/a",
]


def check_response_quality(response_text: str, min_length: int = 50) -> ValidationResult:
    """
    Checks if LLM response meets minimum quality standards.
    
    Flags responses that are too short or indicate uncertainty.
    
    Args:
        response_text: LLM response to check
        min_length: Minimum acceptable response length
        
    Returns:
        ValidationResult with status and details
    """
    # Check for empty response
    if not response_text or not response_text.strip():
        return ValidationResult(
            status="FAIL_EMPTY",
            details="Response is empty"
        )
    
    # Check length
    if len(response_text.strip()) < min_length:
        return ValidationResult(
            status="FAIL_LOW_QUALITY",
            details=f"Response too short: {len(response_text)} chars (min: {min_length})"
        )
    
    # Check for uncertainty indicators
    response_lower = response_text.lower()
    for indicator in LOW_QUALITY_INDICATORS:
        if indicator in response_lower:
            return ValidationResult(
                status="FAIL_LOW_QUALITY",
                details=f"Uncertainty detected: '{indicator}'"
            )
    
    return ValidationResult(status="PASS")


def check_score_consistency(
    score: int,
    categories: list[str],
) -> ValidationResult:
    """
    Checks if score and categories are consistent.
    
    Catches cases where LLM assigns high score but no categories.
    
    Args:
        score: Numeric score (0-100)
        categories: List of identified categories/factors
        
    Returns:
        ValidationResult with status and details
    """
    # Validate score range
    if score < 0 or score > 100:
        return ValidationResult(
            status="FAIL_INVALID_SCORE",
            details=f"Score {score} is outside valid range 0-100"
        )
    
    # Check if high score has categories
    if score >= 50 and len(categories) == 0:
        return ValidationResult(
            status="WARN_NO_CATEGORIES",
            details="High score but no categories identified"
        )
    
    return ValidationResult(status="PASS")


def run_all_validations(
    response_text: str,
    score: int,
    categories: list[str],
) -> ValidationResult:
    """
    Runs all validation checks and returns the first failure (or PASS).
    
    Checks are run in priority order:
    1. Consistency (important)
    2. Quality (informational)
    
    Args:
        response_text: Full LLM response
        score: Numeric score
        categories: List of categories/factors
        
    Returns:
        ValidationResult with first failure or PASS
    """
    # Important: Score/categories consistency
    consistency_check = check_score_consistency(score, categories)
    if not consistency_check.passed:
        return consistency_check
    
    # Informational: Response quality
    quality_check = check_response_quality(response_text)
    if not quality_check.passed:
        return quality_check
    
    return ValidationResult(status="PASS")

