"""
Guardrails - Automated Safety Checks.

Provides real-time validation of LLM outputs to catch critical errors.
These are deterministic evaluators that run synchronously.

For complex evaluation (LLM-as-a-Judge), run asynchronously in batch mode
to avoid slowing down the UI.
"""

import re
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""
    status: str  # PASS, FAIL_PII_LEAKAGE, FAIL_LOW_QUALITY, etc.
    details: Optional[str] = None
    
    @property
    def passed(self) -> bool:
        return self.status == "PASS"


# Regex patterns for PII detection
PII_PATTERNS = {
    "IBAN": r"[A-Z]{2}\d{2}[A-Z0-9]{1,30}",
    "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "PHONE_US": r"\b\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "PASSPORT": r"\b[A-Z]{1,2}\d{6,9}\b",
}

# Keywords that indicate low quality or uncertainty
LOW_QUALITY_INDICATORS = [
    "i don't know",
    "i'm not sure",
    "unable to determine",
    "cannot assess",
    "unknown",
    "n/a",
]


def check_pii_leakage(response_text: str) -> GuardrailResult:
    """
    Checks if LLM response contains leaked PII.
    
    In a compliant system, PII should be masked (e.g., "IBAN: ****1234")
    not exposed in raw form.
    
    Args:
        response_text: LLM response to check
        
    Returns:
        GuardrailResult with status and details
    """
    found_pii = []
    
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, response_text, re.IGNORECASE)
        if matches:
            # Don't log actual PII values, just the count
            found_pii.append(f"{pii_type}:{len(matches)}")
    
    if found_pii:
        logger.warning(f"PII leakage detected: {found_pii}")
        return GuardrailResult(
            status="FAIL_PII_LEAKAGE",
            details=f"Detected: {', '.join(found_pii)}"
        )
    
    return GuardrailResult(status="PASS")


def check_response_quality(response_text: str, min_length: int = 50) -> GuardrailResult:
    """
    Checks if LLM response meets minimum quality standards.
    
    Flags responses that are too short or indicate uncertainty.
    
    Args:
        response_text: LLM response to check
        min_length: Minimum acceptable response length
        
    Returns:
        GuardrailResult with status and details
    """
    # Check length
    if len(response_text.strip()) < min_length:
        return GuardrailResult(
            status="FAIL_LOW_QUALITY",
            details=f"Response too short: {len(response_text)} chars (min: {min_length})"
        )
    
    # Check for uncertainty indicators
    response_lower = response_text.lower()
    for indicator in LOW_QUALITY_INDICATORS:
        if indicator in response_lower:
            return GuardrailResult(
                status="FAIL_LOW_QUALITY",
                details=f"Uncertainty detected: '{indicator}'"
            )
    
    return GuardrailResult(status="PASS")


def check_risk_score_consistency(
    risk_score: int,
    risk_level: str,
    risk_factors: list[str],
) -> GuardrailResult:
    """
    Checks if risk score, level, and factors are consistent.
    
    Catches cases where LLM assigns high score but says "LOW" risk.
    
    Args:
        risk_score: Numeric risk score (0-100)
        risk_level: Risk level string (LOW, MEDIUM, HIGH, CRITICAL)
        risk_factors: List of identified risk factors
        
    Returns:
        GuardrailResult with status and details
    """
    # Expected score ranges
    LEVEL_RANGES = {
        "LOW": (0, 25),
        "MEDIUM": (26, 50),
        "HIGH": (51, 75),
        "CRITICAL": (76, 100),
    }
    
    expected_range = LEVEL_RANGES.get(risk_level.upper())
    if not expected_range:
        return GuardrailResult(
            status="FAIL_INVALID_LEVEL",
            details=f"Unknown risk level: {risk_level}"
        )
    
    min_score, max_score = expected_range
    
    # Check if score matches level
    if not (min_score <= risk_score <= max_score):
        return GuardrailResult(
            status="FAIL_INCONSISTENT",
            details=f"Score {risk_score} doesn't match level {risk_level} (expected {min_score}-{max_score})"
        )
    
    # Check if high score has factors
    if risk_score >= 50 and len(risk_factors) == 0:
        return GuardrailResult(
            status="WARN_NO_FACTORS",
            details="High risk score but no risk factors identified"
        )
    
    return GuardrailResult(status="PASS")


def run_all_guardrails(
    response_text: str,
    risk_score: int,
    risk_level: str,
    risk_factors: list[str],
) -> GuardrailResult:
    """
    Runs all guardrail checks and returns the first failure (or PASS).
    
    Checks are run in priority order:
    1. PII leakage (critical)
    2. Consistency (important)
    3. Quality (informational)
    
    Args:
        response_text: Full LLM response
        risk_score: Numeric risk score
        risk_level: Risk level string
        risk_factors: List of risk factors
        
    Returns:
        GuardrailResult with first failure or PASS
    """
    # Critical: PII leakage
    pii_check = check_pii_leakage(response_text)
    if not pii_check.passed:
        return pii_check
    
    # Important: Score/level consistency
    consistency_check = check_risk_score_consistency(risk_score, risk_level, risk_factors)
    if not consistency_check.passed:
        return consistency_check
    
    # Informational: Response quality
    quality_check = check_response_quality(response_text)
    if not quality_check.passed:
        return quality_check
    
    return GuardrailResult(status="PASS")

