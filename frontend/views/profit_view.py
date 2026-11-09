"""
利润分析模块视图 (Profitability Analytics View)
全链路全成本真实核算：销售收入 - 采购成本 - 头程物流 - 尾程派送 - 平台佣金 - 广告花费 = 广告后真实净贡献
严格解耦保本 ACoS 与目标 ACoS，动态驱动广告控本止血
"""

import streamlit as st
import pandas as pd
from frontend.components.kpi_card import render_kpi_card, render_empty_state, render_page_header
from analyzer.sku_profit_model import (
    calculate_sku_profit_analytics,
    generate_sku_cost_template,
)
from frontend.utils.formatters import fmt_money, fmt_pct, fmt_num, fmt_ratio, safe_num_divide


def render_profit_view():
    render_page_header("利润分析", "全成本动态利润核算大盘：打通商品供应链成本与广告消耗，识别真实赚钱与失血亏损款")

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
            icon_type="profit",
            action_label="前往数据中心上传报表",
            action_key="profit_to_dh_btn",
        )
        if st.session_state.get("profit_to_dh_btn"):
            st.session_state["active_page"] = "data_hub"
            st.rerun()
        return

    # 运行真实 SKU 利润模型计算
    # // FIX: 统一调用签名并解构 (p_df, p_sum) 元组，防止 AttributeError
    p_df, p_sum = calculate_sku_profit_analytics(
        item_df,
        cost_dict=sku_cost_dict,
        target_acos_ratio=0.80,
    )

    tot_sales = p_sum.get("total_sales", 0.0)
    tot_spend = p_sum.get("total_spend", 0.0)
    pre_ad_profit = p_sum.get("total_pre_ad_profit", 0.0)
    post_ad_profit = p_sum.get("total_post_ad_net_profit", 0.0)
    configured_skus = p_sum.get("configured_sku_count", 0)
    missing_cost_skus = p_sum.get("missing_cost_sku_count", 0)
    actual_acos = safe_num_divide(tot_spend, tot_sales, default=0.0)
    post_margin = p_sum.get("overall_net_margin", 0.0) * 100.0

    # 2. 核心利润 KPI 卡片
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("累计广告销售收入", f"${tot_sales:,.2f}", sub_title=f"广告总投入: ${tot_spend:,.2f}", badge="广告盘", badge_color="blue")
    with k2:
        render_kpi_card("已核算广告前贡献利润", f"${pre_ad_profit:,.2f}", sub_title=f"已核算 SKU: {configured_skus} 款", badge="毛利盘", badge_color="slate")
    with k3:
        p_color = "green" if post_ad_profit >= 0 else "red"
        render_kpi_card("广告后真实净贡献利润", f"${post_ad_profit:,.2f}", sub_title=f"核算净利率: {post_margin:.1f}%", badge=f"{post_margin:.1f}%", badge_color=p_color)
    with k4:
        if missing_cost_skus > 0:
            render_kpi_card("成本缺失待补录", f"{missing_cost_skus} 款 SKU", sub_title="缺失成本时不输出假净利", badge="待补录", badge_color="amber")
        else:
            render_kpi_card("成本底表覆盖率", "100.0%", sub_title="全量 SKU 真实成本均已对齐", badge="已对齐", badge_color="green")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 3. 利润核算公式与口径说明
    st.markdown("#### 全链路利润核算逻辑与动态保本公式")
    st.markdown(
        """
        <div class="card" style="padding: 18px 22px; margin-bottom: 16px; background: #F8F9FA;">
            <div style="font-weight: 600; font-size: 13.5px; color: #1D1D1F; margin-bottom: 6px;">真实单位经济学核算口径规范</div>
            <div style="font-size: 12.5px; color: #86868B; line-height: 1.7;">
                • <strong>严格区分指标</strong>：核算单件采购物流成本使用<strong>销售件数 (Units Sold)</strong>，客单价核算使用<strong>广告订单数 (Orders)</strong>。<br/>
                • <strong>广告前贡献利润</strong> = 销售额 - (采购成本 + 头程海运 + 尾程派送 + 包装损耗) × 销售件数 - 平台佣金 (销售额 × 佣金率)<br/>
                • <strong>动态保本 ACoS</strong> = 广告前贡献利润 ÷ 销售额（即当前 SKU 能承受的最大广告花费比例）<br/>
                • <strong>广告后贡献利润</strong> = 广告前贡献利润 - 广告总花费<br/>
                • <strong>严肃性护栏</strong>：对于尚未在数据中心配置成本底表的 SKU，<strong>坚决不输出虚假净利润</strong>，系统标明“成本缺失待补录”。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4. SKU 利润台账明细
    st.markdown("#### 各 SKU 真实利润与动态保本台账 (先聚合后核算)")
    if not p_df.empty:
        v_df = p_df.copy()
        for pct_col in ["实际ACoS", "广告前贡献利润率", "广告后贡献利润率", "保本ACoS", "目标ACoS"]:
            if pct_col in v_df.columns:
                v_df[f"{pct_col}%"] = v_df[pct_col].apply(lambda x: f"{x*100.0:.1f}%" if pd.notna(x) else "-")

        st.dataframe(
            v_df[[
                "SKU", "成本真实性", "广告销售额", "广告订单", "销售件数", "平均客单价",
                "广告花费", "实际ACoS%", "广告前贡献利润", "广告后贡献利润", "保本ACoS%", "目标ACoS%", "盈利健康等级", "经营决策建议"
            ]],
            column_config={
                "SKU": st.column_config.TextColumn("统一商品编码 (SKU)", width="medium"),
                "成本真实性": st.column_config.TextColumn("成本状态"),
                "广告销售额": st.column_config.NumberColumn("广告销售额", format="$%.2f"),
                "广告订单": st.column_config.NumberColumn("出单量", format="%d"),
                "销售件数": st.column_config.NumberColumn("销售件数", format="%d"),
                "平均客单价": st.column_config.NumberColumn("客单价", format="$%.2f"),
                "广告花费": st.column_config.NumberColumn("广告花费", format="$%.2f"),
                "实际ACoS%": st.column_config.TextColumn("实际 ACoS"),
                "广告前贡献利润": st.column_config.NumberColumn("广告前贡献利润", format="$%.2f"),
                "广告后贡献利润": st.column_config.NumberColumn("广告后贡献利润", format="$%.2f"),
                "保本ACoS%": st.column_config.TextColumn("动态保本 ACoS"),
                "目标ACoS%": st.column_config.TextColumn("目标 ACoS"),
                "盈利健康等级": st.column_config.TextColumn("盈利评级"),
                "经营决策建议": st.column_config.TextColumn("决策指引", width="large"),
            },
            use_container_width=True,
            hide_index=True,
        )
