"""
Tool definitions for LLM Function Calling.

EXAMPLE FILE - Customize for your use case.

Contains JSON Schema definitions that describe available tools to the LLM.
These definitions follow the OpenAI tools format.
"""

from typing import Callable, Optional
import json

# ============================================================================
# EXAMPLE TOOL DEFINITIONS
# ============================================================================
# Uncomment and customize these for your specific use case.
# These definitions tell the LLM what tools are available.

# TOOL_DEFINITIONS = [
#     {
#         "type": "function",
#         "function": {
#             "name": "lookup_database",
#             "description": (
#                 "Looks up information in the database. "
#                 "Use this when you need to verify or retrieve data."
#             ),
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "query": {
#                         "type": "string",
#                         "description": "The search query or entity name",
#                     },
#                     "table": {
#                         "type": "string",
#                         "description": "The table to search (optional)",
#                     },
#                 },
#                 "required": ["query"],
#             },
#         },
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "validate_data",
#             "description": (
#                 "Validates data against business rules. "
#                 "Use this to check if data meets requirements."
#             ),
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "data": {
#                         "type": "string",
#                         "description": "The data to validate",
#                     },
#                     "rule_type": {
#                         "type": "string",
#                         "description": "Type of validation rule to apply",
#                     },
#                 },
#                 "required": ["data"],
#             },
#         },
#     },
# ]


# ============================================================================
# EXAMPLE TOOL IMPLEMENTATIONS
# ============================================================================

def lookup_database(query: str, table: Optional[str] = None) -> str:
    """
    Example database lookup function.
    
    Replace this with actual database queries for your use case.
    
    Args:
        query: Search query
        table: Optional table name
        
    Returns:
        JSON string with lookup results
    """
    # TODO: Implement actual database lookup
    return json.dumps({
        "found": False,
        "message": f"No results found for '{query}'",
        "table": table,
    })


def validate_data(data: str, rule_type: Optional[str] = None) -> str:
    """
    Example data validation function.
    
    Replace this with actual validation logic for your use case.
    
    Args:
        data: Data to validate
        rule_type: Type of validation rule
        
    Returns:
        JSON string with validation results
    """
    # TODO: Implement actual validation logic
    return json.dumps({
        "valid": True,
        "data": data,
        "rule_type": rule_type or "default",
    })


# ============================================================================
# TOOL REGISTRY
# ============================================================================
# Mapping of function names to actual Python functions

TOOL_FUNCTIONS: dict[str, Callable] = {
    "lookup_database": lookup_database,
    "validate_data": validate_data,
}

# Empty by default - uncomment the definitions above to enable tools
TOOL_DEFINITIONS: list = []


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
