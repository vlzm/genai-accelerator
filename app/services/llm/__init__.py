"""
LLM Provider abstraction layer.

Supports multiple providers:
- Azure OpenAI (production)
- OpenAI (development)
- Anthropic Claude
- Ollama (local, free)

No LangChain dependency - lightweight native implementation.
"""

from app.services.llm.base import BaseLLMProvider, LLMResponse
from app.services.llm.factory import get_llm_provider, LLMProviderType

__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "get_llm_provider",
    "LLMProviderType",
]

