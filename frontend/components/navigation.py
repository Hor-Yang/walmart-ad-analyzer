"""
Apple 风格侧边栏统一导航 (Apple macOS Style Navigation)
"""

import streamlit as st

NAV_MODULES = [
    {"id": "dashboard", "title": "经营总览", "sub": "Dashboard", "icon": "🪟"},
    {"id": "ads_analytics", "title": "广告分析", "sub": "Ads Analytics", "icon": "📢"},
    {"id": "sales_analytics", "title": "销售分析", "sub": "Sales Analytics", "icon": "🛒"},
    {"id": "inventory", "title": "库存管理", "sub": "Inventory", "icon": "📦"},
    {"id": "products", "title": "产品管理", "sub": "Products", "icon": "🏷️"},
    {"id": "profitability", "title": "利润分析", "sub": "Profitability", "icon": "💰"},
    {"id": "ai_intelligence", "title": "AI 决策中心", "sub": "AI Center", "icon": "⚙️"},
    {"id": "data_hub", "title": "数据中心", "sub": "Data Hub", "icon": "🗄️"},
    {"id": "settings", "title": "系统设置", "sub": "Settings", "icon": "⚙️"},
]


def render_sidebar_navigation() -> str:
    """渲染完全符合 Apple 设计语言的侧边栏导航"""
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "dashboard"

    with st.sidebar:
        # Apple 风格品牌 Header
        st.markdown(
            """
            <div style="padding: 10px 4px 20px 4px; display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                <div style="width: 38px; height: 38px; border-radius: 10px; background: #e8f2fe; display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 2px 6px rgba(0, 113, 227, 0.12);">
                    📊
                </div>
                <div>
                    <div style="font-size: 15px; font-weight: 700; color: #111827; letter-spacing: -0.02em;">CrossBorder BI</div>
                    <div style="font-size: 11px; color: #86868b; font-weight: 400;">智能经营分析工作台 · v2.5</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 渲染导航项
        for mod in NAV_MODULES:
            mod_id = mod["id"]
            is_active = st.session_state["active_page"] == mod_id
            label = f"{mod['icon']}  {mod['title']}  {mod['sub']}"
            btn_type = "primary" if is_active else "secondary"
            
            if st.button(label, key=f"nav_btn_{mod_id}", use_container_width=True, type=btn_type):
                st.session_state["active_page"] = mod_id
                st.rerun()

        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
        
        # 底部状态指示器
        cached_count = len([k for k, v in st.session_state.get("section_data", {}).items() if v is not None])
        st.markdown(
            f"""
            <div style="padding: 12px 14px; background: rgba(0,0,0,0.02); border-radius: 12px; font-size: 11.5px; color: #6b7280; border: 1px solid rgba(0,0,0,0.04);">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span>数据就绪状态:</span>
                    <strong style="color: #0071e3;">{cached_count}/8 模块</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>核心平台:</span>
                    <span style="color: #059669; font-weight: 600;">Walmart (在线)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return st.session_state["active_page"]
