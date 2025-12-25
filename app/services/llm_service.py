"""
LLM Service - High-level interface for AI operations.

This module provides a simplified interface to the LLM providers.
It handles provider initialization and exposes the analyze_transaction method.

Supports multiple providers via LLM_PROVIDER environment variable:
- azure: Azure OpenAI (production)
- openai: Standard OpenAI API
- anthropic: Anthropic Claude
- ollama: Local models (free)

No LangChain dependency - uses lightweight native implementation.
"""

from typing import Optional

from app.services.llm import BaseLLMProvider, LLMResponse, get_llm_provider


class LLMService:
    """
    High-level LLM service for KYC/AML analysis.
    
    Wraps the provider abstraction layer for easy use by business logic.
    """
    
    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        """
        Initialize LLM service.
        
        Args:
            provider: Optional provider instance. If not provided,
                     uses the configured provider from LLM_PROVIDER env var.
        """
        self._provider = provider or get_llm_provider()
    
    @property
    def provider(self) -> BaseLLMProvider:
        """Returns the underlying LLM provider."""
        return self._provider
    
    def analyze_transaction(
        self,
        comment: str,
        amount: float,
        sender_id: str,
        receiver_id: str,
    ) -> LLMResponse:
        """
        Analyzes a transaction for AML/KYC risk.
        
        Args:
            comment: Transaction comment text
            amount: Transaction amount
            sender_id: Sender identifier
            receiver_id: Receiver identifier
            
        Returns:
            Structured LLMResponse with risk assessment
        """
        return self._provider.analyze_transaction(
            comment=comment,
            amount=amount,
            sender_id=sender_id,
            receiver_id=receiver_id,
        )
    
    def get_model_version(self) -> str:
        """Returns the model version string for audit logging."""
        return self._provider.get_model_version()


# Singleton instance for reuse
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Returns singleton LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def reset_llm_service() -> None:
    """Resets the singleton instance. Useful for testing."""
    global _llm_service
    _llm_service = None
