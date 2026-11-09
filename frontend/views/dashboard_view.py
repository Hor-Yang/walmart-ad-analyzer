"""
经营总览首页 (Dashboard View - Apple Design Edition)
遵循 Apple macOS 极简高端规范：
1. 容器：全量使用统一 .card 样式 (border-radius: 16px, background: #FFFFFF, 弥散阴影, 呼吸感 Padding 24px)
2. 图表去噪：隐藏繁杂网格与多余边框，使用平滑样条曲线 (Spline)
3. 文本与排版：标题 #1D1D1F，说明文字 #86868B，单色微图标
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from frontend.components.kpi_card import render_apple_kpi_card, render_empty_state, render_page_header
from frontend.utils.formatters import safe_num_divide, fmt_money
from frontend.utils.data_context import filter_dataframe_by_global


def render_dashboard_view():
    # 1. 页面主标题区 (Apple 极简大排版)
    render_page_header("经营总览", "跨平台全链路经营大盘：销售、广告、利润、库存实时穿透与异常预警")

    sec_data_raw = st.session_state.get("section_data", {})
    daily_trend_df_raw = st.session_state.get("daily_trend_df")
    filters = st.session_state.get("global_filters", {})

    # // FIX: 全局筛选生效管道，对所有相关业务底表应用实质过滤
    sec_data = {}
    for k, v in sec_data_raw.items():
        if v is not None and isinstance(v, pd.DataFrame):
            sec_data[k] = filter_dataframe_by_global(v, filters, k)
        else:
            sec_data[k] = v

    daily_trend_df = filter_dataframe_by_global(daily_trend_df_raw, filters, "daily_trend") if daily_trend_df_raw is not None else None

    camp_df = sec_data.get("campaign")
    item_df = sec_data.get("ad_item")

    # // FIX: 提取真实可用数据，优先使用统一宏观指标汇总
    try:
        from analyzer.metrics import summarize_overview
        overview = summarize_overview(sec_data) if sec_data else {}
    except Exception:
        overview = {}

    total_spend = float(overview.get("大盘总花费") or 0.0)
    total_ad_sales = float(overview.get("总销售额") or 0.0)
    total_orders = int(overview.get("总订单") or 0)

    # 兜底扫描
    if total_spend == 0.0 and total_ad_sales == 0.0:
        for t_name, df_cand in sec_data.items():
            if df_cand is not None and isinstance(df_cand, pd.DataFrame) and not df_cand.empty:
                sp_c = next((c for c in ["广告花费", "花费", "spend", "cost", "总花费"] if c in df_cand.columns), None)
                sl_c = next((c for c in ["总销售额", "销售额", "sales", "attributed sales", "广告销售额"] if c in df_cand.columns), None)
                od_c = next((c for c in ["广告订单", "订单", "订单量", "orders", "order"] if c in df_cand.columns), None)
                if sp_c:
                    total_spend = max(total_spend, float(pd.to_numeric(df_cand[sp_c], errors="coerce").fillna(0).sum()))
                if sl_c:
                    total_ad_sales = max(total_ad_sales, float(pd.to_numeric(df_cand[sl_c], errors="coerce").fillna(0).sum()))
                if od_c:
                    total_orders = max(total_orders, int(pd.to_numeric(df_cand[od_c], errors="coerce").fillna(0).sum()))

    has_store_sales = False
    store_sales = 0.0
    if daily_trend_df is not None and not daily_trend_df.empty:
        sl_c = next((c for c in ["销售额", "总销售额", "sales"] if c in daily_trend_df.columns), None)
        od_c = next((c for c in ["订单量", "广告订单", "订单", "orders"] if c in daily_trend_df.columns), None)
        if sl_c:
            store_sales = float(pd.to_numeric(daily_trend_df[sl_c], errors="coerce").sum())
            if store_sales > 0:
                has_store_sales = True
        if od_c:
            total_orders = max(total_orders, int(pd.to_numeric(daily_trend_df[od_c], errors="coerce").sum()))

    has_real_data = (total_spend > 0) or (total_ad_sales > 0) or has_store_sales

    # // FIX: 彻底移除预设销售额、广告花费、ROAS 及随机数据！没有真实数据时展示规范空状态
    if not has_real_data:
        go_dh = render_empty_state(
            title="暂无经营数据",
            description="系统尚未导入广告报表或销售走势表。请前往「数据中心」上传您的首份报表，系统将自动激活全景大盘与 AI 经营诊断。",
            icon_type="chart",
            action_label="前往数据中心上传报表",
            action_key="dash_to_dh_btn",
        )
        if go_dh:
            st.session_state["active_page"] = "data_hub"
            st.rerun()
        return

    # 真实业务数据展示指标
    display_sales = store_sales if has_store_sales else total_ad_sales
    sales_title = "店铺总 GMV" if has_store_sales else "广告归因销售额"
    display_spend = total_spend
    display_roas = safe_num_divide(total_ad_sales, total_spend, default=0.0)

    # 2. 核心 4 大 Apple KPI 卡片 (统一 .card 样式，纯白、圆角 16px、呼吸感留白)
    k_col1, k_col2, k_col3, k_col4 = st.columns(4)

    with k_col1:
        render_apple_kpi_card(
            label=sales_title,
            value=f"${display_sales:,.0f}" if display_sales > 10000 else f"${display_sales:,.2f}",
            badge="实时全量" if has_store_sales else "广告归因",
            badge_type="blue" if has_store_sales else "green",
            sub_title="全渠道已完成/归因订单",
        )

    with k_col2:
        render_apple_kpi_card(
            label="广告支出",
            value=f"${display_spend:,.0f}" if display_spend > 10000 else f"${display_spend:,.2f}",
            badge="实时消耗",
            badge_type="gray",
            sub_title="已对齐多平台广告总花费",
        )

    with k_col3:
        roas_eval = "达标" if display_roas >= 3.0 else ("偏低" if display_roas > 0 else "无出单")
        roas_type = "green" if display_roas >= 3.0 else "red"
        render_apple_kpi_card(
            label="广告产出比 (ROAS)",
            value=f"{display_roas:.2f}x",
            badge=roas_eval,
            badge_type=roas_type,
            sub_title="广告销售额 ÷ 广告花费",
        )

    with k_col4:
        # 库存真实周转天数
        inv_df = sec_data.get("inventory") or st.session_state.get("inventory_df")
        if inv_df is not None and not inv_df.empty:
            render_apple_kpi_card(
                label="实时在库 SKU 数",
                value=f"{len(inv_df):,} 款",
                badge="库存同步",
                badge_type="green",
                sub_title="供应链现货管理",
            )
        else:
            render_apple_kpi_card(
                label="累计广告出单量",
                value=f"{total_orders:,} 单",
                badge="已成交",
                badge_type="blue",
                sub_title="广告转化订单总数",
            )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 3. 下方双卡片联动 (统一 .card 类，去噪图表)
    c_left, c_right = st.columns([1.8, 1.0])

    with c_left:
        st.markdown(
            """
            <div class="card">
                <div class="card-title">
                    <span>销售与广告趋势</span>
                    <span style="font-size: 12px; font-weight: 500; color: #86868B; background: #F5F5F7; padding: 4px 10px; border-radius: 8px;">
                        真实走势
                    </span>
                </div>
            """,
            unsafe_allow_html=True,
        )

        fig_trend = go.Figure()

        # // FIX: 彻底移除正弦波随机趋势！使用真实日度或实体数据聚合
        if daily_trend_df is not None and not daily_trend_df.empty and "日期" in daily_trend_df.columns:
            d_sort = daily_trend_df.copy()
            d_sort["日期"] = pd.to_datetime(d_sort["日期"], errors="coerce")
            d_grouped = d_sort.dropna(subset=["日期"]).groupby("日期").agg({
                "销售额": "sum" if "销售额" in d_sort.columns else "count",
                "花费": "sum" if "花费" in d_sort.columns else "count",
            }).reset_index().tail(30)
            x_vals = [d.strftime("%m-%d") for d in d_grouped["日期"]]
            y_sales = list(d_grouped["销售额"])
            y_ads = list(d_grouped["花费"])
        elif camp_df is not None and not camp_df.empty:
            # 若无日度表，按 Top 广告活动展示真实柱状结构
            c_name_col = next((c for c in ["活动名", "广告活动", "campaign"] if c in camp_df.columns), camp_df.columns[0])
            c_sp_col = next((c for c in ["花费", "广告花费", "spend"] if c in camp_df.columns), None)
            c_sl_col = next((c for c in ["销售额", "总销售额", "sales"] if c in camp_df.columns), None)
            c_top = camp_df.sort_values(by=c_sp_col, ascending=False).head(10) if c_sp_col else camp_df.head(10)
            x_vals = [str(n)[:12] for n in c_top[c_name_col]]
            y_ads = list(pd.to_numeric(c_top[c_sp_col], errors="coerce").fillna(0)) if c_sp_col else []
            y_sales = list(pd.to_numeric(c_top[c_sl_col], errors="coerce").fillna(0)) if c_sl_col else []
        else:
            x_vals, y_sales, y_ads = [], [], []

        if x_vals:
            # 销售额面积平滑曲线 (Apple 蓝)
            if y_sales:
                fig_trend.add_trace(go.Scatter(
                    x=x_vals,
                    y=y_sales,
                    name="销售额",
                    mode="lines+markers",
                    line=dict(shape="spline", smoothing=1.3, color="#0071E3", width=2.5),
                    marker=dict(size=4, color="#FFFFFF", line=dict(color="#0071E3", width=2)),
                    fill="tozeroy",
                    fillcolor="rgba(0, 113, 227, 0.06)",
                ))

            # 广告支出平滑曲线 (Apple 薄荷绿)
            if y_ads:
                fig_trend.add_trace(go.Scatter(
                    x=x_vals,
                    y=y_ads,
                    name="广告支出",
                    mode="lines+markers",
                    line=dict(shape="spline", smoothing=1.3, color="#34C759", width=2.2),
                    marker=dict(size=4, color="#FFFFFF", line=dict(color="#34C759", width=2)),
                    fill="tozeroy",
                    fillcolor="rgba(52, 199, 89, 0.05)",
                ))

            # 去噪布局配置：透明背景、无多余外框、淡化 Y 轴网格线
            fig_trend.update_layout(
                height=270,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    font=dict(size=12, color="#86868B"),
                ),
                hovermode="x unified",
            )
            fig_trend.update_xaxes(showgrid=False, linecolor="rgba(0,0,0,0)", tickfont=dict(size=11, color="#A1A1A6"), nticks=7)
            fig_trend.update_yaxes(showgrid=True, gridcolor="#F5F5F7", linecolor="rgba(0,0,0,0)", tickfont=dict(size=11, color="#A1A1A6"))

            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("上传更多包含日期粒度的报表后，将自动展示时间序列走势曲线。")
        st.markdown("</div>", unsafe_allow_html=True)

    with c_right:
        st.markdown(
            """
            <div class="card">
                <div class="card-title">
                    <span>广告花费渠道分布</span>
                    <span style="font-size: 13px; color: #86868B; font-weight: normal;">真实构成</span>
                </div>
            """,
            unsafe_allow_html=True,
        )

        # // FIX: 彻底移除硬编码 [52, 24, 14, 10]，提取平台/设备/页面真实分布
        plat_df = sec_data.get("platform")
        page_df = sec_data.get("page_type")
        donut_labels = []
        donut_values = []

        if plat_df is not None and not plat_df.empty:
            p_col = next((c for c in ["平台", "设备", "终端", "platform"] if c in plat_df.columns), plat_df.columns[0])
            s_col = next((c for c in ["花费", "广告花费", "spend"] if c in plat_df.columns), None)
            if s_col:
                p_agg = plat_df.groupby(p_col)[s_col].sum().reset_index()
                donut_labels = list(p_agg[p_col].astype(str))
                donut_values = list(pd.to_numeric(p_agg[s_col], errors="coerce").fillna(0))
        elif page_df is not None and not page_df.empty:
            p_col = next((c for c in ["页面类型", "页面位置", "page_type"] if c in page_df.columns), page_df.columns[0])
            s_col = next((c for c in ["花费", "广告花费", "spend"] if c in page_df.columns), None)
            if s_col:
                p_agg = page_df.groupby(p_col)[s_col].sum().reset_index()
                donut_labels = list(p_agg[p_col].astype(str))
                donut_values = list(pd.to_numeric(p_agg[s_col], errors="coerce").fillna(0))
        elif camp_df is not None and not camp_df.empty:
            c_name_col = next((c for c in ["活动名", "广告活动", "campaign"] if c in camp_df.columns), camp_df.columns[0])
            c_sp_col = next((c for c in ["花费", "广告花费", "spend"] if c in camp_df.columns), None)
            if c_sp_col:
                c_agg = camp_df.groupby(c_name_col)[c_sp_col].sum().sort_values(ascending=False).head(5)
                donut_labels = [str(k)[:12] for k in c_agg.index]
                donut_values = list(c_agg.values)

        donut_colors = ["#2B3648", "#38A3A5", "#F4A261", "#E76F51", "#A1A1A6"]

        if donut_values and sum(donut_values) > 0:
            fig_donut = go.Figure(data=[go.Pie(
                labels=donut_labels,
                values=donut_values,
                hole=0.68,
                marker_colors=donut_colors[:len(donut_labels)],
                textinfo="none",
                hoverinfo="label+percent",
                direction="clockwise",
                sort=False,
            )])

            fig_donut.update_layout(
                height=230,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.2,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=11, color="#86868B"),
                ),
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("载入平台终端或广告活动报表后，将自动展示各渠道的花费构成。")

        st.markdown("</div>", unsafe_allow_html=True)
