"""
利润分析模块视图 (Profitability Analytics View)
全链路全成本真实核算：销售收入 - 采购成本 - 头程物流 - 尾程派送 - 平台佣金 - 广告花费 = 广告后真实净贡献
严格解耦保本 ACoS 与目标 ACoS，动态驱动广告控本止血
"""

import streamlit as st
import pandas as pd
from frontend.components.kpi_card import render_kpi_card, render_empty_state
from analyzer.sku_profit_model import (
    calculate_sku_profit_analytics,
    generate_sku_cost_template,
)
from frontend.utils.formatters import fmt_money, fmt_pct, fmt_num, fmt_ratio
from analyzer.metrics import safe_divide


def render_profit_view():
    st.markdown("## 💰 利润分析 (Profitability Analytics)")
    st.caption("全成本动态利润核算大盘：打通商品供应链成本与广告消耗，识别真实赚钱与失血亏损款")

    sec_data = st.session_state.get("section_data", {})
    sku_cost_df = st.session_state.get("sku_cost_df")
    sku_cost_dict = st.session_state.get("sku_cost_dict", {})
    item_df = sec_data.get("ad_item")
    camp_df = sec_data.get("campaign")

    # 1. 检查数据源准备情况
    if item_df is None or item_df.empty:
        render_empty_state(
            title="暂无商品广告与出单数据",
            description="计算真实利润需要结合商品出单数据与成本参数。请在「数据中心」上传「④ 商品广告列表」以及「SKU 成本底表」。",
            icon="💰",
            action_label="👉 前往数据中心上传报表",
            action_key="profit_to_dh_btn",
        )
        if st.session_state.get("profit_to_dh_btn"):
            st.session_state["active_page"] = "data_hub"
            st.rerun()
        return

    # 运行真实 SKU 利润模型计算
    profit_res = calculate_sku_profit_analytics(
        item_df,
        sku_cost_dict=sku_cost_dict,
        default_commission_rate=0.15,
        default_cost_ratio=0.65,
    )
    p_df = profit_res.get("profit_df", pd.DataFrame())
    p_sum = profit_res.get("summary", {})

    tot_sales = p_sum.get("总销售额", 0.0)
    tot_spend = p_sum.get("总广告花费", 0.0)
    pre_ad_profit = p_sum.get("广告前贡献总利润", 0.0)
    post_ad_profit = p_sum.get("广告后实际净利润", 0.0)
    be_acos = p_sum.get("全店加权保本ACoS", 0.35)
    actual_acos = safe_divide(tot_spend, tot_sales) if tot_sales > 0 else 0.0
    post_margin = safe_divide(post_ad_profit, tot_sales) * 100.0 if tot_sales > 0 else 0.0

    # 2. 核心利润 KPI 卡片
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("累计总销售收入", f"${tot_sales:,.2f}", sub_title=f"广告总投入: ${tot_spend:,.2f}", badge="全渠道GMV", badge_color="blue")
    with k2:
        render_kpi_card("广告前毛利润", f"${pre_ad_profit:,.2f}", sub_title="已扣采购+头程+尾程+佣金", badge="毛利总盘", badge_color="slate")
    with k3:
        p_color = "green" if post_ad_profit >= 0 else "red"
        render_kpi_card("广告后净贡献利润", f"${post_ad_profit:,.2f}", sub_title=f"全店净利润率: {post_margin:.1f}%", badge=f"{post_margin:.1f}%", badge_color=p_color)
    with k4:
        acos_diff = (actual_acos - be_acos) * 100.0
        be_color = "green" if acos_diff <= 0 else "red"
        diff_txt = f"低于保本线 {abs(acos_diff):.1f}%" if acos_diff <= 0 else f"超支击穿保本线 {acos_diff:.1f}%"
        render_kpi_card("加权保本 ACoS", f"{be_acos*100:.1f}%", sub_title=f"实际 ACoS: {actual_acos*100:.1f}% ({diff_txt})", badge="动态保本线", badge_color=be_color)

    st.markdown("---")

    # 3. 利润核算公式与口径说明
    st.markdown("#### 📐 全链路利润核算逻辑与动态保本公式")
    st.markdown(
        """
        > [!NOTE] 真实利润核算公式拆解
        > - **广告前毛利** = `销售额 - 采购成本 - 头程海运 - 尾程派送 - 沃尔玛平台佣金 (15%)`
        > - **动态保本 ACoS** = `广告前毛利率 = (广告前毛利 ÷ 销售额)`
        > - **广告后净利润** = `广告前毛利 - 广告总花费`
        > - **业务规则**：当实际广告 `ACoS > 保本 ACoS` 时，该 SKU 处于**“出单越多净亏越多”**的倒贴失血状态，AI 决策中枢将强制触发降价调控。
        """
    )

    # 4. SKU 利润台账明细
    st.markdown("#### 📑 各 SKU 真实利润与盈亏状态台账")
    if not p_df.empty:
        v_df = p_df.copy()
        for pct_col in ["保本ACoS", "实际ACoS", "目标ACoS", "广告后净利率"]:
            if pct_col in v_df.columns:
                v_df[f"{pct_col}%"] = pd.to_numeric(v_df[pct_col], errors="coerce") * 100.0

        st.dataframe(
            v_df,
            column_config={
                "sku": st.column_config.TextColumn("统一商品编码 (SKU) / Item ID", width="medium"),
                "销售额": st.column_config.NumberColumn("销售总额", format="$%.2f"),
                "广告花费": st.column_config.NumberColumn("广告花费", format="$%.2f"),
                "广告前毛利": st.column_config.NumberColumn("广告前贡献毛利", format="$%.2f"),
                "广告后实际净利润": st.column_config.NumberColumn("广告后净利润", format="$%.2f"),
                "保本ACoS%": st.column_config.NumberColumn("保本ACoS", format="%.1f%%"),
                "实际ACoS%": st.column_config.NumberColumn("实际ACoS", format="%.1f%%"),
                "广告后净利率%": st.column_config.NumberColumn("净利率", format="%.1f%%"),
                "盈亏状态": st.column_config.TextColumn("盈亏判定"),
            },
            use_container_width=True,
            hide_index=True,
        )
