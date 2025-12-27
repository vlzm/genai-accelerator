"""
Tools module for LLM Function Calling.

Provides deterministic tools that the LLM can invoke to ground its decisions.
This prevents hallucinations by giving the model access to real data sources.

Available tools:
- check_sanctions_list: Verifies entities against global sanctions databases
- check_pep_status: Checks if person is a Politically Exposed Person
- validate_amount_threshold: Checks if amount exceeds reporting thresholds
"""

from app.services.tools.sanctions import (
    check_sanctions_list,
    check_pep_status,
)
from app.services.tools.thresholds import validate_amount_threshold
from app.services.tools.definitions import TOOL_DEFINITIONS, get_tool_by_name, execute_tool

__all__ = [
    "check_sanctions_list",
    "check_pep_status",
    "validate_amount_threshold",
    "TOOL_DEFINITIONS",
    "get_tool_by_name",
    "execute_tool",
]

