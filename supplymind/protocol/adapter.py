"""
Data adapter — load external data (CSV, JSON, DataFrame) into UDP Schema.

Provides utility functions to convert raw data files into SupplyMindData.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from supplymind.protocol.schema import (
    DemandRecord,
    InventorySnapshot,
    LocationMaster,
    SKUMaster,
    SupplyMindData,
)


# Standard column name mappings for common formats
DEFAULT_DEMAND_COLUMNS = {
    "sku_id": ["sku_id", "sku", "product_id", "item_id", "material", "商品编码"],
    "location_id": ["location_id", "location", "store", "warehouse", "dc", "门店", "仓库"],
    "date": ["date", "日期", "sales_date", "order_date", "dt"],
    "quantity": ["quantity", "qty", "销量", "sales_qty", "demand", "amount", "数量"],
    "revenue": ["revenue", "销售额", "sales_amount", "收入"],
    "is_promo": ["is_promo", "promo", "促销", "promotion_flag"],
}

DEFAULT_SKU_COLUMNS = {
    "sku_id": ["sku_id", "sku", "product_id", "item_id", "material", "商品编码"],
    "name": ["name", "product_name", "item_name", "description", "品名", "商品名称"],
    "category": ["category", "cat", "分类", "品类", "category_path"],
    "unit": ["unit", "uom", "单位"],
    "unit_cost": ["unit_cost", "cost", "成本", "采购价"],
    "unit_price": ["unit_price", "price", "售价", "零售价"],
    "shelf_life_days": ["shelf_life_days", "shelf_life", "保质期"],
    "lead_time_days": ["lead_time_days", "lead_time", "提前期"],
    "moq": ["moq", "min_order_qty", "最小起订量"],
}

DEFAULT_INVENTORY_COLUMNS = {
    "sku_id": ["sku_id", "sku", "product_id", "item_id", "material", "商品编码"],
    "location_id": ["location_id", "location", "store", "warehouse", "dc", "仓库"],
    "date": ["date", "日期", "snapshot_date"],
    "on_hand": ["on_hand", "stock", "inventory", "在手库存", "库存量"],
    "in_transit": ["in_transit", "transit", "在途", "在途库存"],
    "allocated": ["allocated", "reserved", "已分配", "占用"],
}


def _find_column(df: pd.DataFrame, mapping: dict[str, list[str]], target: str) -> Optional[str]:
    """Find the actual column name in df that matches a target field."""
    candidates = mapping.get(target, [])
    # Exact match first
    lower_cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_cols:
            return lower_cols[cand.lower()]
    return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert to float."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int | None = None) -> Optional[int]:
    """Safely convert to int."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _safe_bool(value: Any) -> Optional[bool]:
    """Safely convert to bool."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in ("true", "1", "yes", "y", "是"):
            return True
        if lower in ("false", "0", "no", "n", "否", ""):
            return False
    return None


def load_demand_from_csv(
    path: str | Path,
    column_mapping: dict[str, str] | None = None,
    encoding: str = "utf-8",
) -> list[DemandRecord]:
    """Load demand history from CSV file into DemandRecord list.

    Args:
        path: Path to CSV file
        column_mapping: Manual override of {target_field: actual_column_name}
        encoding: File encoding

    Returns:
        List of DemandRecord objects
    """
    df = pd.read_csv(path, encoding=encoding)

    mapping = column_mapping or {}
    records = []

    for _, row in df.iterrows():
        sku_col = mapping.get("sku_id") or _find_column(df, DEFAULT_DEMAND_COLUMNS, "sku_id")
        loc_col = mapping.get("location_id") or _find_column(df, DEFAULT_DEMAND_COLUMNS, "location_id")
        date_col = mapping.get("date") or _find_column(df, DEFAULT_DEMAND_COLUMNS, "date")
        qty_col = mapping.get("quantity") or _find_column(df, DEFAULT_DEMAND_COLUMNS, "quantity")

        if not all([sku_col, loc_col, date_col, qty_col]):
            continue

        rev_col = mapping.get("revenue") or _find_column(df, DEFAULT_DEMAND_COLUMNS, "revenue")
        promo_col = mapping.get("is_promo") or _find_column(df, DEFAULT_DEMAND_COLUMNS, "is_promo")

        try:
            record = DemandRecord(
                sku_id=str(row[sku_col]).strip(),
                location_id=str(row[loc_col]).strip(),
                demand_date=pd.to_datetime(row[date_col]).date(),
                quantity=_safe_float(row[qty_col]),
                revenue=_safe_float(row.get(rev_col, None)) if rev_col else None,
                is_promo=_safe_bool(row.get(promo_col, None)) if promo_col else None,
            )
            records.append(record)
        except (ValueError, KeyError, TypeError):
            continue

    return records


def load_sku_master_from_csv(
    path: str | Path,
    column_mapping: dict[str, str] | None = None,
    encoding: str = "utf-8",
) -> list[SKUMaster]:
    """Load SKU master data from CSV file.

    Args:
        path: Path to CSV file
        column_mapping: Manual column name override
        encoding: File encoding

    Returns:
        List of SKUMaster objects
    """
    df = pd.read_csv(path, encoding=encoding)
    mapping = column_mapping or {}
    skus = []

    for _, row in df.iterrows():
        id_col = mapping.get("sku_id") or _find_column(df, DEFAULT_SKU_COLUMNS, "sku_id")
        name_col = mapping.get("name") or _find_column(df, DEFAULT_SKU_COLUMNS, "name")
        if not id_col or not name_col:
            continue

        cat_col = mapping.get("category") or _find_column(df, DEFAULT_SKU_COLUMNS, "category")
        unit_col = mapping.get("unit") or _find_column(df, DEFAULT_SKU_COLUMNS, "unit")
        cost_col = mapping.get("unit_cost") or _find_column(df, DEFAULT_SKU_COLUMNS, "unit_cost")
        price_col = mapping.get("unit_price") or _find_column(df, DEFAULT_SKU_COLUMNS, "unit_price")
        shelf_col = mapping.get("shelf_life_days") or _find_column(df, DEFAULT_SKU_COLUMNS, "shelf_life_days")
        lead_col = mapping.get("lead_time_days") or _find_column(df, DEFAULT_SKU_COLUMNS, "lead_time_days")
        moq_col = mapping.get("moq") or _find_column(df, DEFAULT_SKU_COLUMNS, "moq")

        # Parse category as list
        cat_raw = row.get(cat_col, "") if cat_col else ""
        if isinstance(cat_raw, str) and cat_raw.strip():
            category = [c.strip() for c in str(cat_raw).replace("/", "|").split("|") if c.strip()]
        elif isinstance(cat_raw, str):
            category = [cat_raw.strip()] if cat_raw.strip() else []
        else:
            category = []

        try:
            sku = SKUMaster(
                sku_id=str(row[id_col]).strip(),
                name=str(row[name_col]).strip(),
                category=category,
                unit=str(row[unit_col]) if unit_col and pd.notna(row.get(unit_col)) else "件",
                unit_cost=_safe_float(row.get(cost_col, 0)) if cost_col else 0.0,
                unit_price=_safe_float(row.get(price_col, 0)) if price_col else 0.0,
                shelf_life_days=_safe_int(row.get(shelf_col, None)) if shelf_col else None,
                lead_time_days=_safe_float(row.get(lead_col, 7.0)) if lead_col else 7.0,
                moq=_safe_float(row.get(moq_col, None)) if moq_col else None,
            )
            skus.append(sku)
        except (ValueError, KeyError, TypeError):
            continue

    return skus


def load_inventory_from_csv(
    path: str | Path,
    column_mapping: dict[str, str] | None = None,
    encoding: str = "utf-8",
) -> list[InventorySnapshot]:
    """Load inventory snapshots from CSV file.

    Args:
        path: Path to CSV file
        column_mapping: Manual column name override
        encoding: File encoding

    Returns:
        List of InventorySnapshot objects
    """
    df = pd.read_csv(path, encoding=encoding)
    mapping = column_mapping or {}
    snapshots = []

    for _, row in df.iterrows():
        sku_col = mapping.get("sku_id") or _find_column(df, DEFAULT_INVENTORY_COLUMNS, "sku_id")
        loc_col = mapping.get("location_id") or _find_column(df, DEFAULT_INVENTORY_COLUMNS, "location_id")
        date_col = mapping.get("date") or _find_column(df, DEFAULT_INVENTORY_COLUMNS, "date")
        onhand_col = mapping.get("on_hand") or _find_column(df, DEFAULT_INVENTORY_COLUMNS, "on_hand")

        if not all([sku_col, loc_col, date_col, onhand_col]):
            continue

        transit_col = mapping.get("in_transit") or _find_column(df, DEFAULT_INVENTORY_COLUMNS, "in_transit")
        alloc_col = mapping.get("allocated") or _find_column(df, DEFAULT_INVENTORY_COLUMNS, "allocated")

        try:
            snap = InventorySnapshot(
                sku_id=str(row[sku_col]).strip(),
                location_id=str(row[loc_col]).strip(),
                snapshot_date=pd.to_datetime(row[date_col]).date(),
                on_hand=_safe_float(row[onhand_col]),
                in_transit=_safe_float(row.get(transit_col, None)) if transit_col else None,
                allocated=_safe_float(row.get(alloc_col, None)) if alloc_col else None,
            )
            snapshots.append(snap)
        except (ValueError, KeyError, TypeError):
            continue

    return snapshots


def load_dataset(
    demand_path: str | Path | None = None,
    sku_path: str | Path | None = None,
    inventory_path: str | Path | None = None,
    location_path: str | Path | None = None,
    demand_columns: dict[str, str] | None = None,
    sku_columns: dict[str, str] | None = None,
    inventory_columns: dict[str, str] | None = None,
) -> SupplyMindData:
    """Load a complete dataset from CSV files into SupplyMindData.

    Args:
        demand_path: Path to demand history CSV
        sku_path: Path to SKU master CSV
        inventory_path: Path to inventory snapshot CSV
        location_path: Path to locations CSV
        demand_columns: Column mapping override for demand data
        sku_columns: Column mapping override for SKU master
        inventory_columns: Column mapping override for inventory data

    Returns:
        Fully populated SupplyMindData object
    """
    data = SupplyMindData()

    if demand_path and os.path.exists(demand_path):
        data.demand_history = load_demand_from_csv(demand_path, demand_columns)

    if sku_path and os.path.exists(sku_path):
        data.sku_master = load_sku_master_from_csv(sku_path, sku_columns)

    if inventory_path and os.path.exists(inventory_path):
        data.inventory_snapshots = load_inventory_from_csv(inventory_path, inventory_columns)

    return data


def dataframe_to_demand_records(df: pd.DataFrame, column_mapping: dict[str, str] | None = None) -> list[DemandRecord]:
    """Convert a pandas DataFrame to DemandRecord list.

    This is useful when data is already loaded in memory.
    """
    # Write to temp CSV then use loader (simple but effective)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        df.to_csv(f, index=False)
        tmp_path = f.name
    try:
        return load_demand_from_csv(tmp_path, column_mapping)
    finally:
        os.unlink(tmp_path)
