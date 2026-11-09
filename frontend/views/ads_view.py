"""
广告分析模块视图 (Ads Analytics View)
支持多平台（Walmart / Wayfair / eBay / Shein / Temu）广告表现分析
完整集成：概览看板、广告活动健康度、搜索词挖掘、关键词与出价诊断、商品表现、多期走势、店铺矩阵与展示位置分析
"""

import html
import io
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analyzer import (
    summarize_overview,
    agg_metrics,
    analyze_campaign_health,
    ALL_CAMPAIGN_TAGS,
    mine_search_terms,
    analyze_keyword_bids,
    diagnose_ad_items,
    analyze_placements,
    build_action_items,
    build_sku_trend_data,
    extract_period_label,
    generate_store_overview_analysis,
    generate_product_matrix_analysis,
    get_decision_mapping_guide,
    calculate_sku_profit_analytics,
)

# 动态容错导入决策与六层模型
try:
    from analyzer import AdDecisionEngine
except ImportError:
    AdDecisionEngine = None

from frontend.utils.formatters import (
    fmt_money,
    fmt_pct,
    fmt_num,
    fmt_ratio,
    fmt_opt_float,
    format_metrics_for_display,
    render_kpi_row,
)
from frontend.utils.data_context import (
    parse_single_file_cached,
    parse_trend_data_cached,
    update_section,
)
from frontend.components.kpi_card import render_empty_state


def safe_html(val) -> str:
    if val is None:
        return ""
    return html.escape(str(val))


def render_ads_view():
    st.markdown("## 📢 广告分析 (Ads Analytics)")
    st.caption("全渠道广告多维诊断：漏斗分析、精准控词、竞价阶梯、商品健康度与位置溢价优化")

    # 1. 顶部平台切换器与参数微调
    p_col1, p_col2, p_col3 = st.columns([2, 1, 1])
    with p_col1:
        sel_ad_platform = st.selectbox(
            "选择分析的广告平台",
            ["Walmart Sponsored Products (原生直连)", "Wayfair Sponsored Products (预留)", "eBay Promoted Listings (预留)", "Shein 广告托管 (预留)", "Temu 推广中心 (预留)"],
            index=0,
            key="ads_view_platform_sel",
        )
    with p_col2:
        target_acos_pct = st.number_input("目标 ACoS (%)", min_value=5.0, max_value=80.0, value=30.0, step=1.0, key="ads_target_acos_input")
        target_acos = target_acos_pct / 100.0
    with p_col3:
        breakeven_acos_pct = st.number_input("保本 ACoS (%)", min_value=10.0, max_value=90.0, value=35.0, step=1.0, key="ads_be_acos_input")
        breakeven_acos = breakeven_acos_pct / 100.0

    if "Walmart" not in sel_ad_platform:
        render_empty_state(
            title=f"{sel_ad_platform} 广告数据对接中",
            description=f"当前系统正在配置 {sel_ad_platform} 的 API 与报表适配器。目前已接入 Walmart 广告引擎，请切换回 Walmart 查看完整的广告分析体系。",
            icon="🔌",
        )
        return

    sec_data = st.session_state.get("section_data", {})
    sku_mapping = st.session_state.get("sku_mapping", {})
    daily_trend_df = st.session_state.get("daily_trend_df")
    trend_files = st.session_state.get("trend_files", [])

    # 2. 广告核心二级子业务 Tab 体系
    ad_tabs = st.tabs([
        "🎯 统一智能决策中枢",
        "📊 概览与全店漏斗",
        "🏷️ 广告活动健康度",
        "🔍 搜索词挖掘与控词",
        "🎯 关键词出价诊断",
        "📦 商品广告表现",
        "📈 多期走势与归因",
        "🏬 店铺矩阵分析",
        "📱 广告位置分析",
    ])

    # =========================================================================
    # TAB 1: 🎯 统一智能决策中枢 (AdDecisionEngine)
    # =========================================================================
    with ad_tabs[0]:
        st.markdown("### 🎯 统一智能决策中枢（4 层广告决策与防冲突引擎）")
        st.caption("数据层清洗对齐 -> 专家规则并发评估 -> 冲突仲裁与动作去重 -> 最终结构化决策指令矩阵。")

        active_tables = {k: sec_data.get(k) for k in [
            "campaign", "search_term", "keyword", "ad_item", "platform", "page_type"
        ]}
        if active_tables.get("ad_item") is None and sec_data.get("trend") is not None:
            active_tables["ad_item"] = sec_data["trend"].get("period_df")

        has_any = any(v is not None and not v.empty for v in active_tables.values())

        if not has_any:
            render_empty_state(
                title="暂无广告数据",
                description="请在「数据中心」上传广告活动列表、搜索词列表或多期走势报表，系统将自动激活统一决策引擎。",
                icon="💡",
                action_label="👉 前往数据中心上传报表",
                action_key="ads_to_dh_btn",
            )
            if st.session_state.get("ads_to_dh_btn"):
                st.session_state["active_page"] = "data_hub"
                st.rerun()
        elif AdDecisionEngine is not None:
            engine = AdDecisionEngine(
                target_acos=target_acos,
                breakeven_acos=breakeven_acos,
                cost_dict=st.session_state.get("sku_cost_dict", {}),
            )
            engine_res = engine.run(active_tables)
            dec_matrix = engine_res.get("decision_matrix", pd.DataFrame())
            exec_sum = engine_res.get("executive_summary", {})
            overview = summarize_overview(active_tables)

            render_kpi_row(overview, title="当前广告账户综合汇总表现")

            # 沃尔玛广告总监三大核心经营决策
            st.markdown("#### 🎯 沃尔玛广告总监 · 核心决策直达")
            c_prob = exec_sum.get("core_problem_answer", "大盘运行稳定。")
            st.markdown(
                f"""
                <div style="background: #fff1f2; border: 1px solid #fecdd3; border-left: 5px solid #e11d48; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px;">
                    <div style="font-weight: 700; font-size: 14px; color: #9f1239; margin-bottom: 4px;">
                        ❓ 核心痛点诊断：
                    </div>
                    <div style="font-size: 13.5px; color: #881337; line-height: 1.5;">
                        {safe_html(c_prob)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 结构化决策清单
            st.markdown("##### 📋 全量结构化决策执行指令矩阵")
            if not dec_matrix.empty:
                st.dataframe(dec_matrix, use_container_width=True, hide_index=True)
            else:
                st.info("当前数据未触发明确调优阈值，请继续观察。")

    # =========================================================================
    # TAB 2: 📊 概览与全店漏斗
    # =========================================================================
    with ad_tabs[1]:
        st.markdown("### 📊 广告全店漏斗与宏观指标")
        active_tables = {k: sec_data.get(k) for k in ["campaign", "search_term", "keyword", "ad_item", "platform", "page_type"]}
        overview = summarize_overview(active_tables)
        render_kpi_row(overview)

        # 漏斗转化图
        imp = overview.get("曝光量", 0)
        clk = overview.get("点击量", 0)
        ord_cnt = overview.get("订单量", 0)

        if imp > 0:
            fig = go.Figure(go.Funnel(
                y=["曝光展现 (Impressions)", "有效点击 (Clicks)", "成交转化 (Orders)"],
                x=[imp, clk, ord_cnt],
                textinfo="value+percent initial",
                marker=dict(color=["#94a3b8", "#3b82f6", "#10b981"]),
            ))
            fig.update_layout(height=280, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # =========================================================================
    # TAB 3: 🏷️ 广告活动健康度
    # =========================================================================
    with ad_tabs[2]:
        st.markdown("### 🏷️ 广告活动（Campaign）健康度与预算撞顶诊断")
        camp_df = sec_data.get("campaign")
        if camp_df is not None and not camp_df.empty:
            health_res = analyze_campaign_health(camp_df, target_acos=target_acos)
            st.dataframe(health_res.get("summary_df", pd.DataFrame()), use_container_width=True, hide_index=True)
        else:
            st.info("💡 请在「数据中心」上传「① 广告活动报表」以查看活动健康度。")

    # =========================================================================
    # TAB 4: 🔍 搜索词挖掘与控词
    # =========================================================================
    with ad_tabs[3]:
        st.markdown("### 🔍 搜索词挖掘与精准控词清单")
        st_df = sec_data.get("search_term")
        if st_df is not None and not st_df.empty:
            st_res = mine_search_terms(st_df, target_acos=target_acos)
            neg_df = st_res.get("negative_candidates", pd.DataFrame())
            exp_df = st_res.get("expansion_candidates", pd.DataFrame())
            
            s_t1, s_t2 = st.tabs([f"🚫 建议否定词清单 ({len(neg_df)}个)", f"💎 建议拓词清单 ({len(exp_df)}个)"])
            with s_t1:
                st.dataframe(neg_df, use_container_width=True, hide_index=True)
            with s_t2:
                st.dataframe(exp_df, use_container_width=True, hide_index=True)
        else:
            st.info("💡 请在「数据中心」上传「② 搜索词报表」以挖掘否定词与拓词。")

    # =========================================================================
    # TAB 5: 🎯 关键词出价诊断
    # =========================================================================
    with ad_tabs[4]:
        st.markdown("### 🎯 投放关键词（Keyword）竞价与阶梯调价")
        kw_df = sec_data.get("keyword")
        if kw_df is not None and not kw_df.empty:
            kw_res = analyze_keyword_bids(kw_df, target_acos=target_acos)
            st.dataframe(kw_res.get("detail_df", pd.DataFrame()), use_container_width=True, hide_index=True)
        else:
            st.info("💡 请在「数据中心」上传「③ 关键词报表」以查看关键词出价诊断。")

    # =========================================================================
    # TAB 6: 📦 商品广告表现
    # =========================================================================
    with ad_tabs[5]:
        st.markdown("### 📦 商品广告（Ad Item）表现与僵尸款识别")
        item_df = sec_data.get("ad_item")
        if item_df is not None and not item_df.empty:
            item_res = diagnose_ad_items(item_df, target_acos=target_acos)
            st.dataframe(item_res.get("detail_df", pd.DataFrame()), use_container_width=True, hide_index=True)
        else:
            st.info("💡 请在「数据中心」上传「④ 商品广告列表」以分析各 SKU 表现。")

    # =========================================================================
    # TAB 7: 📈 多期走势与归因
    # =========================================================================
    with ad_tabs[6]:
        st.markdown("### 📈 SKU / 全周期多期走势与归因分析")
        if trend_files:
            file_records_tuple = tuple((f["filename"], f["bytes"]) for f in trend_files)
            sku_summary_df, period_sku_df, anomalies, daily_macro = parse_trend_data_cached(
                file_records_tuple,
                tuple(sku_mapping.items()),
                target_acos=target_acos,
                breakeven_acos=breakeven_acos,
            )
            if not sku_summary_df.empty:
                st.dataframe(sku_summary_df, use_container_width=True, hide_index=True)
            else:
                st.caption("走势汇总计算中...")
        elif daily_trend_df is not None and not daily_trend_df.empty:
            st.dataframe(daily_trend_df.head(50), use_container_width=True, hide_index=True)
        else:
            st.info("💡 请在「数据中心」上传「多期趋势报表」或「日度走势报表」。")

    # =========================================================================
    # TAB 8: 🏬 店铺矩阵分析
    # =========================================================================
    with ad_tabs[7]:
        st.markdown("### 🏬 4 象限商品矩阵与全店经营")
        camp_df = sec_data.get("campaign")
        item_df = sec_data.get("ad_item")
        if camp_df is not None and not camp_df.empty:
            matrix_res = generate_product_matrix_analysis(item_df if item_df is not None else camp_df)
            st.dataframe(matrix_res.get("matrix_df", pd.DataFrame()), use_container_width=True, hide_index=True)
        else:
            st.info("💡 请在「数据中心」上传「① 广告活动报表」以生成店铺矩阵。")

    # =========================================================================
    # TAB 9: 📱 广告位置分析
    # =========================================================================
    with ad_tabs[8]:
        st.markdown("### 📱 广告位置与设备终端（Platform & Page Type）表现")
        plat_df = sec_data.get("platform")
        page_df = sec_data.get("page_type")
        if plat_df is not None or page_df is not None:
            plc_res = analyze_placements(plat_df, page_df)
            if not plc_res.get("platform_df", pd.DataFrame()).empty:
                st.markdown("#### 设备终端表现")
                st.dataframe(plc_res["platform_df"], use_container_width=True, hide_index=True)
            if not plc_res.get("page_type_df", pd.DataFrame()).empty:
                st.markdown("#### 页面类型表现")
                st.dataframe(plc_res["page_type_df"], use_container_width=True, hide_index=True)
        else:
            st.info("💡 请在「数据中心」上传「⑤ 平台报表」或「⑥ 页面类型报表」以分析展示位置溢价。")
