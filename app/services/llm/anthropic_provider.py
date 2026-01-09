"""
Anthropic Claude provider implementation.

Alternative provider using Claude models.
"""

import json
import logging
from typing import Any, Optional

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
    
    Uses Claude for text analysis.
    Note: Claude doesn't have native JSON mode, so we enforce it via prompt.
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        system_prompt: Optional[str] = None,
    ):
        super().__init__(system_prompt=system_prompt)
        
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
    
    @retry(
        retry=retry_if_exception_type(anthropic.RateLimitError),
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
        """API call with tool/function calling support (converts OpenAI format to Anthropic)."""
        try:
            system_content = ""
            user_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                elif msg["role"] == "tool":
                    user_messages.append({
                        "role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": msg.get("tool_call_id", ""), "content": msg["content"]}]
                    })
                elif msg["role"] == "assistant" and msg.get("tool_calls"):
                    content_blocks = []
                    if msg.get("content"):
                        content_blocks.append({"type": "text", "text": msg["content"]})
                    for tc in msg["tool_calls"]:
                        content_blocks.append({
                            "type": "tool_use", "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": json.loads(tc["function"]["arguments"]),
                        })
                    user_messages.append({"role": "assistant", "content": content_blocks})
                else:
                    user_messages.append(msg)
            
            # Convert OpenAI tool format to Anthropic
            anthropic_tools = []
            for tool in tools:
                if tool.get("type") == "function":
                    func = tool["function"]
                    anthropic_tools.append({
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                    })
            
            kwargs = {"model": self.model, "max_tokens": max_tokens, "system": system_content, "messages": user_messages}
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools
            
            response = self.client.messages.create(**kwargs)
            
            result = {"content": None, "tool_calls": None}
            text_parts, tool_calls = [], []
            
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_calls.append({"id": block.id, "type": "function", "function": {"name": block.name, "arguments": json.dumps(block.input)}})
            
            if text_parts:
                result["content"] = "\n".join(text_parts)
            if tool_calls:
                result["tool_calls"] = tool_calls
            
            return result
            
        except anthropic.RateLimitError:
            logger.warning("Anthropic rate limit hit, will retry...")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
    
    def get_model_version(self) -> str:
        return self._model_version
