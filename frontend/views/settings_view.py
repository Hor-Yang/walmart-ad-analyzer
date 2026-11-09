"""
系统设置模块视图 (Settings View)
多平台接口连接状态、多币种与时区偏好、数据缓存清理与系统环境监控
"""

import streamlit as st
import pandas as pd
from data_loader.session_storage import clear_session_cache
from frontend.components.kpi_card import render_kpi_card


def render_settings_view():
    st.markdown("## ⚙️ 系统设置 (System Settings)")
    st.caption("跨平台 API 连接配置、多店铺授权、多币种汇率、时区偏好与本地会话缓存维护")

    set_tabs = st.tabs(["🌐 平台渠道与店铺配置", "💱 货币与时区参数", "🧹 数据与缓存管理"])

    # =========================================================================
    # TAB 1: 平台渠道配置
    # =========================================================================
    with set_tabs[0]:
        st.markdown("#### 1. 跨境电商平台直连接口状态")
        channels_df = pd.DataFrame([
            {"平台名称": "Walmart 美国站", "对接模式": "报表适配器 (Active)", "默认币种": "USD", "连接状态": "🟢 正常运转", "最后同步": "刚刚"},
            {"平台名称": "Wayfair", "对接模式": "API / 报表 (Ready)", "默认币种": "USD", "连接状态": "🟡 联调准备", "最后同步": "待配置"},
            {"平台名称": "eBay", "对接模式": "API / 报表 (Ready)", "默认币种": "USD / EUR", "连接状态": "⚪ 待接入", "最后同步": "-"},
            {"平台名称": "Shein 半托管", "对接模式": "全托管/半托管适配器", "默认币种": "USD", "连接状态": "⚪ 待接入", "最后同步": "-"},
            {"平台名称": "Temu 半托管", "对接模式": "半托管商家端适配器", "默认币种": "USD", "连接状态": "⚪ 待接入", "最后同步": "-"},
        ])
        st.dataframe(channels_df, use_container_width=True, hide_index=True)

    # =========================================================================
    # TAB 2: 货币与时区
    # =========================================================================
    with set_tabs[1]:
        st.markdown("#### 2. 全局核算口径与参数")
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("系统基准核算货币 (Base Currency)", ["USD ($) - 美元", "CNY (¥) - 人民币", "EUR (€) - 欧元"], index=0)
            st.number_input("USD ↔ CNY 换算汇率", value=7.20, step=0.01)
        with c2:
            st.selectbox("平台归因基准时区", ["America/Los_Angeles (PST/PDT 太平洋时间)", "America/New_York (EST/EDT 东部时间)", "Asia/Shanghai (UTC+8 北京时间)"], index=0)
            st.number_input("平台默认佣金抽成比例 (%)", value=15.0, step=0.5)

    # =========================================================================
    # TAB 3: 数据与缓存管理
    # =========================================================================
    with set_tabs[2]:
        st.markdown("#### 3. 会话数据持久化与缓存清理")
        st.warning("⚠️ 清除本地会话缓存将重置当前浏览器存储的所有临时报表，需重新上传才能恢复分析。")
        
        if st.button("🚨 清空所有板块缓存并重置系统", key="reset_cache_btn", type="primary"):
            clear_session_cache()
            for key in ["section_data", "section_files", "section_file_bytes", "daily_trend_df", "sku_cost_df", "sku_cost_dict", "sku_mapping", "trend_files"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.success("✅ 缓存已彻底清空！页面将在 2 秒内刷新重置。")
            st.rerun()
