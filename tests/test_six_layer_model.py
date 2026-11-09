import unittest
import pandas as pd
from analyzer.data_quality import inspect_data_quality
from analyzer.traffic_structure import analyze_traffic_structure
from analyzer.diagnosis_12_issues import diagnose_12_advertising_issues
from analyzer.effect_tracker import log_optimization_actions, load_tracking_history, clear_tracking_history
from analyzer.search_term_miner import mine_search_terms

class TestSixLayerModel(unittest.TestCase):
    def test_search_term_no_dummy_fabrication(self):
        """测试核心Bug修复：缺失【搜索词】字段时严禁捏造虚假【搜索词_1】"""
        # 模拟误传了广告活动表
        fake_camp_df = pd.DataFrame({
            "广告活动": ["stgh06-auto-F-3.26", "stgh06-广泛--Full-长尾挖掘"],
            "广告花费": [50.0, 30.0],
            "广告订单": [10, 5],
            "总销售额": [200.0, 100.0],
        })
        neg_df, mining_df, hc_df, stats = mine_search_terms(fake_camp_df)
        self.assertTrue(mining_df.empty)
        self.assertTrue(neg_df.empty)
        self.assertIn("error", stats)
        # 确保没有任何 '搜索词_1' 存在
        if not mining_df.empty and "搜索词" in mining_df.columns:
            self.assertFalse(any("搜索词_" in s for s in mining_df["搜索词"]))

    def test_data_quality_inspection(self):
        """测试第一层：数据质量分析引擎"""
        camp_df = pd.DataFrame({
            "广告活动": ["Camp_1", "Camp_2"],
            "广告花费": [100.0, 50.0],
            "广告订单": [10, 5],
            "总销售额": [500.0, 200.0],
        })
        res = inspect_data_quality({"campaign": camp_df})
        self.assertGreaterEqual(res["score"], 60)
        self.assertIn(res["confidence"], ["高置信度", "中置信度"])
        self.assertFalse(res["guardrail_active"])

    def test_traffic_structure(self):
        """测试第二层：流量结构与匹配方式剖析"""
        camp_df = pd.DataFrame({
            "广告活动": ["stgh06-auto-F-3.26", "stgh06-manual-exact-01"],
            "广告花费": [80.0, 20.0],
            "总销售额": [240.0, 100.0],
            "广告订单": [8, 4],
            "点击": [100, 20],
            "曝光量": [10000, 2000],
        })
        res = analyze_traffic_structure(campaign_df=camp_df)
        avm = res["auto_vs_manual_df"]
        self.assertFalse(avm.empty)
        self.assertIn("🤖 Auto (自动投放)", avm["投放模式"].values)
        self.assertIn("🎯 Manual (手动投放)", avm["投放模式"].values)

    def test_12_issues_diagnosis(self):
        """测试第四层：十二项全息问题诊断体系"""
        camp_df = pd.DataFrame({
            "广告活动": ["stgh06-high-roas"],
            "每日预算": [50.0],
            "广告花费": [48.0], # 预算撞顶
            "总销售额": [250.0],
            "ROAS": [5.2],
        })
        issues = diagnose_12_advertising_issues({"campaign": camp_df})
        self.assertGreaterEqual(len(issues), 1)
        issue_1 = issues[0]
        # 校验行业标准字段
        for field in ["issue_type", "severity", "entity", "data_evidence", "root_cause", "confidence", "action", "expected_impact", "observation_window"]:
            self.assertIn(field, issue_1)

    def test_effect_tracker(self):
        """测试第六层：效果追踪与模型迭代库"""
        clear_tracking_history()
        actions = [{
            "对象标识": "chair",
            "所属活动/范围": "Camp_1",
            "决策领域": "搜索词否词",
            "优先级": "P0",
            "当前指标依据": "花费$30 0单",
            "决策执行指令": "精准否定",
            "建议调整幅度": "100%",
            "验证周期": "3天",
            "成功判断标准": "花费归零",
        }]
        saved_count = log_optimization_actions(actions)
        self.assertEqual(saved_count, 1)
        history = load_tracking_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["entity"], "chair")
        clear_tracking_history()

if __name__ == "__main__":
    unittest.main()
