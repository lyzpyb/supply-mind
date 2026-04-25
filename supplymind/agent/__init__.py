"""
SupplyMind Agent Toolkit — expose SupplyMind skills as agent-ready tools.

Inspired by HuggingFace ml-intern's ToolSpec/ToolRouter pattern.
Each SupplyMind skill is registered as a ToolSpec with:
  - name: tool name for LLM function calling
  - description: natural language description (when/how to use)
  - parameters: JSON Schema (OpenAI function calling format)
  - handler: async callable(args) -> (str_output, bool_success)

Usage:
    from supplymind.agent import get_tool_router, create_supplymind_tools

    tools = create_supplymind_tools()
    router = get_tool_router(tools)
    output, ok = await router.call_tool("demand_forecast", {"horizon": 14})
"""

from supplymind.agent.tools import (
    ToolSpec,
    ToolRouter,
    create_supplymind_tools,
    get_tool_router,
)

__all__ = [
    "ToolSpec",
    "ToolRouter",
    "create_supplymind_tools",
    "get_tool_router",
]
