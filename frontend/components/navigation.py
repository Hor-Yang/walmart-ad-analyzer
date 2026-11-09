"""
Apple 风格侧边栏统一导航 (Apple macOS Style Navigation)
遵循规范：
1. 彻底移除彩色 Emoji 图标
2. 统一纯净单色矢量图标库 (Lucide Icons)
3. 激活状态使用 Apple 主题色高亮背景 (Capsule Highlight)
"""

import streamlit as st

NAV_MODULES = [
    {"id": "dashboard", "title": "经营总览", "sub": "Dashboard"},
    {"id": "ads_analytics", "title": "广告分析", "sub": "Ads Analytics"},
    {"id": "sales_analytics", "title": "销售分析", "sub": "Sales Analytics"},
    {"id": "inventory", "title": "库存管理", "sub": "Inventory"},
    {"id": "products", "title": "产品管理", "sub": "Products"},
    {"id": "profitability", "title": "利润分析", "sub": "Profitability"},
    {"id": "ai_intelligence", "title": "AI 决策中心", "sub": "AI Center"},
    {"id": "data_hub", "title": "数据中心", "sub": "Data Hub"},
    {"id": "settings", "title": "系统设置", "sub": "Settings"},
]


def render_sidebar_navigation() -> str:
    """渲染完全符合 Apple 设计语言的侧边栏导航"""
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "dashboard"

    with st.sidebar:
        # Apple 风格品牌 Header：单色矢量 Logo 代替彩色 Emoji
        st.markdown(
            """
            <div style="padding: 10px 4px 22px 4px; display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <div style="width: 36px; height: 36px; border-radius: 10px; background: #0071E3; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(0, 113, 227, 0.25);">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="20" x2="18" y2="10"></line>
                        <line x1="12" y1="20" x2="12" y2="4"></line>
                        <line x1="6" y1="20" x2="6" y2="14"></line>
                    </svg>
                </div>
                <div>
                    <div style="font-size: 15px; font-weight: 700; color: #1D1D1F; letter-spacing: -0.02em;">CrossBorder BI</div>
                    <div style="font-size: 11px; color: #86868B; font-weight: 400;">智能经营分析工作台 · v2.5</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 渲染 9 大单色矢量导航项（无彩色 Emoji）
        for mod in NAV_MODULES:
            mod_id = mod["id"]
            is_active = st.session_state["active_page"] == mod_id
            label = f"{mod['title']}  {mod['sub']}"
            btn_type = "primary" if is_active else "secondary"
            
            if st.button(label, key=f"nav_btn_{mod_id}", use_container_width=True, type=btn_type):
                st.session_state["active_page"] = mod_id
                st.rerun()

        st.markdown("<div style='height: 36px;'></div>", unsafe_allow_html=True)
        
        # 底部状态指示器：极简无生硬边框
        cached_count = len([k for k, v in st.session_state.get("section_data", {}).items() if v is not None])
        st.markdown(
            f"""
            <div style="padding: 12px 14px; background: rgba(0, 0, 0, 0.02); border-radius: 12px; font-size: 11.5px; color: #86868B; border: 1px solid rgba(0, 0, 0, 0.03);">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span>数据就绪状态:</span>
                    <strong style="color: #0071E3;">{cached_count}/8 模块</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>连接平台:</span>
                    <span style="color: #059669; font-weight: 600;">Walmart (Active)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return st.session_state["active_page"]
