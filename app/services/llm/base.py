"""
Base class for LLM providers.

Defines the interface that all providers must implement.
This abstraction allows swapping providers without changing business logic.

Supports two modes:
1. Simple mode: Direct JSON response (analyze)
2. Agent mode: Tool-calling with grounding (analyze_with_tools) - to be implemented
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# Default system prompt - CUSTOMIZE FOR YOUR USE CASE
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant specialized in analyzing and processing text.

Your task is to analyze the provided input and:
1. Assess the content based on relevant criteria
2. Identify key categories or themes
3. Provide a clear summary of your analysis
4. Optionally, provide processed/transformed content

Scoring Guidelines:
- LOW (0-25): Minimal significance or concern
- MEDIUM (26-50): Moderate significance, may need attention
- HIGH (51-75): Significant findings, requires review
- CRITICAL (76-100): Critical findings, immediate action recommended

Always respond in valid JSON format with the following structure:
{
    "score": <integer 0-100>,
    "categories": ["<category1>", "<category2>", ...],
    "summary": "<detailed analysis and reasoning>",
    "processed_content": "<optional transformed content>"
}
"""


class LLMResponse(BaseModel):
    """Structured response from LLM analysis."""
    score: int
    categories: list[str]
    reasoning: str  # Maps to 'summary' in JSON response
    processed_content: Optional[str] = None
    tools_used: Optional[list[str]] = None
    # Observability: full trace of LLM interaction
    trace: Optional[dict] = None


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement:
    - _call_api: Raw API call with retry logic
    - get_model_version: Returns model identifier for audit
    
    Provides the analyze method for text analysis.
    """
    
    def __init__(self, system_prompt: Optional[str] = None):
        """
        Initialize provider with optional custom system prompt.
        
        Args:
            system_prompt: Custom system prompt. If None, uses DEFAULT_SYSTEM_PROMPT.
        """
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the provider name (e.g., 'azure', 'openai')."""
        pass
    
    @abstractmethod
    def _call_api(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> str:
        """
        Makes API call to the LLM provider.
        
        Args:
            messages: Chat messages in OpenAI format
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response
            
        Returns:
            Raw response content string (should be valid JSON)
        """
        pass
    
    @abstractmethod
    def get_model_version(self) -> str:
        """Returns the model version string for audit logging."""
        pass
    
    def _parse_llm_response(self, raw_response: str) -> LLMResponse:
        """Parses and validates LLM response JSON."""
        try:
            # Clean response if wrapped in markdown code blocks
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            parsed = json.loads(cleaned)
            
            # Map 'summary' to 'reasoning' if present
            if 'summary' in parsed and 'reasoning' not in parsed:
                parsed['reasoning'] = parsed.pop('summary')
            
            return LLMResponse(**parsed)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {raw_response}")
            raise ValueError(f"Invalid LLM response format: {e}") from e
    
    def analyze(
        self,
        input_text: str,
        context: Optional[str] = None,
    ) -> LLMResponse:
        """
        Analyzes input text with optional context.
        
        Args:
            input_text: Primary text to analyze
            context: Optional additional context
            
        Returns:
            Structured LLMResponse with analysis results
        """
        from datetime import datetime
        
        # Build user message
        user_message = f"Please analyze the following input:\n\n{input_text}"
        if context:
            user_message += f"\n\nAdditional Context:\n{context}"
        user_message += "\n\nProvide your analysis in the required JSON format."
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]
        
        # Initialize trace for observability
        trace = {
            "started_at": datetime.utcnow().isoformat(),
            "model": self.get_model_version(),
            "input": {
                "input_text": input_text[:500] + "..." if len(input_text) > 500 else input_text,
                "context": context[:200] + "..." if context and len(context) > 200 else context,
            },
        }
        
        try:
            raw_response = self._call_api(messages)
            trace["completed_at"] = datetime.utcnow().isoformat()
            trace["raw_response_preview"] = raw_response[:500] if raw_response else None
            
            result = self._parse_llm_response(raw_response)
            result.trace = trace
            
            return result
            
        except Exception as e:
            trace["error"] = str(e)
            trace["completed_at"] = datetime.utcnow().isoformat()
            raise


# ============================================================================
# EXAMPLE: Tool-based Analysis (Agent Mode)
# ============================================================================
# Uncomment and customize the code below to enable function calling / tools.
# This is useful when you need to ground LLM decisions in external data sources.
#
# Example use cases:
# - Checking databases or APIs for entity verification
# - Looking up reference data
# - Performing calculations or validations
#
# def _call_api_with_tools(
#     self,
#     messages: list[dict],
#     tools: list[dict],
#     temperature: float = 0.1,
#     max_tokens: int = 1000,
# ) -> dict:
#     """
#     Makes API call with tool/function calling support.
#     
#     Args:
#         messages: Chat messages in OpenAI format
#         tools: List of tool definitions
#         temperature: Sampling temperature
#         max_tokens: Maximum tokens in response
#         
#     Returns:
#         Response dict with 'content' and optional 'tool_calls'
#     """
#     pass
#
# EXAMPLE_TOOL_DEFINITIONS = [
#     {
#         "type": "function",
#         "function": {
#             "name": "lookup_database",
#             "description": "Look up information in the database",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "query": {
#                         "type": "string",
#                         "description": "The search query",
#                     }
#                 },
#                 "required": ["query"],
#             },
#         },
#     },
# ]
