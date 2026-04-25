"""What-If Skill — main implementation."""

from __future__ import annotations

import logging
import copy
from datetime import date

from supplymind.skills.common.what_if.schema import (
    WhatIfInput, WhatIfOutput, ScenarioResult, ScenarioDef,
)

logger = logging.getLogger(__name__)


class WhatIfSimulator:
    """Multi-scenario simulation and comparison engine.

    Runs the same underlying skill with different parameter sets,
    producing a side-by-side comparison of outcomes.
    """

    def run(self, input_data: WhatIfInput | dict) -> WhatIfOutput:
        """Run what-if analysis across multiple scenarios."""
        if isinstance(input_data, dict):
            params = WhatIfInput(**input_data)
        else:
            params = input_data

        base = dict(params.base_params)
        scenarios_raw = [
            s if isinstance(s, ScenarioDef) else ScenarioDef(**s)
            for s in params.scenarios
        ]

        # Run baseline (base_params only)
        baseline_result = self._run_skill(base, params.skill_name)
        baseline_metrics = self._extract_metrics(baseline_result, params.compare_metrics)

        # Run each scenario
        scenario_results: list[ScenarioResult] = []
        for sc in scenarios_raw:
            merged = {**base, **sc.params}
            raw = self._run_skill(merged, params.skill_name)
            metrics = self._extract_metrics(raw, params.compare_metrics)

            # Compute diff from baseline
            diff_pct = {}
            for m in params.compare_metrics:
                b_val = baseline_metrics.get(m)
                s_val = metrics.get(m)
                if b_val is not None and s_val is not None and b_val != 0:
                    diff_pct[m] = round((s_val - b_val) / abs(b_val) * 100, 2)

            scenario_results.append(ScenarioResult(
                scenario_name=sc.name,
                metrics=metrics,
                raw_output=raw,
                vs_baseline_diff_pct=diff_pct,
            ))

        # Determine best scenario based on first metric (lower is better for cost-type)
        best_name = self._pick_best(scenario_results, params.compare_metrics)
        recommendation = self._generate_recommendation(best_name, scenario_results, params.compare_metrics)

        # Build comparison table
        comp_table = []
        row = {"scenario": "BASELINE", **{f"baseline_{k}": v for k, v in baseline_metrics.items()}}
        comp_table.append(row)
        for sr in scenario_results:
            row = {
                "scenario": sr.scenario_name,
                **sr.metrics,
                **{f"vs_base_{k}%": v for k, v in sr.vs_baseline_diff_pct.items()},
            }
            comp_table.append(row)

        return WhatIfOutput(
            baseline=baseline_metrics,
            scenarios=scenario_results,
            best_scenario=best_name,
            recommendation=recommendation,
            comparison_table=comp_table,
        )

    @staticmethod
    def _run_skill(params: dict, skill_name: str) -> dict:
        """Run a skill with given parameters and return output as dict."""
        try:
            # Dynamic skill dispatch
            skill_map = {
                "inventory-policy-sim": ("supplymind.skills.inventory.policy_sim.main", "InventoryPolicySim", "PolicySimInput"),
                "inventory-newsvendor": ("supplymind.skills.inventory.newsvendor.main", "NewsvendorPricing", "NewsvendorInput"),
                "inventory-safety-stock": ("supplymind.skills.inventory.safety_stock.main", "SafetyStockCalculator", "SafetyStockInput"),
                "demand-forecast": ("supplymind.skills.demand.forecast.main", "DemandForecast", "ForecastInput"),
                "pricing-markdown": ("supplymind.skills.pricing.markdown.main", "PricingMarkdown", "MarkdownInput"),
                "pricing-elasticity": ("supplymind.skills.pricing.elasticity.main", "PricingElasticity", "ElasticityInput"),
            }

            if skill_name not in skill_map:
                return {"error": f"Unknown skill: {skill_name}", "params_used": params}

            mod_path, cls_name, input_cls_name = skill_map[skill_name]
            import importlib
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, cls_name)
            input_cls = getattr(importlib.import_module(mod_path.replace(".main", ".schema")), input_cls_name)

            instance = cls()
            result = instance.run(input_cls(**params))
            return result.model_dump() if hasattr(result, "model_dump") else dict(result)

        except Exception as e:
            logger.warning(f"What-If skill run failed for {skill_name}: {e}")
            return {"error": str(e), "params_used": params}

    @staticmethod
    def _extract_metrics(raw_output: dict, metric_keys: list[str]) -> dict:
        """Extract relevant metrics from raw skill output."""
        metrics = {}
        for key in metric_keys:
            # Try direct key, then nested search
            if key in raw_output:
                metrics[key] = raw_output[key]
            else:
                # Flat search for partial match
                for k, v in raw_output.items():
                    if key.lower().replace("_", "") == k.lower().replace("_", ""):
                        metrics[key] = v
                        break
                if key not in metrics and isinstance(raw_output, dict):
                    # Recurse one level
                    for v in raw_output.values():
                        if isinstance(v, dict) and key in v:
                            metrics[key] = v[key]
                            break
        return metrics

    @staticmethod
    def _pick_best(scenario_results: list[ScenarioResult], metric_keys: list[str]) -> str:
        """Pick best scenario (minimize first cost-like metric)."""
        if not scenario_results:
            return ""

        primary = metric_keys[0] if metric_keys else None
        if not primary:
            return scenario_results[0].scenario_name

        best = min(scenario_results, key=lambda s: s.metrics.get(primary, float('inf')))
        return best.scenario_name

    @staticmethod
    def _generate_recommendation(best_name: str, results: list[ScenarioResult], keys: list[str]) -> str:
        """Generate natural language recommendation."""
        if not best_name or not results:
            return "Insufficient data for recommendation."

        best = next((r for r in results if r.scenario_name == best_name), None)
        if not best:
            return f"Recommended scenario: {best_name}"

        parts = [f"Best scenario: '{best_name}'"]
        for k in keys[:3]:
            val = best.metrics.get(k)
            diff = best.vs_baseline_diff_pct.get(k)
            if val is not None:
                suffix = f" ({diff:+.1f}% vs baseline)" if diff is not None else ""
                parts.append(f"  → {k}: {val}{suffix}")

        return "\n".join(parts)
