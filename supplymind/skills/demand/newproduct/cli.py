"""
New Product Demand Forecasting Skill — CLI entry point.
"""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.demand.newproduct.main import DemandNewProduct
from supplymind.skills.demand.newproduct.schema import NewProductInput


@click.command()
@click.option("--sku-id", "-s", required=True, help="New product SKU ID")
@click.option("--name", "-n", default="", help="Product name")
@click.option("--category", "-c", default="", help="Product category (for finding similar products)")
@click.option("--reference-data", "-r", type=click.Path(exists=True), help="CSV of similar products' history")
@click.option("--horizon", "-h", default=90, type=int, help="Forecast horizon in days (default: 90)")
@click.option("--peak-demand", "-p", default=None, type=float, help="Expected peak daily demand")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output JSON file path")
def demand_newproduct(sku_id: str, name: str, category: str, reference_data: str | None,
                      horizon: int, peak_demand: float | None, output: str | None):
    """Generate cold-start demand forecast for a new product.

    Example:
        supplymind demand-newproduct --sku-id NEW001 --category dairy --reference-data sim.csv --horizon 60
    """
    # Load reference data if provided
    ref_history = []
    if reference_data:
        try:
            import csv
            with open(reference_data, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ref_history.append({
                        "sku_id": row.get("sku_id", ""),
                        "quantity": float(row.get("quantity", 0)),
                        "date": row.get("date", ""),
                        "category": row.get("category", ""),
                    })
        except Exception as e:
            click.echo(f"Error loading reference data: {e}", err=True)
            sys.exit(1)

    params = NewProductInput(
        sku_id=sku_id,
        name=name,
        category=category,
        reference_history=ref_history,
        horizon=horizon,
        expected_peak_demand=peak_demand,
    )

    skill = DemandNewProduct()
    result = skill.run(params)

    output_dict = result.model_dump()

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        click.echo(f"New product forecast saved to {output}")
    else:
        _print_report(result)


def _print_report(result):
    click.echo()
    click.echo("=" * 65)
    click.echo("  SupplyMind - New Product Demand Forecast")
    click.echo("=" * 65)
    click.echo()

    if result.forecasts:
        fc = result.forecasts[0]
        s = result.summary
        click.echo(f"  SKU:                  {fc.sku_id}")
        click.echo(f"  Method:               {fc.method_used}")
        click.echo(f"  Horizon:              {s.get('horizon_days', 0)} days")
        click.echo(f"  Total Predicted:      {fc.total_predicted:,.1f} units")
        click.echo(f"  Confidence Score:     {fc.confidence_score:.1%} (naturally low for new products)")
        click.echo()
        click.echo(f"  Reasoning:")
        click.echo(f"    {fc.reasoning}")
        click.echo()

        if fc.similar_products_used:
            click.echo(f"  Similar Products Used: {', '.join(fc.similar_products_used)}")

    click.echo()
    click.echo("=" * 65)


if __name__ == "__main__":
    demand_newproduct()
