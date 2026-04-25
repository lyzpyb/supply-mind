"""Pricing Elasticity Skill — main implementation."""

from __future__ import annotations

import logging
from datetime import date

from supplymind.core.pricing_models import estimate_elasticity, ElasticityResult
from supplymind.skills.pricing.elasticity.schema import ElasticityInput, ElasticityOutput

logger = logging.getLogger(__name__)


class PricingElasticity:
    """Estimate price elasticity from historical price-quantity data.

    Uses log-log OLS regression to estimate the constant-elasticity
    demand model: ln(Q) = α + β·ln(P)
    """

    def run(self, input_data: ElasticityInput | dict) -> ElasticityOutput:
        """Run elasticity estimation."""
        if isinstance(input_data, dict):
            params = ElasticityInput(**input_data)
        else:
            params = input_data

        result: ElasticityResult = estimate_elasticity(
            prices=params.prices,
            quantities=params.quantities,
        )

        # Generate human-readable interpretation
        interp = self._interpret(result)

        return ElasticityOutput(
            elasticity=result.elasticity,
            std_error=result.std_error,
            r_squared=result.r_squared,
            classification=result.classification,
            n_obs=result.n_obs,
            revenue_optimal_price=result.revenue_optimal_price,
            interpretation=interp,
        )

    @staticmethod
    def _interpret(r: ElasticityResult) -> str:
        """Generate business-friendly interpretation of results."""
        parts = [f"Elasticity = {r.elasticity:.3f} ({r.classification})"]
        parts.append(f"R² = {r.r_squared:.3f} (based on {r.n_obs} observations)")

        if r.elasticity < -1.5:
            parts.append("Demand is HIGHLY elastic — price changes significantly impact volume.")
            if r.revenue_optimal_price:
                parts.append(f"Revenue-maximizing price ≈ ${r.revenue_optimal_price:.2f}")
        elif r.elasticity < -0.5:
            parts.append("Demand is moderately elastic — pricing matters but not extremely.")
        elif r.elasticity >= -0.5 and r.elasticity < 0.5:
            parts.append("Demand is INELASTIC — customers are relatively price-insensitive.")
            parts.append("Consider raising prices to increase revenue.")
        else:
            parts.append("Unusual positive elasticity — may indicate Veblen/Giffen goods or data issues.")

        return " ".join(parts)
