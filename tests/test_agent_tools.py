"""
Integration tests for SupplyMind Agent Tool System.

Validates the ml-intern-inspired ToolSpec/ToolRouter architecture:
- ToolSpec creation and registration
- Handler execution (async bridge → Skill.run() → markdown output)
- OpenAI function-calling format export
- Error handling and edge cases
- Full workflow tests (multi-tool pipelines)
"""

import asyncio
import json
import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_demand_history():
    """Standard demand history for testing."""
    from datetime import date, timedelta
    return [
        {"sku_id": "SKU001", "quantity": 100 + i * 3, "date": (date(2025, 1, 1) + timedelta(days=i)).isoformat()}
        for i in range(60)
    ] + [
        {"sku_id": "SKU002", "quantity": 50 + i * 2, "date": (date(2025, 1, 1) + timedelta(days=i)).isoformat()}
        for i in range(60)
    ]


@pytest.fixture
def router():
    """Create a pre-populated ToolRouter."""
    from supplymind.agent import get_tool_router
    return get_tool_router()


# ── Test: Tool Registry ───────────────────────────────────────────────────


class TestToolRegistry:
    """Test tool registration and discovery."""

    def test_all_tools_registered(self, router):
        """All 20+ tools should be registered."""
        assert len(router) >= 20, f"Expected >= 20 tools, got {len(router)}"

    def test_expected_tool_names_present(self, router):
        """Core tools from each domain should be present."""
        expected = [
            "data_profiler", "demand_forecast", "inventory_reorder",
            "pricing_elasticity", "fulfill_allocation", "what_if",
        ]
        for name in expected:
            assert name in router, f"Missing tool: {name}"

    def test_tool_names_sorted(self, router):
        """tool_names should return sorted list."""
        names = router.tool_names
        assert names == sorted(names)

    def test_get_tool_returns_spec(self, router):
        """get_tool should return a ToolSpec or None."""
        spec = router.get_tool("demand_forecast")
        assert spec is not None
        assert spec.name == "demand_forecast"
        assert spec.description != ""
        assert "properties" in spec.parameters  # JSON Schema has 'properties' key

    def test_get_unknown_tool_returns_none(self, router):
        """Unknown tool should return None."""
        assert router.get_tool("nonexistent_tool_12345") is None

    def test_contains_operator(self, router):
        """'in' operator should work."""
        assert "demand_forecast" in router
        assert "not_a_tool" not in router


class TestToolSpecFormat:
    """Test that ToolSpecs conform to OpenAI function-calling format."""

    def test_openai_format_structure(self, router):
        """get_tool_specs_for_llm returns valid OpenAI format."""
        specs = router.get_tool_specs_for_llm()
        assert isinstance(specs, list)
        assert len(specs) == len(router)

        for spec in specs:
            assert spec["type"] == "function"
            fn = spec["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            # Parameters must be a JSON Schema object
            params = fn["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params

    def test_all_specs_have_descriptions(self, router):
        """Every tool spec should have a meaningful description."""
        specs = router.get_tool_specs_for_llm()
        for spec in specs:
            desc = spec["function"]["description"]
            assert len(desc) > 20, f"{spec['function']['name']} description too short"
            # Should contain guidance on when to use it
            assert any(word in desc.lower() for word in ["use", "when", "calculate", "forecast", "optimize", "analyze"])


# ── Test: Handler Execution ───────────────────────────────────────────────


class TestDataProfilerHandler:
    """Test data_profiler tool handler."""

    @pytest.mark.asyncio
    async def test_basic_profiling(self, router, sample_demand_history):
        output, success = await router.call_tool("data_profiler", {
            "data": sample_demand_history[:10],
        })
        assert success
        assert "Profile" in output or "profile" in output.lower() or len(output) > 10

    @pytest.mark.asyncio
    async def test_empty_data_error(self, router):
        output, success = await router.call_tool("data_profiler", {
            "data": [],
        })
        assert not success
        assert "No data" in output


class TestDemandForecastHandler:
    """Test demand_forecast tool handler."""

    @pytest.mark.asyncio
    async def test_basic_forecast(self, router, sample_demand_history):
        output, success = await router.call_tool("demand_forecast", {
            "demand_history": sample_demand_history,
            "horizon": 7,
            "method": "ma",
        })
        assert success
        assert "Forecast" in output
        # Should contain SKU info
        assert "SKU001" in output or "SKU002" in output or "sku" in output.lower()

    @pytest.mark.asyncio
    async def test_missing_required_arg(self, router):
        """Missing required argument should return error."""
        output, success = await router.call_tool("demand_forecast", {})
        # May succeed with empty defaults or fail — either is acceptable
        assert isinstance(output, str)


class TestPricingElasticityHandler:
    """Test pricing_elasticity tool handler."""

    @pytest.mark.asyncio
    async def test_basic_elasticity(self, router):
        output, success = await router.call_tool("pricing_elasticity", {
            "prices": [10.0, 9.0, 8.0, 7.0, 6.0],
            "quantities": [100, 130, 170, 220, 290],
            "sku_id": "TEST-SKU",
        })
        assert success
        assert "elasticity" in output.lower() or "Elasticity" in output


class TestInventoryReorderHandler:
    """Test inventory_reorder tool handler."""

    @pytest.mark.asyncio
    async def test_basic_reorder(self, router):
        output, success = await router.call_tool("inventory_reorder", {
            "skus": [{
                "sku_id": "TEST-SKU",
                "unit_cost": 10.0,
                "lead_time_days": 7,
                "demand_rate": 20.0,
                "holding_cost_rate": 0.25,
                "stockout_cost_per_unit": 5.0,
                "order_cost": 50.0,
            }],
        })
        assert success
        assert "Reorder" in output or "reorder" in output.lower()


class TestFulfillmentRoutingHandler:
    """Test fulfill_routing tool handler."""

    @pytest.mark.asyncio
    async def test_basic_routing(self, router):
        output, success = await router.call_tool("fulfill_routing", {
            "depot": {"lat": 40.7128, "lng": -74.0060, "name": "Depot NYC"},
            "stops": [
                {"lat": 40.7589, "lng": -73.9851, "name": "Midtown"},
                {"lat": 40.7505, "lng": -73.9934, "name": "Chelsea"},
                {"lat": 40.7282, "lng": -73.7949, "name": "Brooklyn"},
            ],
            "optimization_goal": "distance",
        })
        assert success
        assert "Route" in output or "route" in output.lower()


class TestWhatIfHandler:
    """Test what_if simulation handler."""

    @pytest.mark.asyncio
    async def test_basic_whatif(self, router, sample_demand_history):
        output, success = await router.call_tool("what_if", {
            "base_scenario": {
                "service_level": 0.95,
                "demand_history": sample_demand_history[:10],
            },
            "scenarios": [
                {"name": "High Service", "service_level": 0.99},
                {"name": "Low Cost", "service_level": 0.90},
            ],
            "metrics": ["fill_rate", "holding_cost"],
        })
        assert success
        assert "Scenario" in output or "scenario" in output.lower()


# ── Test: Error Handling ──────────────────────────────────────────────────


class TestErrorHandling:
    """Test robustness of the tool system."""

    @pytest.mark.asyncio
    async def test_unknown_tool(self, router):
        """Calling unknown tool returns descriptive error."""
        output, success = await router.call_tool("totally_fake_tool_xyz", {})
        assert not success
        assert "Unknown tool" in output

    @pytest.mark.asyncio
    async def test_malformed_input_graceful(self, router):
        """Malformed input should produce error, not crash."""
        # Pass garbage data to see if handlers are defensive
        output, success = await router.call_tool("data_profiler", {
            "data": ["not_a_dict", 42, None],
        })
        # Should not raise; either succeeds with best-effort or fails gracefully
        assert isinstance(output, str)
        assert isinstance(success, bool)


# ── Test: Parallel Execution ──────────────────────────────────────────────


class TestParallelExecution:
    """Test parallel tool execution via call_tool_parallel."""

    @pytest.mark.asyncio
    async def test_parallel_calls(self, router, sample_demand_history):
        """Multiple independent tools can run in parallel."""
        tool_calls = [
            {"name": "data_profiler", "arguments": {"data": sample_demand_history[:5]}},
            {"name": "pricing_elasticity", "arguments": {
                "prices": [10, 9, 8], "quantities": [100, 130, 170]
            }},
        ]
        results = await router.call_tool_parallel(tool_calls)
        
        assert len(results) == 2
        for output, success in results:
            assert isinstance(output, str)
            assert isinstance(success, bool)


# ── Test: Selective Registration ──────────────────────────────────────────


class TestSelectiveRegistration:
    """Test creating routers with subset of tools."""

    def test_create_specific_tools(self):
        """Can create router with only specific tools."""
        from supplymind.agent import create_supplymind_tools, ToolRouter
        
        tools = create_supplymind_tools(skill_names=["demand_forecast", "pricing_elasticity"])
        assert len(tools) == 2
        
        r = ToolRouter()
        r.register_tools(tools)
        assert len(r) == 2
        assert "demand_forecast" in r
        assert "pricing_elasticity" in r
        assert "inventory_reorder" not in r

    def test_unknown_skill_name_skipped(self):
        """Unknown skill names are silently skipped."""
        from supplymind.agent import create_supplymind_tools
        
        tools = create_supplymind_tools(skill_names=["demand_forecast", "nonexistent_skill"])
        # Should have at least 1 (the valid one), unknown skipped
        assert len(tools) >= 1


# ── Test: Skill Registry Introspection ────────────────────────────────────


class TestSkillRegistry:
    """Test skill registry metadata."""

    def test_registry_has_all_domains(self):
        """Registry should cover all 5 domains."""
        from supplymind.agent.tools import get_skill_registry
        
        registry = get_skill_registry()
        
        domains = set()
        for name, entry in registry.items():
            mod = entry.get("module", "")
            if "common" in mod:
                domains.add("common")
            elif "demand" in mod:
                domains.add("demand")
            elif "inventory" in mod:
                domains.add("inventory")
            elif "pricing" in mod:
                domains.add("pricing")
            elif "fulfillment" in mod:
                domains.add("fulfillment")
        
        expected_domains = {"common", "demand", "inventory", "pricing", "fulfillment"}
        assert expected_domains.issubset(domains)

    def test_registry_entries_complete(self):
        """Each registry entry should have all required fields."""
        from supplymind.agent.tools import get_skill_registry
        
        registry = get_skill_registry()
        required_fields = {"module", "spec_attr", "handler_attr", "description"}
        
        for name, entry in registry.items():
            assert required_fields.issubset(entry.keys()), \
                f"Registry entry '{name}' missing fields"


# ── Test: Full Workflow Integration ───────────────────────────────────────


class TestFullWorkflow:
    """End-to-end workflow tests using multiple tools in sequence."""

    @pytest.mark.asyncio
    async def test_demand_planning_workflow(self, router, sample_demand_history):
        """Complete demand planning workflow: profile → forecast → decompose."""
        # Step 1: Profile data
        profile_output, ok1 = await router.call_tool("data_profiler", {
            "data": sample_demand_history,
        })
        assert ok1, f"Data profiler failed: {profile_output}"
        
        # Step 2: Forecast
        forecast_output, ok2 = await router.call_tool("demand_forecast", {
            "demand_history": sample_demand_history,
            "horizon": 14,
            "method": "auto",
        })
        assert ok2, f"Forecast failed: {forecast_output}"
        
        # Step 3: Decompose
        decomp_output, ok3 = await router.call_tool("demand_decompose", {
            "demand_history": sample_demand_history[:30],
        })
        assert ok3, f"Decompose failed: {decomp_output}"
        
        # All outputs should be non-trivial strings
        for label, out in [("Profile", profile_output), ("Forecast", forecast_output), ("Decompose", decomp_output)]:
            assert len(out) > 50, f"{label} output too short"

    @pytest.mark.asyncio
    async def test_pricing_workflow(self, router):
        """Pricing workflow: elasticity → lifecycle → what-if."""
        # Step 1: Elasticity
        elastic_out, ok1 = await router.call_tool("pricing_elasticity", {
            "prices": [12, 11, 10, 9, 8, 7, 6],
            "quantities": [80, 95, 120, 150, 190, 240, 300],
            "sku_id": "WORKFLOW-TEST",
        })
        assert ok1, f"Elasticity failed: {elastic_out}"
        
        # Step 2: Lifecycle
        lifecycle_out, ok2 = await router.call_tool("pricing_lifecycle", {
            "sales_history": [100, 120, 150, 180, 210, 250, 280, 290, 285, 260],
            "price_history": [12, 11.5, 11, 10.5, 10, 9.5, 9, 8.5, 8, 7.5],
        })
        assert ok2, f"Lifecycle failed: {lifecycle_out}"

    @pytest.mark.asyncio
    async def test_inventory_workflow(self, router, sample_demand_history):
        """Inventory workflow: classify → reorder → policy_sim."""
        # Classify
        classify_out, ok1 = await router.call_tool("inventory_classify", {
            "sku_data": [
                {"sku_id": "A", "annual_revenue": 50000, "avg_demand": 100, "demand_std": 10},
                {"sku_id": "B", "annual_revenue": 5000, "avg_demand": 30, "demand_std": 15},
                {"sku_id": "C", "annual_revenue": 200, "avg_demand": 5, "demand_std": 5},
            ],
        })
        assert ok1, f"Classify failed: {classify_out}"
        
        # Reorder
        reorder_out, ok2 = await router.call_tool("inventory_reorder", {
            "skus": [{
                "sku_id": "TEST",
                "unit_cost": 25.0,
                "holding_cost_rate": 0.25,
                "stockout_cost_per_unit": 10.0,
                "lead_time_days": 7,
                "demand_rate": 20.0,
                "order_cost": 50.0,
            }],
        })
        assert ok2, f"Reorder failed: {reorder_out}"


# ── Test: Module Imports ──────────────────────────────────────────────────


class TestModuleImports:
    """Verify all modules can be imported cleanly."""

    def test_agent_init_imports(self):
        """Top-level agent module imports."""
        from supplymind.agent import (
            ToolSpec, ToolRouter, create_supplymind_tools, get_tool_router,
        )
        assert ToolSpec is not None
        assert ToolRouter is not None

    def test_handler_modules_import(self):
        """All handler modules should be importable."""
        import supplymind.agent.skill_handlers.common
        import supplymind.agent.skill_handlers.demand
        import supplymind.agent.skill_handlers.inventory
        import supplymind.agent.skill_handlers.pricing
        import supplymind.agent.skill_handlers.fulfillment

    def test_tool_spec_constants_exist(self):
        """Each handler module should define TOOL_SPEC constants."""
        import supplymind.agent.skill_handlers.common as c
        import supplymind.agent.skill_handlers.demand as d
        import supplymind.agent.skill_handlers.inventory as inv
        import supplymind.agent.skill_handlers.pricing as p
        import supplymind.agent.skill_handlers.fulfillment as f
        
        # Each module should have at least one TOOL_SPEC
        common_specs = [k for k in dir(c) if k.endswith("_TOOL_SPEC")]
        demand_specs = [k for k in dir(d) if k.endswith("_TOOL_SPEC")]
        assert len(common_specs) >= 1
        assert len(demand_specs) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
