"""
Apple 风格统一 KPI 指标卡与空状态组件 (Apple Metric Cards & States)
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
    渲染完全遵循 Apple 视觉语言规范的 KPI 卡片：
    第一行：指标名称 + 拟态微圆角徽章（如 +12.4%）
    第二行：32px 超大平滑数字字体
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
        sub_html = f'<div style="font-size: 12px; color: #9ca3af; margin-top: 6px;">{safe_sub}</div>'

    st.markdown(
        f"""
        <div class="apple-kpi-card">
            <div class="apple-kpi-header">
                <span class="apple-kpi-label">{safe_label}</span>
                {badge_html}
            </div>
            <div class="apple-kpi-value">{safe_value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# 保留对旧命名兼容的代理函数
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
    icon: str = "📈",
    action_label: Optional[str] = None,
    action_key: Optional[str] = None,
) -> bool:
    """渲染 Apple 极简通透风格的空数据引导状态"""
    safe_title = html.escape(str(title))
    safe_desc = html.escape(str(description))
    
    st.markdown(
        f"""
        <div style="background: #ffffff; border-radius: 20px; border: 1px solid rgba(0,0,0,0.05); padding: 50px 30px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.02); margin: 20px 0;">
            <div style="font-size: 42px; margin-bottom: 14px; opacity: 0.85;">{icon}</div>
            <div style="font-size: 18px; font-weight: 600; color: #111827; margin-bottom: 8px;">{safe_title}</div>
            <div style="font-size: 13.5px; color: #6b7280; max-width: 460px; margin: 0 auto 20px auto; line-height: 1.6;">{safe_desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    if action_label and action_key:
        col1, col2, col3 = st.columns([1.2, 1, 1.2])
        with col2:
            return st.button(action_label, key=action_key, use_container_width=True, type="primary")
    return False
