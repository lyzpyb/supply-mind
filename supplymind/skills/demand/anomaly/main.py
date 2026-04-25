"""
Demand Anomaly Detection Skill — main implementation.

Detects and handles outliers in demand history data.
Supports Z-score, IQR, and moving average methods.
"""

from __future__ import annotations

import logging
import numpy as np
from typing import Optional

from supplymind.core.statistics import (
    detect_outliers_zscore,
    detect_outliers_iqr,
    detect_anomalies_moving_avg,
)
from supplymind.skills.demand.anomaly.schema import (
    AnomalyInput, AnomalyOutput, SKUAnomalySummary, AnomalyRecord,
)

logger = logging.getLogger(__name__)


class DemandAnomaly:
    """Detect and clean anomalies in demand data."""

    def run(self, input_data: AnomalyInput | dict) -> AnomalyOutput:
        if isinstance(input_data, dict):
            params = AnomalyInput(**input_data)
        else:
            params = input_data

        demand_history = params.demand_history
        method = params.method if params.method != "auto" else "zscore"
        action = params.action

        # Group by SKU
        sku_groups: dict[str, list[dict]] = {}
        for r in demand_history:
            sku_id = r.get("sku_id", "")
            if sku_id not in sku_groups:
                sku_groups[sku_id] = []
            sku_groups[sku_id].append(r)

        all_cleaned: list[dict] = []
        per_sku: list[SKUAnomalySummary] = []
        total_removed = 0

        for sku_id, records in sorted(sku_groups.items()):
            quantities = np.array([r.get("quantity", 0) for r in records])

            # Detect anomalies
            if method == "zscore":
                result = detect_outliers_zscore(quantities.tolist(), params.threshold)
            elif method == "iqr":
                result = detect_outliers_iqr(quantities.tolist(), params.threshold)
            elif method == "moving_avg":
                result = detect_anomalies_moving_avg(quantities.tolist(), threshold_std=params.threshold)
            else:
                result = detect_outliers_zscore(quantities.tolist(), params.threshold)

            outlier_set = set(result.outlier_indices)

            # Build cleaned output and anomaly records
            anomaly_records: list[AnomalyRecord] = []
            cleaned_count = 0

            for i, record in enumerate(records):
                is_anomaly = i in outlier_set

                if is_anomaly and action == "remove":
                    total_removed += 1
                    anomaly_records.append(AnomalyRecord(
                        sku_id=sku_id,
                        location_id=record.get("location_id", ""),
                        date=str(record.get("date", "")),
                        original_value=record.get("quantity", 0),
                        cleaned_value=0.0,
                        z_score=round(float(abs(quantities[i] - np.mean(quantities)) / (np.std(quantities) + 1e-10)), 2),
                        method=method,
                    ))
                    continue

                # For "replace" or "flag": include with possibly modified value
                clean_val = record.get("quantity", 0)
                if is_anomaly and action == "replace":
                    # Replace with interpolated value (simple: use median of neighbors)
                    clean_val = float(np.median(quantities))

                if is_anomaly:
                    anomaly_records.append(AnomalyRecord(
                        sku_id=sku_id,
                        location_id=record.get("location_id", ""),
                        date=str(record.get("date", "")),
                        original_value=record.get("quantity", 0),
                        cleaned_value=round(clean_val, 2),
                        z_score=round(float(abs(quantities[i] - np.mean(quantities)) / (np.std(quantities) + 1e-10)), 2),
                        method=method,
                    ))

                new_record = dict(record)
                new_record["quantity"] = round(clean_val, 2) if is_anomaly and action == "replace" else clean_val
                all_cleaned.append(new_record)
                cleaned_count += 1

            per_sku.append(SKUAnomalySummary(
                sku_id=sku_id,
                total_records=len(records),
                anomaly_count=len(anomaly_records),
                anomaly_pct=round(len(anomaly_records) / max(len(records), 1) * 100, 1),
                anomalies=anomaly_records[:20],  # Limit stored anomalies
            ))

        return AnomalyOutput(
            cleaned_demand_history=all_cleaned,
            original_count=len(demand_history),
            removed_count=total_removed,
            per_sku_summary=per_sku,
            summary={
                "total_skus_affected": sum(1 for s in per_sku if s.anomaly_count > 0),
                "total_anomalies_found": sum(s.anomaly_count for s in per_sku),
                "method_used": method,
                "action_taken": action,
                "removal_rate": round(total_removed / max(len(demand_history), 1) * 100, 1),
            },
        )
