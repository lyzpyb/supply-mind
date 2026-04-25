"""
Demand Decomposition Skill — CLI entry point.
"""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.demand.decompose.main import DemandDecompose
from supplymind.skills.demand.decompose.schema import DecomposeInput
from supplymind.protocol.adapter import load_demand_from_csv


@click.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True), help="Path to demand CSV")
@click.option("--period", "-p", default=None, type=int, help="Seasonal period (auto-detect if omitted)")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output JSON file path")
def demand_decompose(input: str, period: int | None, output: str | None):
    """Decompose demand into trend, seasonal, and residual components.

    Example:
        supplymind demand-decompose --input data/demand.csv --period 7
    """
    try:
        records = load_demand_from_csv(input)
    except Exception as e:
        click.echo(f"Error loading data: {e}", err=True)
        sys.exit(1)

    demand_dicts = [
        {"sku_id": r.sku_id, "location_id": r.location_id,
         "date": r.demand_date.isoformat(), "quantity": r.quantity}
        for r in records
    ]

    params = DecomposeInput(demand_history=demand_dicts, period=period)
    skill = DemandDecompose()
    result = skill.run(params)

    output_dict = result.model_dump()

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        click.echo(f"Decomposition saved to {output}")
    else:
        _print_report(result)


def _print_report(result):
    click.echo()
    click.echo("=" * 65)
    click.echo("  SupplyMind - Demand Decomposition Report")
    click.echo("=" * 65)
    click.echo()

    s = result.summary
    click.echo(f"  SKUs Analyzed:         {s.get('total_skus', 0)}")
    click.echo(f"  Avg Seasonality Str.:  {s.get('avg_seasonality_strength', 0):.2%}")
    click.echo(f"  Strong Seasonality:    {s.get('strong_seasonality_skus', 0)} SKU(s)")
    click.echo()

    td = s.get("trend_distribution", {})
    click.echo(f"  Trend Distribution:")
    click.echo(f"    Increasing: {td.get('increasing', 0)} | Decreasing: {td.get('decreasing', 0)} | Stable: {td.get('stable', 0)}")

    sd = s.get("seasonality_distribution", {})
    click.echo(f"  Seasonality Distribution:")
    click.echo(f"    Strong: {sd.get('strong', 0)} | Moderate: {sd.get('moderate', 0)} | Weak: {sd.get('weak', 0)} | None: {sd.get('none', 0)}")
    click.echo()
    click.echo("=" * 65)


if __name__ == "__main__":
    demand_decompose()
