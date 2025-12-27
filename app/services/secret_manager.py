"""
Secret Manager with hybrid authentication.

Supports two modes:
- LOCAL: Reads secrets from environment variables (.env file)
- CLOUD: Uses Azure Managed Identity to fetch from Key Vault

Security Note: Using DefaultAzureCredential ensures zero hardcoded secrets
in production. The credential chain automatically selects the best auth method.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment-based configuration.
    
    In LOCAL mode: reads from .env file
    In CLOUD mode: Key Vault values override these defaults
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Environment mode
    env: str = "LOCAL"
    
    # Database settings
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "kyc_db"
    database_user: str = "postgres"
    database_password: str = ""
    
    # LLM Provider selection
    # Options: azure, openai, anthropic, ollama
    llm_provider: str = "azure"
    
    # Azure OpenAI settings (provider: azure)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment_name: str = "gpt-4.1"
    azure_openai_api_version: str = "2024-12-01-preview"  # Latest API version
    
    # OpenAI settings (provider: openai)
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"  # Modern model with good tool calling support
    
    # Anthropic settings (provider: anthropic)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    
    # Ollama settings (provider: ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    
    # Azure Key Vault (for CLOUD mode)
    azure_keyvault_url: str = ""
    
    # RAG / Vector Search (can be disabled)
    rag_enabled: bool = True
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    
    @property
    def is_local(self) -> bool:
        return self.env.upper() == "LOCAL"
    
    @property
    def database_url(self) -> str:
        """Constructs PostgreSQL connection URL."""
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached application settings.
    
    Uses LRU cache to avoid re-reading env vars on every call.
    """
    return Settings()


def get_secret(secret_name: str) -> Optional[str]:
    """
    Retrieves a secret value based on environment mode.
    
    Args:
        secret_name: Name of the secret to retrieve
        
    Returns:
        Secret value or None if not found
        
    Security Note:
        - LOCAL mode: Returns environment variable (for development only)
        - CLOUD mode: Uses Managed Identity to fetch from Key Vault
    """
    settings = get_settings()
    
    if settings.is_local:
        # LOCAL DEV: Read from environment variables
        return os.environ.get(secret_name)
    
    # CLOUD PROD: Use Azure Managed Identity
    # DefaultAzureCredential automatically uses:
    # 1. Environment variables (if set)
    # 2. Managed Identity (in Azure)
    # 3. Azure CLI credentials (for local Azure dev)
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
    
    if not settings.azure_keyvault_url:
        raise ValueError("AZURE_KEYVAULT_URL must be set in CLOUD mode")
    
    credential = DefaultAzureCredential()
    client = SecretClient(
        vault_url=settings.azure_keyvault_url,
        credential=credential
    )
    
    try:
        secret = client.get_secret(secret_name)
        return secret.value
    except Exception as e:
        # Log error but don't expose details (security)
        raise RuntimeError(f"Failed to retrieve secret '{secret_name}'") from e


def get_database_password() -> str:
    """
    Retrieves database password from appropriate source.
    
    Returns:
        Database password string
    """
    settings = get_settings()
    
    if settings.is_local:
        return settings.database_password
    
    # In CLOUD mode, fetch from Key Vault
    password = get_secret("DATABASE-PASSWORD")
    if not password:
        raise ValueError("DATABASE-PASSWORD not found in Key Vault")
    return password


def get_openai_api_key() -> str:
    """
    Retrieves Azure OpenAI API key from appropriate source.
    
    Returns:
        API key string
    """
    settings = get_settings()
    
    if settings.is_local:
        return settings.azure_openai_api_key
    
    # In CLOUD mode, fetch from Key Vault
    api_key = get_secret("AZURE-OPENAI-API-KEY")
    if not api_key:
        raise ValueError("AZURE-OPENAI-API-KEY not found in Key Vault")
    return api_key

