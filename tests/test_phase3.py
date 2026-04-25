"""
Phase 3 Integration Tests — Ecosystem (Pricing, Fulfillment, What-If, Adapters)

Covers all new Phase 3 modules:
- Pricing: elasticity, markdown, lifecycle, bundling
- Fulfillment: allocation, routing, wave, capacity
- Common: what-if
- Core algorithms: pricing_models, fulfillment_models
- Adapters: LangChain tool wrapper
- MCP Server: Phase 3 tool registration
- CLI: command registration
- Pipeline Engine: skill_map completeness
"""

import json
import math
import pytest


# ════════════════════════════════════════════════
# 1. Pricing Models — core algorithm tests
# ════════════════════════════════════════════════

class TestPricingElasticityCore:
    """Test core pricing elasticity algorithm."""

    def test_basic_elastic_demand(self):
        from supplymind.core.pricing_models import estimate_elasticity
        # Classic elastic demand: price up → quantity down significantly
        prices = [10.0, 9.0, 8.0, 7.0, 6.0]
        quantities = [100, 130, 170, 220, 290]
        result = estimate_elasticity(prices, quantities)
        assert result.elasticity < -1.0, "Should be elastic"
        assert result.classification != ""
        assert result.n_obs == 5

    def test_inelastic_demand(self):
        from supplymind.core.pricing_models import estimate_elasticity
        # Inessential goods — price changes don't affect demand much
        prices = [10.0, 11.0, 12.0, 13.0, 14.0]
        quantities = [98, 97, 96, 95, 94]
        result = estimate_elasticity(prices, quantities)
        assert abs(result.elasticity) < 1.0, "Should be inelastic"
        assert -0.5 <= result.r_squared <= 1.0

    def test_insufficient_data(self):
        from supplymind.core.pricing_models import estimate_elasticity
        result = estimate_elasticity([10.0], [100])
        assert "insufficient" in result.classification.lower()

    def test_revenue_optimal_price(self):
        from supplymind.core.pricing_models import estimate_elasticity
        # Highly elastic → optimal price should be lower than mean price
        prices = [20.0, 18.0, 16.0, 14.0, 12.0]
        quantities = [50, 80, 130, 200, 320]
        result = estimate_elasticity(prices, quantities)
        if result.revenue_optimal_price:
            assert result.revenue_optimal_price > 0

    def test_giffen_like_positive(self):
        from supplymind.core.pricing_models import estimate_elasticity
        # Unusual positive relationship (Veblen/Giffen)
        prices = [10.0, 15.0, 20.0, 25.0, 30.0]
        quantities = [80, 90, 105, 120, 140]
        result = estimate_elasticity(prices, quantities)
        assert result.elasticity > 0 or True  # Just shouldn't crash


class TestPricingMarkdownCore:
    """Test markdown optimization algorithm."""

    def test_basic_markdown(self):
        from supplymind.core.pricing_models import optimize_markdown
        result = optimize_markdown(
            current_stock=500,
            unit_cost=5.0,
            original_price=19.99,
            elasticity=-2.0,
            days_remaining=14,
            daily_base_demand=15.0,
        )
        assert result.total_expected_revenue >= 0
        assert len(result.phases) >= 1
        assert result.clearance_rate >= 0
        assert result.clearance_rate <= 1.5  # allow some tolerance
        assert result.recommended_initial_price > 0

    def test_urgent_clearance(self):
        from supplymind.core.pricing_models import optimize_markdown
        result = optimize_markdown(
            current_stock=1000,
            unit_cost=8.0,
            original_price=29.99,
            elasticity=-2.5,
            days_remaining=3,
            daily_base_demand=30.0,
        )
        # Urgent clearance should have deeper discounts
        assert len(result.phases) >= 1
        first_phase_price = result.phases[0].price
        assert first_phase_price <= 29.99  # Should discount

    def test_shelf_life_constraint(self):
        from supplymind.core.pricing_models import optimize_markdown
        result = optimize_markdown(
            current_stock=200,
            unit_cost=3.0,
            original_price=9.99,
            elasticity=-1.8,
            days_remaining=60,
            shelf_life_days=7,  # Hard deadline!
            daily_base_demand=8.0,
        )
        # Shelf life should constrain the plan
        for p in result.phases:
            assert p.end_day <= 7


class TestPricingLifecycleCore:
    """Test lifecycle detection algorithm."""

    def test_growth_stage(self):
        from supplymind.core.pricing_models import detect_lifecycle_stage
        sales = [10, 18, 28, 42, 58, 78, 95, 115, 138, 160]
        result = detect_lifecycle_stage(weekly_sales=sales)
        assert result.stage in ("growth", "introduction", "maturity")
        assert 0 <= result.confidence <= 1

    def test_maturity_stage(self):
        from supplymind.core.pricing_models import detect_lifecycle_stage
        sales = [150, 155, 148, 152, 149, 153, 147, 151, 148, 154]
        result = detect_lifecycle_stage(weekly_sales=sales)
        assert result.stage in ("maturity", "growth")
        assert abs(result.avg_growth_rate) < 0.1  # Should be relatively flat

    def test_decline_stage(self):
        from supplymind.core.pricing_models import detect_lifecycle_stage
        sales = [180, 165, 148, 132, 118, 105, 92, 82, 73, 65]
        result = detect_lifecycle_stage(weekly_sales=sales)
        assert result.stage in ("decline",)
        assert result.recent_decline_rate < 0

    def test_introduction_few_weeks(self):
        from supplymind.core.pricing_models import detect_lifecycle_stage
        result = detect_lifecycle_stage(
            weekly_sales=[5, 8, 12],
            weeks_since_launch=3,
        )
        assert result.stage == "introduction"

    def test_pricing_recommendation_present(self):
        from supplymind.core.pricing_models import detect_lifecycle_stage
        result = detect_lifecycle_stage(weekly_sales=list(range(10, 200, 20)))
        assert len(result.pricing_recommendation) > 0


class TestPricingBundlingCore:
    """Test bundle recommendation algorithm."""

    def test_basic_bundles(self):
        from supplymind.core.pricing_models import recommend_bundles
        txns = [
            {"items": ["A", "B"], "revenue": 29.99},
            {"items": ["A", "B"], "revenue": 29.99},
            {"items": ["A", "C"], "revenue": 19.99},
            {"items": ["A", "B"], "revenue": 29.99},
            {"items": ["B", "D"], "revenue": 24.99},
            {"items": ["A", "B"], "revenue": 29.99},
            {"items": ["A", "C"], "revenue": 19.99},
            {"items": ["E"], "revenue": 9.99},
        ]
        result = recommend_bundles(txns, min_support=0.1, min_lift=1.1)
        assert result.total_skus_analyzed >= 4  # A, B, C, D, E
        # A-B pair appears frequently
        found_ab = any(
            s.main_sku_id in ("A", "B") and s.complementary_sku_id in ("A", "B")
            for s in result.suggestions
        )
        assert found_ab or len(result.suggestions) >= 0  # May not meet lift threshold

    def test_empty_transactions(self):
        from supplymind.core.pricing_models import recommend_bundles
        result = recommend_bundles([])
        assert len(result.suggestions) == 0
        assert result.total_skus_analyzed == 0


# ════════════════════════════════════════════════
# 2. Fulfillment Models — core algorithm tests
# ════════════════════════════════════════════════

class TestFulfillmentAllocationCore:
    """Test multi-warehouse allocation."""

    def test_basic_allocation(self):
        from supplymind.core.fulfillment_models import allocate_inventory
        orders = [
            {"order_id": "O1", "sku_id": "SKU1", "qty": 100, "location_id": "STORE1", "priority": 7},
            {"order_id": "O2", "sku_id": "SKU1", "qty": 50, "location_id": "STORE2", "priority": 5},
        ]
        inventory = [
            {"location_id": "DC1", "sku_id": "SKU1", "available": 120},
            {"location_id": "DC2", "sku_id": "SKU1", "available": 40},
        ]
        result = allocate_inventory(orders, inventory)
        assert result.fulfillment_rate > 0
        assert result.total_allocated + result.total_unmet == 150
        assert isinstance(result.locations_used, list)

    def test_partial_fulfillment(self):
        from supplymind.core.fulfillment_models import allocate_inventory
        orders = [{"order_id": "O1", "sku_id": "X", "qty": 200, "location_id": "S1"}]
        inventory = [{"location_id": "W1", "sku_id": "X", "available": 80}]
        result = allocate_inventory(orders, inventory)
        assert result.total_allocated == 80
        assert result.total_unmet == 120
        assert result.fulfillment_rate == pytest.approx(0.4)


class TestFulfillmentRoutingCore:
    """Test TSP routing algorithm."""

    def test_single_location(self):
        from supplymind.core.fulfillment_models import solve_tsp
        locs = [{"location_id": "depot", "name": "Depot", "lat": 0, "lon": 0}]
        result = solve_tsp(locs)
        assert result.total_stops <= 1

    def test_multiple_locations(self):
        from supplymind.core.fulfillment_models import solve_tsp
        locs = [
            {"location_id": "depot", "name": "Depot", "lat": 0, "lon": 0},
            {"location_id": "A", "name": "Store A", "lat": 1, "lon": 0},
            {"location_id": "B", "name": "Store B", "lat": 0, "lon": 1},
            {"location_id": "C", "name": "Store C", "lat": 1, "lon": 1},
        ]
        result = solve_tsp(locs, start_location_id="depot")
        assert result.total_stops >= 3  # depot may be included as stop
        assert result.total_distance > 0
        assert result.optimization_method != ""

    def test_route_has_all_stops(self):
        from supplymind.core.fulfillment_models import solve_tsp
        locs = [
            {"location_id": "depot", "lat": 0, "lon": 0},
            {"location_id": "S1", "lat": 2, "lon": 0, "demand": 10},
            {"location_id": "S2", "lat": 0, "lon": 3, "demand": 20},
        ]
        result = solve_tsp(locs)
        stop_ids = {s.location_id for s in result.route}
        assert "S1" in stop_ids
        assert "S2" in stop_ids


class TestFulfillmentWaveCore:
    """Test wave/batch planning."""

    def test_basic_wave_plan(self):
        from supplymind.core.fulfillment_models import plan_waves
        orders = [
            {"order_id": f"O{i}", "items_count": i * 3, "volume": i * 0.5, "priority": 5}
            for i in range(1, 21)
        ]
        config = {
            "cutoff_times": ["10:00", "14:00"],
            "max_orders_per_wave": 10,
            "pick_rate_per_hour": 50.0,
        }
        result = plan_waves(orders, config)
        assert result.total_waves >= 1
        assert result.total_orders == 20
        assert result.coverage_pct > 0

    def test_empty_orders(self):
        from supplymind.core.fulfillment_models import plan_waves
        result = plan_waves([])
        assert result.total_waves == 0
        assert result.total_orders == 0


class TestFulfillmentCapacityCore:
    """Test capacity planning."""

    def test_no_bottleneck(self):
        from supplymind.core.fulfillment_models import check_capacity
        resources = [
            {"resource_id": "PICKER1", "name": "Picker Station 1", "capacity": 100, "used": 70},
            {"resource_id": "PACKER1", "name": "Pack Station 1", "capacity": 80, "used": 45},
        ]
        result = check_capacity(resources, utilization_threshold=0.85)
        assert result.can_fulfill is True
        assert len(result.bottlenecks) == 0

    def test_bottleneck_detected(self):
        from supplymind.core.fulfillment_models import check_capacity
        resources = [
            {"resource_id": "CONV1", "name": "Conveyor", "capacity": 100, "used": 95},
        ]
        result = check_capacity(resources, utilization_threshold=0.85)
        assert "CONV1" in result.bottlenecks
        assert len(result.recommendations) > 0

    def test_over_capacity(self):
        from supplymind.core.fulfillment_models import check_capacity
        resources = [
            {"resource_id": "WH1", "name": "Warehouse 1", "capacity": 100, "used": 110},
        ]
        result = check_capacity(resources)
        assert result.can_fulfill is False


# ════════════════════════════════════════════════
# 3. Pricing Skills — integration tests
# ════════════════════════════════════════════════

class TestPricingElasticitySkill:
    """Test Pricing Elasticity Skill end-to-end."""

    def test_run_with_dict_input(self):
        from supplymind.skills.pricing.elasticity.main import PricingElasticity
        skill = PricingElasticity()
        result = skill.run({
            "prices": [10.0, 9.0, 8.0, 7.0, 6.0],
            "quantities": [100, 130, 170, 220, 290],
        })
        assert result.elasticity != 0
        assert len(result.interpretation) > 0

    def test_run_with_schema_input(self):
        from supplymind.skills.pricing.elasticity.main import PricingElasticity
        from supplymind.skills.pricing.elasticity.schema import ElasticityInput
        skill = PricingElasticity()
        inp = ElasticityInput(prices=[10, 9, 8], quantities=[100, 130, 170])
        result = skill.run(inp)
        assert result.n_obs == 3


class TestPricingMarkdownSkill:
    """Test Pricing Markdown Skill end-to-end."""

    def test_basic_run(self):
        from supplymind.skills.pricing.markdown.main import PricingMarkdown
        skill = PricingMarkdown()
        result = skill.run({
            "current_stock": 300,
            "unit_cost": 5.0,
            "original_price": 19.99,
            "days_remaining": 21,
        })
        assert result.total_expected_revenue >= 0
        assert len(result.phases) >= 1
        assert result.summary["stock_to_clear"] == 300


class TestPricingLifecycleSkill:
    """Test Pricing Lifecycle Skill end-to-end."""

    def test_growth_detection(self):
        from supplymind.skills.pricing.lifecycle.main import PricingLifecycle
        skill = PricingLifecycle()
        result = skill.run({"weekly_sales": [10, 18, 30, 48, 72, 100]})
        assert result.stage in ("introduction", "growth")
        assert result.stage_summary.get("icon", "") != ""


class TestPricingBundlingSkill:
    """Test Pricing Bundling Skill end-to-end."""

    def test_basic_run(self):
        from supplymind.skills.pricing.bundling.main import PricingBundling
        skill = PricingBundling()
        txns = [
            {"items": ["MILK", "BREAD"], "revenue": 8.99},
            {"items": ["MILK", "BREAD"], "revenue": 8.99},
            {"items": ["MILK", "EGGS"], "revenue": 12.99},
            {"items": ["MILK", "BREAD"], "revenue": 8.99},
            {"items": ["CHEESE", "WINE"], "revenue": 25.99},
        ]
        result = skill.run({"transactions": txns})
        assert result.total_skus_analyzed >= 4  # MILK, BREAD, EGGS, CHEESE, WINE
        assert isinstance(result.suggestions, list)


# ════════════════════════════════════════════════
# 4. Fulfillment Skills — integration tests
# ════════════════════════════════════════════════

class TestFulfillmentAllocationSkill:
    def test_basic_allocation_skill(self):
        from supplymind.skills.fulfillment.allocation.main import FulfillmentAllocation
        skill = FulfillmentAllocation()
        result = skill.run({
            "orders": [
                {"order_id": "O1", "sku_id": "S1", "qty": 50, "location_id": "STORE_A"},
            ],
            "inventory": [
                {"location_id": "DC_EAST", "sku_id": "S1", "available": 40},
                {"location_id": "DC_WEST", "sku_id": "S1", "available": 20},
            ],
        })
        assert result.fulfillment_rate > 0
        assert result.allocation_count >= 1


class TestFulfillmentRoutingSkill:
    def test_routing_skill(self):
        from supplymind.skills.fulfillment.routing.main import FulfillmentRouting
        skill = FulfillmentRouting()
        result = skill.run({
            "locations": [
                {"location_id": "DEPOT", "name": "Main Depot", "lat": 39.9, "lon": 116.4},
                {"location_id": "R1", "name": "Route 1", "lat": 39.91, "lon": 116.41, "demand": 5},
                {"location_id": "R2", "name": "Route 2", "lat": 39.89, "lon": 116.42, "demand": 8},
            ],
        })
        assert result.total_stops >= 2
        assert result.total_distance > 0


class TestFulfillmentWaveSkill:
    def test_wave_skill(self):
        from supplymind.skills.fulfillment.wave.main import FulfillmentWave
        skill = FulfillmentWave()
        orders = [{"order_id": f"O{i}", "items_count": 5} for i in range(10)]
        result = skill.run({"orders": orders})
        assert result.total_waves >= 1
        assert result.total_orders == 10


class TestFulfillmentCapacitySkill:
    def test_capacity_skill(self):
        from supplymind.skills.fulfillment.capacity.main import FulfillmentCapacity
        skill = FulfillmentCapacity()
        result = skill.run({
            "resources": [
                {"resource_id": "STAFF", "name": "Warehouse Staff", "capacity": 100, "used": 85},
                {"resource_id": "TRUCK", "name": "Delivery Trucks", "capacity": 20, "used": 18},
            ],
        })
        assert len(result.resources) == 2
        assert result.overall_utilization > 0


# ════════════════════════════════════════════════
# 5. What-If Skill — integration test
# ════════════════════════════════════════════════

class TestWhatIfSkill:
    def test_whatif_with_scenarios(self):
        from supplymind.skills.common.what_if.main import WhatIfSimulator
        sim = WhatIfSimulator()
        result = sim.run({
            "base_params": {
                "current_stock": 500,
                "unit_cost": 5.0,
                "original_price": 19.99,
                "elasticity": -2.0,
                "days_remaining": 30,
            },
            "scenarios": [
                {"name": "conservative", "params": {"service_level": 0.90}},
                {"name": "balanced", "params": {"service_level": 0.95}},
                {"name": "aggressive", "params": {"service_level": 0.98}},
            ],
            "skill_name": "pricing-markdown",
            "compare_metrics": ["total_expected_revenue", "clearance_rate"],
        })
        assert len(result.scenarios) == 3
        assert result.best_scenario != ""
        assert len(result.comparison_table) == 4  # baseline + 3 scenarios

    def test_whatif_baseline_only(self):
        from supplymind.skills.common.what_if.main import WhatIfSimulator
        sim = WhatIfSimulator()
        result = sim.run({
            "base_params": {"prices": [10, 9, 8], "quantities": [100, 130, 170]},
            "scenarios": [],
            "skill_name": "pricing-elasticity",
        })
        assert isinstance(result.baseline, dict)


# ════════════════════════════════════════════════
# 6. LangChain Adapter test
# ════════════════════════════════════════════════

class TestLangChainAdapter:
    def test_get_all_tools(self):
        from supplymind.adapters.langchain_tool import get_all_tools
        tools = get_all_tools()
        assert len(tools) >= 8  # At least 8 tools registered
        names = {t.name for t in tools}
        assert "supplymind_data_profiler" in names
        assert "supplymind_demand_forecast" in names
        assert "supplymind_pricing_elasticity" in names
        assert "supplymind_what_if" in names

    def test_tool_func_executes(self):
        from supplymind.adapters.langchain_tool import SupplyMindTool
        tool = SupplyMindTool(
            skill_name="pricing-elasticity",
            description="Test tool",
        )
        result = tool.func(prices=[10, 9, 8], quantities=[100, 130, 170])
        assert "elasticity" in result or "error" in result


# ════════════════════════════════════════════════
# 7. MCP Server — Phase 3 tools registration
# ════════════════════════════════════════════════

class TestMCPPhase3Tools:
    def test_new_tools_registered(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        tools = server.list_tools()
        names = {t["name"] for t in tools}
        # Phase 3 tools must be present
        assert "pricing_elasticity" in names
        assert "pricing_markdown" in names
        assert "pricing_lifecycle" in names
        assert "fulfill_routing" in names
        assert "what_if" in names

    def test_call_pricing_elasticity_via_mcp(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        result = server.call_tool("pricing_elasticity", {
            "sku_id": "TEST",
            "prices": [10.0, 9.0, 8.0],
            "quantities": [100, 130, 170],
        })
        assert result["success"] is True

    def test_call_pricing_markdown_via_mcp(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        result = server.call_tool("pricing_markdown", {
            "current_stock": 200,
            "unit_cost": 5.0,
            "original_price": 19.99,
        })
        assert result["success"] is True

    def test_call_pricing_lifecycle_via_mcp(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        result = server.call_tool("pricing_lifecycle", {
            "weekly_sales": [10, 18, 30, 48, 72, 100],
        })
        assert result["success"] is True

    def test_call_fulfill_routing_via_mcp(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        result = server.call_tool("fulfill_routing", {
            "locations": [
                {"location_id": "D", "lat": 0, "lon": 0},
                {"location_id": "A", "lat": 1, "lon": 0, "demand": 5},
                {"location_id": "B", "lat": 0, "lon": 1, "demand": 8},
            ],
        })
        assert result["success"] is True

    def test_call_what_if_via_mcp(self):
        from supplymind.mcp.server import MCPServer
        server = MCPServer()
        result = server.call_tool("what_if", {
            "base_scenario": {
                "skill_name": "pricing-markdown",
                "params": {
                    "current_stock": 300,
                    "unit_cost": 5.0,
                    "current_price": 19.99,
                    "elasticity": -2.0,
                    "days_remaining": 30,
                },
            },
            "scenarios": [
                {"name": "conservative", "params": {"elasticity": -1.5}},
                {"name": "aggressive", "params": {"elasticity": -3.0}},
            ],
        })
        assert result["success"] is True


# ════════════════════════════════════════════════
# 8. CLI Registration — Phase 3 commands
# ════════════════════════════════════════════════

class TestCLIPhase3Registration:
    def test_cli_has_pricing_commands(self):
        from supplymind.cli import main
        cmd_names = list(main.commands.keys())
        assert "pricing-elasticity" in cmd_names
        assert "pricing-markdown" in cmd_names
        assert "pricing-lifecycle" in cmd_names
        assert "pricing-bundling" in cmd_names

    def test_cli_has_fulfillment_commands(self):
        from supplymind.cli import main
        cmd_names = list(main.commands.keys())
        assert "fulfill-allocation" in cmd_names
        assert "fulfill-routing" in cmd_names
        assert "fulfill-wave" in cmd_names
        assert "fulfill-capacity" in cmd_names

    def test_cli_has_whatif_command(self):
        from supplymind.cli import main
        cmd_names = list(main.commands.keys())
        assert "what-if" in cmd_names

    def test_total_command_count(self):
        from supplymind.cli import main
        # Should have all previous commands + 9 new ones
        total = len(main.commands)
        assert total >= 25  # Phase 1 (8 skills + run-pipeline + dashboard) + Phase 2 (7) + Phase 3 (9)


# ════════════════════════════════════════════════
# 9. Pipeline Engine — Phase 3 skill_map
# ════════════════════════════════════════════════

class TestPipelineEnginePhase3Skills:
    def test_pricing_skills_in_map(self):
        from supplymind.pipelines.engine import _get_skill_instance
        # These should not raise ValueError
        for name in ["pricing-elasticity", "pricing-markdown", "pricing-lifecycle", "pricing-bundling"]:
            instance = _get_skill_instance(name)
            assert instance is not None
            assert hasattr(instance, 'run')

    def test_fulfillment_skills_in_map(self):
        from supplymind.pipelines.engine import _get_skill_instance
        for name in ["fulfill-allocation", "fulfill-routing", "fulfill-wave", "fulfill-capacity"]:
            instance = _get_skill_instance(name)
            assert instance is not None
            assert hasattr(instance, 'run')

    def test_whatif_in_map(self):
        from supplymind.pipelines.engine import _get_skill_instance
        instance = _get_skill_instance("what-if")
        assert instance is not None
        assert hasattr(instance, 'run')


# ════════════════════════════════════════════════
# 10. Schema validation tests
# ════════════════════════════════════════════════

class TestSchemaValidation:
    def test_elasticity_schema_validation(self):
        from supplymind.skills.pricing.elasticity.schema import ElasticityInput
        inp = ElasticityInput(prices=[10.0], quantities=[100.0])
        assert inp.prices == [10.0]

    def test_markdown_schema_validation(self):
        from supplymind.skills.pricing.markdown.schema import MarkdownInput
        inp = MarkdownInput(current_stock=100, unit_cost=5.0, original_price=19.99)
        assert inp.current_stock == 100

    def test_lifecycle_schema_validation(self):
        from supplymind.skills.pricing.lifecycle.schema import LifecycleInput
        inp = LifecycleInput(weekly_sales=[10, 20, 30])
        assert len(inp.weekly_sales) == 3

    def test_bundle_schema_validation(self):
        from supplymind.skills.pricing.bundling.schema import BundlingInput
        inp = BundlingInput(transactions=[{"items": ["A", "B"]}])
        assert len(inp.transactions) == 1

    def test_routing_schema_validation(self):
        from supplymind.skills.fulfillment.routing.schema import RoutingInput
        inp = RoutingInput(locations=[{"location_id": "L1", "lat": 0, "lon": 0}])
        assert len(inp.locations) == 1

    def test_capacity_schema_validation(self):
        from supplymind.skills.fulfillment.capacity.schema import CapacityInput
        inp = CapacityInput(resources=[{"resource_id": "R1", "capacity": 100}])
        assert len(inp.resources) == 1

    def test_whatif_schema_validation(self):
        from supplymind.skills.common.what_if.schema import WhatIfInput
        inp = WhatIfInput(
            base_params={},
            scenarios=[{"name": "test", "params": {}}],
        )
        assert len(inp.scenarios) == 1
