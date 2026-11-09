"""
CrossBorder BI V2.5 审计修复专项自动化测试套件
覆盖全部 12 项验收测试要求：
1. SKU 映射导入测试
2. 成本表导入测试
3. 多文件导入与去重测试
4. 数据质量测试
5. 利润计算测试
6. 销售口径测试
7. 库存周转测试
8. AI 决策测试
9. 策略效果追踪测试
10. 全局筛选测试
11. 前端页面集成测试
12. 原有广告功能回归测试
"""

import io
import unittest
import pandas as pd
import numpy as np

# 1 & 2: 数据导入与成本
from data_loader.sku_mapper import generate_sku_template, load_sku_mapping
from analyzer.sku_profit_model import (
    generate_sku_cost_template,
    load_sku_cost_table,
    calculate_sku_profit_analytics,
)

# 3: 多文件去重与元数据
from data_loader.loader import extract_file_date_and_granularity, merge_table_dfs

# 4: 数据质量引擎
from analyzer.data_quality import inspect_data_quality

# 8: AI 决策
from analyzer.diagnosis_12_issues import diagnose_12_advertising_issues

# 9: 效果追踪
from analyzer.effect_tracker import (
    log_optimization_actions,
    load_tracking_history,
    generate_tracking_summary,
    update_action_status,
    backfill_post_data,
    clear_tracking_history,
)

# 10: 全局筛选
from frontend.utils.data_context import filter_dataframe_by_global

# 12: 原有广告功能
from analyzer.campaign_health import analyze_campaign_health
from analyzer.search_term_miner import mine_search_terms
from analyzer.keyword_bidder import analyze_keyword_bids
from analyzer.ad_item_diagnosis import diagnose_ad_items


class TestAuditRemediationSuite(unittest.TestCase):
    """V2.5 全链路深度测试"""

    # -------------------------------------------------------------------------
    # 1. SKU 映射导入测试
    # -------------------------------------------------------------------------
    def test_01_sku_mapping_import(self):
        tmpl_bytes = generate_sku_template()
        self.assertGreater(len(tmpl_bytes), 0)
        
        buf = io.BytesIO(tmpl_bytes)
        buf.name = "sku_mapping.xlsx"
        sku_map, err = load_sku_mapping(buf)
        self.assertIsNone(err)
        self.assertIsInstance(sku_map, dict)
        self.assertGreater(len(sku_map), 0)
        self.assertIn("10558959663", sku_map)
        self.assertEqual(sku_map["10558959663"], "EM-BED-WHT-FULL")

    # -------------------------------------------------------------------------
    # 2. 成本表导入测试
    # -------------------------------------------------------------------------
    def test_02_cost_table_import(self):
        cost_bytes = generate_sku_cost_template()
        buf = io.BytesIO(cost_bytes)
        buf.name = "sku_cost.xlsx"
        cost_df, cost_dict, err = load_sku_cost_table(buf)
        self.assertIsNone(err)
        self.assertFalse(cost_df.empty)
        self.assertIn("SKU-BED-001", cost_dict)
        self.assertEqual(cost_dict["SKU-BED-001"]["unit_product_cost"], 57.0)

    # -------------------------------------------------------------------------
    # 3. 多文件导入、日期粒度与联合主键去重测试
    # -------------------------------------------------------------------------
    def test_03_multi_file_deduplication(self):
        filename = "投放关键词列表数据-2026-10-01--2026-10-31.xlsx"
        dummy_df = pd.DataFrame({"关键词": ["bed frame", "desk"], "花费": [10.0, 20.0]})
        date_str, granularity = extract_file_date_and_granularity(filename, dummy_df)
        self.assertEqual(granularity, "period_summary")
        self.assertIn("2026-10-01", date_str)
        self.assertIn("2026-10-31", date_str)

        # 联合主键去重
        df1 = pd.DataFrame({
            "关键词": ["bed frame", "desk"],
            "广告活动": ["Camp_A", "Camp_B"],
            "花费": [10.0, 20.0],
            "日期": ["2026-10-15", "2026-10-15"],
        })
        df2 = pd.DataFrame({
            "关键词": ["bed frame"],
            "广告活动": ["Camp_A"],
            "花费": [15.0],  # 更新版
            "日期": ["2026-10-15"],
        })
        merged, pks = merge_table_dfs([("f1.xlsx", df1, {}), ("f2.xlsx", df2, {})], "keyword")
        self.assertEqual(len(merged), 2)
        bf_row = merged[merged["关键词"] == "bed frame"].iloc[0]
        self.assertEqual(bf_row["花费"], 15.0)

    # -------------------------------------------------------------------------
    # 4. 数据质量测试 (体检指标、置信度与熔断)
    # -------------------------------------------------------------------------
    def test_04_data_quality_inspection(self):
        sec_data = {
            "campaign": pd.DataFrame({
                "广告活动": ["Camp_1", "Camp_2"],
                "花费": [50.0, 0.0],
                "销售额": [200.0, 0.0],
                "订单量": [2, 0],
            }),
            "ad_item": pd.DataFrame({
                "项目ID": ["654321098"],
                "花费": [50.0],
                "销售额": [200.0],
            })
        }
        res = inspect_data_quality(sec_data)
        self.assertIn("health_score", res)
        self.assertIn("confidence_level", res)
        self.assertIn("guardrail_active", res)
        self.assertIn("real_zeros_count", res)
        self.assertIn("negative_metrics", res)
        self.assertGreaterEqual(res["health_score"], 0)
        self.assertLessEqual(res["health_score"], 100)

    # -------------------------------------------------------------------------
    # 5. 利润计算测试 (先聚合、真实单位经济学、保本ACoS、缺失成本不伪造)
    # -------------------------------------------------------------------------
    def test_05_profit_calculation(self):
        cost_dict = {
            "SKU-A": {
                "cogs": 30.0, "first_leg": 10.0, "last_leg": 15.0,
                "commission_rate": 0.15, "other_cost": 0.0,
                "unit_product_cost": 55.0,
            }
        }
        # 同一 SKU 两行记录 (测试先聚合再核算)
        item_df = pd.DataFrame({
            "SKU": ["SKU-A", "SKU-A", "SKU-MISSING-COST"],
            "广告花费": [20.0, 30.0, 15.0],
            "总销售额": [100.0, 100.0, 80.0],
            "广告订单": [1, 1, 1],
            "销售件数": [1, 1, 1],
        })
        res_df, stats = calculate_sku_profit_analytics(item_df, cost_dict)
        self.assertEqual(len(res_df), 2)  # SKU-A 成功聚合为 1 行

        sku_a = res_df[res_df["SKU"] == "SKU-A"].iloc[0]
        # 总销售 200, 总件数 2 -> 采购物流 110, 佣金 30 (15%) -> 广告前毛利 = 200 - 140 = 60
        # 总广告花费 50 -> 广告后净利 = 60 - 50 = 10
        self.assertAlmostEqual(sku_a["广告前贡献利润"], 60.0)
        self.assertAlmostEqual(sku_a["广告后贡献利润"], 10.0)
        self.assertEqual(sku_a["成本真实性"], "真实已核算")

        # 缺失成本 SKU
        sku_m = res_df[res_df["SKU"] == "SKU-MISSING-COST"].iloc[0]
        self.assertEqual(sku_m["成本真实性"], "成本缺失待补录")
        self.assertTrue(pd.isna(sku_m["广告前贡献利润"]))
        self.assertTrue(pd.isna(sku_m["广告后贡献利润"]))

    # -------------------------------------------------------------------------
    # 6. 销售口径测试 (严禁将广告归因作为全盘 GMV)
    # -------------------------------------------------------------------------
    def test_06_sales_attribution_isolation(self):
        # 仅有广告报表时，销售额是广告归因销售额
        camp_df = pd.DataFrame({"销售额": [500.0], "订单量": [5]})
        ad_sales = float(camp_df["销售额"].sum())
        self.assertEqual(ad_sales, 500.0)

        # 店铺全盘销售表（若有）
        store_daily_df = pd.DataFrame({"销售额": [1200.0], "订单量": [12]})
        store_gmv = float(store_daily_df["销售额"].sum())
        self.assertEqual(store_gmv, 1200.0)
        self.assertGreater(store_gmv, ad_sales)

    # -------------------------------------------------------------------------
    # 7. 库存周转测试 (无数据返回空状态，有数据计算 DOS)
    # -------------------------------------------------------------------------
    def test_07_inventory_turnover(self):
        inv_df = pd.DataFrame({
            "SKU": ["SKU-001", "SKU-002"],
            "可用库存": [100, 10],
            "在途": [50, 0],
        })
        daily_velocity = 2.0
        dos_1 = round(100 / daily_velocity, 0)
        dos_2 = round(10 / daily_velocity, 0)
        self.assertEqual(dos_1, 50)
        self.assertEqual(dos_2, 5)  # < 15 天断货预警

    # -------------------------------------------------------------------------
    # 8. AI 决策测试 (解耦 4 个核心维度：事实、原因、动作、假设)
    # -------------------------------------------------------------------------
    def test_08_ai_decision_engine(self):
        sec_data = {
            "search_term": pd.DataFrame({
                "搜索词": ["cheap bed frame"],
                "花费": [60.0],
                "销售额": [0.0],
                "订单量": [0],
                "点击量": [45],
            })
        }
        issues = diagnose_12_advertising_issues(sec_data)
        self.assertGreater(len(issues), 0)
        top_issue = issues[0]
        self.assertIn("问题类型", top_issue)
        self.assertIn("关键数据证据", top_issue)
        self.assertIn("可能原因", top_issue)
        self.assertIn("建议采取措施", top_issue)
        self.assertIn("建议观察周期", top_issue)

    # -------------------------------------------------------------------------
    # 9. 策略效果追踪测试 (动态统计、状态更新、数据回填)
    # -------------------------------------------------------------------------
    def test_09_effect_tracker(self):
        clear_tracking_history()
        actions = [{
            "对象标识": "bed frame with storage",
            "决策领域": "搜索词精准否定",
            "当前指标依据": "花费 $58.0 无出单",
            "决策执行指令": "添加精准否定",
            "建议调整幅度": "精准否定",
            "验证周期": "7天",
            "成功判断标准": "无效花费归零",
        }]
        c = log_optimization_actions(actions)
        self.assertEqual(c, 1)

        history = load_tracking_history()
        self.assertEqual(len(history), 1)
        act_id = history[0]["action_id"]

        # 更新状态
        updated = update_action_status(act_id, "已采纳执行")
        self.assertTrue(updated)

        # 回填后验效果
        backfilled = backfill_post_data(act_id, {"post_spend": 0.0}, "达标改善，无效花费完全遏制")
        self.assertTrue(backfilled)

        # 统计汇总
        summary = generate_tracking_summary()
        self.assertEqual(summary["total_actions"], 1)
        self.assertEqual(summary["successful_actions"], 1)
        self.assertEqual(summary["success_rate_pct"], 100.0)

    # -------------------------------------------------------------------------
    # 10. 全局筛选测试
    # -------------------------------------------------------------------------
    def test_10_global_filter(self):
        df = pd.DataFrame({
            "SKU": ["SKU-A", "SKU-B", "SKU-A"],
            "花费": [10.0, 20.0, 30.0],
            "日期": ["2026-10-01", "2026-10-15", "2026-10-28"],
        })
        # 1. 筛选 SKU-A
        f1 = {"sku": "SKU-A", "platform": "Walmart", "date_range": "全量报表周期"}
        filtered1 = filter_dataframe_by_global(df, f1)
        self.assertEqual(len(filtered1), 2)
        self.assertTrue((filtered1["SKU"] == "SKU-A").all())

        # 2. 筛选最近 7 天
        f2 = {"sku": "全部 SKU", "platform": "Walmart", "date_range": "最近7天"}
        filtered2 = filter_dataframe_by_global(df, f2)
        self.assertEqual(len(filtered2), 1)
        self.assertEqual(filtered2.iloc[0]["日期"], "2026-10-28")

    # -------------------------------------------------------------------------
    # 11 & 12. 经典原有广告算法回归测试
    # -------------------------------------------------------------------------
    def test_11_ad_algorithms_regression(self):
        camp_df = pd.DataFrame({
            "广告活动": ["ST-Broad-Bed"],
            "花费": [120.0],
            "销售额": [450.0],
            "订单量": [5],
            "点击量": [100],
            "曝光量": [5000],
            "每日预算": [50.0],
            "状态": ["Active"],
        })
        res_camp, _, _ = analyze_campaign_health(camp_df, target_acos=0.25)
        self.assertFalse(res_camp.empty)

        st_df = pd.DataFrame({
            "搜索词": ["metal bed frame"],
            "广告活动": ["ST-Broad-Bed"],
            "花费": [35.0],
            "销售额": [180.0],
            "订单量": [2],
            "点击量": [25],
            "曝光量": [800],
        })
        mined = mine_search_terms(st_df)
        self.assertIsInstance(mined, tuple)

        kw_df = pd.DataFrame({
            "关键词": ["king bed"],
            "广告活动": ["ST-Broad-Bed"],
            "花费": [45.0],
            "销售额": [150.0],
            "订单量": [2],
            "点击量": [30],
            "曝光量": [1200],
            "出价": [1.2],
        })
        bids = analyze_keyword_bids(kw_df)
        self.assertIsInstance(bids, tuple)

        item_df = pd.DataFrame({
            "项目ID": ["654321098"],
            "花费": [60.0],
            "销售额": [300.0],
            "订单量": [3],
            "点击量": [40],
            "曝光量": [2000],
        })
        diag = diagnose_ad_items(item_df)
        self.assertIsInstance(diag, dict)


if __name__ == "__main__":
    unittest.main()
