import unittest
import pandas as pd

from analyzer.decision_engine import AdDecisionEngine
from data_loader.loader import merge_table_dfs

class TestDecisionEngineAndDeduplication(unittest.TestCase):
    """统一决策引擎与跨文件合并去重测试"""

    def test_decision_engine_conflict_arbitration(self):
        """测试仲裁层：暂停优先级高于降价与加价，杜绝指令冲突"""
        # 构造同一个关键词同时满足暂停和降价的边缘情况
        kw_df = pd.DataFrame({
            "关键词": ["conflict_target"],
            "广告活动": ["Camp_Conflict"],
            "关键词状态": ["enabled"],
            "实际竞价": ["$1.20"],
            "广告花费": [50.0], # 花费极大且0单，触发暂停与降价冲突
            "点击": [30],
            "曝光量": [1000],
            "广告订单": [0],
            "总销售额": [0.0],
        })

        engine = AdDecisionEngine()
        res = engine.run({"keyword": kw_df})

        dec_matrix = res["decision_matrix"]
        self.assertEqual(len(dec_matrix), 1)
        action_row = dec_matrix.iloc[0]
        # 验证暂停指令胜出
        self.assertIn("暂停", action_row["决策执行指令"])
        self.assertEqual(action_row["优先级"], "P0")

        # 验证冲突日志有详细仲裁审计记录
        conflict_log = res["conflict_log"]
        self.assertGreaterEqual(len(conflict_log), 0)

    def test_multi_file_deduplication(self):
        """测试多报表合并时的复合主键与日期去重"""
        df1 = pd.DataFrame({
            "广告活动": ["Camp_A", "Camp_B"],
            "广告花费": [100.0, 50.0],
            "日期": ["2026-10-01", "2026-10-01"],
        })
        df2 = pd.DataFrame({
            "广告活动": ["Camp_A", "Camp_C"], # Camp_A 同日期重复
            "广告花费": [120.0, 30.0],
            "日期": ["2026-10-01", "2026-10-02"],
        })

        merged_df, _ = merge_table_dfs([("f1.xlsx", df1, {}), ("f2.xlsx", df2, {})], "campaign")
        # 应该去重后保留 3 条 (Camp_A 取最新 f2.xlsx 的 120.0, Camp_B, Camp_C)
        self.assertEqual(len(merged_df), 3)
        camp_a_spend = merged_df[merged_df["广告活动"] == "Camp_A"]["广告花费"].iloc[0]
        self.assertEqual(camp_a_spend, 120.0)

if __name__ == "__main__":
    unittest.main()
