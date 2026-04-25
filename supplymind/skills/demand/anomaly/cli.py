"""Demand Anomaly Skill — CLI."""
from __future__ import annotations

import json
import sys
import click
from supplymind.skills.demand.anomaly.main import DemandAnomaly
from supplymind.skills.demand.anomaly.schema import AnomalyInput
from supplymind.protocol.adapter import load_demand_from_csv

@click.command()
@click.option("--input", "-i", required=True, type=click.Path(exists=True))
@click.option("--method", "-m", type=click.Choice(["zscore", "iqr", "moving_avg", "auto"]), default="auto")
@click.option("--threshold", "-t", default=3.0, type=float)
@click.option("--action", "-a", type=click.Choice(["flag", "remove", "replace"]), default="flag")
@click.option("--output", "-o", default=None, type=click.Path())
def demand_anomaly(input: str, method: str, threshold: float, action: str, output: str | None):
    """Detect and clean anomalies in demand data.

    Example:
        supplymind demand-anomaly --input data/demand.csv --action remove --output cleaned.csv
    """
    records = load_demand_from_csv(input)
    demand_dicts = [
        {"sku_id": r.sku_id, "location_id": r.location_id,
         "date": r.demand_date.isoformat(), "quantity": r.quantity}
        for r in records
    ]
    params = AnomalyInput(demand_history=demand_dicts, method=method, threshold=threshold, action=action)
    result = DemandAnomaly().run(params)

    if output:
        with open(output, "w") as f:
            json.dump(result.model_dump(), f, indent=2, default=str)
        click.echo(f"✅ Anomaly result saved to {output}")
    else:
        click.echo(json.dumps(result.model_dump(), indent=2, default=str))

if __name__ == "__main__":
    demand_anomaly()
