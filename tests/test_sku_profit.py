import unittest
import pandas as pd
import io

from analyzer.sku_profit_model import (
    generate_sku_cost_template,
    load_sku_cost_table,
    calculate_sku_profit_analytics,
)

class TestSkuProfitModel(unittest.TestCase):
    """SKU 商品单位成本与真实净利模型测试"""

    def test_generate_and_load_template(self):
        """测试模板生成及反向解析读取"""
        excel_bytes = generate_sku_cost_template()
        self.assertGreater(len(excel_bytes), 0)

        buf = io.BytesIO(excel_bytes)
        buf.name = "sku_cost_template.xlsx"
        cost_dict, err = load_sku_cost_table(buf)
        self.assertIsNone(err)
        self.assertIn("SKU-BED-001", cost_dict)
        info = cost_dict["SKU-BED-001"]
        # 采购 25 + 头程 12 + 尾程 18 + 包装 2 = 57.0
        self.assertEqual(info["unit_product_cost"], 57.0)
        self.assertAlmostEqual(info["commission_rate"], 0.15)

    def test_calculate_sku_profit_analytics(self):
        """测试广告前毛利与广告后真实净利的准确计算"""
        cost_dict = {
            "SKU-GOOD": {
                "cogs": 20.0, "first_leg": 10.0, "last_leg": 15.0,
                "commission_rate": 0.15, "other_cost": 2.0,
                "unit_product_cost": 47.0,
            },
            "SKU-LOSS": {
                "cogs": 50.0, "first_leg": 20.0, "last_leg": 20.0,
                "commission_rate": 0.15, "other_cost": 5.0,
                "unit_product_cost": 95.0,
            }
        }

        ad_df = pd.DataFrame({
            "SKU": ["SKU-GOOD", "SKU-LOSS"],
            "广告花费": [50.0, 100.0],
            "总销售额": [500.0, 120.0],
            "广告订单": [5, 1], # SKU-GOOD 客单价 100，SKU-LOSS 客单价 120
        })

        profit_df, stats = calculate_sku_profit_analytics(ad_df, cost_dict)
        self.assertEqual(len(profit_df), 2)

        # SKU-GOOD: 客单价 100, 单位成本 47, 佣金 15 -> 单位广告前毛利 = 100 - 47 - 15 = 38
        # 总毛利 = 5 * 38 = 190. 广告花费 50 -> 广告后净利 = 190 - 50 = 140 > 0
        good_row = profit_df[profit_df["SKU"] == "SKU-GOOD"].iloc[0]
        self.assertAlmostEqual(good_row["广告前毛利"], 190.0)
        self.assertAlmostEqual(good_row["广告后真实净利"], 140.0)
        self.assertIn("强力净盈利", good_row["盈利状态"])

        # SKU-LOSS: 客单价 120, 单位成本 95, 佣金 18 -> 单位广告前毛利 = 120 - 95 - 18 = 7
        # 总毛利 = 1 * 7 = 7. 广告花费 100 -> 广告后净利 = 7 - 100 = -93 < 0
        loss_row = profit_df[profit_df["SKU"] == "SKU-LOSS"].iloc[0]
        self.assertAlmostEqual(loss_row["广告后真实净利"], -93.0)
        self.assertIn("真实净亏损", loss_row["盈利状态"])

        self.assertEqual(stats["profitable_sku_count"], 1)
        self.assertEqual(stats["loss_sku_count"], 1)

if __name__ == "__main__":
    unittest.main()
