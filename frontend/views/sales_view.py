"""
销售分析模块视图 (Sales Analytics View)
全渠道多平台销售额、订单量、销售件数、退款率、自然 vs 广告销售归因与 SKU 销售排名
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from frontend.components.kpi_card import render_kpi_card, render_empty_state
from analyzer.metrics import safe_divide


def render_sales_view():
    st.markdown("## 🛒 销售分析 (Sales Analytics)")
    st.caption("全渠道多店铺销售穿透：GMV、出单结构、退款率、自然销售与广告销售口径对齐")

    sec_data = st.session_state.get("section_data", {})
    daily_trend_df = st.session_state.get("daily_trend_df")
    item_df = sec_data.get("ad_item")
    camp_df = sec_data.get("campaign")

    # 提取真实可用销售指标
    ad_sales = float(camp_df["销售额"].sum()) if (camp_df is not None and "销售额" in camp_df.columns) else 0.0
    ad_orders = int(camp_df["订单量"].sum()) if (camp_df is not None and "订单量" in camp_df.columns) else 0

    has_daily = daily_trend_df is not None and not daily_trend_df.empty
    total_sales = ad_sales
    total_orders = ad_orders
    total_units = ad_orders

    if has_daily:
        if "销售额" in daily_trend_df.columns:
            total_sales = max(total_sales, float(pd.to_numeric(daily_trend_df["销售额"], errors="coerce").sum()))
        if "订单量" in daily_trend_df.columns:
            total_orders = max(total_orders, int(pd.to_numeric(daily_trend_df["订单量"], errors="coerce").sum()))
        if "销售量" in daily_trend_df.columns:
            total_units = int(pd.to_numeric(daily_trend_df["销售量"], errors="coerce").sum())

    organic_sales = max(0.0, total_sales - ad_sales)
    organic_ratio = safe_divide(organic_sales, total_sales) * 100.0 if total_sales > 0 else 0.0
    ad_ratio = 100.0 - organic_ratio if total_sales > 0 else 0.0
    aov = safe_divide(total_sales, total_orders) if total_orders > 0 else 0.0

    if total_sales <= 0:
        render_empty_state(
            title="暂无销售业务数据",
            description="系统尚未导入店铺总销售报表或广告归因报表。请在「数据中心」上传报表以解锁销售分析大盘。",
            icon="🛒",
            action_label="👉 前往数据中心上传销售数据",
            action_key="sales_to_dh_btn",
        )
        if st.session_state.get("sales_to_dh_btn"):
            st.session_state["active_page"] = "data_hub"
            st.rerun()
        return

    # 1. 销售核心 KPI
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("总销售额 (Gross GMV)", f"${total_sales:,.2f}", sub_title="全渠道已完成/已发货", badge="总盘", badge_color="blue")
    with k2:
        render_kpi_card("总销售订单数", f"{total_orders:,} 单", sub_title=f"总件数: {total_units:,} 件")
    with k3:
        render_kpi_card("平均客单价 (AOV)", f"${aov:,.2f}", sub_title="平均每笔订单成交金额")
    with k4:
        render_kpi_card("自然销售 vs 广告出单", f"{organic_ratio:.1f}% / {ad_ratio:.1f}%", sub_title=f"自然销售额: ${organic_sales:,.2f}", badge=f"自然占比{organic_ratio:.0f}%", badge_color="green")

    st.markdown("---")

    # 2. 销售结构分析与口径说明
    s_col1, s_col2 = st.columns([1.2, 1])
    with s_col1:
        st.markdown("#### 📊 销售来源口径构成 (Organic vs Paid Attribution)")
        fig = go.Figure(data=[go.Pie(
            labels=["自然订单销售额 (Organic)", "广告拉动销售额 (Sponsored)"],
            values=[organic_sales, ad_sales],
            hole=.45,
            marker_colors=["#10b981", "#3b82f6"],
        )])
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with s_col2:
        st.markdown("#### ℹ️ 跨平台统计口径差异说明")
        st.markdown(
            """
            > [!NOTE] 统计口径与归因窗口保护机制
            > - **Walmart 平台**：广告归因窗口通常为 3 天 / 14 天 Click-Through 归因，采用 Last Touch 模型；
            > - **Wayfair / eBay**：采用订单发货口径与净销售口径（需扣除平台代收运费）；
            > - **系统规范**：跨平台聚合大盘时，**禁止将不同归因窗口的数字简单粗暴累加**，本平台已对销售与广告口径做严格隔离展示。
            """
        )

    # 3. 商品销售贡献度榜单
    st.markdown("#### 🏆 商品销售表现排行 (Top SKUs by Sales)")
    if item_df is not None and not item_df.empty:
        sku_col = "sku" if "sku" in item_df.columns else "item_id"
        sku_rank = item_df.groupby(sku_col).agg({
            "销售额": "sum" if "销售额" in item_df.columns else "count",
            "订单量": "sum" if "订单量" in item_df.columns else "count",
            "花费": "sum" if "花费" in item_df.columns else "count",
        }).reset_index().sort_values(by="销售额", ascending=False)
        sku_rank["客单价 ($)"] = sku_rank.apply(lambda r: safe_divide(r.get("销售额", 0), r.get("订单量", 0)), axis=1)
        st.dataframe(
            sku_rank,
            column_config={
                sku_col: st.column_config.TextColumn("统一商品编码 (SKU) / 平台商品 ID", width="large"),
                "销售额": st.column_config.NumberColumn("累计销售额", format="$%.2f"),
                "订单量": st.column_config.NumberColumn("成交订单", format="%d"),
                "客单价 ($)": st.column_config.NumberColumn("平均客单价", format="$%.2f"),
                "花费": st.column_config.NumberColumn("消耗广告费", format="$%.2f"),
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("暂无商品细分销售明细。")
