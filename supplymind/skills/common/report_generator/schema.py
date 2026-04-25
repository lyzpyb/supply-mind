"""Report Generator Skill — Schema."""

from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ReportInput(BaseModel):
    title: str = "SupplyMind Analysis Report"
    sections: list[dict] = Field(default_factory=list)
    format: Literal["markdown", "html", "json"] = "markdown"
    include_charts: bool = True


class ReportOutput(BaseModel):
    title: str = ""
    content: str = ""  # The rendered report (markdown or HTML)
    format: str = "markdown"
    section_count: int = 0
    generated_at: str = ""
