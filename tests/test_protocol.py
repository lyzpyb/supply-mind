"""
Protocol (UDP) tests — validates schema, validators, and adapters.
"""

import os
import tempfile
from datetime import date

import numpy as np
import pandas as pd
import pytest

from supplymind.protocol.schema import (
    SKUMaster, DemandRecord, InventorySnapshot, LocationMaster,
    SupplyMindData,
)
from supplymind.protocol.validators import DataValidator, ValidationResult, Severity
from supplymind.protocol.adapter import (
    load_demand_from_csv, load_sku_master_from_csv, load_inventory_from_csv,
    load_dataset,
)


class TestSKUMaster:
    def test_create_sku(self):
        sku = SKUMaster(
            sku_id="TEST001",
            name="Test Product",
            category=["食品", "乳制品"],
            unit_cost=20.0,
            unit_price=35.0,
        )
        assert sku.sku_id == "TEST001"
        assert abs(sku.margin - 0.4286) < 0.01  # (35-20)/35

    def test_category_path(self):
        sku = SKUMaster(sku_id="S1", name="S1", category=["A", "B", "C"])
        assert sku.category_path == "A > B > C"

    def test_empty_category(self):
        sku = SKUMaster(sku_id="S1", name="S1")
        assert sku.category_path == "未分类"


class TestDemandRecord:
    def test_parse_date_string(self):
        r = DemandRecord(sku_id="S1", location_id="L1",
                         date="2026-03-15", quantity=42.5)
        assert r.demand_date == date(2026, 3, 15)
        assert r.quantity == 42.5


class TestInventorySnapshot:
    def test_derive_available(self):
        snap = InventorySnapshot(
            sku_id="S1", location_id="L1",
            date=date.today(), on_hand=100,
            allocated=30,
        )
        assert snap.available == 70.0

    def test_explicit_available(self):
        snap = InventorySnapshot(
            sku_id="S1", location_id="L1",
            date=date.today(), on_hand=100,
            available=50.0,
        )
        assert snap.available == 50.0


class TestSupplyMindData:
    @pytest.fixture
    def sample_data(self) -> SupplyMindData:
        data = SupplyMindData()
        data.sku_master.append(SKUMaster(sku_id="S1", name="SKU1"))
        data.sku_master.append(SKUMaster(sku_id="S2", name="SKU2"))

        for i in range(90):
            d = date(2026, 1, 1).__add__(__import__('datetime').timedelta(days=i))
            data.demand_history.append(
                DemandRecord(sku_id="S1", location_id="L1", date=d,
                             quantity=100 + i % 7 * 10 + np.random.randn() * 5)
            )

        return data

    def test_unique_skus(self, sample_data):
        assert len(sample_data.unique_skus) >= 1

    def test_get_sku(self, sample_data):
        sku = sample_data.get_sku("S1")
        assert sku is not None
        assert sku.name == "SKU1"

    def test_get_nonexistent_sku(self, sample_data):
        assert sample_data.get_sku("NONEXISTENT") is None

    def test_date_range(self, sample_data):
        dr = sample_data.date_range
        assert dr is not None
        assert dr[0] <= dr[1]

    def test_filter_demand(self, sample_data):
        records = sample_data.get_demand_for_sku("S1")
        assert len(records) > 0
        # All should be S1
        assert all(r.sku_id == "S1" for r in records)


class TestDataValidator:
    @pytest.fixture
    def good_data(self) -> SupplyMindData:
        data = SupplyMindData()
        for i in range(60):
            d = date(2026, 1, 1).__add__(__import__('datetime').timedelta(days=i))
            data.demand_history.append(
                DemandRecord(sku_id=f"S{i%3}", location_id="L1", date=d,
                             quantity=50 + (i % 10) * 3)
            )
        return data

    def test_valid_data_passes(self, good_data):
        validator = DataValidator(min_records=30)
        result = validator.validate(good_data)
        assert result.is_valid is True
        assert result.score > 50

    def test_insufficient_data_fails(self):
        data = SupplyMindData()
        for i in range(5):
            data.demand_history.append(
                DemandRecord(sku_id="S1", location_id="L1",
                             date=date(2026, 1, i+1), quantity=i*10)
            )
        validator = DataValidator(min_records=30)
        result = validator.validate(data)
        assert result.is_valid is True  # Still valid but low score
        assert any(i.severity == Severity.CRITICAL for i in result.issues)

    def test_to_dict_output(self, good_data):
        validator = DataValidator()
        result = validator.validate(good_data)
        d = result.to_dict()
        assert "is_valid" in d
        assert "score" in d
        assert "issues" in d


class TestAdapter:
    def test_load_demand_from_csv(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write("sku_id,location_id,date,quantity\n")
            f.write("S1,L1,2026-01-01,100\n")
            f.write("S1,L1,2026-01-02,120\n")
            tmp_path = f.name

        try:
            records = load_demand_from_csv(tmp_path)
            assert len(records) == 2
            assert records[0].sku_id == "S1"
            assert records[0].quantity == 100.0
        finally:
            os.unlink(tmp_path)

    def test_load_sku_master(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write("sku_id,name,category,unit_cost,unit_price,lead_time_days\n")
            f.write('MILK,全脂牛奶,"食品/乳制品",20,35,3\n')
            tmp_path = f.name

        try:
            skus = load_sku_master_from_csv(tmp_path)
            assert len(skus) == 1
            assert skus[0].sku_id == "MILK"
            assert skus[0].category == ["食品", "乳制品"]
        finally:
            os.unlink(tmp_path)

    def test_column_mapping_override(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write("product_code,store,sales_dt,volume\n")
            f.write("P1,S1,2026-03-15,50\n")
            tmp_path = f.name

        try:
            records = load_demand_from_csv(tmp_path, column_mapping={
                "sku_id": "product_code",
                "location_id": "store",
                "date": "sales_dt",
                "quantity": "volume",
            })
            assert len(records) == 1
            assert records[0].sku_id == "P1"
        finally:
            os.unlink(tmp_path)

    def test_load_dataset_combined(self):
        # Create temp files
        with tempfile.TemporaryDirectory() as tmpdir:
            demand_path = os.path.join(tmpdir, "demand.csv")
            sku_path = os.path.join(tmpdir, "skus.csv")

            with open(demand_path, 'w') as f:
                f.write("sku_id,location_id,date,quantity\nS1,L1,2026-01-01,100\n")

            with open(sku_path, 'w') as f:
                f.write("sku_id,name\nS1,Test SKU\n")

            data = load_dataset(demand_path=demand_path, sku_path=sku_path)
            assert len(data.demand_history) == 1
            assert len(data.sku_master) == 1
