"""
Dataset Registry — discover and load built-in and user datasets.

Provides a catalog of available datasets and a unified load interface.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATASETS_DIR = Path(__file__).resolve().parent.parent.parent / "datasets"

_BUILTIN_DATASETS: dict[str, dict[str, Any]] = {
    "retail_grocery": {
        "name": "Retail Grocery",
        "description": "450-row synthetic retail grocery dataset with 5 SKUs across 2 stores over 90 days",
        "dir": "retail_grocery",
        "files": {
            "demand": "sample_demand.csv",
            "sku_master": "sku_master.csv",
            "inventory": "inventory_snapshot.csv",
        },
        "domain": "retail",
        "sku_count": 5,
        "location_count": 2,
        "days": 90,
    },
}


def list_datasets() -> list[dict[str, Any]]:
    """List all available datasets (built-in + discovered)."""
    results = []
    for key, meta in _BUILTIN_DATASETS.items():
        ds_dir = DATASETS_DIR / meta["dir"]
        results.append({
            "id": key,
            "name": meta["name"],
            "description": meta["description"],
            "available": ds_dir.exists(),
            "domain": meta.get("domain", ""),
            "sku_count": meta.get("sku_count"),
            "location_count": meta.get("location_count"),
        })

    # Discover additional dataset directories
    if DATASETS_DIR.exists():
        for d in sorted(DATASETS_DIR.iterdir()):
            if d.is_dir() and d.name not in _BUILTIN_DATASETS:
                csv_files = list(d.glob("*.csv"))
                if csv_files:
                    results.append({
                        "id": d.name,
                        "name": d.name.replace("_", " ").title(),
                        "description": f"User dataset with {len(csv_files)} CSV files",
                        "available": True,
                        "domain": "custom",
                    })
    return results


def load_dataset(dataset_id: str) -> "SupplyMindData":
    """Load a dataset by ID into SupplyMindData.

    Args:
        dataset_id: Dataset identifier (e.g., "retail_grocery")

    Returns:
        SupplyMindData populated from the dataset files
    """
    from supplymind.protocol.adapter import load_dataset as _load

    meta = _BUILTIN_DATASETS.get(dataset_id)
    if meta:
        ds_dir = DATASETS_DIR / meta["dir"]
        files = meta["files"]
        return _load(
            demand_path=ds_dir / files["demand"] if "demand" in files else None,
            sku_path=ds_dir / files["sku_master"] if "sku_master" in files else None,
            inventory_path=ds_dir / files["inventory"] if "inventory" in files else None,
        )

    # Try as a directory name
    ds_dir = DATASETS_DIR / dataset_id
    if not ds_dir.exists():
        raise FileNotFoundError(f"Dataset '{dataset_id}' not found in {DATASETS_DIR}")

    demand = _find_file(ds_dir, ["demand", "sales", "sample_demand"])
    sku = _find_file(ds_dir, ["sku_master", "sku", "products", "items"])
    inventory = _find_file(ds_dir, ["inventory", "stock", "inventory_snapshot"])

    return _load(demand_path=demand, sku_path=sku, inventory_path=inventory)


def get_dataset_path(dataset_id: str) -> Path:
    """Get the directory path for a dataset."""
    meta = _BUILTIN_DATASETS.get(dataset_id)
    if meta:
        return DATASETS_DIR / meta["dir"]
    path = DATASETS_DIR / dataset_id
    if path.exists():
        return path
    raise FileNotFoundError(f"Dataset '{dataset_id}' not found")


def validate_dataset(dataset_id: str) -> dict[str, Any]:
    """Validate a dataset and return a quality report."""
    data = load_dataset(dataset_id)

    report = {
        "dataset_id": dataset_id,
        "demand_records": len(data.demand_history),
        "sku_count": len(data.sku_master),
        "inventory_snapshots": len(data.inventory_snapshots),
        "issues": [],
    }

    if not data.demand_history:
        report["issues"].append("No demand records found")
    else:
        skus = {r.sku_id for r in data.demand_history}
        report["demand_skus"] = len(skus)

        quantities = [r.quantity for r in data.demand_history]
        negatives = sum(1 for q in quantities if q < 0)
        if negatives:
            report["issues"].append(f"{negatives} negative quantities in demand data")

        zeros = sum(1 for q in quantities if q == 0)
        if zeros > len(quantities) * 0.5:
            report["issues"].append(f"High zero-demand ratio: {zeros}/{len(quantities)}")

    if data.sku_master:
        master_ids = {s.sku_id for s in data.sku_master}
        demand_ids = {r.sku_id for r in data.demand_history}
        orphan = demand_ids - master_ids
        if orphan:
            report["issues"].append(f"SKUs in demand but not in master: {orphan}")

    report["valid"] = len(report["issues"]) == 0
    return report


def _find_file(directory: Path, name_hints: list[str]) -> Path | None:
    for hint in name_hints:
        for f in directory.glob(f"*{hint}*.csv"):
            return f
    csvs = list(directory.glob("*.csv"))
    return csvs[0] if csvs else None
