"""
Base class for LLM providers.

Defines the interface that all providers must implement.
This abstraction allows swapping providers without changing business logic.

Supports two modes:
1. Simple mode: Direct JSON response (analyze_transaction)
2. Agent mode: Tool-calling with grounding (analyze_with_tools)
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# System prompt for simple analysis (no tools)
AML_SYSTEM_PROMPT_SIMPLE = """You are an expert Anti-Money Laundering (AML) and Know Your Customer (KYC) compliance analyst.

Your task is to analyze transaction comments for potential risk indicators. You must:

1. Identify suspicious patterns (e.g., structuring, layering, unusual terminology)
2. Flag potential PII that should be protected
3. Assess the overall risk level based on compliance red flags
4. Provide clear reasoning for your assessment

Risk Levels:
- LOW (0-25): Normal transaction, no concerns
- MEDIUM (26-50): Minor concerns, may need review
- HIGH (51-75): Significant concerns, requires investigation
- CRITICAL (76-100): Major red flags, immediate action needed

Always respond in valid JSON format with the following structure:
{
    "risk_score": <integer 0-100>,
    "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
    "risk_factors": ["<factor1>", "<factor2>", ...],
    "reasoning": "<detailed explanation>"
}
"""

# System prompt for agent mode with tools
AML_SYSTEM_PROMPT_AGENT = """You are a Senior AML/KYC Compliance Officer with access to verification tools.

Your task is to analyze transactions for potential money laundering and compliance risks.

CRITICAL INSTRUCTIONS:
1. When you see ANY person name or company name in the transaction, you MUST call check_sanctions_list to verify they are not sanctioned.
2. For high-value transactions or names that sound like officials, also call check_pep_status.
3. ALWAYS call validate_amount_threshold to check if reporting is required.
4. Base your final risk assessment on the ACTUAL results from these tools, not assumptions.

After gathering all tool results, provide your final assessment in this JSON format:
{
    "risk_score": <integer 0-100>,
    "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
    "risk_factors": ["<factor1>", "<factor2>", ...],
    "reasoning": "<detailed explanation including tool results>",
    "tools_used": ["<tool1>", "<tool2>", ...],
    "compliance_actions": ["<action1>", "<action2>", ...]
}

Risk Level Guidelines:
- LOW (0-25): Clean sanctions check, amount under threshold, no red flags
- MEDIUM (26-50): Minor concerns, PEP involvement, or amount near threshold
- HIGH (51-75): Potential structuring, multiple flags, or partial sanctions match
- CRITICAL (76-100): Confirmed sanctions match, definite structuring, or PEP with high-value transaction
"""


class LLMResponse(BaseModel):
    """Structured response from LLM analysis."""
    risk_score: int
    risk_level: str
    risk_factors: list[str]
    reasoning: str
    tools_used: Optional[list[str]] = None
    compliance_actions: Optional[list[str]] = None
    # Observability: full trace of LLM interaction
    trace: Optional[dict] = None


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement:
    - _call_api: Raw API call with retry logic
    - _call_api_with_tools: API call with function calling support
    - get_model_version: Returns model identifier for audit
    
    Provides two analysis modes:
    - analyze_transaction: Simple direct analysis
    - analyze_with_tools: Agent mode with tool calling (recommended)
    """
    
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
            tools: List of tool definitions
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Response dict with 'content' and optional 'tool_calls'
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
            return LLMResponse(**parsed)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {raw_response}")
            raise ValueError(f"Invalid LLM response format: {e}") from e
    
    def analyze_transaction(
        self,
        comment: str,
        amount: float,
        sender_id: str,
        receiver_id: str,
    ) -> LLMResponse:
        """
        Analyzes a transaction for AML/KYC risk (simple mode).
        
        This method uses direct LLM analysis without tool calling.
        For production use, prefer analyze_with_tools().
        
        Args:
            comment: Transaction comment text
            amount: Transaction amount
            sender_id: Sender identifier
            receiver_id: Receiver identifier
            
        Returns:
            Structured LLMResponse with risk assessment
        """
        user_message = f"""Analyze the following transaction for AML/KYC risk:

Transaction Details:
- Comment: {comment}
- Amount: {amount}
- Sender ID: {sender_id}
- Receiver ID: {receiver_id}

Provide your risk assessment in JSON format."""

        messages = [
            {"role": "system", "content": AML_SYSTEM_PROMPT_SIMPLE},
            {"role": "user", "content": user_message},
        ]
        
        raw_response = self._call_api(messages)
        return self._parse_llm_response(raw_response)
    
    def analyze_with_tools(
        self,
        comment: str,
        amount: float,
        currency: str,
        sender_id: str,
        receiver_id: str,
    ) -> LLMResponse:
        """
        Analyzes a transaction using agent mode with tool calling.
        
        This is the recommended method for production. It uses function calling
        to ground the LLM's decisions in real data (sanctions lists, thresholds).
        
        The agent loop:
        1. LLM receives transaction and decides which tools to call
        2. Tools are executed and results returned to LLM
        3. LLM synthesizes final risk assessment based on tool results
        
        Includes full tracing for observability and evaluation.
        
        Args:
            comment: Transaction comment text
            amount: Transaction amount
            currency: Currency code (USD, EUR, etc.)
            sender_id: Sender identifier
            receiver_id: Receiver identifier
            
        Returns:
            Structured LLMResponse with risk assessment, tool usage, and trace
        """
        from app.services.tools import TOOL_DEFINITIONS, execute_tool
        from datetime import datetime
        
        # Initialize trace for observability
        trace = {
            "started_at": datetime.utcnow().isoformat(),
            "model": self.get_model_version(),
            "input": {
                "comment": comment,
                "amount": amount,
                "currency": currency,
                "sender_id": sender_id,
                "receiver_id": receiver_id,
            },
            "steps": [],  # Each iteration step
            "tool_calls": [],  # Detailed tool call log
            "total_iterations": 0,
        }
        
        user_message = f"""Analyze this transaction for AML/KYC compliance:

Transaction Details:
- Comment: "{comment}"
- Amount: {amount} {currency}
- Sender ID: {sender_id}
- Receiver ID: {receiver_id}

Use the available tools to verify entities and check thresholds before making your assessment."""

        messages = [
            {"role": "system", "content": AML_SYSTEM_PROMPT_AGENT},
            {"role": "user", "content": user_message},
        ]
        
        tools_used = []
        tool_results = []  # Store tool results for fallback
        max_iterations = 8  # Increased to allow more complex analyses
        
        for iteration in range(max_iterations):
            trace["total_iterations"] = iteration + 1
            step_trace = {
                "iteration": iteration + 1,
                "action": None,
                "tool_calls": [],
            }
            
            # Call LLM with tools
            response = self._call_api_with_tools(
                messages=messages,
                tools=TOOL_DEFINITIONS,
                temperature=0.1,
                max_tokens=1500,
            )
            
            # Check if LLM wants to call tools
            if response.get("tool_calls"):
                step_trace["action"] = "tool_calls"
                
                # Add assistant's response to history
                messages.append({
                    "role": "assistant",
                    "content": response.get("content") or "",
                    "tool_calls": response["tool_calls"],
                })
                
                # Execute each tool call
                for tool_call in response["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])
                    
                    logger.info(f"Executing tool: {function_name} with args: {function_args}")
                    tools_used.append(function_name)
                    
                    # Trace the tool call
                    tool_trace = {
                        "tool": function_name,
                        "arguments": function_args,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    
                    try:
                        # Execute the tool
                        tool_result = execute_tool(function_name, function_args)
                        parsed_result = json.loads(tool_result) if tool_result.startswith("{") else tool_result
                        tool_trace["result"] = parsed_result
                        tool_trace["status"] = "success"
                        # Store for fallback response construction
                        tool_results.append({"tool": function_name, "result": parsed_result})
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        tool_result = json.dumps({"error": str(e)})
                        tool_trace["result"] = {"error": str(e)}
                        tool_trace["status"] = "error"
                    
                    trace["tool_calls"].append(tool_trace)
                    step_trace["tool_calls"].append(tool_trace)
                    
                    # Add tool result to history
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": function_name,
                        "content": tool_result,
                    })
            else:
                # No more tool calls, LLM should provide final answer
                final_content = response.get("content", "")
                step_trace["action"] = "final_response"
                step_trace["content_preview"] = final_content[:200] if final_content else ""
                
                if final_content:
                    try:
                        result = self._parse_llm_response(final_content)
                        # Ensure tools_used is populated
                        if result.tools_used is None:
                            result.tools_used = tools_used
                        
                        # Finalize trace
                        trace["completed_at"] = datetime.utcnow().isoformat()
                        trace["final_output"] = {
                            "risk_score": result.risk_score,
                            "risk_level": result.risk_level,
                            "risk_factors": result.risk_factors,
                        }
                        trace["steps"].append(step_trace)
                        result.trace = trace
                        
                        return result
                    except ValueError as e:
                        # If parsing failed, ask LLM to provide proper JSON
                        logger.warning(f"Failed to parse response, requesting JSON format: {e}")
                        step_trace["parse_error"] = str(e)
                        messages.append({
                            "role": "assistant",
                            "content": final_content,
                        })
                        messages.append({
                            "role": "user",
                            "content": "Please provide your final risk assessment in the required JSON format with risk_score, risk_level, risk_factors, and reasoning fields.",
                        })
                        trace["steps"].append(step_trace)
                        continue
                
                # Empty response - ask for final assessment
                if tools_used:
                    logger.info("Empty response after tools, requesting final assessment")
                    step_trace["action"] = "empty_response_retry"
                    messages.append({
                        "role": "user",
                        "content": "Based on the tool results above, provide your final risk assessment in JSON format.",
                    })
                    trace["steps"].append(step_trace)
                    continue
                else:
                    trace["error"] = "LLM returned empty response without calling any tools"
                    raise ValueError("LLM returned empty response without calling any tools")
            
            trace["steps"].append(step_trace)
        
        # If we exhausted iterations, construct response from tool results
        logger.warning(f"Agent loop exceeded {max_iterations} iterations, constructing fallback response")
        trace["completed_at"] = datetime.utcnow().isoformat()
        trace["error"] = f"Exceeded {max_iterations} iterations"
        
        # Build intelligent fallback from tool results
        risk_factors = []
        risk_score = 50  # Default medium
        
        for tr in tool_results:
            if isinstance(tr.get("result"), dict):
                res = tr["result"]
                # Check sanctions results
                if res.get("is_sanctioned"):
                    risk_factors.append(f"SANCTIONS HIT: {res.get('entity', 'Unknown')} ({res.get('sanction_list', 'Unknown list')})")
                    risk_score = max(risk_score, 90)
                # Check PEP results
                if res.get("is_pep"):
                    risk_factors.append(f"PEP MATCH: {res.get('entity', 'Unknown')} ({res.get('position', 'Unknown position')})")
                    risk_score = max(risk_score, 75)
                # Check threshold results
                if res.get("requires_sar"):
                    risk_factors.append(f"SAR REQUIRED: Amount ${res.get('amount', 0):,.0f} exceeds threshold")
                    risk_score = max(risk_score, 70)
        
        if not risk_factors:
            risk_factors = ["Analysis could not complete - manual review required"]
        
        risk_level = (
            "CRITICAL" if risk_score >= 76 else
            "HIGH" if risk_score >= 51 else
            "MEDIUM" if risk_score >= 26 else
            "LOW"
        )
        
        return LLMResponse(
            risk_score=risk_score,
            risk_level=risk_level,
            risk_factors=risk_factors,
            reasoning=f"Automated fallback analysis. Tools used: {', '.join(tools_used) if tools_used else 'none'}. Manual review recommended.",
            tools_used=tools_used,
            compliance_actions=["MANUAL_REVIEW"],
            trace=trace,
        )
