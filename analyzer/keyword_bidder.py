from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from .metrics import safe_divide

def analyze_keyword_bids(
    keyword_df: pd.DataFrame,
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame, Dict[str, Any]]:
    """
    关键词出价优化分析模块：
    输出四类关键词清单：
    1. 该降价：enabled、花费 ≥ $10、ROAS < 1.5 或 订单 = 0 -> 建议竞价下调 20%
    2. 该加价：enabled、ROAS ≥ 4.0、ACOS ≤ 25% (且有订单) -> 建议竞价上调 15%
    3. 该暂停：enabled、花费 ≥ $20、订单 = 0 -> 建议 paused
    4. 被误暂停的潜力词：paused、历史 ROAS ≥ 3.0 -> 建议恢复 enabled

    输出列：关键词、匹配方式(broad/phrase/exact)、所在活动、当前竞价、建议竞价、状态、依据数字
    """
    empty_cols = ["关键词", "匹配方式", "所在活动", "当前竞价", "建议竞价", "状态", "依据数字", "建议分类"]
    empty_res = {
        "bid_down": pd.DataFrame(columns=empty_cols),
        "bid_up": pd.DataFrame(columns=empty_cols),
        "pause": pd.DataFrame(columns=empty_cols),
        "unpause": pd.DataFrame(columns=empty_cols),
    }
    empty_stats = {
        "bid_down_count": 0, "bid_up_count": 0,
        "pause_count": 0, "unpause_count": 0,
        "pause_spend": 0.0,
    }

    if keyword_df is None or keyword_df.empty:
        return empty_res, pd.DataFrame(columns=empty_cols), empty_stats

    df = keyword_df.copy()

    # 规范列名
    kw_col = None
    for cand in ["关键词", "keyword", "keywords", "kw"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                kw_col = col
                break
        if kw_col:
            break
    if kw_col and kw_col != "关键词":
        df = df.rename(columns={kw_col: "关键词"})
    elif "关键词" not in df.columns:
        df["关键词"] = [f"关键词_{i+1}" for i in range(len(df))]

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

    status_col = None
    for cand in ["关键词状态", "状态", "status", "keyword status", "state"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                status_col = col
                break
        if status_col:
            break
    if status_col and status_col != "关键词状态":
        df = df.rename(columns={status_col: "关键词状态"})
    elif "关键词状态" not in df.columns:
        df["关键词状态"] = "enabled"

    match_col = None
    for cand in ["匹配方式", "match type", "match_type", "matchtype"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                match_col = col
                break
        if match_col:
            break
    if match_col and match_col != "匹配方式":
        df = df.rename(columns={match_col: "匹配方式"})
    elif "匹配方式" not in df.columns:
        df["匹配方式"] = "broad"

    # 标准化数值
    num_aliases = {
        "广告花费": ["广告花费", "花费", "spend", "cost", "ad spend"],
        "曝光量": ["曝光量", "曝光", "impressions", "impression"],
        "点击": ["点击", "点击量", "clicks", "click"],
        "广告订单": ["广告订单", "订单", "orders", "order", "conversions"],
        "总销售额": ["总销售额", "销售额", "sales", "total sales", "attributed sales"],
        "竞价": ["广告竞价", "竞价", "bid", "current bid", "建议竞价", "出价"],
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

    # 规范关键字段
    df["关键词"] = df["关键词"].astype(str).str.strip()
    df["所在活动"] = df["广告活动"].astype(str).str.strip()
    df["状态"] = df["关键词状态"].astype(str).str.lower().str.strip()
    df["匹配方式"] = df["匹配方式"].astype(str).str.lower().str.strip()
    df["当前竞价"] = df["竞价"]

    # 重算指标
    df["ROAS"] = safe_divide(df["总销售额"], df["广告花费"])
    df["ACOS"] = safe_divide(df["广告花费"], df["总销售额"])
    df["CTR"] = safe_divide(df["点击"], df["曝光量"])
    df["CPC"] = safe_divide(df["广告花费"], df["点击"])

    roas_val = df["ROAS"].apply(lambda x: 0.0 if x is None or pd.isna(x) else float(x))
    acos_val = df["ACOS"].apply(lambda x: 1.0 if x is None or pd.isna(x) else float(x))

    # =========================================================================
    # 3. 该暂停：enabled、花费 ≥ $20、订单 = 0（最紧急止损项，优先归类）
    # =========================================================================
    pause_mask = (df["状态"] == "enabled") & (df["广告花费"] >= 20.0) & (df["广告订单"] == 0)
    pause_raw = df[pause_mask].copy()

    if not pause_raw.empty:
        pause_raw["建议分类"] = "该暂停"
        pause_raw["建议竞价"] = "建议 paused"
        pause_raw["依据数字"] = pause_raw.apply(
            lambda r: f"花费 ${r['广告花费']:.2f}，点击 {int(r['点击'])}，0订单转化", axis=1
        )
    else:
        pause_raw = pd.DataFrame(columns=df.columns.tolist() + ["建议分类", "建议竞价", "依据数字"])

    # =========================================================================
    # 1. 该降价：enabled、花费 ≥ $10、(ROAS < 1.5 或 订单 = 0)（排除已归入"该暂停"的词）
    # 建议竞价下调 20%
    # =========================================================================
    bid_down_mask = (
        (df["状态"] == "enabled")
        & (df["广告花费"] >= 10.0)
        & ((roas_val < 1.5) | (df["广告订单"] == 0))
        & (~pause_mask)
    )
    bid_down_raw = df[bid_down_mask].copy()

    if not bid_down_raw.empty:
        bid_down_raw["建议分类"] = "该降价"
        bid_down_raw["建议竞价"] = bid_down_raw["当前竞价"].apply(
            lambda b: f"${round(b * 0.80, 2):.2f} (-20%)" if b > 0 else "0.00"
        )
        bid_down_raw["依据数字"] = bid_down_raw.apply(
            lambda r: f"花费 ${r['广告花费']:.2f}，订单 {int(r['广告订单'])}，ROAS {r['ROAS']:.2f}"
            if r["ROAS"] is not None and not pd.isna(r["ROAS"]) and r["ROAS"] > 0
            else f"花费 ${r['广告花费']:.2f}，点击 {int(r['点击'])}，0订单",
            axis=1,
        )
    else:
        bid_down_raw = pd.DataFrame(columns=df.columns.tolist() + ["建议分类", "建议竞价", "依据数字"])

    # =========================================================================
    # 2. 该加价：enabled、ROAS ≥ 4.0、ACOS ≤ 25% (且有订单)
    # 建议竞价上调 15%
    # =========================================================================
    bid_up_mask = (
        (df["状态"] == "enabled")
        & (roas_val >= 4.0)
        & (acos_val <= 0.25)
        & (df["广告订单"] >= 1)
    )
    bid_up_raw = df[bid_up_mask].copy()

    if not bid_up_raw.empty:
        bid_up_raw["建议分类"] = "该加价"
        bid_up_raw["建议竞价"] = bid_up_raw["当前竞价"].apply(
            lambda b: f"${round(b * 1.15, 2):.2f} (+15%)" if b > 0 else "0.00"
        )
        bid_up_raw["依据数字"] = bid_up_raw.apply(
            lambda r: f"ROAS {r['ROAS']:.2f}，ACOS {r['ACOS']*100:.1f}%，订单 {int(r['广告订单'])}，销售额 ${r['总销售额']:.2f}",
            axis=1,
        )
    else:
        bid_up_raw = pd.DataFrame(columns=df.columns.tolist() + ["建议分类", "建议竞价", "依据数字"])

    # =========================================================================
    # 4. 被误暂停的潜力词：paused、历史 ROAS ≥ 3.0
    # 建议恢复 enabled
    # =========================================================================
    unpause_mask = (
        (df["状态"] == "paused")
        & (roas_val >= 3.0)
        & (df["广告订单"] >= 1)
    )
    unpause_raw = df[unpause_mask].copy()

    if not unpause_raw.empty:
        unpause_raw["建议分类"] = "被误暂停"
        unpause_raw["建议竞价"] = unpause_raw["当前竞价"].apply(
            lambda b: f"恢复 enabled (${b:.2f})" if b > 0 else "恢复 enabled"
        )
        unpause_raw["依据数字"] = unpause_raw.apply(
            lambda r: f"历史 ROAS {r['ROAS']:.2f}，订单 {int(r['广告订单'])}，销售额 ${r['总销售额']:.2f}，花费 ${r['广告花费']:.2f}",
            axis=1,
        )
    else:
        unpause_raw = pd.DataFrame(columns=df.columns.tolist() + ["建议分类", "建议竞价", "依据数字"])

    # 规范各表输出列与格式
    target_cols = ["关键词", "匹配方式", "所在活动", "当前竞价", "建议竞价", "状态", "依据数字", "建议分类"]

    def clean_output(raw_sub: pd.DataFrame, sort_col: str = "广告花费") -> pd.DataFrame:
        if raw_sub.empty:
            return pd.DataFrame(columns=target_cols)
        sorted_sub = raw_sub.sort_values(sort_col, ascending=False).reset_index(drop=True)
        return sorted_sub[target_cols]

    bid_down_df = clean_output(bid_down_raw)
    bid_up_df = clean_output(bid_up_raw, sort_col="总销售额")
    pause_df = clean_output(pause_raw)
    unpause_df = clean_output(unpause_raw, sort_col="总销售额")

    all_recommendations = pd.concat(
        [pause_df, bid_down_df, bid_up_df, unpause_df], ignore_index=True
    )

    stats = {
        "pause_count": len(pause_df),
        "pause_spend": float(pause_raw["广告花费"].sum()) if not pause_raw.empty else 0.0,
        "bid_down_count": len(bid_down_df),
        "bid_down_spend": float(bid_down_raw["广告花费"].sum()) if not bid_down_raw.empty else 0.0,
        "bid_up_count": len(bid_up_df),
        "bid_up_sales": float(bid_up_raw["总销售额"].sum()) if not bid_up_raw.empty else 0.0,
        "unpause_count": len(unpause_df),
        "unpause_sales": float(unpause_raw["总销售额"].sum()) if not unpause_raw.empty else 0.0,
    }

    result_dict = {
        "pause": pause_df,
        "bid_down": bid_down_df,
        "bid_up": bid_up_df,
        "unpause": unpause_df,
    }

    return result_dict, all_recommendations, stats
