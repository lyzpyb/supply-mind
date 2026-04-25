"""Fulfillment Wave — main."""
from __future__ import annotations
from supplymind.core.fulfillment_models import plan_waves
from supplymind.skills.fulfillment.wave.schema import (
    WaveInput, WaveOutput, WaveBatchSchema, WaveConfig, OrderForWave,
)

class FulfillmentWave:
    def run(self, input_data: WaveInput | dict) -> WaveOutput:
        if isinstance(input_data, dict):
            params = WaveInput(**input_data)
        else:
            params = input_data

        config = params.config.model_dump() if params.config else None
        orders = [o if isinstance(o, OrderForWave) else OrderForWave(**o) for o in params.orders]

        result = plan_waves(
            orders=[o.model_dump() for o in orders],
            wave_config=config,
        )

        return WaveOutput(
            waves=[
                WaveBatchSchema(
                    wave_id=w.wave_id,
                    cutoff_time=w.cutoff_time,
                    orders_count=w.orders_count,
                    total_items=w.total_items,
                    estimated_pick_hours=w.estimated_pick_hours,
                    priority=w.priority,
                )
                for w in result.waves
            ],
            total_orders=result.total_orders,
            total_waves=result.total_waves,
            utilization_avg=result.utilization_avg,
            coverage_pct=result.coverage_pct,
        )
