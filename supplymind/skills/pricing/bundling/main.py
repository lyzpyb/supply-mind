"""Pricing Bundling Skill — main implementation."""

from __future__ import annotations

import logging

from supplymind.core.pricing_models import recommend_bundles, BundleResult
from supplymind.skills.pricing.bundling.schema import (
    BundlingInput, BundlingOutput, BundleSuggestionSchema, TransactionRecord,
)

logger = logging.getLogger(__name__)


class PricingBundling:
    """Recommend product bundles based on co-purchase patterns.

    Uses association rule mining (support/confidence/lift metrics)
    to find complementary product pairs that sell well together.
    """

    def run(self, input_data: BundlingInput | dict) -> BundlingOutput:
        """Run bundle recommendation."""
        if isinstance(input_data, dict):
            params = BundlingInput(**input_data)
        else:
            params = input_data

        # Normalize transaction records
        txns = []
        for t in params.transactions:
            if isinstance(t, dict):
                txns.append(t)
            else:
                txns.append({"items": t.items, "revenue": t.revenue})

        result: BundleResult = recommend_bundles(
            transaction_data=txns,
            min_support=params.min_support,
            min_confidence=params.min_confidence,
            min_lift=params.min_lift,
            top_k=params.top_k,
        )

        suggestions = [
            BundleSuggestionSchema(
                main_sku_id=s.main_sku_id,
                complementary_sku_id=s.complementary_sku_id,
                lift_factor=s.lift_factor,
                bundle_discount_pct=s.bundle_discount_pct,
                expected_revenue_lift=s.expected_revenue_lift,
                confidence=s.confidence,
            )
            for s in result.suggestions
        ]

        return BundlingOutput(
            suggestions=suggestions,
            total_skus_analyzed=result.total_skus_analyzed,
            complementary_pairs_found=result.complementary_pairs_found,
            summary={
                "total_transactions": len(txns),
                "min_support": params.min_support,
                "min_confidence": params.min_confidence,
                "min_lift": params.min_lift,
                "top_k_returned": len(suggestions),
            },
        )
