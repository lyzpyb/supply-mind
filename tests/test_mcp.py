"""Tests for MCP server — tool listing, calling, and error handling."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock


class TestMCPLegacyServer:
    """Test the legacy MCPServer wrapper (works without mcp SDK)."""

    def test_list_tools(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        tools = server.list_tools()
        assert len(tools) >= 20
        names = {t["name"] for t in tools}
        assert "demand_forecast" in names
        assert "inventory_reorder" in names
        assert "data_profiler" in names

    def test_list_tools_have_descriptions(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        tools = server.list_tools()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert len(tool["description"]) > 10

    def test_call_unknown_tool(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        result = server.call_tool("nonexistent_tool", {})
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    def test_handle_tools_list_request(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        response = server.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        })
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) >= 20

    def test_handle_unknown_method(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        response = server.handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "unknown/method",
        })
        assert "error" in response
        assert response["error"]["code"] == -32601

    def test_call_data_profiler(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        result = server.call_tool("data_profiler", {
            "data": [
                {"sku_id": "A", "quantity": 100, "date": "2024-01-01"},
                {"sku_id": "A", "quantity": 120, "date": "2024-01-02"},
                {"sku_id": "B", "quantity": 50, "date": "2024-01-01"},
            ],
            "profile_type": "quick",
        })
        assert result["success"] is True
        assert "result" in result

    def test_handle_tools_call_request(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        response = server.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "data_profiler",
                "arguments": {
                    "data": [{"sku_id": "X", "quantity": 10}],
                    "profile_type": "schema_only",
                },
            },
        })
        assert response["id"] == 3
        assert response["result"]["success"] is True


class TestMCPToolRegistration:
    """Test that all 23 tools are properly registered."""

    EXPECTED_TOOLS = {
        "data_profiler", "report_generator", "what_if",
        "demand_forecast", "demand_decompose", "demand_anomaly",
        "demand_newproduct", "demand_intermittent", "demand_reconcile",
        "inventory_reorder", "inventory_safety_stock", "inventory_policy_sim",
        "inventory_classify", "inventory_multi_echelon", "inventory_newsvendor",
        "pricing_elasticity", "pricing_markdown", "pricing_lifecycle", "pricing_bundling",
        "fulfill_allocation", "fulfill_routing", "fulfill_wave", "fulfill_capacity",
    }

    def test_all_23_tools_in_legacy_server(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        names = {t["name"] for t in server.list_tools()}
        missing = self.EXPECTED_TOOLS - names
        assert not missing, f"Missing tools: {missing}"
        assert len(names) == 23

    def test_each_tool_has_parameters(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        for tool in server.list_tools():
            assert "input_schema" in tool or "parameters" in tool, (
                f"Tool {tool['name']} missing parameters/input_schema"
            )


class TestMCPServerFactory:
    """Test server creation and singleton behavior."""

    def test_get_mcp_server_without_sdk_raises(self):
        with patch("supplymind.mcp.server._MCP_AVAILABLE", False):
            from supplymind.mcp.server import _create_mcp_server
            with pytest.raises(ImportError, match="MCP SDK not installed"):
                _create_mcp_server()

    def test_call_skill_handler_unknown_skill(self):
        import asyncio
        from supplymind.mcp.server import _call_skill_handler
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                _call_skill_handler("nonexistent_skill_xyz", {})
            )
        finally:
            loop.close()
        assert "not found" in result.lower() or "error" in result.lower()


class TestStructuredOutput:
    """Test structured JSON extraction from tool output."""

    def test_extract_json_from_code_block(self):
        from supplymind.agent.tools import _extract_json_from_markdown

        md = '# Report\n\nSome text\n\n```json\n{"key": "value", "num": 42}\n```\n'
        result = _extract_json_from_markdown(md)
        assert result is not None
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_extract_json_from_html_comment(self):
        from supplymind.agent.tools import _extract_json_from_markdown

        md = '# Report\n\nSome text\n\n<!-- JSON: {"status": "ok", "count": 5} -->'
        result = _extract_json_from_markdown(md)
        assert result is not None
        assert result["status"] == "ok"

    def test_html_comment_takes_priority(self):
        from supplymind.agent.tools import _extract_json_from_markdown

        md = (
            '```json\n{"source": "code_block"}\n```\n'
            '<!-- JSON: {"source": "comment"} -->'
        )
        result = _extract_json_from_markdown(md)
        assert result["source"] == "comment"

    def test_no_json_returns_none(self):
        from supplymind.agent.tools import _extract_json_from_markdown

        md = "# Just markdown\n\nNo JSON here."
        result = _extract_json_from_markdown(md)
        assert result is None

    def test_tool_router_json_format(self):
        import asyncio
        from supplymind.agent.tools import ToolRouter, ToolSpec

        async def mock_handler(args):
            return '# Result\n```json\n{"answer": 42}\n```', True

        router = ToolRouter()
        router.register_tool(ToolSpec(
            name="test_tool",
            description="test",
            parameters={},
            handler=mock_handler,
        ))

        loop = asyncio.new_event_loop()
        try:
            result, success = loop.run_until_complete(
                router.call_tool("test_tool", {}, format="json")
            )
        finally:
            loop.close()

        assert success is True
        assert isinstance(result, dict)
        assert result["structured"]["answer"] == 42
        assert "# Result" in result["markdown"]

    def test_tool_router_markdown_format_unchanged(self):
        import asyncio
        from supplymind.agent.tools import ToolRouter, ToolSpec

        async def mock_handler(args):
            return "plain output", True

        router = ToolRouter()
        router.register_tool(ToolSpec(
            name="test_tool",
            description="test",
            parameters={},
            handler=mock_handler,
        ))

        loop = asyncio.new_event_loop()
        try:
            result, success = loop.run_until_complete(
                router.call_tool("test_tool", {}, format="markdown")
            )
        finally:
            loop.close()

        assert success is True
        assert isinstance(result, str)
        assert result == "plain output"

    def test_tool_router_both_format(self):
        import asyncio
        from supplymind.agent.tools import ToolRouter, ToolSpec

        async def mock_handler(args):
            return '# Title\n```json\n{"x": 1}\n```', True

        router = ToolRouter()
        router.register_tool(ToolSpec(
            name="test_tool",
            description="test",
            parameters={},
            handler=mock_handler,
        ))

        loop = asyncio.new_event_loop()
        try:
            result, success = loop.run_until_complete(
                router.call_tool("test_tool", {}, format="both")
            )
        finally:
            loop.close()

        assert success is True
        assert "markdown" in result
        assert "structured" in result
        assert result["structured"]["x"] == 1
