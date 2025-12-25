"""
LLM Provider Factory.

Creates the appropriate LLM provider based on configuration.
Supports runtime switching between providers via LLM_PROVIDER env var.
"""

import logging
from enum import Enum
from typing import Optional

from app.services.llm.base import BaseLLMProvider
from app.services.secret_manager import get_settings

logger = logging.getLogger(__name__)


class LLMProviderType(str, Enum):
    """Supported LLM providers."""
    AZURE = "azure"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


def create_azure_provider() -> BaseLLMProvider:
    """Creates Azure OpenAI provider."""
    from app.services.llm.azure_provider import AzureOpenAIProvider
    from app.services.secret_manager import get_openai_api_key
    
    settings = get_settings()
    api_key = get_openai_api_key()
    
    return AzureOpenAIProvider(
        api_key=api_key,
        endpoint=settings.azure_openai_endpoint,
        deployment_name=settings.azure_openai_deployment_name,
        api_version=settings.azure_openai_api_version,
    )


def create_openai_provider() -> BaseLLMProvider:
    """Creates standard OpenAI provider."""
    from app.services.llm.openai_provider import OpenAIProvider
    
    settings = get_settings()
    
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


def create_anthropic_provider() -> BaseLLMProvider:
    """Creates Anthropic Claude provider."""
    from app.services.llm.anthropic_provider import AnthropicProvider
    
    settings = get_settings()
    
    return AnthropicProvider(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    )


def create_ollama_provider() -> BaseLLMProvider:
    """Creates Ollama local provider."""
    from app.services.llm.ollama_provider import OllamaProvider
    
    settings = get_settings()
    
    return OllamaProvider(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
    )


# Provider factory mapping
_PROVIDER_FACTORIES = {
    LLMProviderType.AZURE: create_azure_provider,
    LLMProviderType.OPENAI: create_openai_provider,
    LLMProviderType.ANTHROPIC: create_anthropic_provider,
    LLMProviderType.OLLAMA: create_ollama_provider,
}


# Singleton cache
_provider_instance: Optional[BaseLLMProvider] = None


def get_llm_provider() -> BaseLLMProvider:
    """
    Returns the configured LLM provider.
    
    Provider is determined by LLM_PROVIDER environment variable.
    Instance is cached for reuse.
    
    Returns:
        Configured LLM provider instance
    """
    global _provider_instance
    
    if _provider_instance is not None:
        return _provider_instance
    
    settings = get_settings()
    provider_type = settings.llm_provider
    
    try:
        provider_enum = LLMProviderType(provider_type.lower())
    except ValueError:
        valid = [p.value for p in LLMProviderType]
        raise ValueError(
            f"Invalid LLM_PROVIDER: '{provider_type}'. "
            f"Valid options: {valid}"
        )
    
    factory = _PROVIDER_FACTORIES.get(provider_enum)
    if factory is None:
        raise ValueError(f"No factory registered for provider: {provider_enum}")
    
    logger.info(f"Initializing LLM provider: {provider_enum.value}")
    _provider_instance = factory()
    
    return _provider_instance


def reset_provider() -> None:
    """
    Resets the cached provider instance.
    
    Useful for testing or runtime provider switching.
    """
    global _provider_instance
    _provider_instance = None

