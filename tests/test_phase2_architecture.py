"""
Phase 2 架构升级自动化测试套件
验证以下核心架构服务：
1. StorageEngine 嵌入式 SQLite 存储引擎 (零外部依赖，标准模型表初始化与 Upsert)
2. MasterCatalogService 统一 SKU 产品中心 (商品注册、跨平台 ID 映射、秒级归一化解析)
3. AdapterService 跨平台表格适配器 (Walmart / Amazon 表格解析与 CDM 转换，归因周期支持)
4. SemanticMetricService 统一语义指标服务 (GMV 与广告归因隔离、TACoS、保本 ACoS、严肃利润核算)
5. UnifiedBusinessQueryService 统一业务数据查询服务 (全局筛选管道贯通)
6. 多租户平台与店铺数据隔离测试
"""

import unittest
import pandas as pd
from services.storage_engine import StorageEngine
from services.catalog_service import MasterCatalogService
from services.adapter_service import (
    WalmartTabularAdapter,
    AmazonTabularAdapter,
    get_adapter_for_platform,
)
from services.metric_service import SemanticMetricService
from services.query_service import UnifiedBusinessQueryService


class TestPhase2Architecture(unittest.TestCase):
    """Phase 2 架构重构专项测试"""

    def setUp(self):
        # 使用内存数据库进行无副作用隔离测试
        self.storage = StorageEngine(db_path=":memory:")
        self.catalog = MasterCatalogService()
        self.catalog.storage = self.storage
        self.metrics = SemanticMetricService()
        self.query_svc = UnifiedBusinessQueryService()
        self.query_svc.storage = self.storage
        self.query_svc.catalog = self.catalog

    # 1. 存储引擎表结构与 Upsert 测试
    def test_01_storage_engine_schema_and_upsert(self):
        df = pd.DataFrame([{
            "master_sku": "SKU-BED-001",
            "spu": "BED-001",
            "product_name": "经典全尺寸铁架床",
            "category_l1": "家具",
            "category_l2": "床架",
            "brand": "自营",
            "lifecycle_stage": "成熟期",
            "is_active": 1,
        }])
        rows = self.storage.upsert_dataframe("dim_master_product", df, pks=["master_sku"])
        self.assertGreaterEqual(rows, 0)

        queried = self.storage.query_df("SELECT * FROM dim_master_product WHERE master_sku = ?", ["SKU-BED-001"])
        self.assertEqual(len(queried), 1)
        self.assertEqual(queried.iloc[0]["product_name"], "经典全尺寸铁架床")

    # 2. 统一 SKU 产品中心与多平台映射测试
    def test_02_catalog_service_mapping_and_resolution(self):
        # 绑定 Walmart Item ID
        self.catalog.bind_platform_item(
            platform_item_id="10558959663",
            master_sku="EM-BED-WHT-FULL",
            platform="walmart",
            store_id="wm_store_1",
        )
        # 绑定 Amazon ASIN
        self.catalog.bind_platform_item(
            platform_item_id="B08XYZ1234",
            master_sku="EM-BED-WHT-FULL",
            platform="amazon",
            store_id="amz_store_1",
        )

        # 反向解析：输入平台 ID 秒级返回统一 Master SKU
        resolved_wm = self.catalog.resolve_master_sku("10558959663")
        resolved_amz = self.catalog.resolve_master_sku("B08XYZ1234")
        self.assertEqual(resolved_wm, "EM-BED-WHT-FULL")
        self.assertEqual(resolved_amz, "EM-BED-WHT-FULL")

        # 档案视图查询
        full_df = self.catalog.get_full_catalog_df()
        self.assertFalse(full_df.empty)
        self.assertIn("Master SKU", full_df.columns)
        self.assertIn("Walmart Item ID", full_df.columns)
        self.assertIn("Amazon ASIN", full_df.columns)

    # 3. 跨平台表格适配器测试 (Walmart & Amazon)
    def test_03_adapters_to_canonical_model(self):
        # 3.1 Walmart 表格适配
        wm_adapter = WalmartTabularAdapter()
        self.assertEqual(wm_adapter.get_attribution_window_days(), 14)
        raw_wm = pd.DataFrame({
            "项目ID": ["10558959663"],
            "广告活动": ["Camp_Bed_Auto"],
            "花费": [45.5],
            "总销售额": [220.0],
            "广告订单": [2],
            "点击": [30],
            "曝光": [1500],
            "日期": ["2026-10-25"],
        })
        cdm_wm = wm_adapter.to_canonical_ad_performance(raw_wm, store_id="wm_store_1", source_file="wm.xlsx")
        self.assertEqual(len(cdm_wm), 1)
        self.assertEqual(cdm_wm.iloc[0]["platform"], "walmart")
        self.assertEqual(cdm_wm.iloc[0]["spend"], 45.5)
        self.assertEqual(cdm_wm.iloc[0]["attributed_sales"], 220.0)

        # 3.2 Amazon 表格适配
        amz_adapter = AmazonTabularAdapter()
        self.assertEqual(amz_adapter.get_attribution_window_days(), 7)
        raw_amz = pd.DataFrame({
            "ASIN": ["B08XYZ1234"],
            "Campaign Name": ["SP_Bed_Exact"],
            "Spend": ["$35.00"],
            "7 Day Total Sales ($)": ["$140.00"],
            "7 Day Total Orders (#)": [1],
            "Clicks": [20],
            "Impressions": [800],
            "Date": ["2026-10-25"],
        })
        cdm_amz = amz_adapter.to_canonical_ad_performance(raw_amz, store_id="amz_store_1", source_file="amz.xlsx")
        self.assertEqual(len(cdm_amz), 1)
        self.assertEqual(cdm_amz.iloc[0]["platform"], "amazon")
        self.assertEqual(cdm_amz.iloc[0]["spend"], 35.0)
        self.assertEqual(cdm_amz.iloc[0]["attributed_sales"], 140.0)

    # 4. 语义指标服务测试 (口径严格隔离与严肃性保护)
    def test_04_semantic_metric_service(self):
        ad_fact = pd.DataFrame({
            "spend": [100.0],
            "attributed_sales": [400.0],
            "orders": [4],
            "clicks": [50],
            "impressions": [2000],
        })
        # 仅有广告时
        kpis_ad_only = self.metrics.calculate_executive_kpis(ad_fact)
        self.assertEqual(kpis_ad_only["display_sales"], 400.0)
        self.assertEqual(kpis_ad_only["sales_title"], "广告归因销售额")
        self.assertIsNone(kpis_ad_only["tacos"])

        # 引入全盘真实 GMV
        sales_fact = pd.DataFrame({
            "gross_sales": [1000.0],
            "orders": [10],
        })
        kpis_full = self.metrics.calculate_executive_kpis(ad_fact, sales_fact)
        self.assertEqual(kpis_full["display_sales"], 1000.0)
        self.assertEqual(kpis_full["sales_title"], "店铺真实总 GMV")
        self.assertAlmostEqual(kpis_full["tacos"], 0.10)  # 100 / 1000 = 10%
        self.assertAlmostEqual(kpis_full["roas"], 4.0)    # 400 / 100 = 4.0x

    # 5. 统一业务查询服务与全局筛选贯通测试
    def test_05_unified_query_service_with_filters(self):
        sec_data = {
            "ad_item": pd.DataFrame({
                "项目ID": ["10558959663", "99999999999"],
                "花费": [50.0, 30.0],
                "总销售额": [200.0, 90.0],
                "广告订单": [2, 1],
                "点击": [20, 10],
                "曝光": [1000, 500],
                "日期": ["2026-10-20", "2026-10-20"],
            })
        }
        filters = {
            "platform": "Walmart",
            "store": "默认店铺 (Walmart)",
            "date_range": "全量报表周期",
            "sku": "全部 SKU",
        }
        res = self.query_svc.get_dashboard_summary(sec_data, filters=filters)
        kpis = res["kpis"]
        self.assertTrue(kpis["has_real_data"])
        self.assertEqual(kpis["spend"], 80.0)
        self.assertEqual(kpis["ad_sales"], 290.0)

    # 6. 多租户数据隔离测试 (Platform & Store Isolation)
    def test_06_tenant_isolation(self):
        df_store1 = pd.DataFrame([{
            "id": "wm_s1_001", "event_date": "2026-10-01", "platform": "walmart", "store_id": "store_1",
            "master_sku": "SKU-A", "spend": 100.0, "attributed_sales": 300.0, "orders": 3, "clicks": 50, "impressions": 2000,
        }])
        df_store2 = pd.DataFrame([{
            "id": "wm_s2_001", "event_date": "2026-10-01", "platform": "walmart", "store_id": "store_2",
            "master_sku": "SKU-A", "spend": 200.0, "attributed_sales": 800.0, "orders": 8, "clicks": 80, "impressions": 3000,
        }])
        self.storage.upsert_dataframe("fact_ad_performance", df_store1, pks=["id"])
        self.storage.upsert_dataframe("fact_ad_performance", df_store2, pks=["id"])

        # 隔离查询 Store 1
        s1_res = self.storage.query_df("SELECT SUM(spend) AS s, SUM(attributed_sales) AS sl FROM fact_ad_performance WHERE store_id = 'store_1'")
        self.assertEqual(s1_res.iloc[0]["s"], 100.0)
        self.assertEqual(s1_res.iloc[0]["sl"], 300.0)

        # 隔离查询 Store 2
        s2_res = self.storage.query_df("SELECT SUM(spend) AS s, SUM(attributed_sales) AS sl FROM fact_ad_performance WHERE store_id = 'store_2'")
        self.assertEqual(s2_res.iloc[0]["s"], 200.0)
        self.assertEqual(s2_res.iloc[0]["sl"], 800.0)


if __name__ == "__main__":
    unittest.main()
