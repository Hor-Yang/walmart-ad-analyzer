import unittest
import pandas as pd
import numpy as np
from data_loader.sku_mapper import apply_sku_mapping, load_sku_mapping
from data_loader.session_storage import (
    save_session_cache,
    load_session_cache,
    get_session_cache_metadata,
    clear_session_cache,
    record_upload_audit_log,
    get_upload_audit_logs,
    generate_audit_log_markdown,
)
from analyzer.ad_item_diagnosis import diagnose_ad_items

class TestSessionAndSKU(unittest.TestCase):
    def test_session_storage_and_audit(self):
        clear_session_cache()
        meta = get_session_cache_metadata()
        self.assertIsNone(meta)

        # 写入会话
        sec_data = {"campaign": pd.DataFrame({"花费": [10.0]})}
        sku_map = {"1001": "SKU-A"}
        saved = save_session_cache(sec_data, sku_map, {}, {"campaign": "camp.xlsx"})
        self.assertTrue(saved)

        loaded = load_session_cache()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["sku_map"]["1001"], "SKU-A")

        meta = get_session_cache_metadata()
        self.assertIsNotNone(meta)
        self.assertEqual(meta["sku_count"], 1)

        # 写入审计日志
        record_upload_audit_log("广告活动", "camp.xlsx", 50, 1024, "测试上传")
        logs = get_upload_audit_logs()
        self.assertTrue(len(logs) >= 1)
        md = generate_audit_log_markdown()
        self.assertIn("camp.xlsx", md)

        clear_session_cache()

    def test_sku_mapping_robustness(self):
        sku_map = {"1001": "EM-BED-WHT", "1002": "EM-BED-BLK"}
        
        # 测试 float 格式的 ID (如 1001.0)
        df = pd.DataFrame({
            "项目ID": [1001.0, "1002", 1003],
            "广告花费": [50.0, 30.0, 10.0],
            "广告订单": [2, 0, 1],
            "总销售额": [200.0, 0.0, 50.0],
            "点击": [20, 15, 5],
            "曝光量": [1000, 800, 300],
        })

        mapped_df = apply_sku_mapping(df, sku_map)
        self.assertIn("SKU", mapped_df.columns)
        self.assertEqual(mapped_df.loc[0, "SKU"], "EM-BED-WHT")
        self.assertEqual(mapped_df.loc[1, "SKU"], "EM-BED-BLK")
        self.assertEqual(mapped_df.loc[2, "SKU"], "1003")

        # 测试 ad_item_diagnosis
        res = diagnose_ad_items(df, sku_map=sku_map)
        top10 = res["top10_items"]
        self.assertIn("SKU", top10.columns)
        self.assertIn("EM-BED-WHT", top10["SKU"].values)

        burning = res["burning_items"]
        self.assertIn("SKU", burning.columns)
        self.assertIn("EM-BED-BLK", burning["SKU"].values)

if __name__ == "__main__":
    unittest.main()
