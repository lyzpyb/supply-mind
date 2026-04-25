"""Fulfillment Allocation — main."""
from __future__ import annotations
from supplymind.core.fulfillment_models import allocate_inventory
from supplymind.skills.fulfillment.allocation.schema import (
    AllocationInput, AllocationOutput, OrderRecord, InventoryRecord,
)

class FulfillmentAllocation:
    def run(self, input_data: AllocationInput | dict) -> AllocationOutput:
        if isinstance(input_data, dict):
            params = AllocationInput(**input_data)
        else:
            params = input_data

        orders = [o if isinstance(o, OrderRecord) else OrderRecord(**o) for o in params.orders]
        inv = [i if isinstance(i, InventoryRecord) else InventoryRecord(**i) for i in params.inventory]

        result = allocate_inventory(
            orders=[o.model_dump() for o in orders],
            inventory=[i.model_dump() for i in inv],
            prioritize_service_level=params.prioritize_service_level,
        )

        return AllocationOutput(
            total_allocated=result.total_allocated,
            total_unmet=result.total_unmet,
            fulfillment_rate=result.fulfillment_rate,
            total_shipping_cost=result.total_shipping_cost,
            locations_used=result.locations_used,
            allocation_count=len(result.allocations),
            summary={"orders_processed": len(orders), "sku_locations": len(inv)},
        )
