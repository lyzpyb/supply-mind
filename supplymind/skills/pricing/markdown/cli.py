"""Pricing Markdown Skill — CLI entry point."""

from __future__ import annotations

import sys
import click

from supplymind.skills.pricing.markdown.main import PricingMarkdown
from supplymind.skills.pricing.markdown.schema import MarkdownInput


@click.command()
@click.option("--stock", "-s", required=True, type=float, help="Current stock to clear")
@click.option("--cost", "-c", required=True, type=float, help="Per-unit cost")
@click.option("--price", "-p", required=True, type=float, help="Original/list price")
@click.option("--elasticity", "-e", default=-2.0, type=float, help="Price elasticity (default: -2.0)")
@click.option("--days", "-d", default=30, type=int, help="Days remaining (default: 30)")
@click.option("--daily-demand", default=10.0, type=float, help="Daily demand at full price")
@click.option("--shelf-life", default=None, type=int, help="Shelf life in days (hard deadline)")
@click.option("--sku-id", default="", help="SKU identifier")
def pricing_markdown(stock: float, cost: float, price: float, elasticity: float,
                     days: int, daily_demand: float, shelf_life: int | None, sku_id: str):
    """Optimize markdown (clearance) pricing strategy.

    Example:
        supplymind pricing-markdown --stock 500 --cost 5.0 --price 19.99 --days 14
    """
    skill = PricingMarkdown()
    result = skill.run(MarkdownInput(
        current_stock=stock,
        unit_cost=cost,
        original_price=price,
        elasticity=elasticity,
        days_remaining=days,
        daily_base_demand=daily_demand,
        shelf_life_days=shelf_life,
        sku_id=sku_id,
    ))

    _print_report(result)


def _print_report(result):
    s = result.summary
    click.echo()
    click.echo("=" * 70)
    click.echo("  🏷️  SupplyMind — Markdown Optimization Report")
    click.echo("=" * 70)
    click.echo()
    click.echo(f"  SKU:                  {s.get('sku_id', 'N/A')}")
    click.echo(f"  Stock to Clear:       {s.get('stock_to_clear'):,.0f} units")
    click.echo(f"  Original Price:       ${s.get('original_price', 0):.2f}")
    click.echo(f"  Unit Cost:            ${s.get('unit_cost', 0):.2f}")
    click.echo(f"  Days Remaining:       {s.get('days_remaining', 0)}")
    click.echo()

    if result.phases:
        click.echo("  Optimal Markdown Phases:")
        click.echo("  " + "-" * 68)
        click.echo(f"  {'Phase':<6} {'Days':>6} {'Price':>9} {'Demand':>9} {'Revenue':>11} {'Remaining':>11}")
        click.echo("  " + "-" * 68)
        for i, p in enumerate(result.phases, 1):
            click.echo(
                f"  {i:<6} {p.start_day}-{p.end_day:>3} ${p.price:>7.2f} "
                f"{p.expected_demand:>9.1f} ${p.expected_revenue:>10,.2f} "
                f"{p.remaining_stock:>10.1f}"
            )

    click.echo()
    click.echo(f"  Total Expected Revenue:  ${result.total_expected_revenue:,.2f}")
    click.echo(f"  Total Expected Sold:     {result.total_expected_sold:,.1f} units")
    click.echo(f"  Clearance Rate:          {result.clearance_rate:.1%}")
    if result.revenue_lift_pct != 0:
        click.echo(f"  Revenue Lift vs Static:  {result.revenue_lift_pct:+.1f}%")
    click.echo(f"  Recommended Start Price: ${result.recommended_initial_price:.2f}")
    click.echo()
    click.echo("=" * 70)


if __name__ == "__main__":
    pricing_markdown()
