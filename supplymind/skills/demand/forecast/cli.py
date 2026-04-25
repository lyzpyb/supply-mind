"""
Demand Forecast Skill — CLI entry point.
"""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.demand.forecast.main import DemandForecast
from supplymind.skills.demand.forecast.schema import ForecastInput
from supplymind.protocol.adapter import load_demand_from_csv


@click.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True), help="Path to demand CSV")
@click.option("--horizon", "-h", default=14, type=int, help="Forecast horizon in days (default: 14)")
@click.option(
    "--method", "-m",
    type=click.Choice(["auto", "ma", "ema", "holt_winters", "croston"]),
    default="auto",
    help="Forecasting method (default: auto)",
)
@click.option("--output", "-o", default=None, type=click.Path(), help="Output JSON file path")
def demand_forecast(input: str, horizon: int, method: str, output: str | None):
    """Generate demand forecasts from historical data.

    Example:
        supplymind demand-forecast --input data/demand.csv --horizon 21 --method holt_winters
    """
    # Load demand data
    try:
        records = load_demand_from_csv(input)
    except Exception as e:
        click.echo(f"❌ Error loading data: {e}", err=True)
        sys.exit(1)

    if not records:
        click.echo("❌ No demand records found in input file.", err=True)
        sys.exit(1)

    # Convert to dict format for ForecastInput
    demand_dicts = [
        {
            "sku_id": r.sku_id,
            "location_id": r.location_id,
            "date": r.demand_date.isoformat(),
            "quantity": r.quantity,
        }
        for r in records
    ]

    params = ForecastInput(
        demand_history=demand_dicts,
        horizon=horizon,
        method=method,
    )

    forecaster = DemandForecast()
    result = forecaster.run(params)

    output_dict = result.model_dump()

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        click.echo(f"✅ Forecast saved to {output}")
    else:
        _print_forecast_report(result)


def _print_forecast_report(result):
    """Print a human-readable forecast report."""
    from datetime import date

    click.echo()
    click.echo("═" * 65)
    click.echo("  📈 SupplyMind — Demand Forecast Report")
    click.echo("═" * 65)
    click.echo()

    summary = result.summary
    click.echo(f"  Horizon:           {result.horizon} days")
    click.echo(f"  Method:             {result.method}")
    click.echo(f"  SKUs Forecasted:    {summary.get('total_skus', 0)}")
    click.echo(f"  Total Predicted:    {summary.get('total_predicted_volume', 0):,.1f} units")
    click.echo(f"  Avg MAPE:           {summary.get('avg_mape', 0):.1f}%")
    click.echo(f"  Weighted MAPE:      {summary.get('weighted_mape', 0):.1f}%")
    click.echo()

    # Per-SKU table
    if result.forecasts:
        click.echo("  ┌──────────────┬──────────┬────────┬─────────┬────────┐")
        click.echo("  │ SKU          │ Method   │ Total  │ MAPE(%) │ Conf   │")
        click.echo("  ├──────────────┼──────────┼────────┼─────────┼────────┤")

        for fc in result.forecasts[:15]:
            conf_bar = "█" * int(fc.confidence_score * 8)
            click.echo(
                f"  │ {fc.sku_id:<12} │ {fc.method_used:<8} │ "
                f"{fc.total_predicted:>6.1f} │ {fc.mape:>7.1f} │ "
                f"{conf_bar:<8} │"
            )

        if len(result.forecasts) > 15:
            click.echo(f"  │ ... and {len(result.forecasts) - 15} more SKUs")
        click.echo("  └──────────────┴──────────┴────────┴─────────┴────────┘")
        click.echo()

    # Low confidence warnings
    low_conf = summary.get("low_confidence_skus", [])
    if low_conf:
        click.echo(f"  ⚠️  Low confidence (<60%) SKUs: {len(low_conf)}")
        for sku_id in low_conf[:5]:
            click.echo(f"     • {sku_id}")

    # High MAPE warnings
    high_mape = summary.get("high_mape_skus", [])
    if high_mape:
        click.echo(f"  🔴 High MAPE (>25%) SKUs: {len(high_mape)}")
        for item in high_mape[:5]:
            click.echo(f"     • {item['sku_id']}: MAPE={item['mape']:.1f}%")

    click.echo()
    click.echo("═" * 65)


if __name__ == "__main__":
    demand_forecast()
