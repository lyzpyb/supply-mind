"""
Pricing Skill Handlers — async bridges for pricing skills.

Covers: elasticity, markdown, lifecycle, bundling
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Price Elasticity ──────────────────────────────────────────────────────

PRICING_ELASTICITY_TOOL_SPEC = {
    "name": "pricing_elasticity",
    "description": (
        "Estimate price elasticity from historical sales data.\n\n"
        "Use this to understand how demand responds to price changes:\n"
        "- Estimates own-price elasticity (log-log regression)\n"
        "- Identifies elastic (price-sensitive) vs inelastic products\n"
        "- Provides revenue optimization guidance\n"
        "- Supports category-level and SKU-level analysis\n\n"
        "Requires historical data with price and quantity sold. "
        "Use BEFORE pricing_markdown to understand price sensitivity first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prices": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Historical prices (time-ordered)",
            },
            "quantities": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Quantities sold at each price point (same order as prices)",
            },
            "dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional dates for each observation (YYYY-MM-DD)",
            },
            "sku_id": {
                "type": "string",
                "description": "SKU identifier",
            },
            "method": {
                "type": "string",
                "enum": ["log_log", "linear", "percent"],
                "default": "log_log",
                "description": "Elasticity estimation method",
            },
        },
        "required": ["prices", "quantities"],
    },
}


async def pricing_elasticity_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for price elasticity tool."""
    try:
        from supplymind.skills.pricing.elasticity.main import PricingElasticity
        from supplymind.skills.pricing.elasticity.schema import ElasticityInput

        input_data = ElasticityInput(
            prices=arguments["prices"],
            quantities=arguments["quantities"],
            dates=arguments.get("dates"),
            sku_id=arguments.get("sku_id"),
            method=arguments.get("method", "log_log"),
        )

        skill = PricingElasticity()
        result = await _run_sync(skill.run, input_data)

        lines = ["# Price Elasticity Analysis", ""]
        if hasattr(result, 'elasticity'):
            e = result.elasticity
            label = "elastic" if abs(e) > 1 else "inelastic"
            lines.append(f"## Elasticity: **{e:.3f}** ({label})")
            lines.append("")
            if e < -1:
                lines.append("- **Revenue insight**: Price decrease → revenue increase (elastic)")
            elif e > -1:
                lines.append("- **Revenue insight**: Price increase → revenue increase (inelastic)")
        
        if hasattr(result, 'interpretation') and result.interpretation:
            lines.append(f"\n## Interpretation\n{result.interpretation}")
        
        if hasattr(result, 'optimal_price'):
            lines.append(f"\n## Suggested Optimal Price: **${result.optimal_price:.2f}**")

        if hasattr(result, 'model_dump'):
            lines.append("\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:2000] + "\n```")
        
        return "\n".join(lines), True

    except Exception as e:
        logger.error("Pricing elasticity error: %s", e, exc_info=True)
        return f"Pricing elasticity error: {e}", False


# ── Markdown / Clearance Pricing ──────────────────────────────────────────

PRICING_MARKDOWN_TOOL_SPEC = {
    "name": "pricing_markdown",
    "description": (
        "Optimize markdown/clearance pricing strategy.\n\n"
        "Use this for end-of-season or clearance events:\n"
        "- Calculates optimal markdown depth and timing\n"
        "- Maximizes revenue given remaining inventory and time horizon\n"
        "- Supports multi-phase markdown strategies\n"
        "- Accounts for inventory holding cost vs urgency to clear\n\n"
        "Use AFTER pricing_elasticity to get accurate elasticity estimates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "current_stock": {
                "type": "number",
                "description": "Units on hand to clear",
            },
            "unit_cost": {
                "type": "number",
                "description": "Per-unit cost",
            },
            "original_price": {
                "type": "number",
                "description": "Current/list price",
            },
            "days_remaining": {
                "type": "integer",
                "default": 30,
                "description": "Days until deadline",
            },
            "elasticity": {
                "type": "number",
                "description": "Price elasticity (from pricing_elasticity). Default: -1.5",
            },
        },
        "required": ["current_stock", "unit_cost", "original_price"],
    },
}


async def pricing_markdown_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for markdown pricing tool."""
    try:
        from supplymind.skills.pricing.markdown.main import PricingMarkdown
        from supplymind.skills.pricing.markdown.schema import MarkdownInput

        input_data = MarkdownInput(
            current_stock=arguments.get("inventory_remaining") or arguments.get("current_stock", 100),
            unit_cost=arguments.get("cost") or arguments.get("unit_cost", 5.0),
            original_price=arguments.get("current_price") or arguments.get("original_price", 20.0),
            days_remaining=arguments.get("days_left") or arguments.get("days_remaining", 30),
            elasticity=arguments.get("elasticity", -1.5),
        )

        skill = PricingMarkdown()
        result = await _run_sync(skill.run, input_data)

        lines = ["# Markdown Optimization", ""]
        if hasattr(result, 'optimal_markdown_price'):
            lines.append(f"## Optimal Markdown Price: **${result.optimal_markdown_price:.2f}**")
        if hasattr(result, 'markdown_percentage'):
            lines.append(f"## Markdown Depth: **{result.markdown_percentage:.1%}**")
        if hasattr(result, 'expected_revenue'):
            lines.append(f"## Expected Revenue: ${result.expected_revenue:,.2f}")
        if hasattr(result, 'model_dump'):
            lines.append("\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:2000] + "\n```")
        return "\n".join(lines), True

    except Exception as e:
        logger.error("Pricing markdown error: %s", e, exc_info=True)
        return f"Pricing markdown error: {e}", False


# ── Lifecycle Pricing ─────────────────────────────────────────────────────

PRICING_LIFECYCLE_TOOL_SPEC = {
    "name": "pricing_lifecycle",
    "description": (
        "Detect product lifecycle stage and recommend pricing strategy.\n\n"
        "Use this to align pricing with product maturity:\n"
        "- Detects stage: introduction, growth, maturity, decline\n"
        "- Recommends stage-appropriate pricing (skimming, penetration, premium, value)\n"
        "- Uses sales trend data to identify inflection points\n"
        "- Suggests timing for price transitions\n\n"
        "Works well combined with pricing_elasticity for data-driven recommendations."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sales_history": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Time-ordered sales volumes (or revenues) per period",
            },
            "price_history": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Time-ordered prices (optional but recommended)",
            },
            "period_dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Dates for each period (YYYY-MM-DD)",
            },
            "product_category": {
                "type": "string",
                "description": "Product category for benchmark comparison",
            },
        },
        "required": ["sales_history"],
    },
}


async def pricing_lifecycle_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for lifecycle detection tool."""
    try:
        from supplymind.skills.pricing.lifecycle.main import PricingLifecycle
        from supplymind.skills.pricing.lifecycle.schema import LifecycleInput

        # Filter None values and map field names to match schema
        clean_args = {k: v for k, v in arguments.items() if v is not None}
        
        input_data = LifecycleInput(
            weekly_sales=clean_args.get("sales_history") or clean_args.get("weekly_sales", []),
            price_history=clean_args.get("price_history"),
            product_category=clean_args.get("product_category") or clean_args.get("category"),
        )

        skill = PricingLifecycle()
        result = await _run_sync(skill.run, input_data)

        lines = ["# Product Lifecycle Analysis", ""]
        if hasattr(result, 'stage'):
            lines.append(f"## Current Stage: **{result.stage.upper()}**")
        if hasattr(result, 'stage_confidence'):
            lines.append(f"Confidence: {result.stage_confidence:.0%}")
        if hasattr(result, 'pricing_recommendation') and result.pricing_recommendation:
            lines.append(f"\n## Pricing Recommendation\n{result.pricing_recommendation}")
        if hasattr(result, 'model_dump'):
            lines.append("\n```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:2000] + "\n```")
        return "\n".join(lines), True

    except Exception as e:
        logger.error("Pricing lifecycle error: %s", e, exc_info=True)
        return f"Pricing lifecycle error: {e}", False


# ── Bundle Recommendation ─────────────────────────────────────────────────

PRICING_BUNDLING_TOOL_SPEC = {
    "name": "pricing_bundling",
    "description": (
        "Recommend product bundles and bundle pricing.\n\n"
        "Use this to increase basket size and margin through bundling:\n"
        "- Analyzes transaction data to find frequently co-purchased items\n"
        "- Suggests optimal product bundles based on affinity\n"
        "- Calculates bundle pricing (discount vs pure-additive)\n"
        "- Estimates revenue lift from bundle introduction\n\n"
        "Requires transaction/basket data or product affinity matrix."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "transactions": {
                "type": "array",
                "items": {"type": "array"},
                "items": {"type": "string"},
                "description": "List of transactions/baskets. Each transaction is a list of SKU IDs purchased together.",
            },
            "sku_prices": {
                "type": "object",
                "description": "Current prices per SKU: {sku_id: price}",
            },
            "max_bundle_size": {
                "type": "integer",
                "default": 3,
                "description": "Maximum number of items per bundle (default: 3)",
            },
            "target_margin": {
                "type": "number",
                "default": 0.25,
                "description": "Target bundle margin (default: 25%)",
            },
        },
        "required": ["transactions", "sku_prices"],
    },
}


async def pricing_bundling_handler(arguments: dict[str, Any]) -> tuple[str, bool]:
    """Handler for bundling recommendation tool."""
    try:
        from supplymind.skills.pricing.bundling.main import PricingBundling
        from supplymind.skills.pricing.bundling.schema import BundlingInput

        input_data = BundlingInput(
            transactions=arguments["transactions"],
            sku_prices=arguments["sku_prices"],
            max_bundle_size=arguments.get("max_bundle_size", 3),
            target_margin=arguments.get("target_margin", 0.25),
        )

        skill = PricingBundling()
        result = await _run_sync(skill.run, input_data)

        lines = ["# Bundle Recommendations", ""]
        if hasattr(result, 'bundles') and result.bundles:
            lines.append("## Recommended Bundles")
            for i, b in enumerate(result.bundles[:10], 1):
                b_dict = b.model_dump() if hasattr(b, 'model_dump') else dict(b)
                skus = b_dict.get('skus', b_dict.get('items', []))
                price = b_dict.get('bundle_price', b_dict.get('price', 'N/A'))
                savings = b_dict.get('customer_savings_pct', b_dict.get('savings', 'N/A'))
                lines.append(f"### Bundle {i}: {skus}")
                lines.append(f"- Bundle Price: ${price}")
                if isinstance(savings, (int, float)):
                    lines.append(f"- Customer Savings: {savings:.1%}")
                lines.append("")
        
        if hasattr(result, 'model_dump'):
            lines.append("```json\n" + json.dumps(result.model_dump(), indent=2, default=str)[:3000] + "\n```")
        return "\n".join(lines), True

    except Exception as e:
        logger.error("Pricing bundling error: %s", e, exc_info=True)
        return f"Pricing bundling error: {e}", False


# ── Utility ────────────────────────────────────────────────────────────────

async def _run_sync(func, *args, **kwargs):
    """Run sync function in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
