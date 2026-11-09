"""
左侧统一导航组件 (Navigation Bar)
规范：9 大一级业务模块、支持快捷状态指示与收折
"""

import streamlit as st

NAV_MODULES = [
    {"id": "dashboard", "title": "经营总览 Dashboard", "icon": "📊", "badge": "实时"},
    {"id": "ads_analytics", "title": "广告分析 Ads Analytics", "icon": "📢", "badge": "核心"},
    {"id": "sales_analytics", "title": "销售分析 Sales Analytics", "icon": "🛒", "badge": "多平台"},
    {"id": "inventory", "title": "库存管理 Inventory", "icon": "📦", "badge": "预警"},
    {"id": "products", "title": "产品管理 Products", "icon": "🏷️", "badge": "统一SKU"},
    {"id": "profitability", "title": "利润分析 Profitability", "icon": "💰", "badge": "全成本"},
    {"id": "ai_intelligence", "title": "AI 决策中心 AI Center", "icon": "🧠", "badge": "六层引擎"},
    {"id": "data_hub", "title": "数据中心 Data Hub", "icon": "🗄️", "badge": "多源导入"},
    {"id": "settings", "title": "系统设置 Settings", "icon": "⚙️", "badge": ""},
]


def render_sidebar_navigation() -> str:
    """渲染侧边栏统一导航，返回当前激活的模块 ID"""
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "dashboard"

    with st.sidebar:
        # 品牌 Header
        st.markdown(
            """
            <div style="padding: 10px 4px 18px 4px; border-bottom: 1px solid #334155; margin-bottom: 14px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="width: 36px; height: 36px; border-radius: 8px; background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); display: flex; align-items: center; justify-content: center; font-size: 20px; color: white;">
                        🌐
                    </div>
                    <div>
                        <div style="font-size: 15px; font-weight: 700; color: #f8fafc; letter-spacing: -0.01em;">CrossBorder BI</div>
                        <div style="font-size: 11px; color: #94a3b8;">智能经营分析工作台 · v2.5</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.caption("核心业务导航")

        # 渲染 9 大导航项
        for mod in NAV_MODULES:
            mod_id = mod["id"]
            is_active = st.session_state["active_page"] == mod_id
            label = f"{mod['icon']} {mod['title']}"
            
            # 使用原生按键样式模拟企业级高亮效果
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"nav_btn_{mod_id}", use_container_width=True, type=btn_type):
                st.session_state["active_page"] = mod_id
                st.rerun()

        st.markdown("---")
        
        # 底部系统运行状态
        cached_count = len([k for k, v in st.session_state.get("section_data", {}).items() if v is not None])
        st.markdown(
            f"""
            <div style="padding: 8px 10px; background: #1e293b; border-radius: 8px; font-size: 11px; color: #94a3b8;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span>已载入数据模块:</span>
                    <strong style="color: #38bdf8;">{cached_count} / 8</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>适配平台:</span>
                    <span style="color: #a7f3d0;">Walmart已连接</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return st.session_state["active_page"]
