"""
Anthropic Claude provider implementation.

Alternative provider using Claude models.
"""

import logging
from typing import Any

import anthropic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude provider.
    
    Uses Claude for transaction analysis.
    Note: Claude doesn't have native JSON mode, so we enforce it via prompt.
    """
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        if not api_key:
            raise ValueError("Anthropic API key not configured")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self._model_version = f"anthropic/{model}"
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    @retry(
        retry=retry_if_exception_type(anthropic.RateLimitError),
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
            # Extract system message and user messages
            system_content = ""
            user_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                else:
                    user_messages.append(msg)
            
            # Add JSON enforcement to system prompt
            system_content += "\n\nIMPORTANT: Respond ONLY with valid JSON, no other text."
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_content,
                messages=user_messages,
            )
            
            content = response.content[0].text
            if not content:
                raise ValueError("Empty response from Anthropic")
            
            return content
            
        except anthropic.RateLimitError:
            logger.warning("Anthropic rate limit hit, will retry...")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
    
    def _call_api_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> dict:
        """
        Tool calling for Anthropic.
        
        Note: Anthropic has its own tool format. For simplicity in this MVP,
        we fall back to simple mode. Full implementation would convert
        OpenAI tool format to Anthropic's format.
        """
        # TODO: Implement full Anthropic tool calling
        # For now, fall back to simple mode
        logger.warning("Anthropic tool calling not fully implemented, using simple mode")
        content = self._call_api(messages, temperature, max_tokens)
        return {"content": content, "tool_calls": None}
    
    def get_model_version(self) -> str:
        return self._model_version

