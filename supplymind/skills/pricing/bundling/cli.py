"""Pricing Bundling Skill — CLI entry point."""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.pricing.bundling.main import PricingBundling
from supplymind.skills.pricing.bundling.schema import BundlingInput


@click.command()
@click.option("--transactions", "-t", required=True, type=click.Path(exists=True),
              help="Path to JSON file with transaction records")
@click.option("--support", default=0.02, type=float, help="Min support threshold")
@click.option("--confidence", default=0.15, type=float, help="Min confidence threshold")
@click.option("--lift", default=1.2, type=float, help="Min lift factor")
@click.option("--top-k", default=10, type=int, help="Number of suggestions to return")
def pricing_bundling(transactions: str, support: float, confidence: float,
                     lift: float, top_k: int):
    """Recommend product bundles based on co-purchase patterns.

    Transaction JSON format:
        [{"items": ["SKU001","SKU002"], "revenue": 29.99}, ...]

    Example:
        supplymind pricing-bundling -t transactions.json
    """
    with open(transactions, "r", encoding="utf-8") as f:
        txn_data = json.load(f)

    skill = PricingBundling()
    result = skill.run(BundlingInput(
        transactions=txn_data,
        min_support=support,
        min_confidence=confidence,
        min_lift=lift,
        top_k=top_k,
    ))

    _print_report(result)


def _print_report(result):
    click.echo()
    click.echo("=" * 72)
    click.echo("  🎁 SupplyMind — Bundle Recommendation Report")
    click.echo("=" * 72)
    click.echo()
    click.echo(f"  SKUs Analyzed:         {result.total_skus_analyzed}")
    click.echo(f"  Complementary Pairs:   {result.complementary_pairs_found}")
    click.echo(f"  Top Suggestions:        {len(result.suggestions)}")

    if result.suggestions:
        click.echo()
        click.echo("  " + "-" * 70)
        click.echo(f"  {'Main SKU':<14} {'Bundle With':<16} {'Lift':>6} {'Disc%':>6} {'Rev Lift':>10} {'Conf':>6}")
        click.echo("  " + "-" * 70)
        for s in result.suggestions:
            click.echo(
                f"  {s.main_sku_id:<14} {s.complementary_sku_id:<16} "
                f"{s.lift_factor:>5.2f}x {s.bundle_discount_pct:>5.1%} "
                f"${s.expected_revenue_lift:>9,.2f} {s.confidence:>5.1%}"
            )
        click.echo("  " + "-" * 70)

    click.echo()
    click.echo("=" * 72)


if __name__ == "__main__":
    pricing_bundling()
