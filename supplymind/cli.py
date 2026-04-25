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


@main.command("mcp-serve")
@click.option("--transport", "-t", default="stdio", type=click.Choice(["stdio", "sse"]),
              help="Transport protocol (default: stdio)")
def mcp_serve(transport: str):
    """Start the MCP server for AI assistant integration.

    Exposes all 23 SupplyMind skills via Model Context Protocol.
    Compatible with Claude Desktop, Cursor, Claude Code, etc.

    \b
    Examples:
        supplymind mcp-serve                    # stdio (default)
        supplymind mcp-serve --transport sse    # SSE for web clients
    """
    try:
        from supplymind.mcp.server import start_mcp_server
        start_mcp_server(transport=transport)
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Install MCP support: pip install supplymind[mcp]", err=True)
        raise SystemExit(1)


@main.command("dataset")
@click.argument("action", type=click.Choice(["list", "validate", "info"]))
@click.option("--id", "dataset_id", default=None, help="Dataset ID (for validate/info)")
def dataset_cmd(action: str, dataset_id: str | None):
    """Manage datasets: list, validate, or inspect.

    \b
    Examples:
        supplymind dataset list
        supplymind dataset validate --id retail_grocery
        supplymind dataset info --id retail_grocery
    """
    from supplymind.datasets import list_datasets, validate_dataset, load_dataset

    if action == "list":
        datasets = list_datasets()
        click.echo(f"\n  Available Datasets ({len(datasets)}):\n")
        for ds in datasets:
            status = "OK" if ds["available"] else "MISSING"
            click.echo(f"  [{status}] {ds['id']}: {ds['description']}")
        click.echo()

    elif action == "validate":
        if not dataset_id:
            click.echo("Error: --id required for validate", err=True)
            sys.exit(1)
        report = validate_dataset(dataset_id)
        click.echo(f"\n  Dataset Validation: {dataset_id}")
        click.echo(f"  Demand records:  {report['demand_records']}")
        click.echo(f"  SKU count:       {report['sku_count']}")
        click.echo(f"  Inventory snaps: {report['inventory_snapshots']}")
        if report["issues"]:
            click.echo(f"  Issues ({len(report['issues'])}):")
            for issue in report["issues"]:
                click.echo(f"    - {issue}")
        else:
            click.echo("  Status: VALID")
        click.echo()

    elif action == "info":
        if not dataset_id:
            click.echo("Error: --id required for info", err=True)
            sys.exit(1)
        data = load_dataset(dataset_id)
        click.echo(f"\n  Dataset: {dataset_id}")
        click.echo(f"  Demand records:  {len(data.demand_history)}")
        if data.demand_history:
            skus = {r.sku_id for r in data.demand_history}
            locs = {r.location_id for r in data.demand_history}
            click.echo(f"  SKUs:            {len(skus)} ({', '.join(sorted(skus)[:5])})")
            click.echo(f"  Locations:       {len(locs)} ({', '.join(sorted(locs)[:5])})")
        click.echo(f"  SKU master:      {len(data.sku_master)} entries")
        click.echo(f"  Inventory snaps: {len(data.inventory_snapshots)} entries")
        click.echo()


@main.command("benchmark")
@click.option("--dataset", "-d", default="retail_grocery", help="Dataset ID to benchmark on")
@click.option("--horizon", "-h", default=14, type=int, help="Forecast horizon in days")
def benchmark_cmd(dataset: str, horizon: int):
    """Run forecast benchmark against industry baselines.

    \b
    Examples:
        supplymind benchmark
        supplymind benchmark --dataset retail_grocery --horizon 7
    """
    from supplymind.benchmark import run_benchmark

    click.echo(f"\n  Running benchmark on '{dataset}' (horizon={horizon})...\n")
    report = run_benchmark(dataset_id=dataset, horizon=horizon)

    click.echo(f"  {'Method':<25} {'MAPE':>8} {'RMSE':>8} {'MAE':>8} {'Time(ms)':>10}")
    click.echo(f"  {'─' * 25} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 10}")
    for r in sorted(report.results, key=lambda x: x.mape):
        marker = " *" if r.method == report.best_method else ""
        click.echo(
            f"  {r.method:<25} {r.mape:>7.1f}% {r.rmse:>8.1f} {r.mae:>8.1f} {r.duration_ms:>9.1f}{marker}"
        )
    click.echo(f"\n  Best: {report.best_method} (MAPE={report.best_mape:.1f}%)\n")


if __name__ == "__main__":
    main()
