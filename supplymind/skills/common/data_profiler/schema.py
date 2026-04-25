"""
Data Profiler Skill — Input/Output schema definitions.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ProfilerInput(BaseModel):
    """Input for the Data Profiler skill.

    Attributes:
        data_path: Path to input data file (CSV/JSON)
        data: In-memory SupplyMindData (alternative to file path)
        output_format: Output format ('json', 'dict')
    """

    data_path: Optional[str] = Field(default=None, description="Path to data file")
    data: Optional[dict] = Field(default=None, description="In-memory data dict")
    output_format: str = Field(default="json", description="Output format")


class ProfilerOutput(BaseModel):
    """Output from the Data Profiler skill.

    Contains a comprehensive data quality report.
    """

    # Overview
    total_records: int = 0
    unique_skus: int = 0
    unique_locations: int = 0
    date_range: str = ""
    data_quality_score: float = 0.0

    # Per-SKU statistics
    sku_stats: list[dict] = Field(default_factory=list)

    # Data quality issues
    missing_values: dict[str, int] = Field(default_factory=dict)
    duplicate_count: int = 0
    outlier_summary: list[dict] = Field(default_factory=list)
    date_gaps: int = 0

    # Statistical summary
    global_stats: dict = Field(default_factory=dict)

    # Recommendations
    recommendations: list[str] = Field(default_factory=list)

    # Validation result
    validation: Optional[dict] = None
