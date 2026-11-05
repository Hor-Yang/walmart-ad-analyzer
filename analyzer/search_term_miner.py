from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from .metrics import safe_divide

def mine_search_terms(
    search_term_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    搜索词深度挖掘模块（高性能优化版）：
    输出三张清单：
    1. 清单A：否词清单（P0 烧钱零转化、P1 低效产出）
    2. 清单B：挖词清单（高转化优质词，建议迁入精准广告活动）
    3. 清单C：高点击零转化词（流量不精准或 Listing 承接力问题）
    4. 统计汇总数据 stats
    """
    if search_term_df is None or search_term_df.empty:
        empty_neg = pd.DataFrame(columns=[
            "优先级", "搜索词", "来源广告活动", "花费", "点击", "CTR", "订单", "总销售额", "ROAS", "建议动作"
        ])
        empty_mining = pd.DataFrame(columns=[
            "搜索词", "来源广告活动", "订单", "总销售额", "ROAS", "当前CPC", "出价建议", "建议动作"
        ])
        empty_hc = pd.DataFrame(columns=[
            "搜索词", "来源广告活动", "花费", "点击", "CTR", "CPC", "订单", "诊断建议"
        ])
        stats = {
            "p0_count": 0, "p0_spend": 0.0,
            "p1_count": 0, "p1_spend": 0.0,
            "mining_count": 0, "mining_sales": 0.0,
            "high_clicks_count": 0,
            "summary_text": "未上传或搜索词数据为空",
        }
        return empty_neg, empty_mining, empty_hc, stats

    df = search_term_df.copy()

    # 规范中英文表头列名
    st_col = None
    for cand in ["搜索词", "customer search term", "search term", "search_term", "query"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                st_col = col
                break
        if st_col:
            break
    if st_col and st_col != "搜索词":
        df = df.rename(columns={st_col: "搜索词"})
    elif "搜索词" not in df.columns:
        df["搜索词"] = [f"搜索词_{i+1}" for i in range(len(df))]

    camp_col = None
    for cand in ["广告活动", "广告活动名称", "campaign name", "campaign", "活动名称"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                camp_col = col
                break
        if camp_col:
            break
    if camp_col and camp_col != "广告活动":
        df = df.rename(columns={camp_col: "广告活动"})
    elif "广告活动" not in df.columns:
        df["广告活动"] = "未关联活动"

    # 基础数值校验与标准化
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

    # 规范搜索词与广告活动
    df["搜索词"] = df["搜索词"].astype(str).str.strip()
    df["来源广告活动"] = df["广告活动"].astype(str).str.strip()

    # 比率重算
    df["CTR"] = safe_divide(df["点击"], df["曝光量"])
    df["CPC"] = safe_divide(df["广告花费"], df["点击"])
    df["CVR"] = safe_divide(df["广告订单"], df["点击"])
    df["ROAS"] = safe_divide(df["总销售额"], df["广告花费"])

    roas_val = df["ROAS"].apply(lambda x: 0.0 if x is None or pd.isna(x) else float(x))

    # =========================================================================
    # 清单 A：否词清单
    # P0：花费 ≥ $15 且 订单 = 0
    # P1：花费 ≥ $10 且 ROAS < 1.0 (排除已进 P0 的词)
    # =========================================================================
    p0_mask = (df["广告花费"] >= 15.0) & (df["广告订单"] == 0)
    p1_mask = (df["广告花费"] >= 10.0) & (roas_val < 1.0) & (~p0_mask)

    p0_df = df[p0_mask].copy()
    p0_df["优先级"] = "P0"

    p1_df = df[p1_mask].copy()
    p1_df["优先级"] = "P1"

    neg_df = pd.concat([p0_df, p1_df], ignore_index=True)

    if not neg_df.empty:
        # 高性能关联：仅针对进入否词候选集的词查询是否在多个广泛/Auto活动出现
        cand_queries = set(neg_df["搜索词"].unique())
        camp_lower = df["来源广告活动"].str.lower()
        is_broad_auto = camp_lower.str.contains("auto") | df["来源广告活动"].str.contains("广泛")
        matched_df = df[df["搜索词"].isin(cand_queries) & is_broad_auto]
        broad_auto_counts = (
            matched_df.groupby("搜索词")["来源广告活动"].nunique().to_dict()
        )

        def generate_neg_action(r: pd.Series) -> str:
            q = r["搜索词"]
            camp = r["来源广告活动"]
            count = broad_auto_counts.get(q, 0)
            if count > 1:
                return f"建议在【{camp}】添加否定精准 '{q}'；该词在多个广泛/Auto活动反复出现，建议同时加否定词组"
            else:
                return f"建议在【{camp}】添加否定精准 '{q}'"

        def safe_rename(d: pd.DataFrame, ren: dict) -> pd.DataFrame:
            res = d.copy()
            for src, dst in ren.items():
                if src in res.columns:
                    if dst in res.columns and dst != src:
                        res = res.drop(columns=[dst])
                    res = res.rename(columns={src: dst})
            return res

        neg_df["建议动作"] = neg_df.apply(generate_neg_action, axis=1)
        neg_df = safe_rename(neg_df, {
            "广告花费": "花费",
            "广告订单": "订单",
        })
        # 排序：P0 在前，同一优先级按花费降序
        neg_df["_sort_p"] = neg_df["优先级"].map({"P0": 0, "P1": 1})
        neg_df = neg_df.sort_values(["_sort_p", "花费"], ascending=[True, False]).drop(columns=["_sort_p"])
        neg_cols = ["优先级", "搜索词", "来源广告活动", "花费", "点击", "CTR", "订单", "总销售额", "ROAS", "建议动作"]
        neg_df = neg_df[neg_cols].reset_index(drop=True)
    else:
        neg_df = pd.DataFrame(columns=[
            "优先级", "搜索词", "来源广告活动", "花费", "点击", "CTR", "订单", "总销售额", "ROAS", "建议动作"
        ])

    # =========================================================================
    # 清单 B：挖词清单（高转化词，迁精准组）
    # 订单 ≥ 2 且 ROAS ≥ 3.0
    # =========================================================================
    mining_mask = (df["广告订单"] >= 2) & (roas_val >= 3.0)
    mining_raw = df[mining_mask].copy()

    def generate_mining_action(r: pd.Series) -> Tuple[float, str]:
        cpc_raw = r.get("当前CPC", r.get("CPC"))
        cpc = float(cpc_raw) if cpc_raw is not None and not pd.isna(cpc_raw) else 0.50
        rec_bid = round(cpc * 1.15, 2)
        action = f"该词已验证出单，建议加入精准匹配活动，出价建议 ${rec_bid:.2f}"
        return rec_bid, action

    if not mining_raw.empty:
        for src, dst in [("广告花费", "花费"), ("广告订单", "订单"), ("CPC", "当前CPC")]:
            if src in mining_raw.columns:
                if dst in mining_raw.columns and dst != src:
                    mining_raw = mining_raw.drop(columns=[dst])
                mining_raw = mining_raw.rename(columns={src: dst})
        bids_actions = mining_raw.apply(generate_mining_action, axis=1)
        mining_raw["出价建议"] = [ba[0] for ba in bids_actions]
        mining_raw["建议动作"] = [ba[1] for ba in bids_actions]
        # 排序：订单降序，ROAS降序
        mining_raw = mining_raw.sort_values(["订单", "ROAS"], ascending=[False, False])
        mining_cols = ["搜索词", "来源广告活动", "订单", "总销售额", "ROAS", "当前CPC", "出价建议", "建议动作"]
        mining_df = mining_raw[mining_cols].reset_index(drop=True)
    else:
        mining_df = pd.DataFrame(columns=[
            "搜索词", "来源广告活动", "订单", "总销售额", "ROAS", "当前CPC", "出价建议", "建议动作"
        ])

    # =========================================================================
    # 清单 C：高点击零转化词
    # 点击 ≥ 50 且 订单 = 0（同时支持行级与跨活动词级聚合判断）
    # =========================================================================
    # 1. 单行维度点击 >= 50 且 订单 = 0
    row_hc = df[(df["点击"] >= 50) & (df["广告订单"] == 0)].copy()

    # 2. 词级跨活动汇总点击 >= 50 且 订单 = 0（只汇总点击>=10的潜在异常词以极速完成）
    high_click_cand = df[(df["点击"] >= 10) & (df["广告订单"] == 0)]
    if not high_click_cand.empty:
        agg_cand = high_click_cand.groupby("搜索词").agg(
            总点击=("点击", "sum"),
            总订单=("广告订单", "sum"),
            总花费=("广告花费", "sum"),
            总曝光=("曝光量", "sum"),
            活动列表=("来源广告活动", lambda x: "、".join(sorted(x.unique()))),
        ).reset_index()
        agg_hc = agg_cand[(agg_cand["总点击"] >= 50) & (agg_cand["总订单"] == 0)]
    else:
        agg_hc = pd.DataFrame()

    hc_rows = []
    seen_queries = set()

    for _, r in row_hc.iterrows():
        q = r["搜索词"]
        seen_queries.add(q)
        cpc_val = r["CPC"]
        ctr_val = r["CTR"]
        hc_rows.append({
            "搜索词": q,
            "来源广告活动": r["来源广告活动"],
            "花费": r["广告花费"],
            "点击": int(r["点击"]),
            "CTR": ctr_val,
            "CPC": cpc_val,
            "订单": 0,
            "诊断建议": "流量不精准或Listing转化问题，建议排查页面承接力或添加否定精准",
        })

    for _, r in agg_hc.iterrows():
        q = r["搜索词"]
        if q not in seen_queries:
            seen_queries.add(q)
            clicks = r["总点击"]
            spend = r["总花费"]
            impr = r["总曝光"]
            cpc_val = safe_divide(spend, clicks)
            ctr_val = safe_divide(clicks, impr)
            hc_rows.append({
                "搜索词": q,
                "来源广告活动": r["活动列表"],
                "花费": spend,
                "点击": int(clicks),
                "CTR": ctr_val,
                "CPC": cpc_val,
                "订单": 0,
                "诊断建议": "跨活动多渠道持续消耗且零转化，流量与商品不符，建议立即在各活动加入否定精准",
            })

    if hc_rows:
        high_clicks_df = pd.DataFrame(hc_rows).sort_values("点击", ascending=False).reset_index(drop=True)
    else:
        high_clicks_df = pd.DataFrame(columns=[
            "搜索词", "来源广告活动", "花费", "点击", "CTR", "CPC", "订单", "诊断建议"
        ])

    # =========================================================================
    # 统计信息计算
    # =========================================================================
    p0_count = len(p0_df)
    p0_spend = float(p0_df["广告花费"].sum()) if not p0_df.empty else 0.0

    p1_count = len(p1_df)
    p1_spend = float(p1_df["广告花费"].sum()) if not p1_df.empty else 0.0

    mining_count = len(mining_df)
    mining_sales = float(mining_df["总销售额"].sum()) if not mining_df.empty else 0.0

    summary_text = (
        f"共识别 P0 否词 {p0_count} 个，合计浪费花费 ${p0_spend:,.2f}；"
        f"P1 否词 {p1_count} 个，合计 ${p1_spend:,.2f}；"
        f"可挖词 {mining_count} 个，贡献销售额 ${mining_sales:,.2f}。"
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
    }

    return neg_df, mining_df, high_clicks_df, stats
