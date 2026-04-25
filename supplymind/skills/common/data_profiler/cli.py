"""
Data Profiler Skill — CLI entry point.
"""

from __future__ import annotations

import json
import sys
import click

from supplymind.skills.common.data_profiler.main import DataProfiler
from supplymind.skills.common.data_profiler.schema import ProfilerInput


@click.command()
@click.option(
    "--input", "-i",
    required=True,
    type=click.Path(exists=True),
    help="Path to input data file (CSV)",
)
@click.option(
    "--output", "-o",
    default=None,
    type=click.Path(),
    help="Path to output JSON file (default: stdout)",
)
@click.option(
    "--format", "fmt",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format (default: text)",
)
def data_profiler(input: str, output: str | None, fmt: str):
    """Profile supply chain data for quality assessment and statistics.

    Example:
        supplymind data-profiler --input data/demand.csv --output profile.json
    """
    profiler = DataProfiler()
    params = ProfilerInput(data_path=input)

    try:
        result = profiler.run(params)
    except Exception as e:
        click.echo(f"❌ Error profiling data: {e}", err=True)
        sys.exit(1)

    if fmt == "json":
        output_dict = result.model_dump()
        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
            click.echo(f"✅ Profile saved to {output}")
        else:
            click.echo(json.dumps(output_dict, indent=2, ensure_ascii=False, default=str))
    else:
        _print_text_report(result)


def _print_text_report(result):
    """Print a human-readable text report."""
    click.echo()
    click.echo("═" * 60)
    click.echo("  📊 SupplyMind — Data Profiler Report")
    click.echo("═" * 60)
    click.echo()

    # Overview
    click.echo(f"  Total Records:     {result.total_records:,}")
    click.echo(f"  Unique SKUs:       {result.unique_skus}")
    click.echo(f"  Unique Locations:  {result.unique_locations}")
    click.echo(f"  Date Range:        {result.date_range}")
    click.echo(f"  Quality Score:     {result.data_quality_score:.1f}/100")
    click.echo()

    # Issues summary
    has_issues = (
        result.missing_values or result.duplicate_count > 0
        or result.outlier_summary or result.date_gaps > 0
    )
    if has_issues:
        click.echo("  ⚠️  Issues Found:")
        if result.missing_values:
            for field, count in result.missing_values.items():
                click.echo(f"    • Missing in {field}: {count} SKU(s)")
        if result.duplicate_count > 0:
            click.echo(f"    • Duplicate records: {result.duplicate_count}")
        if result.outlier_summary:
            click.echo(f"    • Outlier SKU(s): {len(result.outlier_summary)}")
        if result.date_gaps > 0:
            click.echo(f"    • Date gaps: {result.date_gaps}")
        click.echo()

    # Global stats
    if result.global_stats:
        gs = result.global_stats
        click.echo("  📈 Global Statistics:")
        click.echo(f"    Mean demand:      {gs.get('mean', 'N/A')}")
        click.echo(f"    Std dev:          {gs.get('std', 'N/A')}")
        click.echo(f"    CV (variability): {gs.get('cv_global', 'N/A')}")
        click.echo(f"    Granularity:      {gs.get('granularity', 'N/A')}")
        click.echo()

    # Top SKUs
    if result.sku_stats:
        click.echo("  🏷️  Top SKUs by Volume:")
        for i, sku in enumerate(result.sku_stats[:10]):
            bar_len = min(30, int(sku["total_quantity"] / max(s["total_quantity"] for s in result.sku_stats) * 30))
            bar = "█" * bar_len
            click.echo(
                f"    {i+1:>2}. {sku['sku_id']:<12} "
                f"{sku['total_quantity']:>10.1f}  {bar}"
            )
        if len(result.sku_stats) > 10:
            click.echo(f"       ... and {len(result.sku_stats) - 10} more")
        click.echo()

    # Recommendations
    if result.recommendations:
        click.echo("  💡 Recommendations:")
        for rec in result.recommendations:
            click.echo(f"    {rec}")
        click.echo()

    click.echo("═" * 60)


if __name__ == "__main__":
    data_profiler()
