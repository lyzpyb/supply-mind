"""Inventory Classify Skill — Schema."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class ClassifyInput(BaseModel):
    items: list[dict] = Field(default_factory=list, description="Items with 'item_id', 'value', and 'values' (demand history)")
    value_key: str = "revenue"
    values_key: str = "demand_values"
    a_threshold: float = 0.80
    b_threshold: float = 0.95
    cv_x: float = 0.5
    cv_y: float = 1.0


class MatrixCell(BaseModel):
    label: str
    item_ids: list[str] = Field(default_factory=list)
    count: int = 0
    total_value: float = 0.0
    strategy: str = ""


class ClassifyOutput(BaseModel):
    abc_result: dict = Field(default_factory=dict)
    xyz_result: dict = Field(default_factory=dict)
    matrix: dict[str, MatrixCell] = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
