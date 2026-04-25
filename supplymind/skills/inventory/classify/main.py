"""
Inventory ABC-XYZ Classification Skill — main implementation.
"""

from __future__ import annotations

import logging
from supplymind.core.classification import abc_analysis, xyz_classification, abc_xyz_matrix
from supplymind.skills.inventory.classify.schema import (
    ClassifyInput, ClassifyOutput, MatrixCell,
)

logger = logging.getLogger(__name__)


class InventoryClassify:
    """ABC-XYZ classification for inventory strategy decisions."""

    def run(self, input_data: ClassifyInput | dict) -> ClassifyOutput:
        if isinstance(input_data, dict):
            params = ClassifyInput(**input_data)
        else:
            params = input_data

        items = params.items
        if not items:
            return ClassifyOutput(
                summary={"error": "No items provided for classification"}
            )

        # Run combined ABC-XYZ matrix
        result = abc_xyz_matrix(
            items=items,
            value_key=params.value_key,
            values_key=params.values_key,
            a_threshold=params.a_threshold,
            b_threshold=params.b_threshold,
            cv_x=params.cv_x,
            cv_y=params.cv_y,
        )

        # Convert to output format
        abc_dict = {
            "class_a": result.abc_result.class_a,
            "class_b": result.abc_result.class_b,
            "class_c": result.abc_result.class_c,
            "total_value": result.abc_result.total_value,
            "thresholds": result.abc_result.thresholds,
            "items": [
                {"item_id": item.item_id, "value": item.value,
                 "cumulative_pct": item.cumulative_pct, "class_label": item.class_label}
                for item in result.abc_result.items
            ],
        }

        xyz_dict = {
            "class_x": result.xyz_result.class_x,
            "class_y": result.xyz_result.class_y,
            "class_z": result.xyz_result.class_z,
            "items": [
                {"item_id": item.item_id, "cv": item.cv, "class_label": item.class_label}
                for item in result.xyz_result.items
            ],
        }

        matrix_dict: dict[str, MatrixCell] = {}
        for label, cell in result.matrix.items():
            matrix_dict[label] = MatrixCell(
                label=cell.label,
                item_ids=cell.item_ids,
                count=cell.count,
                total_value=round(cell.total_value, 2),
                strategy=cell.strategy,
            )

        return ClassifyOutput(
            abc_result=abc_dict,
            xyz_result=xyz_dict,
            matrix=matrix_dict,
            summary=result.summary,
        )
