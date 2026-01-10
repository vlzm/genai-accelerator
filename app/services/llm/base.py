"""
Base class for LLM providers.

Defines the interface that all providers must implement.
This abstraction allows swapping providers without changing business logic.

Supports two modes:
1. Simple mode: Direct JSON response (analyze)
2. Agent mode: Tool-calling with grounding (analyze_with_tools)
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# Default system prompt for ANALYSIS mode - CUSTOMIZE FOR YOUR USE CASE
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

# System prompt for CHAT mode - conversational Q&A without scoring
CHAT_SYSTEM_PROMPT = """You are a helpful AI assistant. Your goal is to provide clear, accurate, and helpful responses to user questions.

You have access to tools that can help you gather information. Use them when needed.

When responding:
1. Be concise but thorough
2. If you're uncertain, say so
3. Provide actionable information when possible

You MUST always respond in valid JSON format with the following structure:
{
    "reasoning": "<your detailed answer here>",
    "score": null,
    "categories": []
}

Important: In chat mode, score is always null and categories is always empty. Put your full response in the "reasoning" field.
"""


class LLMResponse(BaseModel):
    """
    Structured response from LLM analysis.
    
    Supports two modes:
    - Analysis mode: score and categories are populated
    - Chat mode: score is None, categories is empty, reasoning contains the response
    """
    score: Optional[int] = None  # None in chat mode
    categories: list[str] = []
    reasoning: str  # Maps to 'summary' in JSON response (or full chat response)
    processed_content: Optional[str] = None
    tools_used: Optional[list[str]] = None
    # Observability: full trace of LLM interaction
    trace: Optional[dict] = None
    # Mode indicator
    mode: str = "analysis"  # "analysis" | "chat"


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement:
    - _call_api: Raw API call with retry logic
    - _call_api_with_tools: API call with function calling support  
    - get_model_version: Returns model identifier for audit
    
    Provides two analysis modes:
    - analyze(): Simple direct analysis (no tools)
    - analyze_with_tools(): Agent mode with tool calling
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
        Makes API call to the LLM provider (simple mode).
        
        Args:
            messages: Chat messages in OpenAI format
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response
            
        Returns:
            Raw response content string (should be valid JSON)
        """
        pass
    
    @abstractmethod
    def _call_api_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> dict:
        """
        Makes API call with tool/function calling support.
        
        Args:
            messages: Chat messages in OpenAI format
            tools: List of tool definitions (OpenAI format)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Response dict with structure:
            {
                "content": str | None,
                "tool_calls": [
                    {
                        "id": str,
                        "function": {"name": str, "arguments": str}
                    }
                ] | None
            }
        """
        pass
    
    @abstractmethod
    def get_model_version(self) -> str:
        """Returns the model version string for audit logging."""
        pass
    
    def _parse_llm_response(self, raw_response: str, mode: str = "analysis") -> LLMResponse:
        """
        Parses and validates LLM response JSON.
        
        Args:
            raw_response: Raw string response from LLM
            mode: "analysis" or "chat" - determines validation rules
            
        Returns:
            Parsed LLMResponse object
        """
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
            
            # Set mode in response
            parsed['mode'] = mode
            
            # In chat mode, ensure score is None and categories is empty
            if mode == "chat":
                parsed['score'] = None
                parsed['categories'] = []
            
            return LLMResponse(**parsed)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {raw_response}")
            raise ValueError(f"Invalid LLM response format: {e}") from e
    
    def analyze(
        self,
        input_text: str,
        context: Optional[str] = None,
        mode: str = "analysis",
    ) -> LLMResponse:
        """
        Analyzes input text with optional context (simple mode).
        
        Args:
            input_text: Primary text to analyze
            context: Optional additional context
            mode: "analysis" for scoring mode, "chat" for conversational mode
            
        Returns:
            Structured LLMResponse with analysis results
        """
        # Select system prompt based on mode
        system_prompt = CHAT_SYSTEM_PROMPT if mode == "chat" else self.system_prompt
        
        # Build user message based on mode
        if mode == "chat":
            user_message = input_text
            if context:
                user_message += f"\n\nContext:\n{context}"
            user_message += "\n\nRespond in the required JSON format."
        else:
            user_message = f"Please analyze the following input:\n\n{input_text}"
            if context:
                user_message += f"\n\nAdditional Context:\n{context}"
            user_message += "\n\nProvide your analysis in the required JSON format."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        
        # Initialize trace for observability
        trace = {
            "started_at": datetime.utcnow().isoformat(),
            "model": self.get_model_version(),
            "mode": mode,
            "input": {
                "input_text": input_text[:500] + "..." if len(input_text) > 500 else input_text,
                "context": context[:200] + "..." if context and len(context) > 200 else context,
            },
        }
        
        try:
            raw_response = self._call_api(messages)
            trace["completed_at"] = datetime.utcnow().isoformat()
            trace["raw_response_preview"] = raw_response[:500] if raw_response else None
            
            result = self._parse_llm_response(raw_response, mode=mode)
            result.trace = trace
            
            return result
            
        except Exception as e:
            trace["error"] = str(e)
            trace["completed_at"] = datetime.utcnow().isoformat()
            raise
    
    def analyze_with_tools(
        self,
        input_text: str,
        context: Optional[str] = None,
        agent_prompt: Optional[str] = None,
        max_iterations: int = 8,
        mode: str = "analysis",
    ) -> LLMResponse:
        """
        Analyzes input using agent mode with tool calling.
        
        The agent loop:
        1. LLM receives input and decides which tools to call
        2. Tools are executed and results returned to LLM
        3. Loop continues until LLM provides final JSON answer
        
        Args:
            input_text: Primary text to analyze
            context: Optional additional context
            agent_prompt: Custom system prompt (overrides default)
            max_iterations: Maximum tool-calling iterations
            mode: "analysis" for scoring mode, "chat" for conversational mode
            
        Returns:
            Structured LLMResponse with analysis and tool usage trace
        """
        from app.services.tools import TOOL_DEFINITIONS, execute_tool
        
        # Fall back to simple mode if no tools defined
        if not TOOL_DEFINITIONS:
            logger.warning("No tools defined, falling back to simple analysis")
            return self.analyze(input_text, context, mode=mode)
        
        # Select system prompt based on mode (unless custom prompt provided)
        if agent_prompt:
            system_prompt = agent_prompt
        elif mode == "chat":
            system_prompt = CHAT_SYSTEM_PROMPT
        else:
            system_prompt = self.system_prompt
        
        # Initialize trace
        trace = {
            "started_at": datetime.utcnow().isoformat(),
            "model": self.get_model_version(),
            "mode": f"agent_{mode}",  # "agent_analysis" or "agent_chat"
            "input": {
                "input_text": input_text[:500] + "..." if len(input_text) > 500 else input_text,
                "context": context[:200] + "..." if context and len(context) > 200 else context,
            },
            "tool_calls": [],
            "total_iterations": 0,
        }
        
        # Build user message based on mode
        if mode == "chat":
            user_message = input_text
            if context:
                user_message += f"\n\nContext:\n{context}"
            user_message += "\n\nUse the available tools if needed, then provide your response in JSON format."
        else:
            user_message = f"Please analyze the following input:\n\n{input_text}"
            if context:
                user_message += f"\n\nAdditional Context:\n{context}"
            user_message += "\n\nUse the available tools to gather information, then provide your final analysis in JSON format."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        
        tools_used = []
        
        # Agent loop
        for iteration in range(max_iterations):
            trace["total_iterations"] = iteration + 1
            
            response = self._call_api_with_tools(
                messages=messages,
                tools=TOOL_DEFINITIONS,
                temperature=0.1,
                max_tokens=1500,
            )
            
            # Check if LLM wants to call tools
            if response.get("tool_calls"):
                messages.append({
                    "role": "assistant",
                    "content": response.get("content") or "",
                    "tool_calls": response["tool_calls"],
                })
                
                # Execute each tool
                for tool_call in response["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    func_args = json.loads(tool_call["function"]["arguments"])
                    
                    logger.info(f"Executing tool: {func_name}")
                    tools_used.append(func_name)
                    
                    try:
                        result = execute_tool(func_name, func_args)
                        trace["tool_calls"].append({
                            "tool": func_name,
                            "arguments": func_args,
                            "result": result[:500] if len(result) > 500 else result,
                            "status": "success",
                        })
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        result = json.dumps({"error": str(e)})
                        trace["tool_calls"].append({
                            "tool": func_name,
                            "arguments": func_args,
                            "error": str(e),
                            "status": "error",
                        })
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": func_name,
                        "content": result,
                    })
            else:
                # No tool calls - parse final response
                final_content = response.get("content", "")
                if final_content:
                    try:
                        result = self._parse_llm_response(final_content, mode=mode)
                        result.tools_used = list(set(tools_used))
                        trace["completed_at"] = datetime.utcnow().isoformat()
                        result.trace = trace
                        return result
                    except ValueError:
                        # Ask for proper JSON
                        messages.append({"role": "assistant", "content": final_content})
                        messages.append({
                            "role": "user",
                            "content": "Please provide your response in the required JSON format.",
                        })
                        continue
                
                # Empty response - request final assessment
                if tools_used:
                    final_prompt = (
                        "Based on the tool results, provide your response in JSON format."
                        if mode == "chat"
                        else "Based on the tool results, provide your final analysis in JSON format."
                    )
                    messages.append({
                        "role": "user",
                        "content": final_prompt,
                    })
                    continue
                else:
                    raise ValueError("LLM returned empty response without calling tools")
        
        # Fallback if max iterations exceeded
        logger.warning(f"Agent loop exceeded {max_iterations} iterations")
        trace["completed_at"] = datetime.utcnow().isoformat()
        trace["error"] = "max_iterations_exceeded"
        
        # Return appropriate fallback based on mode
        if mode == "chat":
            return LLMResponse(
                score=None,
                categories=[],
                reasoning="I apologize, but I couldn't complete your request. Please try again or rephrase your question.",
                tools_used=list(set(tools_used)),
                trace=trace,
                mode="chat",
            )
        else:
            return LLMResponse(
                score=50,
                categories=["MANUAL_REVIEW_REQUIRED"],
                reasoning="Analysis incomplete - max iterations exceeded. Manual review required.",
                tools_used=list(set(tools_used)),
                trace=trace,
                mode="analysis",
            )
