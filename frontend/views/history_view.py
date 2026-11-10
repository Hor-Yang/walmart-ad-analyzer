"""
CrossBorder BI · 历史分析与跨周期对比视图 (History Snapshots & Diff View)
遵循规范：
1. 历史报告归档：随时一键载入回放历史某一期的完整诊断面板
2. 双期对比 (Diff Mode)：自动对比两个历史批次，计算并高亮核心指标环比升降、问题词减少量与治愈的亏损 SKU
3. Apple macOS 统一设计系统规范：纯净单色图标、16px 圆角白底卡片、呼吸感留白
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any
from frontend.components.kpi_card import render_apple_kpi_card, render_kpi_card, render_empty_state, render_page_header
from frontend.utils.error_handler import safe_view_render
from services.auth_service import get_current_user
from services.snapshot_service import get_snapshot_service


@safe_view_render("历史对比")
def render_history_view():
    render_page_header("历史分析与跨周期对比", "多期报表快照回溯归档、双期 (Diff Mode) 环比变化、治愈 SKU 与止血效果复盘")

    user = get_current_user()
    user_id = user.get("user_id", "usr_admin")
    snap_svc = get_snapshot_service()

    hist_tabs = st.tabs(["历史快照档案库", "双期跨周期对比 (Diff Mode)"])

    # =========================================================================
    # TAB 1: 历史快照档案库
    # =========================================================================
    with hist_tabs[0]:
        snapshots = snap_svc.list_snapshots(user_id=user_id)

        # 顶部操作栏：保存当前工作台快照
        top_c1, top_c2 = st.columns([2, 1])
        with top_c1:
            st.markdown("#### 历史快照档案列表")
            st.caption("每次完成报表批量导入与诊断后，系统会自动归档快照；您也可以随时保存当前分析快照。")
        with top_c2:
            with st.popover("归档当前工作台快照", use_container_width=True):
                custom_name = st.text_input("快照名称", value=f"沃尔玛分析快照_{pd.Timestamp.now().strftime('%m%d_%H%M')}")
                if st.button("确认保存", type="primary", use_container_width=True):
                    sec_data = st.session_state.get("section_data", {})
                    if any(v is not None and not v.empty for v in sec_data.values() if isinstance(v, pd.DataFrame)):
                        try:
                            from analyzer.metrics import summarize_overview
                            ov = summarize_overview(sec_data)
                        except Exception:
                            ov = {}
                        
                        action_df = None
                        try:
                            from analyzer.action_items import build_action_items
                            action_df, _, _ = build_action_items(sec_data)
                        except Exception:
                            pass

                        new_id = snap_svc.create_snapshot(
                            user_id=user_id,
                            report_name=custom_name,
                            sec_data=sec_data,
                            overview=ov,
                            action_df=action_df,
                            source_files=list(st.session_state.get("section_files", {}).values()),
                        )
                        st.toast("快照保存成功！已归档至个人档案库")
                        st.rerun()
                    else:
                        st.warning("当前工作台无有效数据，请先上传报表后再归档。")

        if not snapshots:
            render_empty_state(
                title="暂无历史快照记录",
                description="系统尚未归档任何分析快照。请前往「数据中心」上传首份业务报表并点击「开始解析并运行六层诊断」，系统将自动为您生成首期分析快照。",
                icon_type="database",
                action_label="前往数据中心上传数据",
                action_key="hist_empty_to_dh_btn",
            )
            if st.session_state.get("hist_empty_to_dh_btn"):
                st.session_state["active_page"] = "data_hub"
                st.rerun()
            return

        # 展示历史快照表格
        snap_df = pd.DataFrame(snapshots)
        display_df = snap_df[[
            "snapshot_id", "report_name", "created_at", "total_spend", "total_sales", "roas", "acos", "total_orders", "issues_count", "p0_count"
        ]].copy()
        display_df["roas"] = display_df["roas"].apply(lambda x: f"{float(x):.2f}x")
        display_df["acos"] = display_df["acos"].apply(lambda x: f"{float(x)*100.0:.1f}%")

        st.dataframe(
            display_df,
            column_config={
                "snapshot_id": st.column_config.TextColumn("快照编号", width="small"),
                "report_name": st.column_config.TextColumn("报告名称", width="medium"),
                "created_at": st.column_config.TextColumn("归档时间", width="medium"),
                "total_spend": st.column_config.NumberColumn("广告花费", format="$%.2f"),
                "total_sales": st.column_config.NumberColumn("销售额", format="$%.2f"),
                "roas": st.column_config.TextColumn("ROAS"),
                "acos": st.column_config.TextColumn("ACoS"),
                "total_orders": st.column_config.NumberColumn("订单量", format="%d"),
                "issues_count": st.column_config.NumberColumn("诊断问题数", format="%d"),
                "p0_count": st.column_config.NumberColumn("P0 紧急项", format="%d"),
            },
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # 快捷管理与回放操作区
        st.markdown("##### 快照详情查看与一键载入")
        op_col1, op_col2, op_col3 = st.columns([1.5, 0.8, 0.8])
        
        snap_options = {s["snapshot_id"]: f"{s['report_name']} ({s['created_at']})" for s in snapshots}
        with op_col1:
            sel_snap_id = st.selectbox("选择目标快照", list(snap_options.keys()), format_func=lambda k: snap_options[k], key="sel_snap_manage")
        
        with op_col2:
            st.write("")
            st.write("")
            if st.button("一键载入到工作台", type="primary", use_container_width=True, key="btn_load_snap"):
                snap_data = snap_svc.get_snapshot(sel_snap_id)
                if snap_data:
                    # 将快照指标回填到当前会话中
                    m = snap_data.get("metrics", {})
                    st.session_state["snapshot_active_preview"] = snap_data
                    st.toast(f"已成功载入快照：{snap_data.get('report_name')}！正在跳转经营总览...")
                    st.session_state["active_page"] = "dashboard"
                    st.rerun()

        with op_col3:
            st.write("")
            st.write("")
            if st.button("删除此快照", use_container_width=True, key="btn_del_snap"):
                snap_svc.delete_snapshot(sel_snap_id, user_id=user_id)
                st.toast("已安全删除该快照记录！")
                st.rerun()

    # =========================================================================
    # TAB 2: 双期跨周期对比 (Diff Mode)
    # =========================================================================
    with hist_tabs[1]:
        st.markdown("#### 双期对比与调优效果评估 (Diff Mode)")
        st.caption("选择历史基准期（如上周/优化前）与对比期（如本周/优化后），系统自动穿透环比变化、治愈 SKU 与止血成效：")

        if len(snapshots) < 2:
            st.info("[提示] 双期对比需要至少归档 2 期历史快照。当前仅有 1 期记录，请在下次更新报表后再进行对比。")
            return

        c_sel1, c_sel2 = st.columns(2)
        snap_opts = {s["snapshot_id"]: f"{s['report_name']} ({s['created_at']}) - Spend: ${s['total_spend']:,.0f}" for s in snapshots}
        snap_keys = list(snap_opts.keys())

        with c_sel1:
            snap_a = st.selectbox("基准期 (Period A - 调优前/基准期)", snap_keys, index=1 if len(snap_keys) > 1 else 0, format_func=lambda k: snap_opts[k], key="diff_snap_a")
        with c_sel2:
            snap_b = st.selectbox("对比期 (Period B - 调优后/新批次)", snap_keys, index=0, format_func=lambda k: snap_opts[k], key="diff_snap_b")

        if snap_a == snap_b:
            st.warning("[提示] 请选择两个不同的历史快照期次进行环比差异比对。")
            return

        diff_res = snap_svc.compare_snapshots(snap_a, snap_b)
        if "error" in diff_res:
            st.error(diff_res["error"])
            return

        deltas = diff_res["deltas"]
        pA = diff_res["period_a"]
        pB = diff_res["period_b"]

        # 1. 核心环比 KPI 卡片 (Apple 规范)
        k1, k2, k3, k4 = st.columns(4)

        with k1:
            sp_delta = deltas["spend_diff"]
            sp_badge = f"{deltas['spend_pct']:+.1f}%"
            sp_type = "green" if sp_delta <= 0 else "gray"  # 花费降低通常说明控本有效
            render_apple_kpi_card(
                label="广告花费环比差额",
                value=f"${sp_delta:+,.2f}",
                badge=sp_badge,
                badge_type=sp_type,
                sub_title=f"基准期 ${pA['spend']:,.0f} → 对比期 ${pB['spend']:,.0f}",
            )

        with k2:
            sl_delta = deltas["sales_diff"]
            sl_badge = f"{deltas['sales_pct']:+.1f}%"
            sl_type = "green" if sl_delta >= 0 else "red"
            render_apple_kpi_card(
                label="销售额环比变动",
                value=f"${sl_delta:+,.2f}",
                badge=sl_badge,
                badge_type=sl_type,
                sub_title=f"基准期 ${pA['sales']:,.0f} → 对比期 ${pB['sales']:,.0f}",
            )

        with k3:
            r_delta = deltas["roas_diff"]
            r_badge = f"{r_delta:+.2f}x"
            r_type = "green" if r_delta >= 0 else "red"
            render_apple_kpi_card(
                label="ROAS 净改善提升",
                value=f"{r_delta:+.2f}x",
                badge=r_badge,
                badge_type=r_type,
                sub_title=f"投产比 {pA['roas']:.2f}x → {pB['roas']:.2f}x",
            )

        with k4:
            iss_red = deltas["issues_reduced"]
            iss_badge = f"解决 {iss_red} 项" if iss_red > 0 else "无新增"
            iss_type = "green" if iss_red > 0 else "gray"
            render_apple_kpi_card(
                label="诊断痛点优化净减少",
                value=f"{iss_red} 项痛点",
                badge=iss_badge,
                badge_type=iss_type,
                sub_title=f"问题实体 {pA['issues']} 项 → {pB['issues']} 项",
            )

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # 2. // FIX: 【任务 1】改用 Native st.container 容器与纯净标题，彻底杜绝 HTML 标签外泄与代码泄漏
        cured_c1, cured_c2 = st.columns(2)
        with cured_c1:
            c_count = deltas["cured_skus_count"]
            with st.container(border=True):
                head1, head2 = st.columns([3, 1])
                with head1:
                    st.markdown("**成功止血与治愈 SKU**")
                with head2:
                    st.caption(f"{c_count} 款已治愈")
                st.caption("在基准期处于严重失血/保本击穿，但在新批次中投产比明显回升或无效消耗得到有效遏制的商品：")
                cured_text = ", ".join(deltas["cured_skus"]) if deltas["cured_skus"] else "暂无严重失血商品（前期运营较稳健）"
                st.success(cured_text)

        with cured_c2:
            d_count = deltas["deteriorated_count"]
            with st.container(border=True):
                head1, head2 = st.columns([3, 1])
                with head1:
                    st.markdown("**需关注的新增恶化 SKU**")
                with head2:
                    st.caption(f"{d_count} 款需排查")
                st.caption("在基准期健康，但在对比期因出价过高或转化受阻导致失血的商品：")
                deteriorated_text = ", ".join(deltas["deteriorated_skus"]) if deltas["deteriorated_skus"] else "未发现恶化商品，大盘表现平稳"
                if d_count > 0:
                    st.error(deteriorated_text)
                else:
                    st.success(deteriorated_text)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # 3. SKU 颗粒度双期明细对比表
        st.markdown("##### 商品级双期表现明细对比 (SKU Diff Table)")
        diff_df = diff_res.get("sku_diff_df", pd.DataFrame())
        if not diff_df.empty:
            st.dataframe(diff_df, use_container_width=True, hide_index=True)
        else:
            st.caption("两期快照中未检测到重叠的商品广告明细数据。")
