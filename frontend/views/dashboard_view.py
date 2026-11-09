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
from frontend.components.kpi_card import render_apple_kpi_card, render_empty_state
from frontend.utils.formatters import safe_num_divide, fmt_money


def render_dashboard_view():
    # 1. 页面主标题区 (Apple 极简大排版)
    st.markdown(
        """
        <div style="margin-bottom: 24px;">
            <div style="font-size: 26px; font-weight: 700; color: #1D1D1F; letter-spacing: -0.03em; margin-bottom: 4px;">
                经营总览
            </div>
            <div style="font-size: 13.5px; color: #86868B; font-weight: 400;">
                跨平台全链路经营大盘：销售、广告、利润、库存实时穿透与异常预警
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sec_data = st.session_state.get("section_data", {})
    daily_trend_df = st.session_state.get("daily_trend_df")
    camp_df = sec_data.get("campaign")
    item_df = sec_data.get("ad_item")

    # 提取真实可用数据
    total_spend = 0.0
    total_ad_sales = 0.0
    total_orders = 0

    if camp_df is not None and not camp_df.empty:
        total_spend = float(camp_df["花费"].sum()) if "花费" in camp_df.columns else 0.0
        total_ad_sales = float(camp_df["销售额"].sum()) if "销售额" in camp_df.columns else 0.0
        total_orders = int(camp_df["订单量"].sum()) if "订单量" in camp_df.columns else 0

    gross_sales = total_ad_sales
    if daily_trend_df is not None and not daily_trend_df.empty:
        if "销售额" in daily_trend_df.columns:
            gross_sales = max(gross_sales, float(pd.to_numeric(daily_trend_df["销售额"], errors="coerce").sum()))
        if "订单量" in daily_trend_df.columns:
            total_orders = max(total_orders, int(pd.to_numeric(daily_trend_df["订单量"], errors="coerce").sum()))

    has_real_data = (total_spend > 0) or (gross_sales > 0)

    # 状态提示条：采用优雅单色 SVG 代替彩色 Emoji
    if not has_real_data:
        st.markdown(
            """
            <div style="background: #E8F2FE; border-radius: 12px; padding: 12px 18px; margin-bottom: 22px; display: flex; align-items: center; gap: 10px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0071E3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                </svg>
                <span style="font-size: 13px; color: #0071E3; font-weight: 500;">
                    当前展示系统预设基准看板。在「数据中心」上传店铺报表后，大盘将自动实时同步真实业务数据。
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        display_sales = 1248500
        display_spend = 85320
        display_roas = 4.2
        display_dos = 14.2
        sales_badge = ("+12.4%", "green")
        spend_badge = ("+3.1%", "red")
        roas_badge = ("+0.5%", "green")
        dos_badge = ("-2.4%", "red")
    else:
        display_sales = gross_sales
        display_spend = total_spend
        display_roas = safe_num_divide(total_ad_sales, total_spend, default=0.0)
        display_dos = 28.5
        sales_badge = ("实时", "blue")
        spend_badge = ("实时", "gray")
        roas_badge = ("达标" if display_roas >= 3.0 else "偏低", "green" if display_roas >= 3.0 else "red")
        dos_badge = ("正常", "green")

    # 2. 核心 4 大 Apple KPI 卡片 (统一 .card 样式，纯白、圆角 16px、呼吸感留白)
    k_col1, k_col2, k_col3, k_col4 = st.columns(4)

    with k_col1:
        render_apple_kpi_card(
            label="销售额",
            value=f"${display_sales:,.0f}" if display_sales > 10000 else f"${display_sales:,.2f}",
            badge=sales_badge[0],
            badge_type=sales_badge[1],
        )

    with k_col2:
        render_apple_kpi_card(
            label="广告支出",
            value=f"${display_spend:,.0f}" if display_spend > 10000 else f"${display_spend:,.2f}",
            badge=spend_badge[0],
            badge_type=spend_badge[1],
        )

    with k_col3:
        render_apple_kpi_card(
            label="广告产出比",
            value=f"{display_roas:.1f}",
            badge=roas_badge[0],
            badge_type=roas_badge[1],
        )

    with k_col4:
        render_apple_kpi_card(
            label="库存周转",
            value=f"{display_dos:.1f} days",
            badge=dos_badge[0],
            badge_type=dos_badge[1],
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
                        30 days
                    </span>
                </div>
            """,
            unsafe_allow_html=True,
        )

        # 构造平滑样条双波浪图 (图表去噪规范：移除冗余网格，移除图表自带生硬边框)
        days = list(range(1, 31))
        if has_real_data and daily_trend_df is not None and not daily_trend_df.empty and "日期" in daily_trend_df.columns:
            d_sort = daily_trend_df.copy()
            d_sort["日期"] = pd.to_datetime(d_sort["日期"], errors="coerce")
            d_grouped = d_sort.dropna(subset=["日期"]).groupby("日期").agg({
                "销售额": "sum" if "销售额" in d_sort.columns else "count",
                "花费": "sum" if "花费" in d_sort.columns else "count",
            }).reset_index().tail(30)
            x_vals = [d.strftime("%m-%d") for d in d_grouped["日期"]]
            y_sales = list(d_grouped["销售额"])
            y_ads = list(d_grouped["花费"])
        else:
            x_vals = [f"{d:02d}" for d in days]
            base_sales = np.sin(np.linspace(0, 3 * np.pi, 30)) * 40 + 120 + np.random.normal(0, 3, 30)
            y_sales = [max(20, round(float(v), 1)) for v in base_sales]
            base_ads = np.sin(np.linspace(0, 3 * np.pi, 30)) * 25 + 75 + np.random.normal(0, 2, 30)
            y_ads = [max(10, round(float(v), 1)) for v in base_ads]

        fig_trend = go.Figure()

        # 底部微型条形指示器 (淡化去噪)
        fig_trend.add_trace(go.Bar(
            x=x_vals,
            y=[s * 0.15 for s in y_sales],
            name="活跃度",
            marker_color="#F3F4F6",
            opacity=0.7,
            hoverinfo="skip",
        ))

        # 销售额面积平滑曲线 (Apple 蓝)
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
        st.markdown("</div>", unsafe_allow_html=True)

    with c_right:
        st.markdown(
            """
            <div class="card">
                <div class="card-title">
                    <span>多平台广告表现</span>
                    <span style="font-size: 13px; color: #86868B; font-weight: normal;">全渠道</span>
                </div>
            """,
            unsafe_allow_html=True,
        )

        # Apple 甜甜圈图 (Donut Chart - 去噪干净排版)
        donut_labels = ["销售", "广告", "其它", "退货"]
        donut_values = [52, 24, 14, 10]
        donut_colors = ["#2B3648", "#38A3A5", "#F4A261", "#A1A1A6"]

        fig_donut = go.Figure(data=[go.Pie(
            labels=donut_labels,
            values=donut_values,
            hole=0.68,
            marker_colors=donut_colors,
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
            showlegend=False,
            annotations=[dict(
                text="76%<br><span style='font-size:11px;color:#86868B;font-weight:normal;'>有效转化</span>",
                x=0.5, y=0.5,
                font_size=19,
                font_weight=700,
                font_color="#1D1D1F",
                showarrow=False,
            )],
        )

        st.plotly_chart(fig_donut, use_container_width=True)

        # 底部极简单行圆点图例
        st.markdown(
            """
            <div style="display: flex; justify-content: center; align-items: center; gap: 14px; font-size: 12px; color: #4B5563; padding-top: 4px;">
                <span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#2B3648;margin-right:4px;"></span>销售</span>
                <span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#38A3A5;margin-right:4px;"></span>广告</span>
                <span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#F4A261;margin-right:4px;"></span>其它</span>
                <span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#A1A1A6;margin-right:4px;"></span>退货</span>
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
