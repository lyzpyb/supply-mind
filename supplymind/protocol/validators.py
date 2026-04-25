"""
Data validators for UDP Schema — quality checks and data health assessment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from supplymind.protocol.schema import SupplyMindData, DemandRecord


class Severity(str, Enum):
    """Issue severity levels."""
    CRITICAL = "critical"   # Blocks execution
    WARNING = "warning"     # May affect quality
    INFO = "info"           # Informational


@dataclass
class ValidationIssue:
    """A single validation finding."""
    severity: Severity
    category: str           # e.g. "missing_values", "outliers", "duplicates"
    field: str              # Affected field
    message: str            # Human-readable description
    affected_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of validating a dataset."""

    is_valid: bool
    score: float  # 0-100 data quality score
    issues: list[ValidationIssue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "critical_issues": self.critical_count,
            "warning_issues": self.warning_count,
            "total_issues": len(self.issues),
            "issues": [
                {
                    "severity": i.severity.value,
                    "category": i.category,
                    "field": i.field,
                    "message": i.message,
                    "affected_count": i.affected_count,
                }
                for i in self.issues
            ],
            "summary": self.summary,
        }


class DataValidator:
    """Validates SupplyMindData for quality and completeness.

    Checks include:
    - Required fields presence
    - Date continuity (gaps detection)
    - Missing values
    - Duplicate records
    - Negative quantities
    - Statistical outliers
    - Data volume adequacy
    """

    def __init__(
        self,
        min_records: int = 30,
        outlier_zscore_threshold: float = 3.0,
        max_gap_days: int = 7,
    ):
        self.min_records = min_records
        self.outlier_zscore_threshold = outlier_zscore_threshold
        self.max_gap_days = max_gap_days

    def validate(self, data: SupplyMindData) -> ValidationResult:
        """Run all validation checks on the dataset."""
        issues: list[ValidationIssue] = []
        summary: dict[str, Any] = {}

        # Basic counts
        n_skus = len(data.unique_skus)
        n_locations = len(data.unique_locations)
        n_records = data.total_records
        date_range = data.date_range

        summary["sku_count"] = n_skus
        summary["location_count"] = n_locations
        summary["record_count"] = n_records
        summary["date_range"] = (
            f"{date_range[0].isoformat()} ~ {date_range[1].isoformat()}"
            if date_range else "N/A"
        )

        # Check 1: Minimum data volume
        if n_records < self.min_records:
            issues.append(ValidationIssue(
                severity=Severity.CRITICAL,
                category="volume",
                field="demand_history",
                message=f"Insufficient data: {n_records} records (minimum {self.min_records})",
                affected_count=n_records,
            ))

        # Check 2: SKU master coverage
        demand_skus = set(data.unique_skus)
        master_skus = {s.sku_id for s in data.sku_master}
        missing_in_master = demand_skus - master_skus
        if missing_in_master:
            issues.append(ValidationIssue(
                severity=Severity.WARNING,
                category="coverage",
                field="sku_master",
                message=f"{len(missing_in_master)} SKU(s) in demand but missing from master",
                affected_count=len(missing_in_master),
                details={"missing_sku_ids": list(missing_in_master)},
            ))

        # Check 3: Date continuity gaps
        if date_range and n_records > 1:
            df = pd.DataFrame([
                {"date": r.demand_date, "sku_id": r.sku_id, "location_id": r.location_id}
                for r in data.demand_history
            ])
            gap_issues = self._check_date_gaps(df, issues)

        # Check 4: Duplicates
        dup_count = self._check_duplicates(data.demand_history, issues)

        # Check 5: Negative or zero quantities
        neg_count = sum(1 for r in data.demand_history if r.quantity < 0)
        if neg_count > 0:
            issues.append(ValidationIssue(
                severity=Severity.CRITICAL,
                category="integrity",
                field="quantity",
                message=f"{neg_count} records with negative quantity",
                affected_count=neg_count,
            ))

        # Check 6: Outliers per SKU
        outlier_info = self._detect_outliers(data, issues)
        summary["outliers_detected"] = outlier_info

        # Calculate quality score
        score = self._calculate_score(n_records, issues, summary)
        is_valid = score >= 30  # Allow low-quality data with warnings

        return ValidationResult(
            is_valid=is_valid,
            score=score,
            issues=issues,
            summary=summary,
        )

    def _check_date_gaps(
        self, df: pd.DataFrame, issues: list[ValidationIssue]
    ) -> int:
        """Check for date continuity gaps per SKU-location."""
        gap_count = 0
        for (sku_id, loc_id), group in df.groupby(["sku_id", "location_id"]):
            dates = sorted(pd.to_datetime(group["date"]).dt.date.unique())
            if len(dates) < 2:
                continue
            for i in range(1, len(dates)):
                gap = (dates[i] - dates[i - 1]).days
                if gap > self.max_gap_days:
                    gap_count += 1
                    if gap_count <= 5:  # Limit issue count
                        issues.append(ValidationIssue(
                            severity=Severity.INFO,
                            category="continuity",
                            field="date",
                            message=(
                                f"Date gap of {gap} days for SKU={sku_id}, "
                                f"Location={loc_id} between {dates[i-1]} and {dates[i]}"
                            ),
                            details={"gap_days": gap, "sku_id": sku_id, "location_id": loc_id},
                        ))
        if gap_count > 5:
            issues.append(ValidationIssue(
                severity=Severity.INFO,
                category="continuity",
                field="date",
                message=f"... and {gap_count - 5} more date gaps detected",
                affected_count=gap_count,
            ))
        return gap_count

    def _check_duplicates(
        self, records: list[DemandRecord], issues: list[ValidationIssue]
    ) -> int:
        """Detect duplicate records."""
        seen: set[tuple] = set()
        duplicates: list[tuple] = []
        for r in records:
            key = (r.sku_id, r.location_id, r.demand_date)
            if key in seen:
                duplicates.append(key)
            else:
                seen.add(key)
        if duplicates:
            issues.append(ValidationIssue(
                severity=Severity.WARNING,
                category="duplicates",
                field="all",
                message=f"{len(duplicates)} duplicate record(s) found",
                affected_count=len(duplicates),
            ))
        return len(duplicates)

    def _detect_outliers(
        self, data: SupplyMindData, issues: list[ValidationIssue]
    ) -> dict[str, Any]:
        """Detect statistical outliers using Z-score."""
        outlier_info: dict[str, Any] = {}
        for sku_id in data.unique_skus:
            records = data.get_demand_for_sku(sku_id)
            if len(records) < 5:
                continue
            quantities = np.array([r.quantity for r in records])
            mean_q = np.mean(quantities)
            std_q = np.std(quantities)
            if std_q == 0:
                continue
            z_scores = np.abs((quantities - mean_q) / std_q)
            outlier_mask = z_scores > self.outlier_zscore_threshold
            n_outliers = int(np.sum(outlier_mask))
            if n_outliers > 0:
                outlier_indices = np.where(outlier_mask)[0].tolist()
                outlier_info[sku_id] = {
                    "count": n_outliers,
                    "indices": outlier_indices,
                    "z_scores": z_scores[outlier_mask].tolist(),
                }
                issues.append(ValidationIssue(
                    severity=Severity.WARNING,
                    category="outliers",
                    field="quantity",
                    message=(
                        f"SKU {sku_id}: {n_outliers} potential outlier(s) "
                        f"(z > {self.outlier_zscore_threshold})"
                    ),
                    affected_count=n_outliers,
                    details={
                        "sku_id": sku_id,
                        "mean": round(float(mean_q), 2),
                        "std": round(float(std_q), 2),
                    },
                ))
        return outlier_info

    def _calculate_score(
        self, n_records: int, issues: list[ValidationIssue], summary: dict
    ) -> float:
        """Calculate overall data quality score (0-100)."""
        score = 100.0

        # Volume penalty
        if n_records < self.min_records:
            score -= 40
        elif n_records < self.min_records * 2:
            score -= 15

        # Issue penalties
        for issue in issues:
            if issue.severity == Severity.CRITICAL:
                score -= 15
            elif issue.severity == Severity.WARNING:
                score -= 5
            elif issue.severity == Severity.INFO:
                score -= 1

        # Coverage bonus
        sku_coverage = summary.get("sku_count", 0)
        if sku_coverage >= 10:
            score += 5
        elif sku_coverage >= 5:
            score += 2

        return max(0.0, min(100.0, score))
