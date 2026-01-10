"""
Tool definitions for LLM Function Calling.

Contains JSON Schema definitions that describe available tools to the LLM.
These definitions follow the OpenAI tools format.

Simple demo tools are provided:
- get_current_time: Returns current date and time
- calculate: Performs arithmetic calculations
"""

import json
import logging
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# TOOL DEFINITIONS (OpenAI format)
# ============================================================================

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": (
                "Returns the current date and time in ISO format. "
                "Use this when you need to know the current time or date "
                "for time-sensitive analysis or logging purposes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Optional timezone name (e.g., 'UTC', 'US/Eastern'). Defaults to UTC.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Performs arithmetic calculations. Supports basic operations: "
                "addition (+), subtraction (-), multiplication (*), division (/), "
                "and exponentiation (**). Use this to compute numeric values "
                "during analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate (e.g., '100 * 1.15', '(50 + 30) / 2')",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_database",
            "description": (
                "Looks up information in the database by query string. "
                "Use this when you need to verify or retrieve data records. "
                "Returns matching records or indicates if nothing was found."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query or entity name to look up",
                    },
                    "table": {
                        "type": "string",
                        "description": "Optional: specific table/collection to search in",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

def get_current_time(timezone: Optional[str] = None) -> str:
    """
    Returns the current date and time.
    
    Args:
        timezone: Optional timezone name (currently only UTC supported)
        
    Returns:
        JSON string with current timestamp
    """
    now = datetime.utcnow()
    
    return json.dumps({
        "current_time": now.isoformat() + "Z",
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "timezone": timezone or "UTC",
    })


def calculate(expression: str) -> str:
    """
    Safely evaluates arithmetic expressions.
    
    Only allows basic arithmetic operations for security.
    
    Args:
        expression: Mathematical expression to evaluate
        
    Returns:
        JSON string with calculation result
    """
    # Security: Only allow safe characters
    allowed_chars = set("0123456789+-*/(). ")
    if not all(c in allowed_chars for c in expression):
        return json.dumps({
            "error": "Invalid characters in expression",
            "expression": expression,
            "allowed": "Numbers and operators: + - * / ( ) **",
        })
    
    try:
        # Evaluate with restricted builtins for safety
        result = eval(expression, {"__builtins__": {}}, {})
        
        return json.dumps({
            "expression": expression,
            "result": result,
            "result_type": type(result).__name__,
        })
    except (SyntaxError, NameError, TypeError, ZeroDivisionError) as e:
        return json.dumps({
            "error": str(e),
            "expression": expression,
        })


def lookup_database(query: str, table: Optional[str] = None) -> str:
    """
    Mock database lookup function.
    
    This is a demo implementation that returns sample data.
    Replace with actual database queries for your use case.
    
    Args:
        query: Search query
        table: Optional table name
        
    Returns:
        JSON string with lookup results
    """
    # Demo: Mock database with sample records
    mock_data = {
        "users": {
            "john": {"id": 1, "name": "John Doe", "status": "active"},
            "jane": {"id": 2, "name": "Jane Smith", "status": "active"},
            "admin": {"id": 0, "name": "Administrator", "status": "system"},
        },
        "products": {
            "widget": {"id": 101, "name": "Widget Pro", "price": 99.99},
            "gadget": {"id": 102, "name": "Gadget Plus", "price": 149.99},
        },
    }
    
    query_lower = query.lower().strip()
    results = []
    
    # Search in specified table or all tables
    tables_to_search = [table] if table and table in mock_data else mock_data.keys()
    
    for tbl in tables_to_search:
        if tbl in mock_data:
            for key, record in mock_data[tbl].items():
                # Match by key or by name field
                if query_lower in key.lower() or query_lower in str(record.get("name", "")).lower():
                    results.append({"table": tbl, "record": record})
    
    if results:
        return json.dumps({
            "found": True,
            "query": query,
            "results": results,
            "count": len(results),
        })
    
    return json.dumps({
        "found": False,
        "query": query,
        "table": table,
        "message": f"No results found for '{query}'",
    })


# ============================================================================
# TOOL REGISTRY
# ============================================================================

TOOL_FUNCTIONS: dict[str, Callable] = {
    "get_current_time": get_current_time,
    "calculate": calculate,
    "lookup_database": lookup_database,
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
    
    logger.info(f"Executing tool '{name}' with args: {arguments}")
    result = func(**arguments)
    logger.debug(f"Tool '{name}' returned: {result[:200]}...")
    
    return result
