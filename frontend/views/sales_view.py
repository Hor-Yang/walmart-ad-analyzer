"""
销售分析模块视图 (Sales Analytics View)
全渠道多平台销售额、订单量、销售件数、退款率、自然 vs 广告销售归因与 SKU 销售排名
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from frontend.components.kpi_card import render_kpi_card, render_empty_state, render_page_header
from frontend.utils.formatters import safe_num_divide


def render_sales_view():
    render_page_header("销售分析", "全渠道多店铺销售穿透：GMV、出单结构、退款率、自然销售与广告销售口径对齐")

    sec_data = st.session_state.get("section_data", {})
    daily_trend_df = st.session_state.get("daily_trend_df")
    item_df = sec_data.get("ad_item")
    camp_df = sec_data.get("campaign")

    # 提取真实可用销售指标
    ad_sales = float(camp_df["销售额"].sum()) if (camp_df is not None and "销售额" in camp_df.columns) else 0.0
    ad_orders = int(camp_df["订单量"].sum()) if (camp_df is not None and "订单量" in camp_df.columns) else 0

    # // FIX: 严格区分店铺真实 GMV 与广告归因销售额，严禁将广告归因销售额直接作为店铺 GMV
    has_store_gmv = False
    store_gmv = 0.0
    total_orders = ad_orders
    total_units = ad_orders

    has_daily = daily_trend_df is not None and not daily_trend_df.empty
    if has_daily:
        if "销售额" in daily_trend_df.columns:
            store_gmv = float(pd.to_numeric(daily_trend_df["销售额"], errors="coerce").sum())
            if store_gmv > 0:
                has_store_gmv = True
        if "订单量" in daily_trend_df.columns:
            total_orders = int(pd.to_numeric(daily_trend_df["订单量"], errors="coerce").sum())
        if "销售量" in daily_trend_df.columns:
            total_units = int(pd.to_numeric(daily_trend_df["销售量"], errors="coerce").sum())

    if ad_sales <= 0 and not has_store_gmv:
        render_empty_state(
            title="暂无销售业务数据",
            description="系统尚未导入店铺总销售报表或广告归因报表。请在「数据中心」上传报表以解锁销售分析大盘。",
            icon_type="sales",
            action_label="前往数据中心上传销售数据",
            action_key="sales_to_dh_btn",
        )
        if st.session_state.get("sales_to_dh_btn"):
            st.session_state["active_page"] = "data_hub"
            st.rerun()
        return

    # 1. 销售核心 KPI (口径严密隔离)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        if has_store_gmv:
            render_kpi_card("店铺真实总 GMV", f"${store_gmv:,.2f}", sub_title="全渠道已完成/已发货真实销售", badge="全店GMV", badge_color="blue")
        else:
            render_kpi_card("广告归因销售额", f"${ad_sales:,.2f}", sub_title="全店真实 GMV 待导入店铺销售主表", badge="广告归因", badge_color="amber")
    with k2:
        render_kpi_card("广告拉动订单数", f"{ad_orders:,} 单", sub_title=f"总出单件数: {total_units:,} 件")
    with k3:
        aov_base = store_gmv if has_store_gmv else ad_sales
        aov_ord = total_orders if total_orders > 0 else 1
        aov = safe_num_divide(aov_base, aov_ord, default=0.0)
        render_kpi_card("平均客单价 (AOV)", f"${aov:,.2f}", sub_title="平均每笔订单成交金额")
    with k4:
        if has_store_gmv and store_gmv >= ad_sales:
            organic_sales = max(0.0, store_gmv - ad_sales)
            organic_ratio = safe_num_divide(organic_sales, store_gmv, default=0.0) * 100.0
            ad_ratio = 100.0 - organic_ratio
            render_kpi_card("自然销售 vs 广告出单", f"{organic_ratio:.1f}% / {ad_ratio:.1f}%", sub_title=f"自然销售额: ${organic_sales:,.2f}", badge=f"自然占比{organic_ratio:.0f}%", badge_color="green")
        else:
            render_kpi_card("广告渗透占比", "广告归因主导", sub_title="当前仅载入广告报表，未导入全盘GMV", badge="单渠道", badge_color="slate")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 2. 销售结构分析与口径说明
    s_col1, s_col2 = st.columns([1.2, 1])
    with s_col1:
        st.markdown("#### 销售来源口径构成 (Organic vs Paid Attribution)")
        if has_store_gmv and store_gmv >= ad_sales:
            organic_sales = max(0.0, store_gmv - ad_sales)
            labels = ["自然订单销售额 (Organic)", "广告拉动销售额 (Sponsored)"]
            vals = [organic_sales, ad_sales]
            colors = ["#34C759", "#0071E3"]
        else:
            labels = ["广告直接归因销售额", "待补录全店自然销售"]
            vals = [ad_sales, 0.0001]
            colors = ["#0071E3", "#E5E5EA"]

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=vals,
            hole=.55,
            marker_colors=colors,
            direction="clockwise",
            sort=False,
        )])
        fig.update_layout(
            height=260,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    with s_col2:
        st.markdown("#### 跨平台统计口径差异说明")
        st.markdown(
            """
            <div class="card" style="padding: 18px 22px; height: 260px; background: #F8F9FA;">
                <div style="font-weight: 600; font-size: 13.5px; color: #1D1D1F; margin-bottom: 6px;">统计口径与归因窗口保护机制</div>
                <div style="font-size: 12.5px; color: #86868B; line-height: 1.6;">
                    • <strong>Walmart 平台</strong>：广告归因窗口通常为 3 天 / 14 天 Click-Through 归因，采用 Last Touch 模型。<br/>
                    • <strong>Wayfair / eBay</strong>：采用订单发货口径与净销售口径（需扣除平台代收运费）。<br/>
                    • <strong>系统规范</strong>：跨平台聚合大盘时，<strong>禁止将不同归因窗口的数字简单粗暴累加</strong>，本平台已对销售与广告口径做严格隔离展示。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 3. 商品销售贡献度榜单
    st.markdown("#### 商品销售表现排行 (Top SKUs by Sales)")
    if item_df is not None and not item_df.empty:
        # // FIX: 防御性多字段查找 SKU 或商品标识列，杜绝 KeyError
        sku_col = next((c for c in ["SKU", "sku", "对应SKU", "商品SKU", "项目ID", "item_id", "Item ID"] if c in item_df.columns), item_df.columns[0])
        sku_rank = item_df.groupby(sku_col).agg({
            "销售额": "sum" if "销售额" in item_df.columns else "count",
            "订单量": "sum" if "订单量" in item_df.columns else "count",
            "花费": "sum" if "花费" in item_df.columns else "count",
        }).reset_index().sort_values(by="销售额", ascending=False)
        sku_rank["客单价 ($)"] = sku_rank.apply(lambda r: safe_num_divide(r.get("销售额", 0), r.get("订单量", 0), default=0.0), axis=1)
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
