"""
Intermittent Demand Forecasting Skill — CLI entry point.
"""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.demand.intermittent.main import DemandIntermittent
from supplymind.skills.demand.intermittent.schema import IntermittentInput
from supplymind.protocol.adapter import load_demand_from_csv


@click.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True), help="Path to demand CSV")
@click.option("--horizon", "-h", default=14, type=int, help="Forecast horizon (default: 14)")
@click.option("--variant", "-v", type=click.Choice(["classic", "sba", "tsb"]), default="sba",
              help="Croston variant (default: sba)")
@click.option("--zero-threshold", default=0.5, type=float,
              help="Zero ratio threshold for intermittent classification (default: 0.5)")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output JSON file path")
def demand_intermittent(input: str, horizon: int, variant: str, zero_threshold: float, output: str | None):
    """Detect and forecast intermittent/sporadic demand.

    Example:
        supplymind demand-intermittent --input data/demand.csv --variant sba --horizon 28
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

    params = IntermittentInput(
        demand_history=demand_dicts,
        horizon=horizon,
        variant=variant,
        zero_threshold=zero_threshold,
    )

    skill = DemandIntermittent()
    result = skill.run(params)

    output_dict = result.model_dump()

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        click.echo(f"Intermittent analysis saved to {output}")
    else:
        _print_report(result)


def _print_report(result):
    click.echo()
    click.echo("=" * 70)
    click.echo("  SupplyMind - Intermittent Demand Analysis")
    click.echo("=" * 70)
    click.echo()

    s = result.summary
    click.echo(f"  Total SKUs Analyzed:   {s.get('total_skus', 0)}")
    click.echo(f"  Intermittent SKUs:      {s.get('intermittent_skus', 0)} ({s.get('intermittent_pct', 0)}%)")
    click.echo(f"  Standard SKUs:         {s.get('standard_skus', 0)}")
    click.echo(f"  Variant Used:           {s.get('variant_used', 'sba')}")
    click.echo(f"  Avg Zero Ratio:         {s.get('avg_zero_ratio', 0):.1%}")
    click.echo()

    if result.results:
        click.echo("  SKU Details:")
        click.echo("  " + "-" * 66)
        click.echo(f"  {'SKU':<14} {'Intermit.':<9} {'Zero%':<8} {'Daily':>8} {'Total':>10} {'Method':<16} {'Rec'}")
        click.echo("  " + "-" * 66)

        for r in result.results[:20]:
            marker = "*" if r.is_intermittent else " "
            click.echo(
                f"{marker}{r.sku_id:<13} {str(r.is_intermittent):<9} "
                f"{r.zero_ratio:<8.1%} {r.predicted_daily:>8.2f} "
                f"{r.total_predicted:>10.1f} {r.method_used:<16} {r.recommendation}"
            )

        if len(result.results) > 20:
            click.echo(f"  ... and {len(result.results) - 20} more")

    click.echo()
    click.echo("  * = Intermittent (Croston recommended)")
    click.echo("=" * 70)


if __name__ == "__main__":
    demand_intermittent()
