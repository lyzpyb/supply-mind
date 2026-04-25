# Retail Grocery Dataset (零售超市示例数据集)

## 概述
模拟一家小型连锁超市 3 个月（2026-01-01 ~ 2026-03-31）的日销售数据。

## 文件说明
| 文件 | 说明 | 记录数 |
|------|------|--------|
| `sample_demand.csv` | 日销售明细 | ~900 条 |
| `sku_master.csv` | 商品主数据 | 5 SKU |
| `inventory_snapshot.csv` | 库存快照 | 10 条 |

## 数据特征
- **SKU 数量**: 5 个（牛奶、蔬菜、矿泉水、面包、鸡蛋）
- **门店数量**: 2 个（STORE_A, STORE_B）
- **时间跨度**: 90 天
- **季节性**: 周末促销效应明显
- **异常值**: 无人工注入，自然波动

## 使用方式

### CLI
```bash
supplymind data-profiler --input datasets/retail_grocery/sample_demand.csv
supplymind demand-forecast --input datasets/retail_grocery/sample_demand.csv --horizon 14
```

### Pipeline
```bash
supplymind run-pipeline pipelines/retail-replenish.yaml \
    --data datasets/retail_grocery/sample_demand.csv
```

### Python API
```python
from supplymind.protocol.adapter import load_dataset

data = load_dataset(
    demand_path="datasets/retail_grocery/sample_demand.csv",
    sku_path="datasets/retail_grocery/sku_master.csv",
    inventory_path="datasets/retail_grocery/inventory_snapshot.csv",
)
print(f"Loaded {len(data.demand_history)} records, {len(data.unique_skus)} SKUs")
```
