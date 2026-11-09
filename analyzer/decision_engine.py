from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from .metrics import safe_divide
from .search_term_miner import mine_search_terms
from .keyword_bidder import analyze_keyword_bids
from .campaign_health import analyze_campaign_health
from .placement_analyzer import analyze_placements
from .store_product_analysis import generate_store_overview_analysis, generate_product_matrix_analysis
from .sku_profit_model import calculate_sku_profit_analytics

class AdDecisionEngine:
    """
    统一广告决策引擎（4 层架构）：
    -------------------------------------------------------------
    1. 数据层 (Data Layer): 统一清洗、对齐数据源，推导大盘客单价、CVR与动态目标线
    2. 规则层 (Rule Layer): 各业务诊断专家规则并发评估
    3. 冲突仲裁层 (Arbitration Layer): 跨模块动作去重、互斥规则判定与优先级裁决
    4. 决策输出层 (Final Decision Layer): 产出结构化决策中枢看板与标准化执行清单
    """

    def __init__(
        self,
        target_acos: float = 0.25,
        breakeven_acos: float = 0.35,
        target_cpa: Optional[float] = None,
        aov_override: Optional[float] = None,
        cost_dict: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        self.target_acos = target_acos
        self.breakeven_acos = breakeven_acos
        self.target_cpa = target_cpa
        self.aov_override = aov_override
        self.cost_dict = cost_dict or {}

    def run(self, tables: Dict[str, Any]) -> Dict[str, Any]:
        """执行完整四层决策流程"""
        # =====================================================================
        # 第 1 层：数据层 (Data Layer)
        # =====================================================================
        data_layer_metrics = self._process_data_layer(tables)

        # =====================================================================
        # 第 2 层：规则层 (Rule Layer)
        # =====================================================================
        raw_recommendations = self._evaluate_rules(tables, data_layer_metrics)

        # =====================================================================
        # 第 3 层：冲突仲裁层 (Conflict Arbitration Layer)
        # =====================================================================
        arbitrated_actions, conflict_log = self._arbitrate_conflicts(raw_recommendations)

        # =====================================================================
        # 第 4 层：最终决策输出层 (Final Decision Layer)
        # =====================================================================
        decision_matrix, executive_summary = self._build_final_decisions(
            arbitrated_actions, conflict_log, data_layer_metrics
        )

        return {
            "data_layer_metrics": data_layer_metrics,
            "decision_matrix": decision_matrix,
            "executive_summary": executive_summary,
            "conflict_log": conflict_log,
            "raw_module_results": raw_recommendations.get("module_results", {}),
        }

    def _process_data_layer(self, tables: Dict[str, Any]) -> Dict[str, Any]:
        """数据层处理：对齐全店宏观指标并推导动态安全界限"""
        tot_spend = 0.0
        tot_sales = 0.0
        tot_orders = 0
        tot_clicks = 0

        # 优先使用 campaign 表或 ad_item 表计算大盘宏观
        primary_df = None
        for cand_key in ["campaign", "ad_item", "keyword"]:
            df_c = tables.get(cand_key)
            if df_c is not None and not df_c.empty:
                primary_df = df_c
                break

        if primary_df is not None and not primary_df.empty:
            for col in ["广告花费", "花费", "spend"]:
                if col in primary_df.columns:
                    tot_spend = float(pd.to_numeric(primary_df[col], errors="coerce").fillna(0.0).sum())
                    break
            for col in ["总销售额", "销售额", "sales"]:
                if col in primary_df.columns:
                    tot_sales = float(pd.to_numeric(primary_df[col], errors="coerce").fillna(0.0).sum())
                    break
            for col in ["广告订单", "订单", "orders"]:
                if col in primary_df.columns:
                    tot_orders = int(pd.to_numeric(primary_df[col], errors="coerce").fillna(0).sum())
                    break
            for col in ["点击", "clicks"]:
                if col in primary_df.columns:
                    tot_clicks = int(pd.to_numeric(primary_df[col], errors="coerce").fillna(0).sum())
                    break

        actual_acos = tot_spend / tot_sales if tot_sales > 0 else 0.0
        actual_roas = tot_sales / tot_spend if tot_spend > 0 else 0.0
        calculated_aov = tot_sales / tot_orders if tot_orders > 0 else 50.0
        effective_aov = self.aov_override if (self.aov_override and self.aov_override > 0) else calculated_aov
        effective_cvr = tot_orders / tot_clicks if tot_clicks > 0 else 0.04
        effective_cpa = self.target_cpa if (self.target_cpa and self.target_cpa > 0) else (effective_aov * self.target_acos)

        return {
            "total_spend": tot_spend,
            "total_sales": tot_sales,
            "total_orders": tot_orders,
            "total_clicks": tot_clicks,
            "actual_acos": actual_acos,
            "actual_roas": actual_roas,
            "effective_aov": effective_aov,
            "effective_cvr": effective_cvr,
            "effective_cpa": effective_cpa,
            "target_acos": self.target_acos,
            "breakeven_acos": self.breakeven_acos,
            "breakeven_roas": 1.0 / self.breakeven_acos if self.breakeven_acos > 0 else 2.86,
            "target_roas": 1.0 / self.target_acos if self.target_acos > 0 else 4.0,
        }

    def _evaluate_rules(self, tables: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
        """规则层评估：调用各独立诊断模块并提炼建议"""
        raw_items: List[Dict[str, Any]] = []
        module_results = {}

        # 1. 搜索词规则
        st_df = tables.get("search_term")
        if st_df is not None and not st_df.empty:
            neg_df, mining_df, hc_df, st_stats = mine_search_terms(
                st_df,
                target_acos=meta["target_acos"],
                aov_override=meta["effective_aov"],
                target_cpa_override=meta["effective_cpa"],
            )
            module_results["search_term"] = {
                "neg_df": neg_df, "mining_df": mining_df, "hc_df": hc_df, "stats": st_stats
            }

            # 提炼否词动作
            for _, r in neg_df.iterrows():
                prio = r.get("优先级", "P0")
                is_p0 = (prio == "P0")
                raw_items.append({
                    "layer": "rule_search_term",
                    "domain": "搜索词否词",
                    "priority": prio,
                    "entity_id": r["搜索词"],
                    "campaign": r["来源广告活动"],
                    "ad_group": r["来源广告组"],
                    "current_stat": f"花费 ${r['花费']:.2f}, 订单 {int(r['订单'])}, ROAS {r['ROAS']:.2f}",
                    "action_code": "NEGATIVE_PHRASE" if "词组" in r["建议否定类型"] else "NEGATIVE_EXACT",
                    "action_text": r["建议动作"],
                    "magnitude": "完全阻断 (100% 否定)" if is_p0 else "精准否定",
                    "rationale": f"累计消耗 ${r['花费']:.2f} 且转化完全为 0 (高于止损线)，判定为非购买意图流量",
                    "risk_warning": "否定前核对是否包含核心词根，避免误伤同词根其他长尾出单词",
                    "validation_window": "3 个自然日",
                    "success_criteria": "该搜索词后续点击与花费彻底归零，无额外沉没资金",
                    "confidence": "高置信度" if float(r["花费"]) >= 20.0 else "中置信度",
                    "estimated_impact": float(r["花费"]),
                    "raw_row": r.to_dict(),
                })

            # 提炼挖词动作
            for _, r in mining_df.iterrows():
                raw_items.append({
                    "layer": "rule_search_term",
                    "domain": "搜索词提拔",
                    "priority": "P2",
                    "entity_id": r["搜索词"],
                    "campaign": r["来源广告活动"],
                    "ad_group": r["来源广告组"],
                    "current_stat": f"订单 {int(r['订单'])}, 销售额 ${r['总销售额']:.2f}, ROAS {r['ROAS']:.2f}",
                    "action_code": "PROMOTE_KEYWORD",
                    "action_text": r["建议动作"],
                    "magnitude": f"初始建议竞价 ${r['出价建议']:.2f} (+15%)",
                    "rationale": f"已累计稳定出单 {int(r['订单'])} 次且 ROAS 达 {r['ROAS']:.2f}，验证具备高购买意向",
                    "risk_warning": "提拔进入新组后需密切观察前 3 天转化承接，避免因竞价过高击穿利润",
                    "validation_window": "7 个自然日",
                    "success_criteria": f"单品精准组内稳定出单，ROAS 维持在 {r['ROAS']:.2f} 以上",
                    "confidence": "高置信度",
                    "estimated_impact": float(r["总销售额"]),
                    "raw_row": r.to_dict(),
                })

        # 2. 关键词出价规则
        kw_df = tables.get("keyword")
        if kw_df is not None and not kw_df.empty:
            kw_res, all_kw_actions, kw_stats = analyze_keyword_bids(
                kw_df,
                target_acos=meta["target_acos"],
                breakeven_acos=meta["breakeven_acos"],
                aov_override=meta["effective_aov"],
                target_cpa_override=meta["effective_cpa"],
            )
            module_results["keyword"] = {
                "results": kw_res, "all_actions": all_kw_actions, "stats": kw_stats
            }

            # 暂停类 (Pause)
            for _, r in kw_res["pause"].iterrows():
                sp = float(r.get("广告花费", 20.0))
                raw_items.append({
                    "layer": "rule_keyword",
                    "domain": "关键词竞价",
                    "priority": "P0",
                    "entity_id": r["关键词"],
                    "campaign": r["所在活动"],
                    "ad_group": "-",
                    "current_stat": r["依据数字"],
                    "action_code": "PAUSE_KEYWORD",
                    "action_text": f"暂停关键词投放: {r['建议出价调整']}",
                    "magnitude": "完全暂停 (100% 暂停)",
                    "rationale": "零订单转化且消耗远超动态止损线，持续造成资金失血",
                    "risk_warning": "暂停后关注所属广告活动整体曝光量变化，若该词为核心流量大词可考虑优化落地页后重新唤醒",
                    "validation_window": "即刻生效，观察 3 天",
                    "success_criteria": "该词不再产生任何花费，广告组资金重新集中于高产词",
                    "confidence": "高置信度",
                    "estimated_impact": sp,
                    "raw_row": r.to_dict(),
                })

            # 降价类 (Bid Down)
            for _, r in kw_res["bid_down"].iterrows():
                raw_items.append({
                    "layer": "rule_keyword",
                    "domain": "关键词竞价",
                    "priority": "P1",
                    "entity_id": r["关键词"],
                    "campaign": r["所在活动"],
                    "ad_group": "-",
                    "current_stat": r["依据数字"],
                    "action_code": "BID_DOWN",
                    "action_text": r["建议出价调整"],
                    "magnitude": "竞价下调 20%",
                    "rationale": f"当前 ACoS 超过保本警戒线 ({meta['breakeven_acos']*100:.1f}%)，需通过降权拉低点击成本",
                    "risk_warning": "下调竞价可能导致首屏展示位掉落，需确保点击量不发生断崖式下跌",
                    "validation_window": "7 个自然日",
                    "success_criteria": "CPC 降低 15%~20%，ACoS 回落至保本线以内，且出单稳定",
                    "confidence": "高置信度",
                    "estimated_impact": 15.0,
                    "raw_row": r.to_dict(),
                })

            # 加价类 (Bid Up)
            for _, r in kw_res["bid_up"].iterrows():
                raw_items.append({
                    "layer": "rule_keyword",
                    "domain": "关键词竞价",
                    "priority": "P2",
                    "entity_id": r["关键词"],
                    "campaign": r["所在活动"],
                    "ad_group": "-",
                    "current_stat": r["依据数字"],
                    "action_code": "BID_UP",
                    "action_text": r["建议出价调整"],
                    "magnitude": "竞价上调 15%",
                    "rationale": f"ROAS 达到或超过目标线 ({1.0/meta['target_acos']:.2f}x)，具备充沛利润安全垫",
                    "risk_warning": "加价放量需确保商品库存充足，防止广告热卖导致断货",
                    "validation_window": "7 个自然日",
                    "success_criteria": "曝光量与订单量环比增长 20% 以上，ROAS 维持达标",
                    "confidence": "高置信度",
                    "estimated_impact": 35.0,
                    "raw_row": r.to_dict(),
                })

            # 恢复投放 (Unpause)
            for _, r in kw_res["unpause"].iterrows():
                raw_items.append({
                    "layer": "rule_keyword",
                    "domain": "关键词竞价",
                    "priority": "P2",
                    "entity_id": r["关键词"],
                    "campaign": r["所在活动"],
                    "ad_group": "-",
                    "current_stat": r["依据数字"],
                    "action_code": "UNPAUSE_KEYWORD",
                    "action_text": r["建议出价调整"],
                    "magnitude": "恢复有效投放 (Enabled)",
                    "rationale": "历史数据验证投产高于保本线，当前误处于暂停状态，存在被压制的潜能",
                    "risk_warning": "恢复初期建议保持原出价或微调，观察 3 天首单转化",
                    "validation_window": "5 个自然日",
                    "success_criteria": "激活出单，恢复正向现金流贡献",
                    "confidence": "中置信度",
                    "estimated_impact": 40.0,
                    "raw_row": r.to_dict(),
                })

        # 3. 广告活动预算规则
        camp_df = tables.get("campaign")
        if camp_df is not None and not camp_df.empty:
            camp_live_df, inactive_summary, budget_notice = analyze_campaign_health(camp_df, days=30)
            module_results["campaign"] = {
                "live_df": camp_live_df,
                "inactive_summary": inactive_summary,
                "budget_notice": budget_notice,
            }

            for _, c in camp_live_df.iterrows():
                tags = c.get("标签列表", [])
                c_name = c["活动名"]
                spend_val = float(c["花费"])
                roas_val = float(c["ROAS"]) if c["ROAS"] is not None and not pd.isna(c["ROAS"]) else 0.0
                daily_b = float(c.get("每日预算", 0.0) or 0.0)

                if "预算撞顶" in tags:
                    action_code = "BUDGET_INCREASE" if roas_val >= meta["target_roas"] else "BUDGET_REALLOCATE"
                    action_txt = (
                        f"优质计划预算撞顶（ROAS {roas_val:.2f}）：建议扩充日预算 +20%~30% 拓量"
                        if action_code == "BUDGET_INCREASE"
                        else f"预算撞顶但投产不足（ROAS {roas_val:.2f}）：建议优先控降低效词出价，严禁盲目加总预算"
                    )
                    raw_items.append({
                        "layer": "rule_campaign",
                        "domain": "活动预算",
                        "priority": "P1",
                        "entity_id": c_name,
                        "campaign": c_name,
                        "ad_group": "-",
                        "current_stat": f"花费 ${spend_val:.2f}, 每日预算 ${daily_b:.2f}, ROAS {roas_val:.2f}",
                        "action_code": action_code,
                        "action_text": action_txt,
                        "estimated_impact": max(10.0, daily_b * 0.2),
                        "raw_row": c.to_dict(),
                    })
                elif "烧钱零转化" in tags and spend_val >= 30.0:
                    raw_items.append({
                        "layer": "rule_campaign",
                        "domain": "活动预算",
                        "priority": "P0",
                        "entity_id": c_name,
                        "campaign": c_name,
                        "ad_group": "-",
                        "current_stat": f"花费 ${spend_val:.2f}, 0订单",
                        "action_code": "PAUSE_CAMPAIGN",
                        "action_text": f"活动累计消耗 ${spend_val:.2f} 零转化，建议暂停活动或全面重置投放组",
                        "estimated_impact": spend_val,
                        "raw_row": c.to_dict(),
                    })

        # 4. 广告位与页面规则
        plat_df = tables.get("platform")
        pg_df = tables.get("page_type")
        if (plat_df is not None and not plat_df.empty) or (pg_df is not None and not pg_df.empty):
            placement_res = analyze_placements(plat_df, pg_df, macro_roas=meta["actual_roas"])
            module_results["placement"] = placement_res

            for _, r in placement_res.get("page_type_df", pd.DataFrame()).iterrows():
                if "裁剪" in r.get("诊断建议", "") or "降低竞价" in r.get("诊断建议", ""):
                    raw_items.append({
                        "layer": "rule_placement",
                        "domain": "投放位置",
                        "priority": "P1",
                        "entity_id": r["页面类型"],
                        "campaign": "全局页面位置",
                        "ad_group": "-",
                        "current_stat": f"花费 ${r['花费']:.2f}, ROAS {r['ROAS']:.2f}",
                        "action_code": "CUT_PLACEMENT_TRAFFIC",
                        "action_text": r["诊断建议"],
                        "estimated_impact": float(r["花费"] * 0.3),
                        "raw_row": r.to_dict(),
                    })

        # 5. SKU 真实利润模型规则
        ad_item_df = tables.get("ad_item")
        if ad_item_df is not None and not ad_item_df.empty and self.cost_dict:
            sku_profit_df, sku_profit_stats = calculate_sku_profit_analytics(
                ad_item_df, self.cost_dict, default_margin=self.breakeven_acos
            )
            module_results["sku_profit"] = {"profit_df": sku_profit_df, "stats": sku_profit_stats}

            for _, r in sku_profit_df.iterrows():
                if r["广告后真实净利"] < -30.0:
                    raw_items.append({
                        "layer": "rule_sku_profit",
                        "domain": "SKU净利",
                        "priority": "P0",
                        "entity_id": r["SKU"],
                        "campaign": "全店SKU",
                        "ad_group": "-",
                        "current_stat": f"广告后净亏损 ${abs(r['广告后真实净利']):.2f}, 实际ACoS {r['实际ACoS']*100:.1f}% (保本线 {r['动态保本ACoS']*100:.1f}%)",
                        "action_code": "STOP_LOSS_SKU",
                        "action_text": r["经营决策指令"],
                        "estimated_impact": abs(float(r["广告后真实净利"])),
                        "raw_row": r.to_dict(),
                    })

        return {"raw_items": raw_items, "module_results": module_results}

    def _arbitrate_conflicts(
        self, raw_recommendations: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """
        冲突仲裁层：
        1. 严格互斥规则：
           - 同实体若存在 PAUSE，则必须压制 BID_DOWN 与 BID_UP
           - 同实体若存在 BID_DOWN，则必须压制 BID_UP
           - 若搜索词被标记 NEGATIVE，但在挖词中出现，按高风险优先否定并记录冲突日志
        2. 优先级加权与去重
        """
        raw_items = raw_recommendations.get("raw_items", [])
        if not raw_items:
            return [], []

        conflict_log: List[Dict[str, str]] = []
        action_priority_map = {
            "PAUSE_KEYWORD": 100,
            "NEGATIVE_PHRASE": 90,
            "NEGATIVE_EXACT": 85,
            "STOP_LOSS_SKU": 80,
            "BID_DOWN": 60,
            "CUT_PLACEMENT_TRAFFIC": 50,
            "BUDGET_REALLOCATE": 40,
            "BUDGET_INCREASE": 35,
            "BID_UP": 30,
            "PROMOTE_KEYWORD": 25,
            "UNPAUSE_KEYWORD": 20,
        }

        # 按实体维度分组
        entity_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for it in raw_items:
            key = (str(it["entity_id"]).strip().lower(), str(it["campaign"]).strip().lower())
            if key not in entity_groups:
                entity_groups[key] = []
            entity_groups[key].append(it)

        arbitrated: List[Dict[str, Any]] = []

        for (ent_id, camp), group in entity_groups.items():
            if len(group) == 1:
                arbitrated.append(group[0])
                continue

            # 发生多重建议冲突，按权重从高到低裁决
            group_sorted = sorted(
                group,
                key=lambda x: action_priority_map.get(x["action_code"], 0),
                reverse=True
            )
            winner = group_sorted[0]
            arbitrated.append(winner)

            # 记录冲突日志
            suppressed = group_sorted[1:]
            for sup in suppressed:
                conflict_log.append({
                    "entity": ent_id,
                    "campaign": camp,
                    "winner_action": f"{winner['action_code']} ({winner['action_text']})",
                    "suppressed_action": f"{sup['action_code']} ({sup['action_text']})",
                    "arbitration_rule": f"基于【止损优先原则】，指令 {winner['action_code']} 压制了冲突指令 {sup['action_code']}",
                })

        # 按优先级 (P0 -> P1 -> P2) 以及预估业务影响排序
        p_weight = {"P0": 0, "P1": 1, "P2": 2}
        arbitrated = sorted(
            arbitrated,
            key=lambda x: (p_weight.get(x["priority"], 9), -x["estimated_impact"])
        )

        return arbitrated, conflict_log

    def _build_final_decisions(
        self,
        arbitrated_actions: List[Dict[str, Any]],
        conflict_log: List[Dict[str, str]],
        meta: Dict[str, Any],
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """决策输出层：构建结构化决策大表与经营摘要看板"""
        cols = [
            "优先级", "决策领域", "操作对象", "对象标识", "所属活动/范围", "当前表现依据", "当前指标依据",
            "建议动作", "决策执行指令", "建议调整幅度", "调整依据", "风险提示", "验证周期",
            "成功判断标准", "置信度", "预估影响金额($)", "执行状态"
        ]
        if not arbitrated_actions:
            empty_df = pd.DataFrame(columns=cols)
            return empty_df, {
                "total_actions": 0, "p0_count": 0, "p1_count": 0, "p2_count": 0,
                "preventable_waste": 0.0, "growth_potential": 0.0, "conflict_count": 0,
                "core_problem_answer": "当前数据不足或未发现高危失血异常。",
                "top3_actions": [],
                "validation_methodology": [],
            }

        rows = []
        p0_c = 0
        p1_c = 0
        p2_c = 0
        preventable_waste = 0.0
        growth_potential = 0.0

        for act in arbitrated_actions:
            prio = act["priority"]
            if prio == "P0":
                p0_c += 1
                preventable_waste += act["estimated_impact"]
            elif prio == "P1":
                p1_c += 1
                preventable_waste += act["estimated_impact"] * 0.5
            else:
                p2_c += 1
                growth_potential += act["estimated_impact"]

            rows.append({
                "优先级": prio,
                "决策领域": act["domain"],
                "操作对象": act["entity_id"],
                "对象标识": act["entity_id"],
                "所属活动/范围": act["campaign"],
                "当前表现依据": act["current_stat"],
                "当前指标依据": act["current_stat"],
                "建议动作": act["action_text"],
                "决策执行指令": act["action_text"],
                "建议调整幅度": act.get("magnitude", "适度"),
                "调整依据": act.get("rationale", act["current_stat"]),
                "风险提示": act.get("risk_warning", "密切监控转化率"),
                "验证周期": act.get("validation_window", "7天"),
                "成功判断标准": act.get("success_criteria", "ROAS稳定且出单平稳"),
                "置信度": act.get("confidence", "高置信度"),
                "预估影响金额($)": round(act["estimated_impact"], 2),
                "执行状态": "待执行",
            })

        decision_df = pd.DataFrame(rows)

        # 核心三大问题应答合成
        act_acos = meta.get("actual_acos", 0.0)
        bk_acos = self.breakeven_acos
        if p0_c > 0 and preventable_waste >= 25.0:
            core_problem = f"🚨 【无效流量严重失血】：当前发现 {p0_c} 起高危实体（累计无效消耗 ${preventable_waste:,.2f} 且 0 转化），正在直接吞噬店铺经营纯利。"
        elif act_acos > bk_acos:
            core_problem = f"⚖️ 【大盘 ACoS 穿透保本线】：整体实际 ACoS ({act_acos*100:.1f}%) 高于动态保本线 ({bk_acos*100:.1f}%)，全店广告处于实质净亏损，需实施结构性降权。"
        else:
            core_problem = "🚀 【头部放量瓶颈】：广告大盘整体健康盈利，但高投产关键词与爆款 SKU 受到预算撞顶或竞价偏低约束，增长潜能尚未充分释放。"

        top3 = []
        for i, act in enumerate(arbitrated_actions[:3]):
            top3.append({
                "rank": f"动作 {i+1}",
                "priority": act.get("priority", "P1"),
                "domain": act.get("domain", "广告调优"),
                "target": f"{act.get('entity_id')} (活动: {act.get('campaign')})",
                "action": act.get("action_text"),
                "magnitude": act.get("magnitude", "适度"),
                "rationale": act.get("rationale", act.get("current_stat")),
                "window": act.get("validation_window", "7天"),
            })

        val_methodology = [
            {"phase": "第 3 天 (止损核验)", "kpi": "无效花费归零", "desc": "核查被否定搜索词与暂停实体的花费是否彻底终止，单日无额外沉没资金流失。"},
            {"phase": "第 7 天 (结构核验)", "kpi": "ACoS 下降且出单平稳", "desc": "核查降价关键词的 ACoS 是否回落至目标线以内，且未出现流量断崖与订单误杀。"},
            {"phase": "第 14 天 (净利核验)", "kpi": "真实净现金贡献提升", "desc": "核算全店及核心 SKU 扣减广告费后的真实毛利润净额是否实现净增长。"},
        ]

        summary = {
            "total_actions": len(decision_df),
            "p0_count": p0_c,
            "p1_count": p1_c,
            "p2_count": p2_c,
            "preventable_waste": round(preventable_waste, 2),
            "growth_potential": round(growth_potential, 2),
            "conflict_count": len(conflict_log),
            "core_problem_answer": core_problem,
            "top3_actions": top3,
            "validation_methodology": val_methodology,
        }

        return decision_df, summary
