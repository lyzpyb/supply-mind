"""
Data Profiler Skill — main implementation.

Analyzes input data for quality, completeness, and statistical properties.
Produces a comprehensive profile report used by downstream Skills.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from supplymind.protocol.schema import SupplyMindData, DemandRecord
from supplymind.protocol.adapter import load_dataset
from supplymind.protocol.validators import DataValidator, ValidationResult
from supplymind.core.statistics import (
    summary_statistics,
    coefficient_of_variation,
    detect_outliers_zscore,
)
from supplymind.skills.common.data_profiler.schema import ProfilerInput, ProfilerOutput

logger = logging.getLogger(__name__)


class DataProfiler:
    """Data quality profiler and statistical summarizer.

    This is the first Skill in most Pipelines. It examines the input data,
    produces a quality score, identifies issues, and generates per-SKU statistics.
    """

    def __init__(self):
        self.validator = DataValidator()

    def run(self, input_data: ProfilerInput | dict | str) -> ProfilerOutput:
        """Run the data profiler.

        Args:
            input_data: ProfilerInput object, dict with 'data_path', or file path string

        Returns:
            ProfilerOutput with full analysis results
        """
        # Normalize input
        if isinstance(input_data, str):
            params = ProfilerInput(data_path=input_data)
        elif isinstance(input_data, dict):
            params = ProfilerInput(**input_data)
        else:
            params = input_data

        # Load data
        data = self._load_data(params)

        if not data.demand_history:
            return ProfilerOutput(
                total_records=0,
                recommendations=["No demand data found. Please check your input file."],
            )

        # Run validation
        validation: ValidationResult = self.validator.validate(data)

        # Compute statistics
        sku_stats = self._compute_sku_stats(data)
        global_stats = self._compute_global_stats(data)
        issues_summary = self._summarize_issues(validation)

        # Generate recommendations
        recommendations = self._generate_recommendations(validation, data)

        return ProfilerOutput(
            total_records=data.total_records,
            unique_skus=len(data.unique_skus),
            unique_locations=len(data.unique_locations),
            date_range=data.date_range[0].isoformat() + " ~ " + data.date_range[1].isoformat()
                         if data.date_range else "N/A",
            data_quality_score=validation.score,
            sku_stats=sku_stats,
            missing_values=issues_summary.get("missing", {}),
            duplicate_count=issues_summary.get("duplicates", 0),
            outlier_summary=issues_summary.get("outliers", []),
            date_gaps=issues_summary.get("date_gaps", 0),
            global_stats=global_stats,
            recommendations=recommendations,
            validation=validation.to_dict(),
        )

    def _load_data(self, params: ProfilerInput) -> SupplyMindData:
        """Load data from file path or use in-memory data."""
        if params.data_path and os.path.exists(params.data_path):
            path = params.data_path

            # Try to find related files in same directory
            base_dir = os.path.dirname(path)
            base_name = os.path.splitext(os.path.basename(path))[0]

            demand_path = path
            sku_path = None
            inv_path = None

            # Look for SKU master file
            for candidate in ["sku_master.csv", "skus.csv", "products.csv", "items.csv",
                              f"{base_name}_sku.csv", f"{base_name}_skus.csv"]:
                cand_path = os.path.join(base_dir, candidate) if base_dir else candidate
                if os.path.exists(cand_path):
                    sku_path = cand_path
                    break

            # Look for inventory file
            for candidate in ["inventory.csv", "stock.csv",
                              f"{base_name}_inventory.csv"]:
                cand_path = os.path.join(base_dir, candidate) if base_dir else candidate
                if os.path.exists(cand_path):
                    inv_path = cand_path
                    break

            return load_dataset(
                demand_path=demand_path,
                sku_path=sku_path,
                inventory_path=inv_path,
        )
        elif params.data:
            # Build from in-memory dict (simplified)
            return self._dict_to_data(params.data)

        return SupplyMindData()

    def _dict_to_data(self, data_dict: dict) -> SupplyMindData:
        """Convert a raw dict to SupplyMindData (basic conversion).

        Handles sparse input by filling in sensible defaults for required fields.
        """
        from datetime import date as _date

        data = SupplyMindData()
        if "demand_history" not in data_dict:
            return data

        for i, r in enumerate(data_dict["demand_history"]):
            if not isinstance(r, dict):
                continue
            try:
                # Fill missing required fields with defaults
                record = DemandRecord(
                    sku_id=r.get("sku_id", f"unknown_{i}"),
                    location_id=r.get("location_id", "DEFAULT"),
                    demand_date=r.get("date", r.get("demand_date", _date.today())),
                    quantity=float(r.get("quantity", 0)),
                    revenue=r.get("revenue"),
                    is_promo=r.get("is_promo"),
                    stockout_flag=r.get("stockout_flag"),
                )
                data.demand_history.append(record)
            except (ValueError, TypeError):
                pass
        return data

    def _compute_sku_stats(self, data: SupplyMindData) -> list[dict]:
        """Compute per-SKU statistical summaries."""
        stats_list = []

        for sku_id in data.unique_skus:
            records = data.get_demand_for_sku(sku_id)
            quantities = [r.quantity for r in records]

            if not quantities:
                continue

            arr = np.array(quantities)
            locations = list(set(r.location_id for r in records))

            stat = summary_statistics(quantities)
            cv = coefficient_of_variation(quantities)

            # Detect outliers
            outlier_result = detect_outliers_zscore(quantities)

            # Date range for this SKU
            dates = [r.demand_date for r in records]
            date_str = f"{min(dates).isoformat()} ~ {max(dates).isoformat()}" if dates else "N/A"

            # Promo ratio
            promo_count = sum(1 for r in records if r.is_promo is True)
            promo_ratio = promo_count / len(records) if records else 0

            # Stockout ratio
            stockout_count = sum(1 for r in records if r.stockout_flag is True)
            stockout_ratio = stockout_count / len(records) if records else 0

            # Get SKU info
            sku_info = data.get_sku(sku_id)

            stats_list.append({
                "sku_id": sku_id,
                "sku_name": sku_info.name if sku_info else sku_id,
                "category": sku_info.category_path if sku_info else "未分类",
                "record_count": len(records),
                "locations": locations,
                "date_range": date_str,
                "mean_daily_demand": round(stat["mean"], 2),
                "std": round(stat["std"], 2),
                "min": round(stat["min"], 2),
                "max": round(stat["max"], 2),
                "median": round(stat["median"], 2),
                "cv": round(cv, 4),
                "total_quantity": round(sum(quantities), 2),
                "outlier_count": len(outlier_result.outlier_indices),
                "promo_ratio": round(promo_ratio, 3),
                "stockout_ratio": round(stockout_ratio, 3),
                "unit_cost": round(sku_info.unit_cost, 2) if sku_info else 0.0,
                "unit_price": round(sku_info.unit_price, 2) if sku_info else 0.0,
            })

        # Sort by total quantity descending
        stats_list.sort(key=lambda x: x["total_quantity"], reverse=True)
        return stats_list

    def _compute_global_stats(self, data: SupplyMindData) -> dict:
        """Compute dataset-level aggregate statistics."""
        all_quantities = [r.quantity for r in data.demand_history]

        if not all_quantities:
            return {}

        arr = np.array(all_quantities)
        stat = summary_statistics(all_quantities)

        # Demand distribution by location
        loc_distribution: dict[str, float] = {}
        for r in data.demand_history:
            loc_distribution[r.location_id] = loc_distribution.get(r.location_id, 0) + r.quantity

        # Time granularity detection
        dates = sorted([r.demand_date for r in data.demand_history])
        if len(dates) >= 2:
            diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            median_gap = sorted(diffs)[len(diffs)//2] if diffs else 0
            if median_gap <= 1:
                granularity = "daily"
            elif median_gap <= 7:
                granularity = "weekly"
            elif median_gap <= 31:
                granularity = "monthly"
            else:
                granularity = f"irregular (median gap: {median_gap}d)"
        else:
            granularity = "unknown"

        return {
            **stat,
            "cv_global": round(coefficient_of_variation(all_quantities), 4),
            "granularity": granularity,
            "location_distribution": {
                k: round(v, 2) for k, v in sorted(
                    loc_distribution.items(), key=lambda x: -x[1]
                )
            },
            "total_revenue": round(
                sum(r.revenue or 0 for r in data.demand_history), 2
            ),
        }

    def _summarize_issues(self, validation: ValidationResult) -> dict:
        """Extract key issue counts from validation result."""
        missing = {}
        duplicates = 0
        outliers = []
        date_gaps = 0

        for issue in validation.issues:
            if issue.category == "coverage":
                missing[issue.field] = issue.affected_count
            elif issue.category == "duplicates":
                duplicates = issue.affected_count
            elif issue.category == "outliers":
                outliers.append({
                    "field": issue.details.get("sku_id", "unknown"),
                    "count": issue.affected_count,
                    "message": issue.message,
                })
            elif issue.category == "continuity":
                date_gaps += 1

        return {
            "missing": missing,
            "duplicates": duplicates,
            "outliers": outliers[:10],  # Limit to top 10
            "date_gaps": date_gaps,
        }

    def _generate_recommendations(
        self, validation: ValidationResult, data: SupplyMindData
    ) -> list[str]:
        """Generate actionable recommendations based on profiling results."""
        recs = []

        # Quality-based recommendations
        if validation.score < 50:
            recs.append("⚠️ 数据质量较低（评分 < 50），建议先清洗数据再进行预测。")
        elif validation.score < 75:
            recs.append("📊 数据质量中等，部分字段可能影响预测精度。")

        # Volume-based
        n = data.total_records
        if n < 30:
            recs.append(f"📉 数据量较少（{n} 条），预测结果置信度会偏低。")
        elif n < 90:
            recs.append(f"📊 数据量适中（{n} 条），建议至少积累 3 个月数据以获得更准确的季节性分析。")

        # Missing SKUs
        if validation.critical_count > 0:
            recs.append(f"🔴 发现 {validation.critical_count} 个严重问题需要修复后才能继续。")

        # Outliers
        outlier_issues = [i for i in validation.issues if i.category == "outliers"]
        if outlier_issues:
            count = sum(i.affected_count for i in outlier_issues)
            recs.append(f"📌 检测到约 {count} 个异常值，建议运行 demand-anomaly Skill 进行清洗。")

        # Date gaps
        gap_issues = [i for i in validation.issues if i.category == "continuity"]
        if gap_issues:
            recs.append("📅 发现日期断点，可能存在缺失日期的数据。")

        # Granularity suggestion
        stats = self._compute_global_stats(data)
        gran = stats.get("granularity", "")
        if gran == "irregular":
            recs.append("⏰ 数据时间粒度不规则，建议统一为日/周粒度。")
        elif gran == "daily" and n > 500:
            recs.append("💡 日粒度数据量充足，可尝试 Holt-Winters 季节性模型。")

        # Positive note
        if validation.score >= 85:
            recs.append("✅ 数据质量良好，可以直接进入预测流程。")

        return recs
