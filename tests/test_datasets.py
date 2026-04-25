"""Tests for dataset registry, loading, and validation."""

import pytest

from supplymind.datasets import list_datasets, load_dataset, validate_dataset, get_dataset_path


class TestDatasetRegistry:
    """Test dataset discovery and listing."""

    def test_list_datasets_includes_retail_grocery(self):
        datasets = list_datasets()
        ids = {d["id"] for d in datasets}
        assert "retail_grocery" in ids

    def test_list_datasets_has_required_fields(self):
        datasets = list_datasets()
        for ds in datasets:
            assert "id" in ds
            assert "name" in ds
            assert "description" in ds
            assert "available" in ds

    def test_retail_grocery_is_available(self):
        datasets = list_datasets()
        rg = next(d for d in datasets if d["id"] == "retail_grocery")
        assert rg["available"] is True
        assert rg["domain"] == "retail"


class TestDatasetLoading:
    """Test loading datasets into SupplyMindData."""

    def test_load_retail_grocery(self):
        data = load_dataset("retail_grocery")
        assert len(data.demand_history) > 0
        assert len(data.sku_master) > 0
        assert len(data.inventory_snapshots) > 0

    def test_load_retail_grocery_demand_records(self):
        data = load_dataset("retail_grocery")
        assert len(data.demand_history) >= 400
        skus = {r.sku_id for r in data.demand_history}
        assert len(skus) >= 3

    def test_load_retail_grocery_sku_master(self):
        data = load_dataset("retail_grocery")
        assert len(data.sku_master) >= 3
        sku_ids = {s.sku_id for s in data.sku_master}
        assert "SKU001" in sku_ids

    def test_load_retail_grocery_inventory(self):
        data = load_dataset("retail_grocery")
        assert len(data.inventory_snapshots) >= 3

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_dataset("nonexistent_dataset_xyz")

    def test_get_dataset_path(self):
        path = get_dataset_path("retail_grocery")
        assert path.exists()
        assert (path / "sample_demand.csv").exists()


class TestDatasetValidation:
    """Test dataset validation."""

    def test_validate_retail_grocery(self):
        report = validate_dataset("retail_grocery")
        assert report["dataset_id"] == "retail_grocery"
        assert report["demand_records"] > 0
        assert report["sku_count"] > 0
        assert report["valid"] is True

    def test_validate_returns_issue_details(self):
        report = validate_dataset("retail_grocery")
        assert "issues" in report
        assert isinstance(report["issues"], list)

    def test_validate_checks_sku_consistency(self):
        report = validate_dataset("retail_grocery")
        assert "demand_skus" in report
        assert report["demand_skus"] >= 3
