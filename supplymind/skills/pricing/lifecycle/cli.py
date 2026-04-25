"""Pricing Lifecycle Skill — CLI entry point."""

from __future__ import annotations

import sys
import click

from supplymind.skills.pricing.lifecycle.main import PricingLifecycle
from supplymind.skills.pricing.lifecycle.schema import LifecycleInput


@click.command()
@click.option("--sales", "-s", required=True, help="Comma-separated weekly sales volumes")
@click.option("--weeks-since-launch", "-w", default=None, type=int, help="Weeks since launch")
@click.option("--sku-id", default="", help="SKU identifier")
@click.option("--category", default="", help="Product category")
def pricing_lifecycle(sales: str, weeks_since_launch: int | None, sku_id: str, category: str):
    """Detect product lifecycle stage from weekly sales.

    Example:
        supplymind pricing-lifecycle -s "10,15,22,35,48,55,60,58,52,45"
    """
    try:
        sales_list = [float(x.strip()) for x in sales.split(",")]
    except ValueError as e:
        click.echo(f"❌ Error parsing sales: {e}", err=True)
        sys.exit(1)

    skill = PricingLifecycle()
    result = skill.run(LifecycleInput(
        weekly_sales=sales_list,
        weeks_since_launch=weeks_since_launch,
        sku_id=sku_id,
        category=category,
    ))

    _print_report(result)


def _print_report(result):
    info = result.stage_summary
    click.echo()
    click.echo("=" * 65)
    click.echo(f"  {info.get('icon', '📦')} SupplyMind — Product Lifecycle Analysis")
    click.echo("=" * 65)
    click.echo()
    click.echo(f"  Stage:                 {result.stage.upper()}")
    click.echo(f"  Confidence:            {result.confidence:.0%}")
    click.echo(f"  Current Week:          Week {result.current_week}")
    click.echo(f"  Weeks Observed:        {info.get('total_weeks_observed', 0)}")
    click.echo(f"  Peak Volume:           {result.peak_volume:,.0f} (week {result.peak_week})")
    click.echo(f"  Avg Growth Rate:       {result.avg_growth_rate:+.2%} WoW")
    click.echo(f"  Recent Trend:          {result.recent_decline_rate:+.2%} WoW")
    click.echo()
    click.echo(f"  Stage Description:")
    click.echo(f"    {info.get('description', '')}")
    click.echo(f"  Typical Duration:      {info.get('typical_duration', '')}")
    click.echo()
    click.echo(f"  Pricing Recommendation:")
    click.echo(f"    {result.pricing_recommendation}")
    click.echo()
    click.echo("=" * 65)


if __name__ == "__main__":
    pricing_lifecycle()
