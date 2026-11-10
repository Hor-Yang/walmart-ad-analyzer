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


def render_page_header(title: str, subtitle: str, badge: Optional[str] = None):
    """
    // FIX: 【重构目标 2】修复 HTML 代码外泄 Bug：
    // 根本原因：多行字符串内嵌 4 个以上前导空格时，Markdown 引擎会将其误判为缩进代码块 (<pre><code>)，导致 HTML 源码赤裸泄露。
    // 解决方案：移除多行前导缩进，采用单行紧凑拼接并确保传入 unsafe_allow_html=True。
    """
    safe_title = html.escape(str(title))
    safe_sub = html.escape(str(subtitle))
    badge_html = f'<span class="apple-badge badge-apple-blue" style="margin-left: 10px; font-size: 12px; vertical-align: middle;">{html.escape(str(badge))}</span>' if badge else ""
    header_html = (
        f'<div style="margin-bottom: 24px;">'
        f'<div style="font-size: 26px; font-weight: 700; color: #1D1D1F; letter-spacing: -0.03em; margin-bottom: 4px; display: flex; align-items: center;">'
        f'<span>{safe_title}</span>{badge_html}'
        f'</div>'
        f'<div style="font-size: 13.5px; color: #86868B; font-weight: 400;">{safe_sub}</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)


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

    # // FIX: 【任务 1】紧凑拼接无前导缩进 HTML，彻底杜绝 Markdown 4空格缩进误判为代码块外泄
    card_html = (
        f'<div class="card" style="margin-bottom: 0px; height: 100%;">'
        f'<div class="kpi-header"><span class="kpi-label">{safe_label}</span>{badge_html}</div>'
        f'<div class="kpi-value">{safe_value}</div>'
        f'{sub_html}'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


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


# 矢量 SVG 图标映射表 (Apple macOS / Lucide 统一纯净线条风格)
_SVG_ICONS = {
    "chart": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <line x1="12" y1="20" x2="12" y2="10"></line>
        <line x1="18" y1="20" x2="18" y2="4"></line>
        <line x1="6" y1="20" x2="6" y2="16"></line>
    </svg>""",
    "sales": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="8" cy="21" r="1"></circle>
        <circle cx="19" cy="21" r="1"></circle>
        <path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"></path>
    </svg>""",
    "cart": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="8" cy="21" r="1"></circle>
        <circle cx="19" cy="21" r="1"></circle>
        <path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"></path>
    </svg>""",
    "profit": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"></path>
        <path d="M12 18V6"></path>
    </svg>""",
    "dollar": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"></path>
        <path d="M12 18V6"></path>
    </svg>""",
    "inventory": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="m7.5 4.27 9 5.15"></path>
        <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"></path>
        <path d="m3.3 7 8.7 5 8.7-5"></path>
        <path d="M12 22V12"></path>
    </svg>""",
    "box": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="m7.5 4.27 9 5.15"></path>
        <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"></path>
        <path d="m3.3 7 8.7 5 8.7-5"></path>
        <path d="M12 22V12"></path>
    </svg>""",
    "products": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z"></path>
        <path d="M7 7h.01"></path>
    </svg>""",
    "tag": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z"></path>
        <path d="M7 7h.01"></path>
    </svg>""",
    "ai": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z"></path>
    </svg>""",
    "sparkles": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z"></path>
    </svg>""",
    "data": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
        <path d="M3 5V19A9 3 0 0 0 21 19V5"></path>
        <path d="M3 12A9 3 0 0 0 21 12"></path>
    </svg>""",
    "database": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#86868B" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
        <path d="M3 5V19A9 3 0 0 0 21 19V5"></path>
        <path d="M3 12A9 3 0 0 0 21 12"></path>
    </svg>""",
}


def render_empty_state(
    title: str,
    description: str,
    icon_type: str = "chart",
    action_label: Optional[str] = None,
    action_key: Optional[str] = None,
    *args,
    **kwargs,
) -> bool:
    """// FIX: 渲染 Apple 极简单色矢量空状态，彻底移除散乱 Emoji，支持多类型单色 SVG"""
    safe_title = html.escape(str(title))
    safe_desc = html.escape(str(description))
    
    # 智能解析图标类型（防御性兼容传入的各类参数）
    k_type = icon_type.lower() if isinstance(icon_type, str) else "chart"
    svg_icon = _SVG_ICONS.get(k_type, _SVG_ICONS["chart"])
    
    # // FIX: 【任务 1】紧凑拼接无前导缩进 HTML，防止空状态组件发生 HTML 代码泄露
    empty_html = (
        f'<div class="card" style="padding: 56px 24px; text-align: center; margin: 20px 0;">'
        f'<div style="width: 54px; height: 54px; margin: 0 auto 16px auto; border-radius: 14px; background: #F5F5F7; display: flex; align-items: center; justify-content: center;">{svg_icon}</div>'
        f'<div style="font-size: 18px; font-weight: 600; color: #1D1D1F; margin-bottom: 6px; letter-spacing: -0.01em;">{safe_title}</div>'
        f'<div style="font-size: 13.5px; color: #86868B; max-width: 440px; margin: 0 auto 22px auto; line-height: 1.6;">{safe_desc}</div>'
        f'</div>'
    )
    st.markdown(empty_html, unsafe_allow_html=True)
    
    if action_label and action_key:
        col1, col2, col3 = st.columns([1.2, 1, 1.2])
        with col2:
            return st.button(action_label, key=action_key, use_container_width=True, type="primary")
    return False
