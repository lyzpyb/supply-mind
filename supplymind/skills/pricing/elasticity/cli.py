"""Pricing Elasticity Skill — CLI entry point."""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.pricing.elasticity.main import PricingElasticity
from supplymind.skills.pricing.elasticity.schema import ElasticityInput


@click.command()
@click.option("--prices", "-p", required=True, help="Comma-separated historical prices")
@click.option("--quantities", "-q", required=True, help="Comma-separated quantities (same length as prices)")
@click.option("--sku-id", default="", help="SKU identifier for context")
def pricing_elasticity(prices: str, quantities: str, sku_id: str):
    """Estimate price elasticity from historical data.

    Example:
        supplymind pricing-elasticity -p "9.99,8.99,7.99" -q "100,130,170"
    """
    try:
        p_list = [float(x.strip()) for x in prices.split(",")]
        q_list = [float(x.strip()) for x in quantities.split(",")]
    except ValueError as e:
        click.echo(f"❌ Error parsing numbers: {e}", err=True)
        sys.exit(1)

    if len(p_list) != len(q_list):
        click.echo(f"❌ Prices ({len(p_list)}) and quantities ({len(q_list)}) must have same length.", err=True)
        sys.exit(1)

    skill = PricingElasticity()
    result = skill.run(ElasticityInput(
        prices=p_list,
        quantities=q_list,
        sku_id=sku_id,
    ))

    _print_report(result)


def _print_report(result):
    click.echo()
    click.echo("=" * 65)
    click.echo("  📊 SupplyMind — Price Elasticity Analysis")
    click.echo("=" * 65)
    click.echo()
    click.echo(f"  Elasticity Coefficient:   {result.elasticity:.4f}")
    click.echo(f"  Classification:           {result.classification}")
    click.echo(f"  Standard Error:           {result.std_error:.4f}")
    click.echo(f"  R² (Goodness of Fit):     {result.r_squared:.4f}")
    click.echo(f"  Observations:             {result.n_obs}")
    if result.revenue_optimal_price:
        click.echo(f"  Revenue-Optimal Price:    ${result.revenue_optimal_price:.2f}")
    click.echo()
    click.echo(f"  Interpretation:")
    click.echo(f"    {result.interpretation}")
    click.echo()
    click.echo("=" * 65)


if __name__ == "__main__":
    pricing_elasticity()
