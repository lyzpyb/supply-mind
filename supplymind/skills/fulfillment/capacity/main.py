"""Fulfillment Capacity — main."""
from __future__ import annotations
from supplymind.core.fulfillment_models import check_capacity
from supplymind.skills.fulfillment.capacity.schema import (
    CapacityInput, CapacityOutput, CapacityCheckSchema, ResourceDef,
)

class FulfillmentCapacity:
    def run(self, input_data: CapacityInput | dict) -> CapacityOutput:
        if isinstance(input_data, dict):
            params = CapacityInput(**input_data)
        else:
            params = input_data

        resources = [r if isinstance(r, ResourceDef) else ResourceDef(**r) for r in params.resources]
        demand_dict = dict(params.demand) if params.demand else None

        result = check_capacity(
            resources=[r.model_dump() for r in resources],
            demand=demand_dict,
            utilization_threshold=params.utilization_threshold,
        )

        return CapacityOutput(
            resources=[
                CapacityCheckSchema(
                    resource_id=r.resource_id,
                    resource_name=r.resource_name,
                    capacity_total=r.capacity_total,
                    capacity_used=r.capacity_used,
                    utilization=r.utilization,
                    is_bottleneck=r.is_bottleneck,
                    slack=r.slack,
                )
                for r in result.resources
            ],
            bottlenecks=result.bottlenecks,
            overall_utilization=result.overall_utilization,
            can_fulfill=result.can_fulfill,
            recommendations=result.recommendations,
        )
