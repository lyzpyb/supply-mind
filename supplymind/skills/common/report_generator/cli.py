"""Report Generator Skill — CLI."""
from __future__ import annotations
import json, sys, click
from supplymind.skills.common.report_generator.main import ReportGenerator
from supplymind.skills.common.report_generator.schema import ReportInput

@click.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True))
@click.option("--format", "-f", type=click.Choice(["markdown", "html", "json"]), default="markdown")
@click.option("--output", "-o", default=None, type=click.Path())
@click.option("--title", "-t", default="SupplyMind Analysis Report")
def report_generator(input: str, format: str, output: str | None, title: str):
    """Generate analysis report from pipeline results.

    Example:
        supplymind report-generator --input pipeline_output.json --format html --output report.html
    """
    with open(input) as f:
        data = json.load(f)
    sections = data.get("sections", data if isinstance(data, list) else [data])
    params = ReportInput(title=title, sections=sections, format=format)
    result = ReportGenerator().run(params)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(result.content)
        click.echo(f"✅ Report saved to {output}")
    else:
        click.echo(result.content)

if __name__ == "__main__":
    report_generator()
