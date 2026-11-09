"""
统一 KPI 指标卡与空状态组件 (Cards & States)
规范：数据优先、整洁优雅、无多余装饰
"""

import html
from typing import Optional, Union
import streamlit as st


def render_kpi_card(
    title: str,
    value: Union[str, int, float],
    sub_title: str = "",
    delta: Optional[str] = None,
    delta_is_positive_good: bool = True,
    badge: Optional[str] = None,
    badge_color: str = "blue",
):
    """渲染现代化 SaaS 企业级指标卡片"""
    safe_title = html.escape(str(title))
    safe_value = html.escape(str(value))
    safe_sub = html.escape(str(sub_title))
    
    delta_html = ""
    if delta:
        safe_delta = html.escape(str(delta))
        # 绿色表示上升或好，红色表示下降或警告
        delta_class = "kpi-delta-up" if delta_is_positive_good else "kpi-delta-down"
        delta_html = f'<span class="{delta_class}">{safe_delta}</span>'

    badge_html = ""
    if badge:
        safe_badge = html.escape(str(badge))
        badge_html = f'<span class="badge badge-{badge_color}">{safe_badge}</span>'

    card_html = f"""
    <div class="kpi-card">
        <div class="kpi-title">
            <span>{safe_title}</span>
            {badge_html}
        </div>
        <div class="kpi-value">{safe_value}</div>
        <div class="kpi-sub">
            {delta_html}
            <span>{safe_sub}</span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def render_empty_state(
    title: str,
    description: str,
    icon: str = "📥",
    action_label: Optional[str] = None,
    action_key: Optional[str] = None,
) -> bool:
    """渲染规范的空数据引导状态，返回用户是否点击了操作按钮"""
    safe_title = html.escape(str(title))
    safe_desc = html.escape(str(description))
    
    st.markdown(
        f"""
        <div class="empty-state-box">
            <div class="empty-state-icon">{icon}</div>
            <div class="empty-state-title">{safe_title}</div>
            <div class="empty-state-desc">{safe_desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    if action_label and action_key:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            return st.button(action_label, key=action_key, use_container_width=True, type="primary")
    return False
