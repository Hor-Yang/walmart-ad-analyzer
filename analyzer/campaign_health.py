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

def summarize_inactive_campaigns(campaign_df: pd.DataFrame) -> Dict[str, Any]:
    """
    汇总 paused / completed / proposal 等历史非 live 活动：
    计算：
    - N: 历史非 live 活动总条数
    - X: 累计总花费
    - Y: 整体平均 ROAS (分子分母相除)
    返回结构化数据及提示文本。
    """
    if campaign_df is None or campaign_df.empty:
        return {
            "count": 0,
            "total_spend": 0.0,
            "total_sales": 0.0,
            "avg_roas": None,
            "description": "暂无历史活动数据",
        }

    # 容错提取活动状态列
    status_col = None
    for cand in ["广告活动状态", "状态", "活动状态", "campaign status", "status", "state"]:
        for col in campaign_df.columns:
            if cand == str(col).strip().lower():
                status_col = col
                break
        if status_col:
            break

    if status_col:
        status_series = campaign_df[status_col].astype(str).str.lower().str.strip()
        inactive_df = campaign_df[status_series != "live"].copy()
    else:
        inactive_df = pd.DataFrame()

    count = len(inactive_df)
    spend = float(inactive_df["广告花费"].sum()) if "广告花费" in inactive_df.columns else 0.0
    sales = float(inactive_df["总销售额"].sum()) if "总销售额" in inactive_df.columns else 0.0
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
) -> List[str]:
    """
    对单条 live 活动打诊断标签：
    - 明星计划：ROAS ≥ 4.0
    - 达标计划：2.5 ≤ ROAS < 4.0
    - 亏损计划：ROAS < 2.5 且 花费 ≥ $20
    - 烧钱零转化：订单 = 0 且 花费 ≥ $20
    - 预算跑不满：日均花费 < 每日预算 × 50%（每日预算 > 0 且提供天数时）
    - 预算撞顶：日均花费 ≥ 每日预算 × 90%（每日预算 > 0 且提供天数时）
    - 样本不足：点击 < 50
    """
    tags = []
    roas = row.get("ROAS")
    spend = float(row.get("广告花费", 0.0) or 0.0)
    orders = float(row.get("广告订单", 0.0) or 0.0)
    clicks = float(row.get("点击", 0.0) or 0.0)
    budget = float(row.get("每日预算", 0.0) or 0.0)

    # 1. 产出维度标签
    if roas is not None and not pd.isna(roas):
        if roas >= 4.0:
            tags.append("明星计划")
        elif 2.5 <= roas < 4.0:
            tags.append("达标计划")
        elif roas < 2.5 and spend >= 20.0:
            tags.append("亏损计划")
    elif spend >= 20.0:
        # 有花费但无销售额/ROAS
        tags.append("亏损计划")

    # 2. 转化异常维度
    if orders == 0 and spend >= 20.0:
        tags.append("烧钱零转化")

    # 3. 统计置信度维度
    if clicks < 50:
        tags.append("样本不足")

    # 4. 预算步调维度（若天数有效且每日预算 > 0）
    if days is not None and days > 0 and budget > 0:
        daily_spend = spend / days
        if daily_spend < budget * 0.50:
            tags.append("预算跑不满")
        elif daily_spend >= budget * 0.90:
            tags.append("预算撞顶")

    return tags

def analyze_campaign_health(
    campaign_df: pd.DataFrame,
    days: Optional[int] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any], Optional[str]]:
    """
    广告活动健康度诊断主入口：
    1. 过滤提取 live 广告活动；
    2. 计算历史非 live 活动汇总信息；
    3. 调用 agg_metrics 计算 live 活动指标；
    4. 执行健康度诊断并赋予标签；
    5. 返回 (live_df, inactive_summary, budget_notice)。
    """
    inactive_summary = summarize_inactive_campaigns(campaign_df)

    if campaign_df is None or campaign_df.empty:
        empty_df = pd.DataFrame(columns=[
            "活动名", "花费", "订单", "销售额", "ROAS", "ACOS", "CPC", "CTR", "CVR", "标签", "每日预算"
        ])
        return empty_df, inactive_summary, "未找到广告活动数据"

    # 容错提取活动状态列
    status_col = None
    for cand in ["广告活动状态", "状态", "活动状态", "campaign status", "status", "state"]:
        for col in campaign_df.columns:
            if cand == str(col).strip().lower():
                status_col = col
                break
        if status_col:
            break

    if status_col:
        status_series = campaign_df[status_col].astype(str).str.lower().str.strip()
        live_raw = campaign_df[status_series == "live"].copy()
    else:
        # 若无状态列，默认全部视为 live 活动
        live_raw = campaign_df.copy()

    if live_raw.empty:
        empty_df = pd.DataFrame(columns=[
            "活动名", "花费", "订单", "销售额", "ROAS", "ACOS", "CPC", "CTR", "CVR", "标签", "每日预算"
        ])
        return empty_df, inactive_summary, "当前无 live 状态的广告活动"

    # 规范广告活动名称列
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

    # 调用第 3 步的通用指标聚合函数重算比率
    metrics_df = agg_metrics(live_raw, group_col="广告活动")

    # 关联每日预算与创建/开始时间（安全容错检测预算列）
    budget_col = None
    for cand in ["每日预算", "日预算", "daily budget", "总预算", "预算", "budget"]:
        for col in live_raw.columns:
            if cand == str(col).strip().lower():
                budget_col = col
                break
        if budget_col:
            break

    if budget_col and budget_col in live_raw.columns:
        budget_map = live_raw.groupby("广告活动")[budget_col].first().to_dict()
        metrics_df["每日预算"] = metrics_df["广告活动"].map(budget_map).fillna(0.0)
    else:
        metrics_df["每日预算"] = 0.0

    # 日期与预算提示
    budget_notice = None
    if days is None or days <= 0:
        budget_notice = "需导出带日期的报表或输入统计天数才能做预算撞顶/跑不满判断"

    # 打诊断标签
    tags_list = []
    for _, row in metrics_df.iterrows():
        t = tag_single_campaign(row, days=days)
        tags_list.append(t)

    metrics_df["标签列表"] = tags_list
    metrics_df["标签"] = metrics_df["标签列表"].apply(lambda ts: "、".join(ts) if ts else "正常运行")

    # 安全重命名列以便展示
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

    # 默认按花费从大到小排序
    result_df = result_df.sort_values("花费", ascending=False).reset_index(drop=True)

    target_cols = [
        "活动名", "花费", "订单", "销售额", "ROAS", "ACOS", "CPC", "CTR", "CVR", "标签", "每日预算", "标签列表"
    ]
    return result_df[[c for c in target_cols if c in result_df.columns]], inactive_summary, budget_notice
