"""What-If Skill — schema."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

class ScenarioDef(BaseModel):
    name: str = ""
    params: dict = Field(default_factory=dict)
    description: str = ""

class WhatIfInput(BaseModel):
    base_params: dict = Field(default_factory=dict)
    scenarios: list[ScenarioDef | dict] = Field(...)
    skill_name: str = "inventory-policy-sim"  # which skill to run per scenario
    compare_metrics: list[str] = Field(default=["total_cost", "service_level"])

class ScenarioResult(BaseModel):
    scenario_name: str = ""
    metrics: dict = Field(default_factory=dict)
    raw_output: Optional[dict] = None
    vs_baseline_diff_pct: dict = Field(default_factory=dict)

class WhatIfOutput(BaseModel):
    baseline: dict = Field(default_factory=dict)
    scenarios: list[ScenarioResult] = Field(default_factory=list)
    best_scenario: str = ""
    recommendation: str = ""
    comparison_table: list[dict] = Field(default_factory=list)
