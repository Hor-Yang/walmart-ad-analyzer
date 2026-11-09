"""
Apple 风格统一 KPI 指标卡与空状态组件 (Apple Metric Cards & States)
遵循设计系统：
1. 统一 .card 规范：border-radius: 16px, background: #FFFFFF, 弥散微阴影
2. 留白呼吸感：padding: 24px
3. 文本层级：数值 #1D1D1F 加粗 32px，副标 #86868B
"""

import html
from typing import Optional, Union
import streamlit as st


def render_apple_kpi_card(
    label: str,
    value: Union[str, int, float],
    badge: Optional[str] = None,
    badge_type: str = "green",  # green, red, blue, gray
    sub_title: str = "",
):
    """
    渲染完全遵循 Apple 视觉语言规范的 KPI 卡片
    """
    safe_label = html.escape(str(label))
    safe_value = html.escape(str(value))
    
    badge_html = ""
    if badge:
        safe_badge = html.escape(str(badge))
        badge_cls = f"badge-apple-{badge_type}"
        badge_html = f'<span class="apple-badge {badge_cls}">{safe_badge}</span>'

    sub_html = ""
    if sub_title:
        safe_sub = html.escape(str(sub_title))
        sub_html = f'<div style="font-size: 12px; color: #86868B; margin-top: 6px;">{safe_sub}</div>'

    st.markdown(
        f"""
        <div class="card" style="margin-bottom: 0px; height: 100%;">
            <div class="kpi-header">
                <span class="kpi-label">{safe_label}</span>
                {badge_html}
            </div>
            <div class="kpi-value">{safe_value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(
    title: str,
    value: Union[str, int, float],
    sub_title: str = "",
    delta: Optional[str] = None,
    delta_is_positive_good: bool = True,
    badge: Optional[str] = None,
    badge_color: str = "blue",
):
    b_type = "green" if delta_is_positive_good else "red"
    badge_text = delta if delta else badge
    if badge_color == "slate":
        b_type = "gray"
    render_apple_kpi_card(
        label=title,
        value=value,
        badge=badge_text,
        badge_type=b_type,
        sub_title=sub_title,
    )


def render_empty_state(
    title: str,
    description: str,
    icon_type: str = "chart",
    action_label: Optional[str] = None,
    action_key: Optional[str] = None,
) -> bool:
    """渲染 Apple 极简矢量风格的空数据引导状态（无生硬边框与 Emoji）"""
    safe_title = html.escape(str(title))
    safe_desc = html.escape(str(description))
    
    st.markdown(
        f"""
        <div class="card" style="padding: 56px 24px; text-align: center; margin: 20px 0;">
            <div style="width: 54px; height: 54px; margin: 0 auto 16px auto; border-radius: 14px; background: #F5F5F7; display: flex; align-items: center; justify-content: center;">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="20" x2="12" y2="10"></line>
                    <line x1="18" y1="20" x2="18" y2="4"></line>
                    <line x1="6" y1="20" x2="6" y2="16"></line>
                </svg>
            </div>
            <div style="font-size: 18px; font-weight: 600; color: #1D1D1F; margin-bottom: 6px; letter-spacing: -0.01em;">{safe_title}</div>
            <div style="font-size: 13.5px; color: #86868B; max-width: 440px; margin: 0 auto 22px auto; line-height: 1.6;">{safe_desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    if action_label and action_key:
        col1, col2, col3 = st.columns([1.2, 1, 1.2])
        with col2:
            return st.button(action_label, key=action_key, use_container_width=True, type="primary")
    return False
