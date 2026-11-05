from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from .metrics import agg_metrics, safe_divide

ALL_CAMPAIGN_TAGS = [
    "全部",
    "明星计划",
    "达标计划",
    "亏损计划",
    "烧钱零转化",
    "预算撞顶",
    "预算跑不满",
    "样本不足",
]

# 统一的标准活动状态映射字典
CAMPAIGN_STATUS_MAP: Dict[str, str] = {
    # 活跃投放状态 (全部映射为 live)
    "live": "live",
    "enabled": "live",
    "active": "live",
    "running": "live",
    "投放中": "live",
    "进行中": "live",
    "有效": "live",
    "启用": "live",
    "已启用": "live",
    "开": "live",
    "正常": "live",
    "serving": "live",
    "eligible": "live",

    # 暂停状态 (全部映射为 paused)
    "paused": "paused",
    "pause": "paused",
    "已暂停": "paused",
    "暂停": "paused",
    "关": "paused",
    "suspended": "paused",

    # 结束/归档状态 (全部映射为 ended)
    "ended": "ended",
    "completed": "ended",
    "已结束": "ended",
    "已完成": "ended",
    "archived": "ended",
    "已归档": "ended",
    "terminated": "ended",
}

def normalize_campaign_status(status_val: Any) -> str:
    """标准化广告活动状态值"""
    if pd.isna(status_val):
        return "live"
    s = str(status_val).strip().lower()
    return CAMPAIGN_STATUS_MAP.get(s, "live" if s in ("", "none", "nan") else s)

def summarize_inactive_campaigns(campaign_df: pd.DataFrame) -> Dict[str, Any]:
    """
    汇总 paused / ended / archived 等历史非 live 活动数据。
    """
    if campaign_df is None or campaign_df.empty:
        return {
            "count": 0,
            "total_spend": 0.0,
            "total_sales": 0.0,
            "avg_roas": None,
            "description": "暂无历史活动数据",
        }

    status_col = None
    for cand in ["广告活动状态", "状态", "活动状态", "campaign status", "status", "state"]:
        for col in campaign_df.columns:
            if cand == str(col).strip().lower():
                status_col = col
                break
        if status_col:
            break

    if status_col:
        norm_status = campaign_df[status_col].apply(normalize_campaign_status)
        inactive_df = campaign_df[norm_status != "live"].copy()
    else:
        inactive_df = pd.DataFrame()

    count = len(inactive_df)
    spend = float(pd.to_numeric(inactive_df.get("广告花费", 0.0), errors="coerce").fillna(0.0).sum()) if not inactive_df.empty else 0.0
    sales = float(pd.to_numeric(inactive_df.get("总销售额", 0.0), errors="coerce").fillna(0.0).sum()) if not inactive_df.empty else 0.0
    avg_roas = safe_divide(sales, spend)

    roas_str = f"{avg_roas:.2f}" if avg_roas is not None else "N/A"
    desc = f"历史已暂停/非活跃活动共 {count} 条，累计花费 ${spend:,.2f}，平均 ROAS {roas_str}"

    return {
        "count": count,
        "total_spend": round(spend, 2),
        "total_sales": round(sales, 2),
        "avg_roas": avg_roas,
        "description": desc,
    }

def tag_single_campaign(
    row: pd.Series,
    days: Optional[int] = None,
    daily_spend_detail: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], Dict[str, str]]:
    """
    对单条 live 活动打诊断标签并生成详细判定原因依据：
    - 明星计划：ROAS ≥ 4.0
    - 达标计划：2.5 ≤ ROAS < 4.0
    - 亏损计划：ROAS < 2.5 且 花费 ≥ $20
    - 烧钱零转化：订单 = 0 且 花费 ≥ $20
    - 预算跑不满：日均耗费 < 每日预算 × 50%
    - 预算撞顶：日均耗费 ≥ 每日预算 × 90%（或实测多天撞顶）
    - 样本不足：点击 < 50
    """
    tags = []
    tag_reasons = {}

    roas = row.get("ROAS")
    spend = float(row.get("广告花费", 0.0) or 0.0)
    orders = float(row.get("广告订单", 0.0) or 0.0)
    clicks = float(row.get("点击", 0.0) or 0.0)
    budget = float(row.get("每日预算", 0.0) or 0.0)

    # 1. 产出维度
    if roas is not None and not pd.isna(roas):
        if roas >= 4.0:
            tags.append("明星计划")
            tag_reasons["明星计划"] = f"投产表现极佳 (ROAS {roas:.2f} ≥ 4.0)，高产出优质计划"
        elif 2.5 <= roas < 4.0:
            tags.append("达标计划")
            tag_reasons["达标计划"] = f"投产稳定达标 (ROAS {roas:.2f} ∈ [2.5, 4.0))"
        elif roas < 2.5 and spend >= 20.0:
            tags.append("亏损计划")
            tag_reasons["亏损计划"] = f"投产疲软 (ROAS {roas:.2f} < 2.5)，累计花费 ${spend:.2f}，侵蚀毛利"
    elif spend >= 20.0:
        tags.append("亏损计划")
        tag_reasons["亏损计划"] = f"累计消耗 ${spend:.2f} 且无销售额产生"

    # 2. 转化异常维度
    if orders == 0 and spend >= 20.0:
        tags.append("烧钱零转化")
        tag_reasons["烧钱零转化"] = f"累计消耗 ${spend:.2f} 产生 0 笔订单转化，紧急止损项"

    # 3. 样本统计置信度
    if clicks < 50:
        tags.append("样本不足")
        tag_reasons["样本不足"] = f"累计点击 {int(clicks)} < 50 次，统计样本偏少，暂不建议草率关停"

    # 4. 预算步调与撞顶深度判定（改用每日真实耗费/日均耗费精准计算）
    if budget > 0:
        # 若传入了该活动的每日耗费明细统计
        if daily_spend_detail and daily_spend_detail.get("total_days", 0) > 0:
            tot_d = daily_spend_detail["total_days"]
            hit_d = daily_spend_detail.get("hit_days", 0)
            avg_d_spend = daily_spend_detail.get("avg_daily_spend", spend / tot_d)
            pct = (avg_d_spend / budget) * 100.0

            if hit_d >= 2 or pct >= 90.0:
                tags.append("预算撞顶")
                tag_reasons["预算撞顶"] = f"近 {tot_d} 天中有 {hit_d} 天耗费达预算90%以上（日均耗费 ${avg_d_spend:.2f}/预算 ${budget:.2f}，占比 {pct:.1f}%），预算严重受限，错失高转化流量"
            elif pct < 50.0:
                tags.append("预算跑不满")
                tag_reasons["预算跑不满"] = f"日均耗费仅 ${avg_d_spend:.2f}，仅占每日预算 ${budget:.2f} 的 {pct:.1f}% (<50%)，竞价过低或流量池过窄"
        elif days is not None and days > 0:
            avg_d_spend = spend / days
            pct = (avg_d_spend / budget) * 100.0
            if pct >= 90.0:
                tags.append("预算撞顶")
                tag_reasons["预算撞顶"] = f"在 {days} 天统计期内，日均耗费 ${avg_d_spend:.2f} 达到每日预算 ${budget:.2f} 的 {pct:.1f}% (≥90%)，面临提早下线风险"
            elif pct < 50.0:
                tags.append("预算跑不满")
                tag_reasons["预算跑不满"] = f"在 {days} 天统计期内，日均耗费 ${avg_d_spend:.2f} 仅占每日预算 ${budget:.2f} 的 {pct:.1f}% (<50%)"

    return tags, tag_reasons

def analyze_campaign_health(
    campaign_df: pd.DataFrame,
    days: Optional[int] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any], Optional[str]]:
    """
    广告活动健康度诊断主入口：
    1. 使用完整的状态映射字典（支持 live, enabled, 投放中 等）精准提取当前有效活动；
    2. 计算历史非 live 活动汇总；
    3. 若包含日期列，精准计算每日真实耗费与撞顶天数；
    4. 执行指标重算与多维健康度诊断打标；
    5. 返回 (live_df, inactive_summary, budget_notice)。
    """
    inactive_summary = summarize_inactive_campaigns(campaign_df)

    if campaign_df is None or campaign_df.empty:
        empty_df = pd.DataFrame(columns=[
            "活动名", "花费", "订单", "销售额", "ROAS", "ACOS", "CPC", "CTR", "CVR", "标签", "每日预算", "标签列表"
        ])
        return empty_df, inactive_summary, "未找到广告活动数据"

    df = campaign_df.copy()

    # 1. 容错提取状态列并精确映射
    status_col = None
    for cand in ["广告活动状态", "状态", "活动状态", "campaign status", "status", "state"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                status_col = col
                break
        if status_col:
            break

    if status_col:
        df["_std_status"] = df[status_col].apply(normalize_campaign_status)
        live_raw = df[df["_std_status"] == "live"].copy()
    else:
        # 无状态列时默认全部视为有效 live 活动
        live_raw = df.copy()

    if live_raw.empty:
        empty_df = pd.DataFrame(columns=[
            "活动名", "花费", "订单", "销售额", "ROAS", "ACOS", "CPC", "CTR", "CVR", "标签", "每日预算", "标签列表"
        ])
        return empty_df, inactive_summary, "当前无有效进行中 (live/enabled) 的广告活动"

    # 2. 规范广告活动名称列
    camp_col = None
    for cand in ["广告活动", "广告活动名称", "活动名称", "活动名", "campaign", "campaign name"]:
        for col in live_raw.columns:
            if cand == str(col).strip().lower():
                camp_col = col
                break
        if camp_col:
            break
    if camp_col and camp_col != "广告活动":
        live_raw = live_raw.rename(columns={camp_col: "广告活动"})
    elif not camp_col and "广告活动" not in live_raw.columns:
        live_raw["广告活动"] = [f"活动_{i+1}" for i in range(len(live_raw))]

    # 3. 每日真实耗费与日期跨度透视（如果报表包含日期维度）
    date_col = None
    for cand in ["日期", "date", "day", "周期", "投放日期"]:
        for col in live_raw.columns:
            if cand == str(col).strip().lower():
                date_col = col
                break
        if date_col:
            break

    # 4. 提取每日预算列
    budget_col = None
    for cand in ["每日预算", "日预算", "daily budget", "总预算", "预算", "budget"]:
        for col in live_raw.columns:
            if cand == str(col).strip().lower():
                budget_col = col
                break
        if budget_col:
            break

    # 预算字典提取
    if budget_col and budget_col in live_raw.columns:
        budget_map = live_raw.groupby("广告活动")[budget_col].first().apply(
            lambda x: pd.to_numeric(x, errors="coerce") or 0.0
        ).to_dict()
    else:
        budget_map = {}

    # 计算各活动逐日真实花费明细
    daily_stats_map = {}
    if date_col and date_col in live_raw.columns and "广告花费" in live_raw.columns:
        spend_num = pd.to_numeric(live_raw["广告花费"], errors="coerce").fillna(0.0)
        temp_daily = live_raw.assign(_spend_clean=spend_num).groupby(["广告活动", date_col], as_index=False)["_spend_clean"].sum()
        for camp_name, g in temp_daily.groupby("广告活动"):
            b_val = budget_map.get(camp_name, 0.0)
            tot_days = len(g)
            avg_d_spend = float(g["_spend_clean"].mean()) if tot_days > 0 else 0.0
            hit_days = int((g["_spend_clean"] >= (b_val * 0.90)).sum()) if b_val > 0 else 0
            daily_stats_map[camp_name] = {
                "total_days": tot_days,
                "hit_days": hit_days,
                "avg_daily_spend": avg_d_spend,
            }
        if days is None or days <= 0:
            unique_dates = live_raw[date_col].nunique()
            days = unique_dates if unique_dates > 0 else days

    # 5. 调用指标聚合函数汇总 live 活动数据
    metrics_df = agg_metrics(live_raw, group_col="广告活动")
    metrics_df["每日预算"] = metrics_df["广告活动"].map(budget_map).fillna(0.0)

    # 预算与统计天数提示
    budget_notice = None
    if (days is None or days <= 0) and not daily_stats_map:
        budget_notice = "提示：未检测到日期列或设定统计天数，预算撞顶/跑不满标签将基于平均预估判断；如需精准天数请设定左侧统计天数。"

    # 6. 执行诊断打标
    tags_list = []
    reasons_list = []
    for _, row in metrics_df.iterrows():
        c_name = row["广告活动"]
        d_stat = daily_stats_map.get(c_name)
        t, r = tag_single_campaign(row, days=days, daily_spend_detail=d_stat)
        tags_list.append(t)
        reasons_list.append("; ".join(r.values()) if r else "指标健康稳定")

    metrics_df["标签列表"] = tags_list
    metrics_df["标签"] = metrics_df["标签列表"].apply(lambda ts: "、".join(ts) if ts else "正常运行")
    metrics_df["诊断详情"] = reasons_list

    # 重命名列用于统一展示
    rename_cols = {
        "广告活动": "活动名",
        "广告花费": "花费",
        "广告订单": "订单",
        "总销售额": "销售额",
    }
    result_df = metrics_df.copy()
    for src, dst in rename_cols.items():
        if src in result_df.columns:
            if dst in result_df.columns and dst != src:
                result_df = result_df.drop(columns=[dst])
            result_df = result_df.rename(columns={src: dst})

    result_df = result_df.sort_values("花费", ascending=False).reset_index(drop=True)

    target_cols = [
        "活动名", "花费", "订单", "销售额", "ROAS", "ACOS", "CPC", "CTR", "CVR", "标签", "每日预算", "诊断详情", "标签列表"
    ]
    return result_df[[c for c in target_cols if c in result_df.columns]], inactive_summary, budget_notice
