"""
指标格式化与展示工具 (Formatters)
"""

import html
from typing import Any, Dict
import pandas as pd
import streamlit as st


def fmt_money(val: Any, default: str = "N/A") -> str:
    if val is None or pd.isna(val):
        return default
    try:
        return f"${float(val):,.2f}"
    except (ValueError, TypeError):
        return default


def fmt_pct(val: Any, default: str = "N/A") -> str:
    if val is None or pd.isna(val):
        return default
    try:
        return f"{float(val)*100:.2f}%"
    except (ValueError, TypeError):
        return default


def fmt_num(val: Any, default: str = "N/A") -> str:
    if val is None or pd.isna(val):
        return default
    try:
        return f"{int(round(float(val))):,}"
    except (ValueError, TypeError):
        return default


def fmt_ratio(val: Any, default: str = "N/A") -> str:
    if val is None or pd.isna(val):
        return default
    try:
        return f"{float(val):.2f}"
    except (ValueError, TypeError):
        return default


def fmt_opt_float(val: Any, default: str = "N/A", prec: int = 2) -> str:
    if val is None or pd.isna(val):
        return default
    try:
        return f"{float(val):.{prec}f}"
    except (ValueError, TypeError):
        return default


def format_metrics_for_display(metrics: Dict[str, Any]) -> Dict[str, str]:
    """将指标字典标准化格式化为可直读文本"""
    out = {}
    out["曝光量"] = fmt_num(metrics.get("曝光量"))
    out["点击量"] = fmt_num(metrics.get("点击量"))
    out["CTR"] = fmt_pct(metrics.get("CTR"))
    out["花费"] = fmt_money(metrics.get("花费"))
    out["CPC"] = fmt_money(metrics.get("CPC"))
    out["订单量"] = fmt_num(metrics.get("订单量"))
    out["CVR"] = fmt_pct(metrics.get("CVR"))
    out["销售额"] = fmt_money(metrics.get("销售额"))
    out["ACoS"] = fmt_pct(metrics.get("ACoS"))
    out["ROAS"] = fmt_ratio(metrics.get("ROAS"))
    return out


def render_kpi_row(metrics: Dict[str, Any], title: str = None):
    """渲染 5 列统一指标卡片栅格"""
    fm = format_metrics_for_display(metrics)
    if title:
        st.markdown(f"**{html.escape(title)}**")
    cols = st.columns(5)
    cols[0].metric("曝光量", fm["曝光量"])
    cols[1].metric("点击量 (CTR)", f"{fm['点击量']} ({fm['CTR']})")
    cols[2].metric("花费 (CPC)", f"{fm['花费']} ({fm['CPC']})")
    cols[3].metric("订单量 (CVR)", f"{fm['订单量']} ({fm['CVR']})")
    cols[4].metric("销售额 (ROAS)", f"{fm['销售额']} ({fm['ROAS']})")
