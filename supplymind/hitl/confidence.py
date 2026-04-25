"""
HITL Confidence Scorer — assess confidence level for decision routing.

Determines whether a decision should be auto, review, or collaborate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceResult:
    score: float  # 0.0 - 1.0
    factors: dict
    recommended_level: str = "auto"  # auto, review, collaborate


class ConfidenceScorer:
    """Calculate decision confidence based on multiple factors."""

    def __init__(
        self,
        auto_threshold: float = 0.90,
        review_threshold: float = 0.60,
    ):
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold

    def score(
        self,
        model_mape: float | None = None,
        data_completeness: float = 1.0,
        historical_accuracy: float | None = None,
        is_new_scenario: bool = False,
        financial_impact: float = 0.0,
        has_anomalies: bool = False,
        extra_factors: dict | None = None,
    ) -> ConfidenceResult:
        """Compute overall confidence score.

        Args:
            model_mape: MAPE of the prediction model (lower is better)
            data_completeness: How complete the input data is (0-1)
            historical_accuracy: Past accuracy of similar decisions (0-1)
            is_new_scenario: Whether this is a new/unseen scenario
            financial_impact: Estimated monetary impact of the decision
            has_anomalies: Whether anomalies were detected in input

        Returns:
            ConfidenceResult with score and recommended HITL level
        """
        factors: dict[str, float] = {}
        weight_total = 0.0
        weighted_score = 0.0

        # Factor 1: Model quality (weight: 0.30)
        if model_mape is not None:
            # MAPE < 10% → full credit, > 50% → zero
            model_score = max(0, 1.0 - model_mape / 50.0)
            factors["model_quality"] = round(model_score, 3)
            weighted_score += model_score * 0.30
            weight_total += 0.30

        # Factor 2: Data completeness (weight: 0.20)
        factors["data_completeness"] = round(data_completeness, 3)
        weighted_score += data_completeness * 0.20
        weight_total += 0.20

        # Factor 3: Historical track record (weight: 0.20)
        if historical_accuracy is not None:
            factors["historical_accuracy"] = round(historical_accuracy, 3)
            weighted_score += historical_accuracy * 0.20
            weight_total += 0.20

        # Factor 4: Scenario familiarity (weight: 0.15)
        scenario_score = 0.0 if is_new_scenario else 0.8
        factors["scenario_familiarity"] = scenario_score
        weighted_score += scenario_score * 0.15
        weight_total += 0.15

        # Factor 5: Financial impact penalty (weight: 0.10)
        # High impact → lower confidence (more human oversight needed)
        impact_penalty = min(0.5, financial_impact / 1_000_000)  # Per million yuan
        impact_score = max(0, 1.0 - impact_penalty)
        factors["financial_impact"] = round(impact_score, 3)
        weighted_score += impact_score * 0.10
        weight_total += 0.10

        # Factor 6: Anomaly presence (weight: 0.05)
        anomaly_score = 0.3 if has_anomalies else 1.0
        factors["anomaly_free"] = anomaly_score
        weighted_score += anomaly_score * 0.05
        weight_total += 0.05

        # Extra factors
        if extra_factors:
            for k, v in extra_factors.items():
                if isinstance(v, (int, float)):
                    factors[f"extra_{k}"] = v
                    weighted_score += v * 0.02
                    weight_total += 0.02

        # Normalize
        final_score = weighted_score / weight_total if weight_total > 0 else 0.5
        final_score = max(0.0, min(1.0, final_score))

        # Determine recommended level
        if final_score >= self.auto_threshold:
            level = "auto"
        elif final_score >= self.review_threshold:
            level = "review"
        else:
            level = "collaborate"

        return ConfidenceResult(
            score=round(final_score, 3),
            factors=factors,
            recommended_level=level,
        )
