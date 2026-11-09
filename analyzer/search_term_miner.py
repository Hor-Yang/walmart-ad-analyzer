from typing import Any, Dict, List, Optional, Tuple
import re
import numpy as np
import pandas as pd
from .metrics import safe_divide

def mine_search_terms(
    search_term_df: pd.DataFrame,
    target_acos: float = 0.25,
    aov_override: Optional[float] = None,
    target_cpa_override: Optional[float] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    搜索词深度挖掘模块（重构聚合与动态阈值版）：
    1. 彻底废除单行判断逻辑，按【广告活动/广告组/搜索词】进行多维聚合分析；
    2. 废除固定 $15 静态数字，改用基于客单价 (AOV)、目标 CPA 和大盘 CVR 的动态止损阈值；
    3. 区分【否定精准】与【否定词组】：
       - 否定词组（Negative Phrase）：跨多活动重复高损耗、自动/广泛组乱窜、或命中通用噪音词根。
       - 否定精准（Negative Exact）：特定活动/组内特定长尾词无效损耗。
    4. 挖词清单：验证出单且高 ROAS 的搜索词，建议提拔至精准广告组。
    5. 高点击零转化词：全店或活动内累计高点击零转化词排查。
    """
    empty_neg = pd.DataFrame(columns=[
        "优先级", "搜索词", "来源广告活动", "来源广告组", "建议否定类型", "花费", "点击", "CTR", "订单", "总销售额", "ROAS", "建议动作"
    ])
    empty_mining = pd.DataFrame(columns=[
        "搜索词", "来源广告活动", "来源广告组", "订单", "总销售额", "ROAS", "当前CPC", "出价建议", "建议动作"
    ])
    empty_hc = pd.DataFrame(columns=[
        "搜索词", "来源广告活动", "花费", "点击", "CTR", "CPC", "订单", "诊断建议"
    ])
    empty_stats = {
        "p0_count": 0, "p0_spend": 0.0,
        "p1_count": 0, "p1_spend": 0.0,
        "mining_count": 0, "mining_sales": 0.0,
        "high_clicks_count": 0,
        "summary_text": "未上传或搜索词数据为空",
    }

    if search_term_df is None or search_term_df.empty:
        return empty_neg, empty_mining, empty_hc, empty_stats

    df = search_term_df.copy()

    # 1. 规范搜索词字段
    st_col = None
    for cand in ["搜索词", "customer search term", "search term", "search_term", "query", "客户搜索词"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                st_col = col
                break
        if st_col:
            break
    if st_col and st_col != "搜索词":
        df = df.rename(columns={st_col: "搜索词"})
    elif "搜索词" not in df.columns:
        # 数据质量底线：严禁捏造虚假搜索词！缺少核心字段直接返回空并标记原因
        empty_stats["summary_text"] = "报表中未找到【搜索词】核心字段。请确认上传的是领星【搜索词列表报表】，而非广告活动列表或关键词报表。"
        empty_stats["error"] = "缺少搜索词字段"
        return empty_neg, empty_mining, empty_hc, empty_stats

    # 2. 规范广告活动字段
    camp_col = None
    for cand in ["广告活动", "广告活动名称", "campaign name", "campaign", "活动名称", "活动名"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                camp_col = col
                break
        if camp_col:
            break
    if camp_col and camp_col != "广告活动":
        df = df.rename(columns={camp_col: "广告活动"})
    elif "广告活动" not in df.columns:
        df["广告活动"] = "通用广告活动"

    # 3. 规范广告组字段
    ag_col = None
    for cand in ["广告组", "广告组名称", "ad group", "ad_group", "adgroup", "ad group name"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                ag_col = col
                break
        if ag_col:
            break
    if ag_col and ag_col != "广告组":
        df = df.rename(columns={ag_col: "广告组"})
    elif "广告组" not in df.columns:
        df["广告组"] = "默认广告组"

    # 4. 规范数值指标字段
    num_aliases = {
        "广告花费": ["广告花费", "花费", "spend", "cost", "ad spend"],
        "曝光量": ["曝光量", "曝光", "impressions", "impression"],
        "点击": ["点击", "点击量", "clicks", "click"],
        "广告订单": ["广告订单", "订单", "orders", "order", "conversions"],
        "总销售额": ["总销售额", "销售额", "sales", "total sales", "attributed sales"],
    }
    for target_col, aliases in num_aliases.items():
        if target_col not in df.columns:
            found = False
            for al in aliases:
                for col in df.columns:
                    if al == str(col).strip().lower():
                        df[target_col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
                        found = True
                        break
                if found:
                    break
            if not found:
                df[target_col] = 0.0
        else:
            df[target_col] = pd.to_numeric(df[target_col], errors="coerce").fillna(0.0)

    # 基础文本规范化
    df["搜索词"] = df["搜索词"].astype(str).str.strip()
    df["广告活动"] = df["广告活动"].astype(str).str.strip()
    df["广告组"] = df["广告组"].astype(str).str.strip()

    # 过滤掉完全无效的空搜索词或系统占位符
    df = df[~df["搜索词"].isin(["", "-", "nan", "None", "null"])].copy()
    if df.empty:
        return empty_neg, empty_mining, empty_hc, empty_stats

    # =========================================================================
    # 核心重构：第一阶段聚合 - 按【广告活动, 广告组, 搜索词】汇总指标
    # （废除单行判断，将同一活动组内分散在各天或各匹配项的同一搜索词合并）
    # =========================================================================
    group_cols = ["广告活动", "广告组", "搜索词"]
    agg_df = df.groupby(group_cols, as_index=False).agg(
        广告花费=("广告花费", "sum"),
        曝光量=("曝光量", "sum"),
        点击=("点击", "sum"),
        广告订单=("广告订单", "sum"),
        总销售额=("总销售额", "sum"),
    )

    # 重算聚合后的关键指标
    agg_df["CTR"] = safe_divide(agg_df["点击"], agg_df["曝光量"])
    agg_df["CPC"] = safe_divide(agg_df["广告花费"], agg_df["点击"])
    agg_df["CVR"] = safe_divide(agg_df["广告订单"], agg_df["点击"])
    agg_df["ROAS"] = safe_divide(agg_df["总销售额"], agg_df["广告花费"])

    # =========================================================================
    # 核心重构：第二阶段聚合 - 跨活动全局搜索词表现透视（纯向量化高速计算）
    # =========================================================================
    df["_is_broad_auto"] = df["广告活动"].astype(str).str.contains(r"auto|广泛|broad", case=False, regex=True)
    global_term_agg = df.groupby("搜索词", as_index=True).agg(
        全店总花费=("广告花费", "sum"),
        全店总曝光=("曝光量", "sum"),
        全店总点击=("点击", "sum"),
        全店总订单=("广告订单", "sum"),
        全店总销售=("总销售额", "sum"),
        关联活动数=("广告活动", "nunique"),
        包含自动或广泛=("_is_broad_auto", "any"),
    ).to_dict("index")

    # 定义典型纯损耗无效词根（一旦这些词根在搜索词中反复出现且零转化，优先建议词组否定）
    STOP_STEMS = {
        "free", "diy", "parts", "repair", "manual", "used", "cheap",
        "how to", "wholesale", "rent", "ebay", "amazon", "youtube", "craigslist"
    }

    # =========================================================================
    # 动态阈值机制：依据客单价 (AOV)、目标 CPA 与大盘 CVR 动态推导止损阈值
    # =========================================================================
    tot_orders = float(df["广告订单"].sum())
    tot_sales = float(df["总销售额"].sum())
    tot_clicks = float(df["点击"].sum())
    calc_aov = (tot_sales / tot_orders) if tot_orders > 0 else 50.0
    effective_aov = aov_override if (aov_override and aov_override > 0) else calc_aov
    overall_cvr = (tot_orders / tot_clicks) if tot_clicks > 0 else 0.05
    effective_cpa = target_cpa_override if (target_cpa_override and target_cpa_override > 0) else (effective_aov * max(0.10, min(0.60, target_acos)))

    # 动态止损线：受客单价保护，结合目标 CPA，保底 $10
    dyn_neg_p0_spend = max(10.0, min(effective_aov * 0.60, effective_cpa * 1.5))
    dyn_neg_p1_spend = dyn_neg_p0_spend * 0.65
    dyn_min_clicks_p0 = max(12, int(1.2 / max(0.02, overall_cvr)))

    # =========================================================================
    # 清单 A：否词清单（动态阈值 + 样本量保护）
    # P0：零转化且 (花费 ≥ 动态止损线 或 点击 ≥ 预期无转化点击线)
    # P1：花费 ≥ P1动态线 且 ROAS < 1.0 (排除已进 P0 的词)
    # =========================================================================
    neg_rows = []
    for _, r in agg_df.iterrows():
        spend = float(r["广告花费"])
        orders = float(r["广告订单"])
        roas_v = float(r["ROAS"]) if r["ROAS"] is not None and not pd.isna(r["ROAS"]) else 0.0
        q = r["搜索词"]
        camp = r["广告活动"]
        ag = r["广告组"]
        clicks = int(r["点击"])
        ctr_val = r["CTR"]
        sales = float(r["总销售额"])

        is_p0 = (orders == 0) and ((spend >= dyn_neg_p0_spend) or (clicks >= dyn_min_clicks_p0 and spend >= 8.0))
        is_p1 = (spend >= dyn_neg_p1_spend) and (roas_v < 1.0) and not is_p0

        if not (is_p0 or is_p1):
            continue

        priority = "P0" if is_p0 else "P1"
        g_info = global_term_agg.get(q, {})
        camp_count = g_info.get("关联活动数", 1)
        has_broad_auto = g_info.get("包含自动或广泛", False)

        # 检查是否包含通用噪音词根
        q_lower = q.lower()
        matched_stems = [st for st in STOP_STEMS if re.search(r"\b" + re.escape(st) + r"\b", q_lower)]

        # 否定匹配类型决策机制：
        # 1. 词组否定（Negative Phrase）：
        #    - 命中噪音词根；或在 >=2 个活动中反复消耗且全店零转化；或在自动/广泛组中频繁窜词浪费
        # 2. 精准否定（Negative Exact）：
        #    - 单一活动内的具体长尾词浪费，精确否定该词本身，避免误伤同词根其他高转化变体
        if matched_stems:
            neg_type = "否定词组 (Negative Phrase)"
            stem_str = "、".join(matched_stems)
            action = f"检测到不相关噪音词根【{stem_str}】，建议在【{camp} - {ag}】添加否定词组 '{stem_str}'，阻止一切衍生无效点击"
        elif camp_count >= 2 and g_info.get("全店总订单", 0) == 0 and (has_broad_auto or spend >= dyn_neg_p0_spend * 1.2):
            neg_type = "否定词组 (Negative Phrase)"
            action = f"该词跨 {camp_count} 个活动反复扩散消耗且全店0转化，建议在【{camp}】添加否定词组，并排查关联活动"
        else:
            neg_type = "否定精准 (Negative Exact)"
            if is_p0:
                action = f"累计消耗 ${spend:.2f} 零转化（触发动态止损线 ${dyn_neg_p0_spend:.2f}），建议在【{camp} - {ag}】添加否定精准 '{q}'，彻底封死单点失血"
            else:
                action = f"投产严重过低 (ROAS {roas_v:.2f})，建议在【{camp} - {ag}】添加否定精准 '{q}' 控本"

        neg_rows.append({
            "优先级": priority,
            "搜索词": q,
            "来源广告活动": camp,
            "来源广告组": ag,
            "建议否定类型": neg_type,
            "花费": spend,
            "点击": clicks,
            "CTR": ctr_val,
            "订单": int(orders),
            "总销售额": sales,
            "ROAS": roas_v,
            "建议动作": action,
        })

    if neg_rows:
        neg_df = pd.DataFrame(neg_rows)
        neg_df["_sort_p"] = neg_df["优先级"].map({"P0": 0, "P1": 1})
        neg_df = neg_df.sort_values(["_sort_p", "花费"], ascending=[True, False]).drop(columns=["_sort_p"]).reset_index(drop=True)
    else:
        neg_df = empty_neg

    # =========================================================================
    # 清单 B：挖词清单（高转化词提拔）
    # 聚合后：订单 ≥ 2 且 ROAS ≥ 3.0
    # =========================================================================
    mining_rows = []
    for _, r in agg_df.iterrows():
        orders = float(r["广告订单"])
        roas_v = float(r["ROAS"]) if r["ROAS"] is not None and not pd.isna(r["ROAS"]) else 0.0
        if orders >= 2 and roas_v >= 3.0:
            cpc_val = float(r["CPC"]) if r["CPC"] is not None and not pd.isna(r["CPC"]) else 0.50
            rec_bid = round(cpc_val * 1.15, 2)
            q = r["搜索词"]
            camp = r["广告活动"]
            ag = r["广告组"]
            sales = float(r["总销售额"])
            action = f"该词在【{camp}】已验证稳定出单，建议提拔加入【单品精准匹配】专属组，建议初始竞价 ${rec_bid:.2f}"
            mining_rows.append({
                "搜索词": q,
                "来源广告活动": camp,
                "来源广告组": ag,
                "订单": int(orders),
                "总销售额": sales,
                "ROAS": roas_v,
                "当前CPC": cpc_val,
                "出价建议": rec_bid,
                "建议动作": action,
            })

    if mining_rows:
        mining_df = pd.DataFrame(mining_rows).sort_values(["订单", "ROAS"], ascending=[False, False]).reset_index(drop=True)
    else:
        mining_df = empty_mining

    # =========================================================================
    # 清单 C：高点击零转化词（聚合点击排查流量精准度与承接力）
    # 1. 组内聚合维度：点击 ≥ 50 且 订单 = 0
    # 2. 全局词级维度：跨活动累计点击 ≥ 50 且 订单 = 0
    # =========================================================================
    hc_rows = []
    seen_queries = set()

    # 1. 活动组内部点击 >= 50
    for _, r in agg_df.iterrows():
        clicks = int(r["点击"])
        orders = int(r["广告订单"])
        if clicks >= 50 and orders == 0:
            q = r["搜索词"]
            seen_queries.add((r["广告活动"], q))
            hc_rows.append({
                "搜索词": q,
                "来源广告活动": f"{r['广告活动']} (组: {r['广告组']})",
                "花费": float(r["广告花费"]),
                "点击": clicks,
                "CTR": r["CTR"],
                "CPC": r["CPC"],
                "订单": 0,
                "诊断建议": "组内高频点击但零转化：流量意图与落地页不符或价格竞争力不足，建议页面排查或加否定精准",
            })

    # 2. 跨活动汇总点击 >= 50（使用字典聚合缓存，避免全表暴力扫描）
    seen_terms_hc = {r["搜索词"] for r in hc_rows}
    for term, g_data in global_term_agg.items():
        tot_clicks = int(g_data.get("全店总点击", 0))
        tot_orders = int(g_data.get("全店总订单", 0))
        if tot_clicks >= 50 and tot_orders == 0:
            if g_data.get("关联活动数", 1) > 1 and term not in seen_terms_hc:
                tot_spend = float(g_data.get("全店总花费", 0.0))
                tot_impr = float(g_data.get("全店总曝光", 0.0))
                hc_rows.append({
                    "搜索词": term,
                    "来源广告活动": f"跨 {g_data.get('关联活动数', 1)} 个活动",
                    "花费": tot_spend,
                    "点击": tot_clicks,
                    "CTR": safe_divide(tot_clicks, tot_impr),
                    "CPC": safe_divide(tot_spend, tot_clicks),
                    "订单": 0,
                    "诊断建议": "全店多活动累计高点击零转化：属于典型泛流量大词消耗，建议在全店相关活动中同步添加否定精准",
                })

    if hc_rows:
        high_clicks_df = pd.DataFrame(hc_rows).sort_values("点击", ascending=False).reset_index(drop=True)
    else:
        high_clicks_df = empty_hc

    # =========================================================================
    # 统计信息汇总
    # =========================================================================
    p0_sub = neg_df[neg_df["优先级"] == "P0"] if not neg_df.empty else pd.DataFrame()
    p1_sub = neg_df[neg_df["优先级"] == "P1"] if not neg_df.empty else pd.DataFrame()

    p0_count = len(p0_sub)
    p0_spend = float(p0_sub["花费"].sum()) if not p0_sub.empty else 0.0

    p1_count = len(p1_sub)
    p1_spend = float(p1_sub["花费"].sum()) if not p1_sub.empty else 0.0

    mining_count = len(mining_df)
    mining_sales = float(mining_df["总销售额"].sum()) if not mining_df.empty else 0.0

    summary_text = (
        f"经跨活动与广告组聚合校验：识别 P0 否词 {p0_count} 个（浪费 ${p0_spend:,.2f}）；"
        f"P1 否词 {p1_count} 个（${p1_spend:,.2f}）；"
        f"高转化可挖词 {mining_count} 个（贡献销售额 ${mining_sales:,.2f}）。"
    )

    stats = {
        "p0_count": p0_count,
        "p0_spend": round(p0_spend, 2),
        "p1_count": p1_count,
        "p1_spend": round(p1_spend, 2),
        "mining_count": mining_count,
        "mining_sales": round(mining_sales, 2),
        "high_clicks_count": len(high_clicks_df),
        "summary_text": summary_text,
        "dynamic_neg_spend_threshold": round(dyn_neg_p0_spend, 2),
        "effective_aov": round(effective_aov, 2),
    }

    return neg_df, mining_df, high_clicks_df, stats
