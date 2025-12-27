"""
Tool definitions for LLM Function Calling.

Contains JSON Schema definitions that describe available tools to the LLM.
These definitions follow the OpenAI tools format.
"""

from typing import Callable, Optional

from app.services.tools.sanctions import check_sanctions_list, check_pep_status
from app.services.tools.thresholds import validate_amount_threshold


# Tool definitions in OpenAI format
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_sanctions_list",
            "description": (
                "Checks if a person or company is on global sanctions lists "
                "(OFAC, EU, UN, INTERPOL). ALWAYS use this tool when you identify "
                "a person or company name in the transaction. This is mandatory "
                "for AML compliance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Full name of the person or company to check",
                    }
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_pep_status",
            "description": (
                "Checks if a person is a Politically Exposed Person (PEP). "
                "PEPs include government officials, their family members, and "
                "close associates. Use this for high-value transactions or "
                "when dealing with individuals in positions of power."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "person_name": {
                        "type": "string",
                        "description": "Full name of the person to check",
                    }
                },
                "required": ["person_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_amount_threshold",
            "description": (
                "Validates transaction amount against regulatory reporting thresholds. "
                "Detects if a Currency Transaction Report (CTR) is required and "
                "identifies potential structuring (splitting transactions to avoid "
                "reporting). Use this for all transactions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "Transaction amount",
                    },
                    "currency": {
                        "type": "string",
                        "description": "Currency code (USD, EUR, GBP, etc.)",
                        "default": "USD",
                    },
                    "transaction_count_24h": {
                        "type": "integer",
                        "description": "Optional: number of transactions by this sender in last 24 hours",
                    },
                },
                "required": ["amount"],
            },
        },
    },
]


# Mapping of function names to actual Python functions
TOOL_FUNCTIONS: dict[str, Callable] = {
    "check_sanctions_list": check_sanctions_list,
    "check_pep_status": check_pep_status,
    "validate_amount_threshold": validate_amount_threshold,
}


def get_tool_by_name(name: str) -> Optional[Callable]:
    """
    Returns the Python function for a given tool name.
    
    Args:
        name: Name of the tool
        
    Returns:
        Callable function or None if not found
    """
    return TOOL_FUNCTIONS.get(name)


def execute_tool(name: str, arguments: dict) -> str:
    """
    Executes a tool by name with given arguments.
    
    Args:
        name: Name of the tool to execute
        arguments: Dictionary of arguments to pass
        
    Returns:
        JSON string result from the tool
        
    Raises:
        ValueError: If tool is not found
    """
    func = get_tool_by_name(name)
    if func is None:
        raise ValueError(f"Unknown tool: {name}")
    
    return func(**arguments)

