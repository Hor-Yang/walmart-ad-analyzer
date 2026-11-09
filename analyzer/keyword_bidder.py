from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from .metrics import safe_divide

def analyze_keyword_bids(
    keyword_df: pd.DataFrame,
    target_acos: float = 0.25,
    breakeven_acos: float = 0.35,
    aov_override: Optional[float] = None,
    target_cpa_override: Optional[float] = None,
    min_clicks_threshold: int = 15,
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame, Dict[str, Any]]:
    """
    关键词出价优化分析模块（动态阈值与防冲突仲裁版）：
    1. 严格区分【实际当前竞价】与【参考建议竞价】，严禁使用建议竞价对缺失的实际竞价进行盲目兜底计算。
    2. 动态阈值机制：废除固定 $20 暂停和 $10 降价阈值，改用基于客单价 (AOV)、目标 CPA 和保本 ACoS 的动态判定。
    3. 样本量保护机制：引入最低点击门槛保护 (clicks >= 15)，防止低样本误杀或过早降权。
    4. 动作去重与防冲突仲裁：同关键词在同活动中严格互斥（暂停 > 降价 > 加价 > 恢复），彻底根除同词既加又降的冲突指令。
    """
    empty_cols = [
        "关键词", "匹配方式", "所在活动", "实际当前竞价", "建议出价调整", "参考建议竞价", "状态", "依据数字", "建议分类"
    ]
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
        "missing_bid_count": 0,
    }

    if keyword_df is None or keyword_df.empty:
        return empty_res, pd.DataFrame(columns=empty_cols), empty_stats

    df = keyword_df.copy()

    # 1. 规范关键词列
    kw_col = None
    for cand in ["关键词", "keyword", "keywords", "kw", "投放词"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                kw_col = col
                break
        if kw_col:
            break
    if kw_col and kw_col != "关键词":
        df = df.rename(columns={kw_col: "关键词"})
    elif "关键词" not in df.columns:
        # 数据质量底线：严禁捏造虚假关键词
        empty_stats["summary_text"] = "报表中未找到【关键词】核心字段。请确认上传的是领星【关键词列表报表】。"
        empty_stats["error"] = "缺少关键词字段"
        return empty_res, pd.DataFrame(columns=empty_cols), empty_stats

    # 2. 规范广告活动列
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

    # 3. 规范状态列
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

    # 4. 规范匹配方式
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

    # =========================================================================
    # 5. 严格区分【实际当前竞价】与【参考建议竞价】（严禁建议值兜底实际值）
    # =========================================================================
    actual_bid_col = None
    # 实际竞价必须排除含有“建议”或“suggested”的列
    for col in df.columns:
        c_clean = str(col).strip().lower()
        if any(ex in c_clean for ex in ["建议", "suggest", "recommend", "推荐"]):
            continue
        if c_clean in ["广告竞价", "竞价", "当前竞价", "实际竞价", "出价", "bid", "current bid", "current_bid", "keyword bid"]:
            actual_bid_col = col
            break

    if actual_bid_col:
        df["实际当前竞价_数值"] = pd.to_numeric(df[actual_bid_col], errors="coerce")
    else:
        # 实际竞价缺失，禁止填 0 或建议值，保留 NaN
        df["实际当前竞价_数值"] = np.nan

    # 独立识别系统/领星建议竞价
    suggested_bid_col = None
    for col in df.columns:
        c_clean = str(col).strip().lower()
        if any(ex in c_clean for ex in ["建议", "suggest", "recommend"]):
            if any(term in c_clean for term in ["竞价", "出价", "bid"]):
                suggested_bid_col = col
                break

    if suggested_bid_col:
        df["参考建议竞价_数值"] = pd.to_numeric(df[suggested_bid_col], errors="coerce")
    else:
        df["参考建议竞价_数值"] = np.nan

    # 格式化展示文本
    df["实际当前竞价"] = df["实际当前竞价_数值"].apply(
        lambda v: f"${v:.2f}" if pd.notna(v) and v > 0 else "未提供/缺失"
    )
    df["参考建议竞价"] = df["参考建议竞价_数值"].apply(
        lambda v: f"${v:.2f}" if pd.notna(v) and v > 0 else "-"
    )

    # 6. 基础表现指标校验
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

    # 基础字段格式清洗
    df["关键词"] = df["关键词"].astype(str).str.strip()
    df["所在活动"] = df["广告活动"].astype(str).str.strip()
    df["状态"] = df["关键词状态"].astype(str).str.lower().str.strip()
    df["匹配方式"] = df["匹配方式"].astype(str).str.lower().str.strip()

    # 重算基础衍生指标
    df["ROAS"] = safe_divide(df["总销售额"], df["广告花费"])
    df["ACOS"] = safe_divide(df["广告花费"], df["总销售额"])
    df["CTR"] = safe_divide(df["点击"], df["曝光量"])
    df["CPC"] = safe_divide(df["广告花费"], df["点击"])

    roas_val = df["ROAS"].apply(lambda x: 0.0 if x is None or pd.isna(x) else float(x))
    acos_val = df["ACOS"].apply(lambda x: 1.0 if x is None or pd.isna(x) else float(x))

    # =========================================================================
    # 动态阈值机制与样本量保护基准推算
    # =========================================================================
    tot_orders = float(df["广告订单"].sum())
    tot_sales = float(df["总销售额"].sum())
    tot_spend = float(df["广告花费"].sum())
    tot_clicks = float(df["点击"].sum())

    calc_aov = (tot_sales / tot_orders) if tot_orders > 0 else 50.0
    effective_aov = aov_override if (aov_override and aov_override > 0) else calc_aov
    effective_cpa = target_cpa_override if (target_cpa_override and target_cpa_override > 0) else (effective_aov * max(0.10, min(0.60, target_acos)))

    # 动态暂停阈值：花费超 2x CPA 或 0.8x 客单价，同时要求最低点击样本保护
    dyn_pause_spend = max(16.0, min(effective_aov * 0.80, effective_cpa * 2.0))
    # 动态降价阈值：花费超 1x CPA 或 0.4x 客单价
    dyn_down_spend = max(10.0, min(effective_aov * 0.40, effective_cpa * 1.0))
    breakeven_roas_benchmark = (1.0 / breakeven_acos) if breakeven_acos > 0 else 2.86
    target_roas_benchmark = (1.0 / target_acos) if target_acos > 0 else 4.0

    is_enabled = df["状态"].isin(["enabled", "live", "active", "启用", "有效", "投放中"])
    is_paused = df["状态"].isin(["paused", "pause", "暂停", "已暂停", "关"])

    # =========================================================================
    # 策略 1. 该暂停（最高止损优先级）：
    # 0 订单，且 (满足最低样本量点击 clicks >= min_clicks_threshold 且花费超动态止损线) 
    # 或 (花费极端超标 >= 1.5倍客单价，触发紧急熔断)
    # =========================================================================
    pause_mask = is_enabled & (df["广告订单"] == 0) & (
        ((df["广告花费"] >= dyn_pause_spend) & (df["点击"] >= min_clicks_threshold)) |
        (df["广告花费"] >= max(25.0, effective_aov * 1.5))
    )
    pause_raw = df[pause_mask].copy()

    if not pause_raw.empty:
        pause_raw["建议分类"] = "该暂停"
        pause_raw["建议出价调整"] = "建议直接暂停 (paused)"
        pause_raw["依据数字"] = pause_raw.apply(
            lambda r: f"花费 ${r['广告花费']:.2f} (超动态止损线 ${dyn_pause_spend:.2f})，点击 {int(r['点击'])} 次，0订单转化", axis=1
        )
    else:
        pause_raw = pd.DataFrame(columns=df.columns.tolist() + ["建议分类", "建议出价调整", "依据数字"])

    # =========================================================================
    # 策略 2. 该降价（次高优先级）：
    # 排除已归入"该暂停"的词，满足基本样本量 (点击 >= 10)，花费达到动态降价线，
    # 且 (ROAS 击穿保本线60% 或 0 订单)
    # =========================================================================
    bid_down_mask = (
        is_enabled
        & (~pause_mask)
        & (df["广告花费"] >= dyn_down_spend)
        & (df["点击"] >= 10)
        & ((roas_val < breakeven_roas_benchmark * 0.70) | (df["广告订单"] == 0))
    )
    bid_down_raw = df[bid_down_mask].copy()

    def calc_bid_down_action(r: pd.Series) -> Tuple[str, str]:
        actual_val = r["实际当前竞价_数值"]
        spend_v = r["广告花费"]
        roas_v = r["ROAS"]
        roas_str = f"ROAS {roas_v:.2f}" if pd.notna(roas_v) else "ROAS 0.00"

        if pd.notna(actual_val) and actual_val > 0:
            new_bid = round(actual_val * 0.80, 2)
            act_text = f"建议调低至 ${new_bid:.2f} (-20%)"
            reason_text = f"花费 ${spend_v:.2f}，{roas_str} (低于保本线 {breakeven_roas_benchmark*0.70:.2f})，按实际竞价 ${actual_val:.2f} 降权控本"
        else:
            act_text = "核实出价后下调 20%"
            reason_text = f"花费 ${spend_v:.2f}，{roas_str}；实际竞价缺失，禁止使用建议竞价计算，请核查后台实际出价后下调"
        return act_text, reason_text

    if not bid_down_raw.empty:
        bid_down_raw["建议分类"] = "该降价"
        down_res = bid_down_raw.apply(calc_bid_down_action, axis=1)
        bid_down_raw["建议出价调整"] = [x[0] for x in down_res]
        bid_down_raw["依据数字"] = [x[1] for x in down_res]
    else:
        bid_down_raw = pd.DataFrame(columns=df.columns.tolist() + ["建议分类", "建议出价调整", "依据数字"])

    # =========================================================================
    # 策略 3. 该加价：
    # 严格排除暂停与降价冲突词，且满足样本量 (订单 >= 2)，ROAS ≥ 目标线且 ACoS 达标
    # =========================================================================
    bid_up_mask = (
        is_enabled
        & (~pause_mask)
        & (~bid_down_mask)
        & (df["广告订单"] >= 2)
        & (roas_val >= target_roas_benchmark)
        & (acos_val <= target_acos)
    )
    bid_up_raw = df[bid_up_mask].copy()

    def calc_bid_up_action(r: pd.Series) -> Tuple[str, str]:
        actual_val = r["实际当前竞价_数值"]
        orders_v = int(r["广告订单"])
        roas_v = r["ROAS"]
        acos_v = r["ACOS"] * 100.0 if pd.notna(r["ACOS"]) else 0.0

        if pd.notna(actual_val) and actual_val > 0:
            new_bid = round(actual_val * 1.15, 2)
            act_text = f"建议调高至 ${new_bid:.2f} (+15%)"
            reason_text = f"ROAS {roas_v:.2f}，ACOS {acos_v:.1f}%，出单 {orders_v} (超目标ROAS {target_roas_benchmark:.2f})，按实际竞价 ${actual_val:.2f} 提价扩量"
        else:
            act_text = "核实出价后上调 15%"
            reason_text = f"ROAS {roas_v:.2f}，ACOS {acos_v:.1f}%，出单 {orders_v}；实际竞价缺失，请核查后台实际出价后加价15%"
        return act_text, reason_text

    if not bid_up_raw.empty:
        bid_up_raw["建议分类"] = "该加价"
        up_res = bid_up_raw.apply(calc_bid_up_action, axis=1)
        bid_up_raw["建议出价调整"] = [x[0] for x in up_res]
        bid_up_raw["依据数字"] = [x[1] for x in up_res]
    else:
        bid_up_raw = pd.DataFrame(columns=df.columns.tolist() + ["建议分类", "建议出价调整", "依据数字"])

    # =========================================================================
    # 策略 4. 被误暂停的潜力词：paused、历史 ROAS ≥ 保本线 (且有订单)
    # =========================================================================
    unpause_mask = is_paused & (roas_val >= breakeven_roas_benchmark) & (df["广告订单"] > 0)
    unpause_raw = df[unpause_mask].copy()

    if not unpause_raw.empty:
        unpause_raw["建议分类"] = "误暂停潜力词"
        unpause_raw["建议出价调整"] = "建议恢复投放 (enabled)"
        unpause_raw["依据数字"] = unpause_raw.apply(
            lambda r: f"历史 ROAS {r['ROAS']:.2f} (高于保本线 {breakeven_roas_benchmark:.2f})，贡献销售额 ${r['总销售额']:.2f}，处于已暂停状态，建议解除暂停",
            axis=1,
        )
    else:
        unpause_raw = pd.DataFrame(columns=df.columns.tolist() + ["建议分类", "建议出价调整", "依据数字"])

    # =========================================================================
    # 动作去重与冲突仲裁机制（Anti-Conflict Arbitration）
    # 冲突优先级严格执行：该暂停 (Pause) > 该降价 (Bid Down) > 该加价 (Bid Up) > 恢复 (Unpause)
    # 确保同一个 (关键词, 所在活动) 只保留唯一、最高权重的指令，杜绝冲突！
    # =========================================================================
    output_cols = [
        "建议分类", "关键词", "匹配方式", "所在活动", "实际当前竞价", "建议出价调整", "参考建议竞价",
        "广告花费", "广告订单", "总销售额", "ROAS", "ACOS", "CTR", "CPC", "状态", "依据数字"
    ]

    def format_output_table(raw_d: pd.DataFrame, sort_by_spend: bool = True) -> pd.DataFrame:
        if raw_d.empty:
            return pd.DataFrame(columns=output_cols)
        d = raw_d.copy()
        if sort_by_spend and "广告花费" in d.columns:
            d = d.sort_values("广告花费", ascending=False)
        return d[[c for c in output_cols if c in d.columns]].reset_index(drop=True)

    fmt_pause = format_output_table(pause_raw)
    fmt_down = format_output_table(bid_down_raw)
    fmt_up = format_output_table(bid_up_raw)
    fmt_unpause = format_output_table(unpause_raw, sort_by_spend=False)

    # 跨表去重仲裁
    pause_keys = set(zip(fmt_pause["关键词"], fmt_pause["所在活动"])) if not fmt_pause.empty else set()
    down_keys = set(zip(fmt_down["关键词"], fmt_down["所在活动"])) if not fmt_down.empty else set()

    # 如果降价表中出现了已暂停的键，从降价表中剔除
    if not fmt_down.empty and pause_keys:
        fmt_down = fmt_down[~fmt_down.apply(lambda r: (r["关键词"], r["所在活动"]) in pause_keys, axis=1)].reset_index(drop=True)
        down_keys = set(zip(fmt_down["关键词"], fmt_down["所在活动"])) if not fmt_down.empty else set()

    # 如果加价表中出现了已暂停或已降价的键，从加价表中剔除
    suppress_for_up = pause_keys.union(down_keys)
    if not fmt_up.empty and suppress_for_up:
        fmt_up = fmt_up[~fmt_up.apply(lambda r: (r["关键词"], r["所在活动"]) in suppress_for_up, axis=1)].reset_index(drop=True)

    result_dict = {
        "pause": fmt_pause,
        "bid_down": fmt_down,
        "bid_up": fmt_up,
        "unpause": fmt_unpause,
    }

    all_actions = pd.concat([
        result_dict["pause"],
        result_dict["bid_down"],
        result_dict["bid_up"],
        result_dict["unpause"],
    ], ignore_index=True)

    # 统计汇总
    missing_actual_bids = int(df["实际当前竞价_数值"].isna().sum())
    pause_spend_sum = float(pause_raw["广告花费"].sum()) if not pause_raw.empty else 0.0

    stats = {
        "bid_down_count": len(result_dict["bid_down"]),
        "bid_up_count": len(result_dict["bid_up"]),
        "pause_count": len(result_dict["pause"]),
        "unpause_count": len(result_dict["unpause"]),
        "pause_spend": round(pause_spend_sum, 2),
        "missing_bid_count": missing_actual_bids,
        "dyn_pause_spend": round(dyn_pause_spend, 2),
        "dyn_down_spend": round(dyn_down_spend, 2),
        "effective_aov": round(effective_aov, 2),
    }

    return result_dict, all_actions, stats
