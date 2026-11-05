import unittest
import pandas as pd
import numpy as np
import io

from analyzer.search_term_miner import mine_search_terms
from analyzer.keyword_bidder import analyze_keyword_bids
from analyzer.campaign_health import analyze_campaign_health
from analyzer.placement_analyzer import analyze_placements
from analyzer.trend_analyzer import build_sku_trend_data
from analyzer.metrics import safe_divide
from data_loader.loader import clean_numeric_series_with_report, parse_and_clean_table

class TestAdToolEdgeCases(unittest.TestCase):
    """边界情况与异常鲁棒性测试套件"""

    def test_safe_divide_edge_cases(self):
        """测试除以零、None、NaN、负数等边界"""
        self.assertIsNone(safe_divide(0, 0))
        self.assertIsNone(safe_divide(100, 0))
        self.assertEqual(safe_divide(None, 10), 0.0)
        self.assertIsNone(safe_divide(10, None))
        self.assertEqual(safe_divide(np.nan, 10), 0.0)
        self.assertIsNone(safe_divide(10, np.nan))
        self.assertAlmostEqual(safe_divide(10, 2), 5.0)

    def test_search_term_empty_and_zero_data(self):
        """测试搜索词报表在全空或全 0 指标下的表现"""
        # 全空 DataFrame
        neg_df, mining_df, hc_df, stats = mine_search_terms(pd.DataFrame())
        self.assertTrue(neg_df.empty)
        self.assertTrue(mining_df.empty)
        self.assertEqual(stats["p0_count"], 0)

        # 全 0 指标
        zero_df = pd.DataFrame({
            "搜索词": ["bed frame", "twin mattress"],
            "广告活动": ["Camp_1", "Camp_2"],
            "广告组": ["Group_1", "Group_2"],
            "广告花费": [0.0, 0.0],
            "点击": [0, 0],
            "曝光量": [0, 0],
            "广告订单": [0, 0],
            "总销售额": [0.0, 0.0],
        })
        neg_df, mining_df, hc_df, stats = mine_search_terms(zero_df)
        self.assertTrue(neg_df.empty) # 0 花费不触发否词
        self.assertTrue(mining_df.empty)

    def test_keyword_bidder_missing_actual_bids(self):
        """测试关键词实际出价缺失时严禁使用建议竞价乘算的安全性"""
        kw_df = pd.DataFrame({
            "关键词": ["wooden bed", "cheap frame"],
            "广告活动": ["SP-Bed", "SP-Bed"],
            "关键词状态": ["enabled", "enabled"],
            "建议竞价": ["$1.50", "$2.00"], # 只有建议出价，缺失实际竞价
            "广告花费": [35.0, 15.0],
            "点击": [25, 12],
            "曝光量": [500, 300],
            "广告订单": [0, 0],
            "总销售额": [0.0, 0.0],
        })
        kw_res, all_actions, stats = analyze_keyword_bids(kw_df)
        self.assertGreater(stats["missing_bid_count"], 0)
        # 验证降价建议中没有盲目计算出的错误浮点数
        if not kw_res["bid_down"].empty:
            down_row = kw_res["bid_down"].iloc[0]
            self.assertIn("核实出价后下调", down_row["建议出价调整"])

    def test_data_cleaning_anomalies_and_negative_values(self):
        """测试异常文本混入与反常负数的清洗捕获"""
        dirty_series = pd.Series(["$12.50", "N/A", "-$5.00", "error_string", "15%"])
        cleaned, anomalies = clean_numeric_series_with_report(dirty_series, "广告花费", "test")
        self.assertEqual(len(cleaned), 5)
        # 负数被取绝对值
        self.assertEqual(cleaned.iloc[2], 5.0)
        # 异常被记录
        self.assertGreaterEqual(len(anomalies), 2)

    def test_trend_analyzer_natural_dates(self):
        """测试趋势分析基于自然日而不是单纯行数的切片正确性"""
        records = [{
            "filename": "trend.xlsx",
            "period": "2026-10-01",
            "df": pd.DataFrame({
                "SKU": ["SKU-A", "SKU-A", "SKU-A"],
                "日期": ["2026-10-01", "2026-10-05", "2026-10-28"], # 跨越大月份
                "广告花费": [10.0, 15.0, 20.0],
                "总销售额": [50.0, 60.0, 70.0],
                "广告订单": [2, 3, 4],
                "点击": [10, 15, 20],
            })
        }]
        period_df, sku_summary_df, anomalies, daily_macro = build_sku_trend_data(records)
        self.assertFalse(sku_summary_df.empty)
        # 确保没有崩溃抛错且正确汇总
        self.assertEqual(len(sku_summary_df), 1)

if __name__ == "__main__":
    unittest.main()
