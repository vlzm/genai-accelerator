"""
LLM Service - High-level interface for AI operations.

This module provides a simplified interface to the LLM providers.
It handles provider initialization and exposes the analyze method.

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
    High-level LLM service for AI-powered analysis.
    
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
    
    def analyze(
        self,
        input_text: str,
        context: Optional[str] = None,
    ) -> LLMResponse:
        """
        Analyzes input text with optional context.
        
        This is the main entry point for analysis operations.
        
        Args:
            input_text: Primary text to analyze
            context: Optional additional context
            
        Returns:
            Structured LLMResponse with analysis results
        """
        return self._provider.analyze(
            input_text=input_text,
            context=context,
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
