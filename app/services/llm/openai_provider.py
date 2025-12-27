"""
OpenAI provider implementation.

Standard OpenAI API (not Azure) for development and testing.
"""

import logging
from typing import Any

from openai import OpenAI, APIError, RateLimitError, BadRequestError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Models that support JSON mode (response_format)
JSON_MODE_MODELS = {
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-turbo-preview",
    "gpt-3.5-turbo-1106", "gpt-3.5-turbo-0125",
    "gpt-4-1106-preview", "gpt-4-0125-preview",
}


class OpenAIProvider(BaseLLMProvider):
    """
    Standard OpenAI provider for development.
    
    Uses the regular OpenAI API (api.openai.com).
    Automatically detects if model supports JSON mode.
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self._model_version = f"openai/{model}"
        self._supports_json_mode = self._check_json_mode_support(model)
    
    def _check_json_mode_support(self, model: str) -> bool:
        """Check if model supports JSON response format."""
        # Check exact match or prefix match (e.g., gpt-4o-2024-05-13)
        for supported in JSON_MODE_MODELS:
            if model == supported or model.startswith(f"{supported}-"):
                return True
        return False
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
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
            # Build request kwargs
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_completion_tokens": max_tokens,  # New API parameter for modern models
            }
            
            # Add JSON mode if supported
            if self._supports_json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = self.client.chat.completions.create(**kwargs)
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from OpenAI")
            
            return content
            
        except BadRequestError as e:
            # If JSON mode failed, retry without it
            if "response_format" in str(e) and self._supports_json_mode:
                logger.warning(f"JSON mode not supported for {self.model}, retrying without it")
                self._supports_json_mode = False
                return self._call_api(messages, temperature, max_tokens)
            raise
        except RateLimitError:
            logger.warning("OpenAI rate limit hit, will retry...")
            raise
        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
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
        """
        Makes API call with function/tool calling support.
        
        Returns dict with 'content' and optional 'tool_calls'.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
                max_completion_tokens=max_tokens,  # New API parameter for modern models
            )
            
            message = response.choices[0].message
            
            result = {
                "content": message.content,
                "tool_calls": None,
            }
            
            # Extract tool calls if present
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            
            return result
            
        except RateLimitError:
            logger.warning("OpenAI rate limit hit, will retry...")
            raise
        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    def get_model_version(self) -> str:
        return self._model_version

