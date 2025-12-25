"""
Base class for LLM providers.

Defines the interface that all providers must implement.
This abstraction allows swapping providers without changing business logic.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


# System prompt for AML/KYC analysis (shared across all providers)
AML_SYSTEM_PROMPT = """You are an expert Anti-Money Laundering (AML) and Know Your Customer (KYC) compliance analyst.

Your task is to analyze transaction comments for potential risk indicators. You must:

1. Identify suspicious patterns (e.g., structuring, layering, unusual terminology)
2. Flag potential PII that should be protected
3. Assess the overall risk level based on compliance red flags
4. Provide clear reasoning for your assessment

Risk Levels:
- LOW (0-25): Normal transaction, no concerns
- MEDIUM (26-50): Minor concerns, may need review
- HIGH (51-75): Significant concerns, requires investigation
- CRITICAL (76-100): Major red flags, immediate action needed

Always respond in valid JSON format with the following structure:
{
    "risk_score": <integer 0-100>,
    "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
    "risk_factors": ["<factor1>", "<factor2>", ...],
    "reasoning": "<detailed explanation>"
}
"""


class LLMResponse(BaseModel):
    """Structured response from LLM analysis."""
    risk_score: int
    risk_level: str
    risk_factors: list[str]
    reasoning: str


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement:
    - _call_api: Raw API call with retry logic
    - get_model_version: Returns model identifier for audit
    
    The analyze_transaction method is shared across all providers.
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the provider name (e.g., 'azure', 'openai')."""
        pass
    
    @abstractmethod
    def _call_api(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> str:
        """
        Makes API call to the LLM provider.
        
        Args:
            messages: Chat messages in OpenAI format
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response
            
        Returns:
            Raw response content string (should be valid JSON)
        """
        pass
    
    @abstractmethod
    def get_model_version(self) -> str:
        """Returns the model version string for audit logging."""
        pass
    
    def analyze_transaction(
        self,
        comment: str,
        amount: float,
        sender_id: str,
        receiver_id: str,
    ) -> LLMResponse:
        """
        Analyzes a transaction for AML/KYC risk.
        
        This method is shared across all providers - only _call_api differs.
        
        Args:
            comment: Transaction comment text
            amount: Transaction amount
            sender_id: Sender identifier
            receiver_id: Receiver identifier
            
        Returns:
            Structured LLMResponse with risk assessment
        """
        user_message = f"""Analyze the following transaction for AML/KYC risk:

Transaction Details:
- Comment: {comment}
- Amount: {amount}
- Sender ID: {sender_id}
- Receiver ID: {receiver_id}

Provide your risk assessment in JSON format."""

        messages = [
            {"role": "system", "content": AML_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        
        raw_response = self._call_api(messages)
        
        try:
            # Clean response if wrapped in markdown code blocks
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            parsed = json.loads(cleaned)
            return LLMResponse(**parsed)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {raw_response}")
            raise ValueError(f"Invalid LLM response format: {e}") from e

