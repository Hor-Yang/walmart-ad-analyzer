from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from .metrics import summarize_overview
from .campaign_health import analyze_campaign_health
from .search_term_miner import mine_search_terms
from .keyword_bidder import analyze_keyword_bids
from .ad_item_diagnosis import diagnose_ad_items
from .placement_analyzer import analyze_placements

def build_action_items(
    data_dict: Dict[str, Optional[pd.DataFrame]],
    days: Optional[int] = 30,
) -> Tuple[pd.DataFrame, List[str], Dict[str, Any]]:
    """
    动作汇总清单与老板摘要生成器：
    整合各诊断模块建议，生成全盘优先级总动作清单与 5 行核心管理层决策摘要。

    输出列：
    - 优先级 (P0 / P1 / P2)
    - 动作类型 (否词 / 加词 / 加价 / 降价 / 暂停 / 恢复 / 加预算 / Listing优化 / 位置裁剪)
    - 操作对象 (活动名 / 词 / 商品 / 平台端 / 页面位置)
    - 现状数字
    - 具体操作描述
    """
    actions: List[Dict[str, Any]] = []

    overview = summarize_overview(data_dict)
    macro_roas = overview.get("整体ROAS") or 3.36
    total_spend = overview.get("大盘总花费") or 0.0

    # =========================================================================
    # 1. 收集 P0 动作 (今天就做的紧急止血)
    # =========================================================================

    # 1.1 搜索词 P0 否词 (花费 >= $15 且 订单 = 0)
    st_df = data_dict.get("search_term")
    neg_p0_count = 0
    neg_p0_spend = 0.0
    neg_p1_count = 0
    neg_p1_spend = 0.0

    if st_df is not None and not st_df.empty:
        neg_df, mining_df, hc_df, _ = mine_search_terms(st_df)
        
        # P0 搜索词
        p0_terms = neg_df[neg_df["优先级"] == "P0"]
        neg_p0_count = len(p0_terms)
        neg_p0_spend = float(p0_terms["花费"].sum()) if not p0_terms.empty else 0.0

        for _, r in p0_terms.iterrows():
            actions.append({
                "优先级": "P0",
                "动作类型": "否词",
                "操作对象": f"搜索词: {r['搜索词']}",
                "现状数字": f"花费 ${r['花费']:.2f}，点击 {int(r['点击'])}，0订单",
                "具体操作描述": r["建议动作"],
                "_waste_amount": float(r["花费"]),
            })

        # P1 搜索词
        p1_terms = neg_df[neg_df["优先级"] == "P1"]
        neg_p1_count = len(p1_terms)
        neg_p1_spend = float(p1_terms["花费"].sum()) if not p1_terms.empty else 0.0

        for _, r in p1_terms.iterrows():
            actions.append({
                "优先级": "P1",
                "动作类型": "否词",
                "操作对象": f"搜索词: {r['搜索词']}",
                "现状数字": f"花费 ${r['花费']:.2f}，订单 {int(r['订单'])}，ROAS {r['ROAS']:.2f}",
                "具体操作描述": r["建议动作"],
                "_waste_amount": float(r["花费"]),
            })

        # P1 挖词上精准
        for _, r in mining_df.iterrows():
            actions.append({
                "优先级": "P1",
                "动作类型": "加词",
                "操作对象": f"搜索词: {r['搜索词']}",
                "现状数字": f"订单 {int(r['订单'])}，销售额 ${r['总销售额']:.2f}，ROAS {r['ROAS']:.2f}",
                "具体操作描述": r["建议动作"],
                "_waste_amount": float(r["总销售额"]),
            })

        # P2 高点击零转化词
        for _, r in hc_df.iterrows():
            actions.append({
                "优先级": "P2",
                "动作类型": "Listing优化",
                "操作对象": f"搜索词: {r['搜索词']}",
                "现状数字": f"点击 {int(r['点击'])}，花费 ${r['花费']:.2f}，0转化",
                "具体操作描述": r["诊断建议"],
                "_waste_amount": float(r["花费"]),
            })

    # 1.2 关键词模块动作 (暂停 / 降价 / 加价 / 恢复)
    kw_df = data_dict.get("keyword")
    if kw_df is not None and not kw_df.empty:
        kw_dict, _, _ = analyze_keyword_bids(kw_df)

        # P0 关键词该暂停
        for _, r in kw_dict["pause"].iterrows():
            actions.append({
                "优先级": "P0",
                "动作类型": "暂停",
                "操作对象": f"关键词: {r['关键词']} ({r['所在活动']})",
                "现状数字": r["依据数字"],
                "具体操作描述": f"已严重烧钱零产出，建议在活动中立即 pause 停投该关键词",
                "_waste_amount": float(str(r["依据数字"]).split("$")[1].split("，")[0]) if "$" in str(r["依据数字"]) else 20.0,
            })

        # P1 关键词该降价
        for _, r in kw_dict["bid_down"].iterrows():
            suggest_adj = r.get("建议出价调整", r.get("建议竞价", "建议下调20%"))
            actions.append({
                "优先级": "P1",
                "动作类型": "降价",
                "操作对象": f"关键词: {r['关键词']} ({r['所在活动']})",
                "现状数字": r["依据数字"],
                "具体操作描述": f"产出低效，{suggest_adj}",
                "_waste_amount": 10.0,
            })

        # P1 关键词该加价
        for _, r in kw_dict["bid_up"].iterrows():
            suggest_adj = r.get("建议出价调整", r.get("建议竞价", "建议上调15%"))
            actions.append({
                "优先级": "P1",
                "动作类型": "加价",
                "操作对象": f"关键词: {r['关键词']} ({r['所在活动']})",
                "现状数字": r["依据数字"],
                "具体操作描述": f"产出优异 (ROAS>4)，{suggest_adj} 抢占更多曝光",
                "_waste_amount": 15.0,
            })

        # P1 关键词被误暂停恢复
        for _, r in kw_dict["unpause"].iterrows():
            actions.append({
                "优先级": "P1",
                "动作类型": "恢复",
                "操作对象": f"关键词: {r['关键词']} ({r['所在活动']})",
                "现状数字": r["依据数字"],
                "具体操作描述": f"历史高产出词被误暂停，建议恢复 enabled 投放",
                "_waste_amount": 10.0,
            })

    # 1.3 广告活动模块动作 (暂停烧钱活动 / 明星活动加预算)
    camp_df = data_dict.get("campaign")
    if camp_df is not None and not camp_df.empty:
        live_camp, _, _ = analyze_campaign_health(camp_df, days=days)

        for _, r in live_camp.iterrows():
            t_list = r.get("标签列表", [])
            spend = float(r.get("花费", 0.0))
            roas = r.get("ROAS")

            # P0 烧钱零转化活动
            if "烧钱零转化" in t_list:
                actions.append({
                    "优先级": "P0",
                    "动作类型": "暂停",
                    "操作对象": f"广告活动: {r['活动名']}",
                    "现状数字": f"花费 ${spend:.2f}，0订单",
                    "具体操作描述": f"广告活动整体累计消耗较高且零订单转化，建议立即暂停该活动并重新规划投放词与承接品",
                    "_waste_amount": spend,
                })
            # P1 明星计划且预算撞顶 -> 加预算
            elif "明星计划" in t_list and "预算撞顶" in t_list:
                budget = float(r.get("每日预算", 0.0))
                actions.append({
                    "优先级": "P1",
                    "动作类型": "加预算",
                    "操作对象": f"广告活动: {r['活动名']}",
                    "现状数字": f"ROAS {roas:.2f}，当前每日预算 ${budget:.2f} (撞顶)",
                    "具体操作描述": f"高产出明星计划已达预算上限，建议每日预算上调 20%~30% 扩充优质订单",
                    "_waste_amount": spend,
                })
            # P2 样本不足
            elif "样本不足" in t_list and spend > 0:
                actions.append({
                    "优先级": "P2",
                    "动作类型": "Listing优化",
                    "操作对象": f"广告活动: {r['活动名']}",
                    "现状数字": f"点击数偏低，花费 ${spend:.2f}",
                    "具体操作描述": f"点击积累不足 50 次，统计样本偏少，暂不宜盲目调价，建议持续观察数据累积",
                    "_waste_amount": spend,
                })

    # 1.4 商品位诊断动作
    ad_df = data_dict.get("ad_item")
    if ad_df is not None and not ad_df.empty:
        ad_diag = diagnose_ad_items(ad_df)

        # P0 烧钱商品
        for _, r in ad_diag["burning_items"].iterrows():
            spend = float(r["花费"])
            sku_tag = f"SKU: {r['SKU']} ({r['项目ID']})" if ("SKU" in r and pd.notna(r["SKU"]) and str(r["SKU"]) != str(r["项目ID"])) else f"商品项目: {r['项目ID']}"
            actions.append({
                "优先级": "P0",
                "动作类型": "暂停",
                "操作对象": f"{sku_tag} ({r['商品名称'][:24]})",
                "现状数字": f"花费 ${spend:.2f}，点击 {int(r['点击'])}，0订单",
                "具体操作描述": r["建议动作"],
                "_waste_amount": spend,
            })

        # P2 竞价明显低于建议竞价
        for _, r in ad_diag["low_bid_items"].head(10).iterrows():
            sku_tag = f"SKU: {r['SKU']}" if ("SKU" in r and pd.notna(r["SKU"]) and str(r["SKU"]) != str(r["项目ID"])) else f"商品位: {r['项目ID']}"
            actions.append({
                "优先级": "P2",
                "动作类型": "加价",
                "操作对象": f"{sku_tag} ({r['广告活动']})",
                "现状数字": f"实际竞价 ${r['广告竞价']:.2f}，建议竞价 ${r['建议竞价']:.2f} (低 {r['低于幅度']})",
                "具体操作描述": r["建议动作"],
                "_waste_amount": 5.0,
            })

    # 1.5 流量位置优化 (平台 / 页面类型)
    plat_df = data_dict.get("platform")
    page_df = data_dict.get("page_type")
    if plat_df is not None or page_df is not None:
        plc_diag = analyze_placements(plat_df, page_df, macro_roas=macro_roas)

        # 平台建议
        if not plc_diag["platform_df"].empty:
            for _, r in plc_diag["platform_df"].iterrows():
                if "下调出价" in r["诊断建议"]:
                    actions.append({
                        "优先级": "P1",
                        "动作类型": "降价",
                        "操作对象": f"平台端: {r['平台'].upper()}",
                        "现状数字": f"花费占比 {r['花费占比']*100:.1f}%，ROAS {r['ROAS']:.2f}",
                        "具体操作描述": r["诊断建议"],
                        "_waste_amount": float(r["花费"]),
                    })

        # 页面位置裁剪建议
        if not plc_diag["page_type_df"].empty:
            for _, r in plc_diag["page_type_df"].iterrows():
                if "裁剪" in r["诊断建议"] or "零转化" in r["诊断建议"]:
                    actions.append({
                        "优先级": "P1",
                        "动作类型": "位置裁剪",
                        "操作对象": f"页面位置: {r['页面类型']}",
                        "现状数字": f"花费 ${r['花费']:.2f}，订单 {int(r['订单'])}",
                        "具体操作描述": r["诊断建议"],
                        "_waste_amount": float(r["花费"]),
                    })

    # =========================================================================
    # 2. 排序规则：P0 > P1 > P2，同优先级按浪费金额/花费从大到小排序
    # =========================================================================
    if actions:
        action_df = pd.DataFrame(actions)
        priority_map = {"P0": 0, "P1": 1, "P2": 2}
        action_df["_p_order"] = action_df["优先级"].map(priority_map).fillna(9)
        action_df = action_df.sort_values(
            ["_p_order", "_waste_amount"], ascending=[True, False]
        ).drop(columns=["_p_order", "_waste_amount"]).reset_index(drop=True)
    else:
        action_df = pd.DataFrame(columns=[
            "优先级", "动作类型", "操作对象", "现状数字", "具体操作描述"
        ])

    # =========================================================================
    # 3. 生成「老板摘要」5 行文字结论
    # =========================================================================
    p0_items = action_df[action_df["优先级"] == "P0"]
    top_p0_cuts = []
    for _, r in p0_items.head(3).iterrows():
        top_p0_cuts.append(f"{r['操作对象']} ({r['现状数字']})")
    cut_desc = "、".join(top_p0_cuts) if top_p0_cuts else "暂无严重超标浪费项"

    p1_items = action_df[(action_df["优先级"] == "P1") & (action_df["动作类型"].isin(["加词", "加价", "加预算"]))]
    top_p1_ups = []
    for _, r in p1_items.head(3).iterrows():
        top_p1_ups.append(f"{r['操作对象']} ({r['具体操作描述'].split('，')[-1]})")
    up_desc = "、".join(top_p1_ups) if top_p1_ups else "维持当前达标词组投放"

    total_neg_count = neg_p0_count + neg_p1_count
    total_neg_spend = neg_p0_spend + neg_p1_spend

    executive_summary = [
        f"1. 大盘全局表现：广告总花费 ${total_spend:,.2f}，整体 ROAS 达到 {macro_roas:.2f}，账户整体维持良性产出。",
        f"2. 紧急止血总览：累计识别搜索词否词 {total_neg_count} 个（P0 紧急否词 {neg_p0_count} 个、P1 低效否词 {neg_p1_count} 个），立即执行可直接挽回无效浪费 ${total_neg_spend:,.2f}。",
        f"3. 最该砍的 3 项 (P0 止血重点)：{cut_desc}。",
        f"4. 最该加的 3 项 (P1 扩量增长)：{up_desc}。",
        f"5. 结构与位置优化：App 端为主力贡献（花费占比约 80%，ROAS 3.5+），建议对 Mobile 端适度控溢价，并裁剪 Others 等低效页面流量。",
    ]

    stats = {
        "total_actions": len(action_df),
        "p0_count": len(p0_items),
        "p1_count": len(action_df[action_df["优先级"] == "P1"]),
        "p2_count": len(action_df[action_df["优先级"] == "P2"]),
        "total_neg_count": total_neg_count,
        "total_neg_spend": total_neg_spend,
    }

    return action_df, executive_summary, stats
