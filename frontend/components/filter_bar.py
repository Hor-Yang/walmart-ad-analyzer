"""
Apple 风格顶部全局筛选栏组件 (Apple Global Filter Bar)
"""

import streamlit as st
from datetime import datetime


def init_global_filters():
    if "global_filters" not in st.session_state:
        st.session_state["global_filters"] = {
            "platform": "Walmart",
            "store": "默认店铺 (Walmart)",
            "date_range": "最近30天",
            "sku": "全部 SKU",
            "category": "全部类目",
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


def render_global_filter_bar(available_skus: list = None, available_categories: list = None) -> dict:
    """渲染紧凑、高雅的 Apple 水平筛选器"""
    init_global_filters()
    filters = st.session_state["global_filters"]

    if available_skus is None:
        available_skus = ["全部 SKU"]
    elif "全部 SKU" not in available_skus:
        available_skus = ["全部 SKU"] + available_skus

    if available_categories is None:
        available_categories = ["全部类目", "家具/床架", "家居生活", "办公家具", "户外园艺"]

    # 布局：左侧 5 个平铺下拉选框 + 右侧同步时间与刷新按钮
    f_cols = st.columns([1.3, 1.8, 1.3, 1.4, 1.4, 2.0])

    with f_cols[0]:
        filters["platform"] = st.selectbox(
            "渠道平台",
            ["Walmart", "Wayfair (接入中)", "eBay (接入中)", "Shein半托管", "Temu半托管"],
            index=0,
            key="gf_platform",
            label_visibility="collapsed",
        )

    with f_cols[1]:
        filters["store"] = st.selectbox(
            "店铺选择",
            ["默认店铺 (Walmart)", "二店 (备用渠道)", "所有关联店铺"],
            index=0,
            key="gf_store",
            label_visibility="collapsed",
        )

    with f_cols[2]:
        filters["date_range"] = st.selectbox(
            "分析周期",
            ["最近30天", "最近14天", "最近7天", "本月自然月", "全量报表周期"],
            index=0,
            key="gf_date_range",
            label_visibility="collapsed",
        )

    with f_cols[3]:
        sku_idx = 0
        curr_sku = filters.get("sku", "全部 SKU")
        if curr_sku in available_skus:
            sku_idx = available_skus.index(curr_sku)
        filters["sku"] = st.selectbox(
            "目标 SKU",
            available_skus,
            index=sku_idx,
            key="gf_sku",
            label_visibility="collapsed",
        )

    with f_cols[4]:
        cat_idx = 0
        curr_cat = filters.get("category", "全部类目")
        if curr_cat in available_categories:
            cat_idx = available_categories.index(curr_cat)
        filters["category"] = st.selectbox(
            "商品类目",
            available_categories,
            index=cat_idx,
            key="gf_cat",
            label_visibility="collapsed",
        )

    with f_cols[5]:
        r_c1, r_c2 = st.columns([3, 1])
        with r_c1:
            st.markdown(
                f"""
                <div style="font-size: 12px; color: #86868b; line-height: 38px; text-align: right;">
                    最后同步时间: {filters.get('last_sync', '实时')}
                </div>
                """,
                unsafe_allow_html=True,
            )
        with r_c2:
            if st.button("🔄", key="gf_refresh_icon_btn", help="刷新并重置时间", use_container_width=True):
                filters["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.rerun()

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.session_state["global_filters"] = filters
    return filters
