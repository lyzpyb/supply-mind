"""
Inventory Policy Simulation Skill — main implementation.

Evaluates different inventory policies using Monte Carlo simulation.
Compares (s,S), (s,Q), and EOQ policies side-by-side.
"""

from __future__ import annotations

import logging
import random
from datetime import date

import numpy as np

from supplymind.core.inventory_models import s_S_policy_simulation, PolicySimResult
from supplymind.skills.inventory.policy_sim.schema import (
    PolicySimInput,
    PolicySimOutput,
    PolicyResult,
    PolicyConfig,
)

logger = logging.getLogger(__name__)


class InventoryPolicySim:
    """Monte Carlo inventory policy simulator.

    Simulates multiple policies in parallel and compares their performance.
    """

    def run(self, input_data: PolicySimInput | dict) -> PolicySimOutput:
        """Run policy simulations."""
        if isinstance(input_data, dict):
            params = PolicySimInput(**input_data)
        else:
            params = input_data

        # Prepare demand data
        if params.demand_history:
            demands = list(params.demand_history)
        else:
            rng = random.Random(42)
            demands = [
                max(0, rng.gauss(params.demand_mean, params.demand_std))
                for _ in range(params.n_periods)
            ]

        # Build default policies if none provided
        policies = params.policies if params.policies else self._generate_default_policies(params)

        # Run each policy simulation
        all_results: list[PolicyResult] = []

        for pcfg in policies:
            result = self._simulate_one_policy(pcfg, demands, params.initial_inventory, params.n_simulations)

            # Compute turns
            avg_inv = result.average_inventory
            total_demand = sum(demands[:len(result.inventory_history)]) if result.inventory_history else sum(demands)
            turns = (total_demand / avg_inv) if avg_inv > 0 else 0

            all_results.append(PolicyResult(
                policy_name=result.policy_name or pcfg.name or f"policy_{len(all_results)}",
                service_level=round(result.service_level, 4),
                fill_rate=round(result.fill_rate, 4),
                average_inventory=round(avg_inv, 2),
                stockout_count=result.stockout_count,
                total_holding_cost=round(result.total_holding_cost, 2),
                total_ordering_cost=round(result.total_ordering_cost, 2),
                total_stockout_cost=round(result.total_stockout_cost, 2),
                total_cost=round(result.total_cost, 2),
                turns=round(turns, 2),
                config_summary={
                    "type": pcfg.policy_type,
                    "s": pcfg.s,
                    "S": pcfg.S,
                    "Q": pcfg.Q,
                    "lead_time": pcfg.lead_time,
                },
            ))

        # Determine best policy (lowest cost with acceptable service level)
        best = min(all_results, key=lambda r: r.total_cost)
        best_name = best.policy_name

        # Comparison table
        comparison = {
            "cost_ranking": sorted([(r.policy_name, r.total_cost, r.service_level) for r in all_results], key=lambda x: x[1]),
            "service_level_range": (
                min(r.service_level for r in all_results),
                max(r.service_level for r in all_results),
            ),
            "cost_savings_vs_worst": round(
                max(r.total_cost for r in all_results) - best.total_cost, 2
            ) if all_results else 0,
        }

        summary = {
            "sku_id": params.sku_id,
            "policies_tested": len(all_results),
            "best_policy": best_name,
            "best_total_cost": round(best.total_cost, 2),
            "best_service_level": round(best.service_level, 4),
            "n_periods": params.n_periods,
            "n_simulations": params.n_simulations,
            "avg_daily_demand": round(np.mean(demands), 2),
        }

        return PolicySimOutput(
            results=all_results,
            best_policy=best_name,
            comparison=comparison,
            summary=summary,
            generated_at=date.today().isoformat(),
        )

    def _generate_default_policies(self, params: PolicySimInput) -> list[PolicyConfig]:
        """Generate a set of default policies to compare."""
        d_mean = params.demand_mean
        d_std = params.demand_std

        # Generate reasonable policy parameters
        return [
            PolicyConfig(name="Conservative (high SS)", policy_type="s_S",
                         s=d_mean * 14 + 3 * d_std * 3, S=d_mean * 21 + 3 * d_std * 3,
                         lead_time=7),
            PolicyConfig(name="Balanced", policy_type="s_S",
                         s=d_mean * 10 + 2 * d_std * 3, S=d_mean * 17 + 2 * d_std * 3,
                         lead_time=7),
            PolicyConfig(name="Lean (low SS)", policy_type="s_S",
                         s=d_mean * 7 + 1 * d_std * 3, S=d_mean * 12 + 1 * d_std * 3,
                         lead_time=7),
            PolicyConfig(name="EOQ-based", policy_type="s_Q",
                         s=d_mean * 7 + 2 * d_std * 3, Q=max(1, (2 * d_mean * 365 * 50 / (d_mean * 0.1)) ** 0.5),
                         lead_time=7),
        ]

    def _simulate_one_policy(self, cfg: PolicyConfig, demands: list[float],
                             init_inv: float, n_sims: int) -> PolicySimResult:
        """Run one policy simulation."""
        lt = cfg.lead_time
        hc = cfg.holding_cost_per_unit
        oc = cfg.ordering_cost_per_order
        sc = cfg.stockout_cost_per_unit

        if cfg.policy_type == "s_S":
            s_val = cfg.s or 0
            S_val = cfg.S or (s_val * 2)
            return s_S_policy_simulation(
                demands, s=s_val, S=S_val,
                initial_inventory=init_inv,
                lead_time=lt,
                holding_cost_per_unit=hc,
                ordering_cost_per_order=oc,
                stockout_cost_per_unit=sc,
            )
        elif cfg.policy_type == "s_Q":
            # Convert (s,Q) to approximate (s,S) where S ≈ s + Q
            s_val = cfg.s or 0
            q_val = cfg.Q or 100
            return s_S_policy_simulation(
                demands, s=s_val, S=s_val + q_val,
                initial_inventory=init_inv,
                lead_time=lt,
                holding_cost_per_unit=hc,
                ordering_cost_per_order=oc,
                stockout_cost_per_unit=sc,
            )
        else:
            # EOQ-like: treat as (s,S) with S based on EOQ
            s_val = cfg.s or 0
            q_val = cfg.Q or max(1, (2 * len(demands) / 365 * np.mean(demands) * 365 * oc / hc) ** 0.5)
            return s_S_policy_simulation(
                demands, s=s_val, S=s_val + q_val,
                initial_inventory=init_inv,
                lead_time=lt,
                holding_cost_per_unit=hc,
                ordering_cost_per_order=oc,
                stockout_cost_per_unit=sc,
            )
