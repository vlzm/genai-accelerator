"""
Ollama provider implementation.

Local LLM provider using Ollama.
Free and private - no API keys needed, runs on your machine.

Install: https://ollama.ai
Run model: ollama run llama3.2
"""

import json
import logging
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """
    Ollama provider for local LLM inference.
    
    Benefits:
    - Free (no API costs)
    - Private (data stays local)
    - Fast iteration during development
    
    Requires Ollama to be running locally with a model pulled.
    """
    
    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        system_prompt: Optional[str] = None,
    ):
        super().__init__(system_prompt=system_prompt)
        
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._model_version = f"ollama/{model}"
        
        # Verify Ollama is running
        self._check_connection()
    
    def _check_connection(self) -> None:
        """Verifies Ollama is accessible."""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"Ollama not accessible at {self.base_url}: {e}")
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running: ollama serve"
            ) from e
    
    @property
    def provider_name(self) -> str:
        return "ollama"
    
    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def _call_api(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> str:
        try:
            # Convert messages to Ollama format
            prompt_parts = []
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    prompt_parts.append(f"System: {content}")
                elif role == "user":
                    prompt_parts.append(f"User: {content}")
                elif role == "assistant":
                    prompt_parts.append(f"Assistant: {content}")
            
            prompt = "\n\n".join(prompt_parts)
            prompt += "\n\nAssistant: "
            
            # Use generate endpoint for more control
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                        "format": "json",  # Request JSON output
                    },
                )
                response.raise_for_status()
                
                result = response.json()
                content = result.get("response", "")
                
                if not content:
                    raise ValueError("Empty response from Ollama")
                
                return content
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"Ollama connection error: {e}")
            raise
    
    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def _call_api_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> dict:
        """API call with tool/function calling support (uses Ollama chat endpoint)."""
        try:
            with httpx.Client(timeout=120.0) as client:
                request_body = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                }
                if tools:
                    request_body["tools"] = tools
                
                response = client.post(f"{self.base_url}/api/chat", json=request_body)
                response.raise_for_status()
                
                result_data = response.json()
                message = result_data.get("message", {})
                
                result = {"content": message.get("content"), "tool_calls": None}
                
                if message.get("tool_calls"):
                    result["tool_calls"] = [
                        {
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": json.dumps(tc.get("function", {}).get("arguments", {})),
                            }
                        }
                        for i, tc in enumerate(message["tool_calls"])
                    ]
                
                return result
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"Ollama connection error: {e}")
            raise
    
    def get_model_version(self) -> str:
        return self._model_version
