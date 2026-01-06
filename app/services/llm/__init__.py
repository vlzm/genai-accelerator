"""
LLM Provider abstraction layer.

Provides a unified interface for multiple LLM providers:
- Azure OpenAI (production)
- OpenAI (development)
- Anthropic Claude
- Ollama (local/free)

Usage:
    from app.services.llm import get_llm_provider
    
    provider = get_llm_provider()
    response = provider.analyze("Analyze this text")
"""

from app.services.llm.base import BaseLLMProvider, LLMResponse, DEFAULT_SYSTEM_PROMPT
from app.services.llm.factory import get_llm_provider, reset_provider, LLMProviderType

__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "DEFAULT_SYSTEM_PROMPT",
    "get_llm_provider",
    "reset_provider",
    "LLMProviderType",
]
