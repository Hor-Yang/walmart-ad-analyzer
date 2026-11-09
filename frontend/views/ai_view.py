"""
AI 决策中心模块视图 (AI Intelligence View)
统一跨模块 AI 分析入口：跨域联动诊断 (广告×库存×利润)、12 类专业广告问题归因、8 要素决策指令生成与策略效果追踪复盘
"""

import streamlit as st
import pandas as pd
from frontend.components.kpi_card import render_kpi_card, render_empty_state, render_page_header
from analyzer.diagnosis_12_issues import diagnose_12_advertising_issues
from analyzer.effect_tracker import (
    log_optimization_actions,
    load_tracking_history,
    generate_tracking_summary,
    clear_tracking_history,
    update_action_status,
    backfill_post_data,
)

try:
    from analyzer import AdDecisionEngine
except ImportError:
    AdDecisionEngine = None


def render_ai_view():
    render_page_header("AI 决策中心", "跨模块企业级智能中枢：广告×库存×利润多域联动诊断、12 类根因穿透与闭环效果复盘")

    sec_data = st.session_state.get("section_data", {})
    camp_df = sec_data.get("campaign")
    st_df = sec_data.get("search_term")
    kw_df = sec_data.get("keyword")
    item_df = sec_data.get("ad_item")

    has_any = any(v is not None and not v.empty for v in [camp_df, st_df, kw_df, item_df])

    if not has_any:
        render_empty_state(
            title="暂无待诊断业务数据",
            description="AI 决策中心需要多模块数据驱动运算。请前往「数据中心」上传报表，系统将自动激活 12 类问题诊断引擎与跨域决策中枢。",
            icon_type="ai",
            action_label="前往数据中心上传数据",
            action_key="ai_to_dh_btn",
        )
        if st.session_state.get("ai_to_dh_btn"):
            st.session_state["active_page"] = "data_hub"
            st.rerun()
        return

    # 1. 跨模块联动诊断卡片 (Cross-Module Synergies)
    st.markdown("#### 1. 跨模块联动规则触发状态 (Cross-Module Synergies)")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(
            """
            <div class="card" style="padding: 20px; height: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-size: 14.5px; font-weight: 600; color: #1D1D1F;">广告 × 库存 断货保护联动</span>
                    <span class="apple-badge badge-apple-green">已激活</span>
                </div>
                <div style="font-size: 12.5px; color: #86868B; line-height: 1.6;">
                    规则：可售天数 DOS &lt; 15 天的商品，<strong>强制拦截加价与拓词动作</strong>，避免断货导致权重崩塌。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with s2:
        st.markdown(
            """
            <div class="card" style="padding: 20px; height: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-size: 14.5px; font-weight: 600; color: #1D1D1F;">广告 × 利润 动态保本止血</span>
                    <span class="apple-badge badge-apple-red">已激活</span>
                </div>
                <div style="font-size: 12.5px; color: #86868B; line-height: 1.6;">
                    规则：实际 ACoS 超过保本线 5% 以上且无新客价值的词/品，<strong>强制降权 15%~25% 止血</strong>。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with s3:
        st.markdown(
            """
            <div class="card" style="padding: 20px; height: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-size: 14.5px; font-weight: 600; color: #1D1D1F;">决策防冲突与动作去重</span>
                    <span class="apple-badge badge-apple-blue">已激活</span>
                </div>
                <div style="font-size: 12.5px; color: #86868B; line-height: 1.6;">
                    规则：同一关键词/商品禁止同时出现“加价”与“暂停/否词”冲突，由决策引擎自动优先级仲裁。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 2. 12 类专业广告问题深度诊断 (Layer 4)
    st.markdown("#### 2. 十二大核心广告问题根因诊断 (12 Diagnostic Issues)")
    st.caption("每条诊断均严格包含：问题描述、关键数据证据、可能原因、置信度、建议措施、预期改善方向与观察周期。")

    raw_tables = {
        "campaign": camp_df,
        "search_term": st_df,
        "keyword": kw_df,
        "ad_item": item_df,
        "platform": sec_data.get("platform"),
        "page_type": sec_data.get("page_type"),
    }
    issues = diagnose_12_advertising_issues(raw_tables, target_acos=0.30, breakeven_acos=0.35)

    if issues:
        st.markdown(f"**共精准识别出 {len(issues)} 项待优化关键问题（已结构化解耦：数据事实、原因推断、建议动作、待验证假设）：**")
        i_cols = st.columns(2)
        for idx, item in enumerate(issues[:10]):  # 突出展示 Top 10 问题
            with i_cols[idx % 2]:
                c_level = item.get("原因置信度", "中")
                badge_c = "badge-apple-red" if c_level == "高" else "badge-apple-gray"
                st.markdown(
                    f"""
                    <div class="card" style="padding: 18px; margin-bottom: 14px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="font-weight: 600; font-size: 14.5px; color: #1D1D1F;">{item.get('问题类型')}</span>
                            <span class="apple-badge {badge_c}">置信度: {c_level}</span>
                        </div>
                        <div style="font-size: 12.5px; color: #4B5563; margin-bottom: 6px; line-height: 1.5;">
                            <strong>数据事实：</strong> {item.get('关键数据证据')}
                        </div>
                        <div style="font-size: 12.5px; color: #86868B; margin-bottom: 6px; line-height: 1.5;">
                            <strong>原因推断：</strong> {item.get('可能原因')}
                        </div>
                        <div style="font-size: 12.5px; color: #059669; background: #E6F7ED; padding: 8px 12px; border-radius: 8px; margin-bottom: 6px; line-height: 1.5;">
                            <strong>建议动作：</strong> {item.get('建议采取的措施')}
                        </div>
                        <div style="font-size: 11.5px; color: #0071E3; background: #E8F2FE; padding: 6px 10px; border-radius: 8px; line-height: 1.4;">
                            <strong>待验证假设：</strong> 预期方向: {item.get('预期改善方向')} | 建议观察周期: {item.get('建议观察周期')}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.success("大盘指标稳健，未检测到显著异常问题。")

    st.markdown("---")

    # 3. 策略执行效果追踪与复盘 (Layer 6)
    st.markdown("#### 3. 优化策略执行记录与闭环复盘 (Strategy Tracking & Calibration)")
    
    col_t1, col_t2 = st.columns([1.5, 0.5])
    with col_t1:
        st.caption("自动归档 AI 生成的建议动作，比对调整前后的真实转化数据，持续校准模型阈值。")
    with col_t2:
        if st.button("清空追踪历史", key="clear_tracking_btn", use_container_width=True):
            clear_tracking_history()
            st.success("已清空历史追踪数据。")
            st.rerun()

    history = load_tracking_history()
    summary = generate_tracking_summary(history)

    k_t1, k_t2, k_t3, k_t4 = st.columns(4)
    with k_t1:
        render_kpi_card("累计归档优化动作", f"{summary.get('total_actions', 0)} 条", sub_title="已落地策略记录")
    with k_t2:
        render_kpi_card("待观察动作", f"{summary.get('pending_actions', 0)} 条", sub_title="处于 3~7 天观察期", badge="进行中", badge_color="blue")
    with k_t3:
        render_kpi_card("符合预期成功率", f"{summary.get('success_rate_pct', 0.0):.1f}%", sub_title=f"已达标 {summary.get('successful_actions', 0)} 项", badge="闭环率", badge_color="green")
    with k_t4:
        render_kpi_card("模型规则校准次数", f"{summary.get('rule_calibrations', 0)} 次", sub_title="动态算法持续进化")

    if history:
        st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
        
        # 优化动作执行状态快速更新操作区
        st.markdown("##### 策略执行状态更新与数据回填")
        act_ids = [r.get("action_id") for r in history if r.get("action_id")]
        if act_ids:
            c_u1, c_u2, c_u3 = st.columns([1.5, 1.2, 1.0])
            with c_u1:
                sel_act_id = st.selectbox("选择要更新的策略记录 ID", act_ids, key="sel_act_to_update")
            with c_u2:
                sel_status = st.selectbox("新执行状态", ["已执行 (采纳)", "忽略 (放弃)", "待新周期报表回测验证"], key="sel_act_status")
            with c_u3:
                st.write("")
                st.write("")
                if st.button("更新状态", key="apply_status_btn", use_container_width=True):
                    update_action_status(sel_act_id, sel_status)
                    st.success(f"已更新策略 {sel_act_id} 状态为 {sel_status}！")
                    st.rerun()
    else:
        st.info("暂无执行记录。在各业务板块导出决策建议并采纳后，系统将自动录入追踪流水。")
