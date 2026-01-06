"""
Tools module for LLM Function Calling (Agent Mode).

This module provides the infrastructure for tool-based analysis.
By default, no tools are enabled (TOOL_DEFINITIONS is empty).

To enable tools for your use case:
1. Edit definitions.py
2. Uncomment/create your tool definitions
3. Set TOOL_DEFINITIONS to your tool list
4. Use analyze_with_tools() instead of analyze()

Example use cases:
- Database lookups for entity verification
- API calls to external services
- Validation against reference data
- Calculations or transformations
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
