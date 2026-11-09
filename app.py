"""
CrossBorder BI · 跨境电商智能经营分析工作台
主入口路由调度器 (Master Application Orchestrator)
统一工作台 · 多平台接入 · 模块化架构 · 跨域 AI 决策中枢
"""

import os
import sys
from pathlib import Path

# 保证根目录在 sys.path 中（确保 Streamlit Cloud 与云端环境平滑运行）
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

# 1. 页面基础全局配置
favicon_path = os.path.join(ROOT_DIR, "assets", "favicon.svg")
st.set_page_config(
    page_title="CrossBorder BI · 跨境电商智能经营分析工作台",
    page_icon=favicon_path if os.path.exists(favicon_path) else None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. 注入企业级 SaaS 统一设计系统 (Design System)
from frontend.styles import inject_saas_theme
inject_saas_theme()

# 3. 导入核心组件与页面视图
from frontend.components import (
    render_sidebar_navigation,
    render_global_filter_bar,
)
from frontend.views import (
    render_dashboard_view,
    render_ads_view,
    render_sales_view,
    render_inventory_view,
    render_products_view,
    render_profit_view,
    render_ai_view,
    render_data_hub_view,
    render_settings_view,
)
try:
    from data_loader.session_storage import load_session_cache
except ImportError:
    def load_session_cache():
        return None


# 4. 初始化全局状态与会话缓存
def init_application_state():
    """初始化并自动恢复上一次的持久化数据会话"""
    if "section_data" not in st.session_state:
        st.session_state["section_data"] = {}
    if "section_files" not in st.session_state:
        st.session_state["section_files"] = {}
    if "section_file_bytes" not in st.session_state:
        st.session_state["section_file_bytes"] = {}
    if "sku_mapping" not in st.session_state:
        st.session_state["sku_mapping"] = {}
    if "daily_trend_df" not in st.session_state:
        st.session_state["daily_trend_df"] = None
    if "sku_cost_df" not in st.session_state:
        st.session_state["sku_cost_df"] = None
    if "sku_cost_dict" not in st.session_state:
        st.session_state["sku_cost_dict"] = {}
    if "trend_files" not in st.session_state:
        st.session_state["trend_files"] = []
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "dashboard"

    # 若内存中无数据，安全尝试从本地缓存中热恢复
    try:
        if not any(v is not None for v in st.session_state["section_data"].values()):
            cached = load_session_cache()
            if isinstance(cached, dict):
                st.session_state["section_data"] = cached.get("section_data", {})
                st.session_state["section_files"] = cached.get("file_names", {})
                if "sku_map" in cached and cached["sku_map"]:
                    st.session_state["sku_mapping"] = cached["sku_map"]
                if "sku_cost_dict" in cached and cached["sku_cost_dict"]:
                    st.session_state["sku_cost_dict"] = cached["sku_cost_dict"]
    except Exception:
        pass


init_application_state()

# 5. 渲染侧边统一导航
active_page = render_sidebar_navigation()

# 6. 计算可用 SKU 列表供全局筛选栏快速选择
# // FIX: 采用防御性多字段探测（兼容中英文与项目ID），彻底修复 KeyError: 'item_id'
available_skus = ["全部 SKU"]
sec_ad_item = st.session_state["section_data"].get("ad_item")
if sec_ad_item is not None and not sec_ad_item.empty:
    sku_c = next((c for c in ["SKU", "sku", "对应SKU", "商品SKU", "项目ID", "item_id", "Item ID", "seller_sku"] if c in sec_ad_item.columns), None)
    if sku_c:
        vals = [str(x).strip() for x in sec_ad_item[sku_c].dropna().unique() if str(x).strip() not in ["", "nan", "None", "-"]]
        available_skus += sorted(list(set(vals)))
if st.session_state.get("sku_mapping"):
    map_vals = [str(x).strip() for x in st.session_state["sku_mapping"].values() if str(x).strip() not in ["", "nan", "None", "-"]]
    available_skus += sorted(list(set(map_vals)))

# 去重并保证 "全部 SKU" 在首位
seen = set()
unique_skus = []
for s in available_skus:
    if s not in seen:
        seen.add(s)
        unique_skus.append(s)
available_skus = unique_skus

# 7. 渲染顶部全局筛选栏
global_filters = render_global_filter_bar(available_skus=available_skus)

# 8. 路由调度分发
VIEW_ROUTER = {
    "dashboard": render_dashboard_view,
    "ads_analytics": render_ads_view,
    "sales_analytics": render_sales_view,
    "inventory": render_inventory_view,
    "products": render_products_view,
    "profitability": render_profit_view,
    "ai_intelligence": render_ai_view,
    "data_hub": render_data_hub_view,
    "settings": render_settings_view,
}

render_func = VIEW_ROUTER.get(active_page, render_dashboard_view)
render_func()
