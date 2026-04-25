"""
SupplyMind CLI — unified command-line entry point.

Usage:
    supplymind data-profiler --input data.csv
    supplymind demand-forecast --input data.csv --horizon 14
    supplymind demand-decompose --input data.csv --period 7
    supplymind demand-newproduct --sku-id NEW001 --category dairy
    supplymind demand-intermittent --input data.csv --variant sba
    supplymind demand-reconcile --input forecasts.json --method bottom_up
    supplymind inventory-classify --input items.json
    supplymind inventory-safety-stock --input items.json
    supplymind inventory-reorder --input forecast.json
    supplymind inventory-policy-sim --sku-id SKU001 --demand-mean 150
    supplymind inventory-multi-echelon --config network.json
    supplymind inventory-newsvendor --price 29.99 --cost 12.00
    supplymind pricing-elasticity -p "9.99,8.99,7.99" -q "100,130,170"
    supplymind pricing-markdown --stock 500 --cost 5.0 --price 19.99 --days 14
    supplymind pricing-lifecycle -s "10,15,22,35,48,55,60,58,52,45"
    supplymind pricing-bundling -t transactions.json
    supplymind fulfill-allocation -o orders.json -i inventory.json
    supplymind fulfill-routing -l locations.json
    supplymind fulfill-wave -o orders.json
    supplymind fulfill-capacity -r resources.json
    supplymind what-if -s scenarios.json
    supplymind run-pipeline pipelines/retail-replenish.yaml --data data.csv
"""

from __future__ import annotations

import sys

import click


@click.group()
@click.version_option(version="0.1.0", prog_name="SupplyMind")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def main(verbose: bool = False):
    """SupplyMind — 供应链计划 Agent 框架 (Skill-based, Self-improving, HITL)"""
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# ── Register Skill commands ──

# Common Skills
main.add_command(
    __import__("supplymind.skills.common.data_profiler.cli", fromlist=["data_profiler"]).data_profiler,
    name="data-profiler",
)
main.add_command(
    __import__("supplymind.skills.common.report_generator.cli", fromlist=["report_generator"]).report_generator,
    name="report-generator",
)

# Demand Skills
main.add_command(
    __import__("supplymind.skills.demand.forecast.cli", fromlist=["demand_forecast"]).demand_forecast,
    name="demand-forecast",
)
main.add_command(
    __import__("supplymind.skills.demand.anomaly.cli", fromlist=["demand_anomaly"]).demand_anomaly,
    name="demand-anomaly",
)

# Demand Skills (Phase 2)
main.add_command(
    __import__("supplymind.skills.demand.decompose.cli", fromlist=["demand_decompose"]).demand_decompose,
    name="demand-decompose",
)
main.add_command(
    __import__("supplymind.skills.demand.newproduct.cli", fromlist=["demand_newproduct"]).demand_newproduct,
    name="demand-newproduct",
)
main.add_command(
    __import__("supplymind.skills.demand.intermittent.cli", fromlist=["demand_intermittent"]).demand_intermittent,
    name="demand-intermittent",
)
main.add_command(
    __import__("supplymind.skills.demand.reconcile.cli", fromlist=["demand_reconcile"]).demand_reconcile,
    name="demand-reconcile",
)

# Inventory Skills (Phase 1)
main.add_command(
    __import__("supplymind.skills.inventory.classify.cli", fromlist=["inventory_classify"]).inventory_classify,
    name="inventory-classify",
)
main.add_command(
    __import__("supplymind.skills.inventory.safety_stock.cli", fromlist=["safety_stock"]).safety_stock,
    name="inventory-safety-stock",
)
main.add_command(
    __import__("supplymind.skills.inventory.reorder.cli", fromlist=["inventory_reorder"]).inventory_reorder,
    name="inventory-reorder",
)

# Inventory Skills (Phase 2)
main.add_command(
    __import__("supplymind.skills.inventory.policy_sim.cli", fromlist=["inventory_policy_sim"]).inventory_policy_sim,
    name="inventory-policy-sim",
)
main.add_command(
    __import__("supplymind.skills.inventory.multi_echelon.cli", fromlist=["inventory_multi_echelon"]).inventory_multi_echelon,
    name="inventory-multi-echelon",
)
main.add_command(
    __import__("supplymind.skills.inventory.newsvendor.cli", fromlist=["inventory_newsvendor"]).inventory_newsvendor,
    name="inventory-newsvendor",
)

# Pricing Skills (Phase 3)
main.add_command(
    __import__("supplymind.skills.pricing.elasticity.cli", fromlist=["pricing_elasticity"]).pricing_elasticity,
    name="pricing-elasticity",
)
main.add_command(
    __import__("supplymind.skills.pricing.markdown.cli", fromlist=["pricing_markdown"]).pricing_markdown,
    name="pricing-markdown",
)
main.add_command(
    __import__("supplymind.skills.pricing.lifecycle.cli", fromlist=["pricing_lifecycle"]).pricing_lifecycle,
    name="pricing-lifecycle",
)
main.add_command(
    __import__("supplymind.skills.pricing.bundling.cli", fromlist=["pricing_bundling"]).pricing_bundling,
    name="pricing-bundling",
)

# Fulfillment Skills (Phase 3)
main.add_command(
    __import__("supplymind.skills.fulfillment.allocation.cli", fromlist=["fulfill_allocation"]).fulfill_allocation,
    name="fulfill-allocation",
)
main.add_command(
    __import__("supplymind.skills.fulfillment.routing.cli", fromlist=["fulfill_routing"]).fulfill_routing,
    name="fulfill-routing",
)
main.add_command(
    __import__("supplymind.skills.fulfillment.wave.cli", fromlist=["fulfill_wave"]).fulfill_wave,
    name="fulfill-wave",
)
main.add_command(
    __import__("supplymind.skills.fulfillment.capacity.cli", fromlist=["fulfill_capacity"]).fulfill_capacity,
    name="fulfill-capacity",
)

# Common Skills (Phase 3)
main.add_command(
    __import__("supplymind.skills.common.what_if.cli", fromlist=["what_if"]).what_if,
    name="what-if",
)


@main.command("run-pipeline")
@click.option("--pipeline", "-p", required=True, type=click.Path(exists=True), help="Pipeline YAML file")
@click.option("--data", "-d", default=None, type=click.Path(exists=True), help="Input data path")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output directory")
def run_pipeline(pipeline: str, data: str | None, output: str | None):
    """Execute a SupplyMind Pipeline from YAML definition."""
    try:
        from supplymind.pipelines.engine import PipelineEngine
        engine = PipelineEngine(pipeline_path=pipeline, data_path=data, output_dir=output)
        result = engine.run()

        click.echo()
        click.echo("═" * 60)
        click.echo(f"  ✅ Pipeline '{result.name}' completed!")
        click.echo("═" * 60)
        click.echo(f"  Status:     {result.status}")
        click.echo(f"  Steps:      {result.completed_steps}/{result.total_steps}")
        click.echo(f"  Duration:   {result.duration_seconds:.1f}s")
        if result.errors:
            click.echo(f"  Errors:     {len(result.errors)}")
            for err in result.errors[:3]:
                click.echo(f"    • {err}")

        # Print summary
        summary = result.output_summary or {}
        if summary:
            click.echo()
            click.echo("  📊 Output Summary:")
            for k, v in list(summary.items())[:10]:
                click.echo(f"    {k}: {v}")

        click.echo()
        click.echo(f"  📄 Report saved to: {output or 'stdout'}")
        click.echo("═" * 60)

    except Exception as e:
        click.echo(f"❌ Pipeline execution failed: {e}", err=True)
        sys.exit(1)


@main.command("dashboard")
@click.option("--host", "-h", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
@click.option("--port", "-p", default=8080, type=int, help="Port number (default: 8080)")
def dashboard(host: str, port: int):
    """Start the SupplyMind Dashboard web server."""
    from supplymind.dashboard.server import start_dashboard
    import time

    server = start_dashboard(host=host, port=port)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\n\n  Shutting down Dashboard...")
        server.shutdown()
        click.echo("  Dashboard stopped.")


if __name__ == "__main__":
    main()
