"""
Azure OpenAI provider implementation.

This is the production provider for Azure deployments.
Uses Managed Identity for authentication in cloud environment.
"""

import logging
from typing import Any, Optional

from openai import AzureOpenAI, APIError, RateLimitError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AzureOpenAIProvider(BaseLLMProvider):
    """
    Azure OpenAI provider for production use.
    
    Security Note: Uses Key Vault via Managed Identity in cloud mode.
    """
    
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment_name: str,
        api_version: str,
        system_prompt: Optional[str] = None,
    ):
        super().__init__(system_prompt=system_prompt)
        
        if not api_key:
            raise ValueError("Azure OpenAI API key not configured")
        if not endpoint:
            raise ValueError("Azure OpenAI endpoint not configured")
        
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint,
        )
        self.deployment_name = deployment_name
        self._model_version = f"azure/{deployment_name}"
    
    @property
    def provider_name(self) -> str:
        return "azure"
    
    @retry(
        retry=retry_if_exception_type(RateLimitError),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(3),
    )
    def _call_api(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from Azure OpenAI")
            
            return content
            
        except RateLimitError:
            logger.warning("Azure OpenAI rate limit hit, will retry...")
            raise
        except APIError as e:
            logger.error(f"Azure OpenAI API error: {e}")
            raise
    
    @retry(
        retry=retry_if_exception_type(RateLimitError),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(3),
    )
    def _call_api_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> dict:
        """API call with tool/function calling support."""
        try:
            kwargs = {
                "model": self.deployment_name,
                "messages": messages,
                "temperature": temperature,
                "max_completion_tokens": max_tokens,
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            
            result = {"content": message.content, "tool_calls": None}
            
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            return result
            
        except RateLimitError:
            logger.warning("Azure OpenAI rate limit hit, will retry...")
            raise
        except APIError as e:
            logger.error(f"Azure OpenAI API error: {e}")
            raise
    
    def get_model_version(self) -> str:
        return self._model_version
