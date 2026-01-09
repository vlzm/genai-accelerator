"""
Tools module for LLM Function Calling (Agent Mode).

This module provides the infrastructure for tool-based analysis.
Tools allow the LLM to perform actions and retrieve data during analysis.

Available tools:
- get_current_time: Returns current date/time
- calculate: Performs arithmetic calculations
- lookup_database: Searches mock database (demo)

To add custom tools:
1. Edit definitions.py
2. Add tool definition (OpenAI format) to TOOL_DEFINITIONS
3. Implement the tool function
4. Register in TOOL_FUNCTIONS dict
5. Use analyze_with_tools() method
"""

from app.services.tools.definitions import (
    TOOL_DEFINITIONS,
    TOOL_FUNCTIONS,
    execute_tool,
    get_tool_by_name,
)

__all__ = [
    "TOOL_DEFINITIONS",
    "TOOL_FUNCTIONS", 
    "execute_tool",
    "get_tool_by_name",
]
