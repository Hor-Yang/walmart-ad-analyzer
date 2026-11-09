"""
AI 决策中心模块视图 (AI Intelligence View)
统一跨模块 AI 分析入口：跨域联动诊断 (广告×库存×利润)、12 类专业广告问题归因、8 要素决策指令生成与策略效果追踪复盘
"""

import streamlit as st
import pandas as pd
from frontend.components.kpi_card import render_kpi_card, render_empty_state
from analyzer.diagnosis_12_issues import diagnose_12_advertising_issues
from analyzer.effect_tracker import (
    log_optimization_actions,
    load_tracking_history,
    generate_tracking_summary,
    clear_tracking_history,
)

try:
    from analyzer import AdDecisionEngine
except ImportError:
    AdDecisionEngine = None


def render_ai_view():
    st.markdown("## 🧠 AI 决策中心 (AI Intelligence Center)")
    st.caption("跨模块企业级智能中枢：广告×库存×利润多域联动诊断、12 类根因穿透与闭环效果复盘")

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
            icon="🧠",
            action_label="👉 前往数据中心上传数据",
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
            <div class="kpi-card">
                <div class="kpi-title"><span>🛡️ 广告 × 库存 断货保护联动</span><span class="badge badge-green">已激活</span></div>
                <div style="font-size: 13px; color: #334155; margin-top: 6px; line-height: 1.5;">
                    规则：可售天数 DOS &lt; 15 天的商品，<strong>强制拦截加价与拓词动作</strong>，避免断货导致权重崩塌。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with s2:
        st.markdown(
            """
            <div class="kpi-card">
                <div class="kpi-title"><span>🩸 广告 × 利润 动态保本止血</span><span class="badge badge-red">已激活</span></div>
                <div style="font-size: 13px; color: #334155; margin-top: 6px; line-height: 1.5;">
                    规则：实际 ACoS 超过保本线 5% 以上且无新客价值的词/品，<strong>强制降权 15%~25% 止血</strong>。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with s3:
        st.markdown(
            """
            <div class="kpi-card">
                <div class="kpi-title"><span>⚖️ 决策防冲突与动作去重</span><span class="badge badge-blue">已激活</span></div>
                <div style="font-size: 13px; color: #334155; margin-top: 6px; line-height: 1.5;">
                    规则：同一关键词/商品禁止同时出现“加价”与“暂停/否词”冲突，由决策引擎自动优先级仲裁。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

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
        st.markdown(f"**共精准识别出 {len(issues)} 项待优化关键问题：**")
        i_cols = st.columns(2)
        for idx, item in enumerate(issues[:10]):  # 突出展示 Top 10 问题
            with i_cols[idx % 2]:
                c_level = item.get("原因置信度", "中")
                badge_c = "badge-red" if c_level == "高" else "badge-amber"
                st.markdown(
                    f"""
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-weight: 700; font-size: 14px; color: #0f172a;">{item.get('问题类型')}</span>
                            <span class="badge {badge_c}">置信度: {c_level}</span>
                        </div>
                        <div style="font-size: 13px; color: #475569; margin-bottom: 6px;">
                            <strong>数据证据：</strong> {item.get('关键数据证据')}
                        </div>
                        <div style="font-size: 13px; color: #64748b; margin-bottom: 6px;">
                            <strong>可能原因：</strong> {item.get('可能原因')}
                        </div>
                        <div style="font-size: 13px; color: #047857; background: #ecfdf5; padding: 6px 10px; border-radius: 4px; margin-bottom: 4px;">
                            👉 <strong>建议措施：</strong> {item.get('建议采取的措施')}
                        </div>
                        <div style="font-size: 11px; color: #94a3b8;">
                            预期方向: {item.get('预期改善方向')} | 观察周期: {item.get('建议观察周期')}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.success("🎉 大盘指标稳健，未检测到显著异常问题。")

    st.markdown("---")

    # 3. 策略执行效果追踪与复盘 (Layer 6)
    st.markdown("#### 3. 优化策略执行记录与效果复盘 (Strategy Tracking & Calibration)")
    
    col_t1, col_t2 = st.columns([1.5, 0.5])
    with col_t1:
        st.caption("自动归档 AI 生成的建议动作，比对调整前后的真实转化数据，持续校准模型阈值。")
    with col_t2:
        if st.button("🗑️ 清空追踪历史", key="clear_tracking_btn", use_container_width=True):
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
    else:
        st.info("💡 暂无执行记录。在各业务板块导出决策建议并采纳后，系统将自动录入追踪流水。")
