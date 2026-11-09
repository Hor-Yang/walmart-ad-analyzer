"""
顶部全局筛选栏组件 (Global Filter Bar)
规范：统一多平台、店铺、周期、SKU、类目的状态同步
"""

import streamlit as st
from datetime import datetime


def init_global_filters():
    """初始化全局筛选器默认状态"""
    if "global_filters" not in st.session_state:
        st.session_state["global_filters"] = {
            "platform": "Walmart",
            "store": "默认店铺 (Walmart 主店)",
            "date_range": "最近30天",
            "sku": "全部 SKU",
            "category": "全部类目",
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


def render_global_filter_bar(available_skus: list = None, available_categories: list = None) -> dict:
    """渲染顶部全局筛选栏，返回当前的筛选状态字典"""
    init_global_filters()
    filters = st.session_state["global_filters"]

    if available_skus is None:
        available_skus = ["全部 SKU"]
    elif "全部 SKU" not in available_skus:
        available_skus = ["全部 SKU"] + available_skus

    if available_categories is None:
        available_categories = ["全部类目", "家具/床架", "家居生活", "办公家具", "户外园艺"]

    with st.container():
        st.markdown(
            f"""
            <div class="global-filter-bar">
                <div class="filter-bar-header">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span>🔍 <b>全局经营与数据范围筛选</b></span>
                        <span class="badge badge-blue">平台隔离保护中</span>
                    </div>
                    <div style="font-size: 11px; color: #94a3b8;">
                        最后同步时间: <span style="color: #475569; font-weight: 500;">{filters.get('last_sync', '实时')}</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        f_cols = st.columns([1.5, 1.8, 1.5, 2.0, 1.6, 0.8])
        
        with f_cols[0]:
            sel_platform = st.selectbox(
                "渠道平台",
                ["Walmart", "Wayfair (接入中)", "eBay (接入中)", "Shein半托管 (接入中)", "Temu半托管 (接入中)", "全部跨平台汇总"],
                index=0,
                key="gf_platform",
                label_visibility="collapsed",
            )
            filters["platform"] = sel_platform

        with f_cols[1]:
            sel_store = st.selectbox(
                "运营店铺",
                ["默认店铺 (Walmart 主店)", "二店 (备用渠道)", "所有关联店铺"],
                index=0,
                key="gf_store",
                label_visibility="collapsed",
            )
            filters["store"] = sel_store

        with f_cols[2]:
            sel_range = st.selectbox(
                "分析周期",
                ["最近7天", "最近14天", "最近30天", "本月自然月", "全量报表周期"],
                index=2,
                key="gf_date_range",
                label_visibility="collapsed",
            )
            filters["date_range"] = sel_range

        with f_cols[3]:
            # SKU 筛选器
            sku_idx = 0
            curr_sku = filters.get("sku", "全部 SKU")
            if curr_sku in available_skus:
                sku_idx = available_skus.index(curr_sku)
            sel_sku = st.selectbox(
                "目标 SKU",
                available_skus,
                index=sku_idx,
                key="gf_sku",
                label_visibility="collapsed",
            )
            filters["sku"] = sel_sku

        with f_cols[4]:
            cat_idx = 0
            curr_cat = filters.get("category", "全部类目")
            if curr_cat in available_categories:
                cat_idx = available_categories.index(curr_cat)
            sel_cat = st.selectbox(
                "商品类目",
                available_categories,
                index=cat_idx,
                key="gf_cat",
                label_visibility="collapsed",
            )
            filters["category"] = sel_cat

        with f_cols[5]:
            if st.button("🔄 刷新", key="gf_refresh_btn", use_container_width=True):
                filters["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.rerun()

    st.session_state["global_filters"] = filters
    return filters
