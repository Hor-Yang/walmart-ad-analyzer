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

from frontend.utils.error_handler import safe_view_render


# // FIX: 全局与模块级异常兜底装饰器，阻断 Traceback 裸露，提供生产级友好提示
@safe_view_render("AI 决策中心")
def render_ai_view():
    # // FIX: 【任务 1】改用 Streamlit 原生安全排版 API，彻底消除 HTML 标签与多行缩进代码块泄露
    st.subheader("AI 决策中心")
    st.caption("跨模块企业级智能中枢：广告×库存×利润多域联动诊断、12 类根因穿透与闭环效果复盘")

    # // FIX: 【任务 3】业务板块逻辑释义 Expander（降低运营人员认知门槛，严格使用纯净文字，无彩色 Emoji）
    with st.expander("[运营逻辑解读] AI 归因诊断、实体溯源与跨域护栏机制", expanded=False):
        st.markdown(
            """
            - **为什么必须明确具体活动与 SKU？**
              在多活动、多变体投放场景中，“泛化报警”（如单纯提示预算不足或投产偏低）无法指导一线实操。本中枢强制将每项诊断强绑定至具体的 **Campaign（广告活动）**、**Ad Group（广告组）**、**Item ID / SKU**，形成「定点定位 → 证据链举证 → 精准执行」的完整决策链路。
            - **广告 × 库存 联动断货保护（DOS Guardrail）**：
              当某个 SKU 在库可用周转天数（DOS）低于 **15 天** 时，出价引擎将强制拦截所有“加预算、提竞价、拓词”的激进建议，自动触发控流与提价控速策略，防止因断货导致权重清零与爆款降权。
            - **广告 × 利润 动态保本止血（Break-even ACoS）**：
              系统基于采购、头程与尾程运费及平台佣金实时计算出 SKU 级保本线。当某个广告活动或关键词实际 ACoS 超过保本红线 5% 以上且无新客价值时，系统自动给出精准下调 20%~30% 竞价或定向否词动作。
            """
        )

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

    # 1. 跨模块联动诊断卡片 (Cross-Module Synergies) - Native 容器呈现
    st.markdown("#### 1. 跨模块联动规则触发状态 (Cross-Module Synergies)")
    s1, s2, s3 = st.columns(3)
    with s1:
        with st.container(border=True):
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.markdown("**广告 × 库存 断货保护联动**")
            with col_h2:
                st.caption("已激活")
            st.caption("规则：可售天数 DOS < 15 天的商品，**强制拦截加价与拓词动作**，避免断货导致权重崩塌。")
    with s2:
        with st.container(border=True):
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.markdown("**广告 × 利润 动态保本止血**")
            with col_h2:
                st.caption("已激活")
            st.caption("规则：实际 ACoS 超过保本线 5% 以上且无新客价值的词/品，**强制降权 15%~25% 止血**。")
    with s3:
        with st.container(border=True):
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.markdown("**决策防冲突与动作去重**")
            with col_h2:
                st.caption("已激活")
            st.caption("规则：同一关键词/商品禁止同时出现“加价”与“暂停/否词”冲突，由决策引擎自动优先级仲裁。")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 2. 12 类专业广告问题深度诊断 (Layer 4)
    st.markdown("#### 2. 十二大核心广告问题根因诊断 (12 Diagnostic Issues)")
    st.caption("每条诊断均严格包含：问题对象定位、问题描述、关键数据证据、可能原因、置信度、建议措施、预期改善方向与观察周期。")

    raw_tables = {
        "campaign": camp_df,
        "search_term": st_df,
        "keyword": kw_df,
        "ad_item": item_df,
        "platform": sec_data.get("platform"),
        "page_type": sec_data.get("page_type"),
        "inventory": sec_data.get("inventory"),
    }
    issues = diagnose_12_advertising_issues(raw_tables, target_acos=0.30, breakeven_acos=0.35)

    if issues:
        st.markdown(f"**共精准识别出 {len(issues)} 项待优化关键问题（已结构化解耦：明确对象、数据事实、原因推断、建议动作、待验证假设）：**")
        i_cols = st.columns(2)
        for idx, item in enumerate(issues[:10]):  # 突出展示 Top 10 问题
            with i_cols[idx % 2]:
                c_level = item.get("原因置信度") or item.get("confidence") or "中"
                # // FIX: 【任务 1 & 任务 2】改用 Native 容器与结构化排版，并前置突出「诊断对象」
                with st.container(border=True):
                    head_col1, head_col2 = st.columns([3, 1])
                    with head_col1:
                        st.markdown(f"**{item.get('问题类型') or item.get('issue_type')}**")
                    with head_col2:
                        st.caption(f"置信度: {c_level}")

                    # // FIX: 【任务 2】实体强绑定（Entity Anchoring）：清晰展示具体是哪一个活动、组或 SKU
                    target_entity = item.get("对象标识") or item.get("entity") or "通用广告大盘"
                    st.info(f"【诊断定位对象】{target_entity}")

                    st.markdown(f"**数据事实：** {item.get('关键数据证据') or item.get('data_evidence')}")
                    st.markdown(f"**原因推断：** {item.get('可能原因') or item.get('root_cause')}")
                    st.success(f"**建议动作：** {item.get('建议采取措施') or item.get('action')}")
                    st.caption(f"待验证假设：预期方向: {item.get('预期改善方向') or item.get('expected_impact')} | 建议观察周期: {item.get('建议观察周期') or item.get('observation_window')}")
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

    # // FIX: 【任务 1】采用 Native st.metric 渲染复盘指标卡，彻底杜绝 HTML 标签外泄
    k_t1, k_t2, k_t3, k_t4 = st.columns(4)
    with k_t1:
        st.metric("累计归档优化动作", f"{summary.get('total_actions', 0)} 条", help="系统自动沉淀落地的全部策略记录")
    with k_t2:
        st.metric("待观察动作", f"{summary.get('pending_actions', 0)} 条", help="当前处于 3~7 天数据观察与复盘期的策略动作")
    with k_t3:
        st.metric("符合预期成功率", f"{summary.get('success_rate_pct', 0.0):.1f}%", help=f"已达标 {summary.get('successful_actions', 0)} 项策略闭环验证")
    with k_t4:
        st.metric("模型规则校准次数", f"{summary.get('rule_calibrations', 0)} 次", help="依据真实回测转化动态微调的算法规则次数")

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
