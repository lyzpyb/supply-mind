"""What-If Skill — CLI."""
from __future__ import annotations
import json, sys, click
from supplymind.skills.common.what_if.main import WhatIfSimulator
from supplymind.skills.common.what_if.schema import WhatIfInput

@click.command()
@click.option("--scenarios", "-s", required=True, type=click.Path(exists=True), help="Scenarios JSON file")
@click.option("--skill", "-k", default="inventory-policy-sim", help="Skill to simulate")
def what_if(scenarios: str, skill: str):
    """Multi-scenario what-if simulation.

    Scenarios JSON format:
        {"base_params": {...}, "scenarios": [{"name":"conservative","params":{...}}, ...]}
    """
    with open(scenarios) as f: data = json.load(f)
    sim = WhatIfSimulator()
    result = sim.run(WhatIfInput(**data, skill_name=skill))
    click.echo(json.dumps(result.model_dump(), indent=2, default=str))

if __name__ == "__main__":
    what_if()
