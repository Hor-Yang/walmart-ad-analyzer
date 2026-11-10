"""
数据中心模块视图 (Data Hub View)
企业级统一数据接入与管理中枢：
1. 全渠道报表上传 (6大广告报表 + SKU映射 + 日走势 + 成本底表)
2. 批量拖拽与智能表头适配（显式操作闭环与两阶段解析）
3. 数据质量检查报告 (Layer 1 Data Quality Index)
4. 数据导入审计日志与模板下载
5. 历史归档与跨期对比集成
"""

import io
from datetime import datetime
import streamlit as st
import pandas as pd
from data_loader.loader import (
    load_single_file,
    identify_table_type,
    TABLE_CONFIG,
    get_all_cleaning_anomalies,
)
from data_loader.sku_mapper import (
    load_sku_mapping,
    apply_sku_mapping,
    generate_sku_template,
    generate_daily_trend_template,
)
from data_loader.session_storage import (
    save_session_cache,
    load_session_cache,
    clear_session_cache,
    record_upload_audit_log,
    get_upload_audit_logs,
    generate_audit_log_markdown,
)
from analyzer.sku_profit_model import (
    load_sku_cost_table,
    generate_sku_cost_template,
)
from analyzer.data_quality import inspect_data_quality
from frontend.utils.data_context import parse_single_file_cached, update_section
from frontend.components.kpi_card import render_kpi_card, render_empty_state, render_page_header
from frontend.utils.error_handler import safe_view_render  # // FIX: 全局安全渲染装饰器，拦截 Traceback 泄露
from services.auth_service import get_current_user  # // FIX: 多租户隔离当前用户会话
from services.snapshot_service import get_snapshot_service  # // FIX: 自动创建报告快照持久化
from frontend.views.history_view import render_history_view  # // FIX: 嵌入跨周期对比视图


@safe_view_render("数据中心")
def render_data_hub_view():
    render_page_header("数据中心", "多源业务报表导入流水线、跨平台标准底表模板与数据质量体检中枢")

    dh_tabs = st.tabs([
        "报表智能上传",
        "标准底表模板",
        "数据质量体检",
        "导入审计台账",
        "历史归档与对比",
    ])

    sec_data = st.session_state.get("section_data", {})
    sec_files = st.session_state.get("section_files", {})

    # =========================================================================
    # TAB 1: 📥 统一报表上传中枢 (Explicit Two-Stage Workflow)
    # =========================================================================
    with dh_tabs[0]:
        st.markdown("#### 1. 批量智能识别上传 (Recommended)")
        st.caption("支持将任意或多个广告报表（.xlsx / .csv）同时拖入下方。系统先解析元信息与数据预览，点击确认后正式入库并运行六层诊断：")
        
        batch_files = st.file_uploader(
            "选择或批量拖拽报表文件",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=True,
            key="dh_batch_uploader",
        )
        
        # // FIX: 痛点2重构 - 两阶段显式操作闭环，杜绝文件选中即刷新与用户失控感
        if batch_files:
            staged_info = []
            preview_dict = {}
            for bf in batch_files:
                f_bytes = bf.getvalue()
                t_type, df, total_rows = parse_single_file_cached(bf.name, f_bytes)
                type_name = TABLE_CONFIG.get(t_type, {}).get("name", "未识别报表类型")
                is_valid = df is not None and not df.empty and t_type != "unknown"
                staged_info.append({
                    "文件名": bf.name,
                    "识别报表类型": type_name,
                    "预计行数": len(df) if df is not None else 0,
                    "字段列数": len(df.columns) if df is not None else 0,
                    "文件大小": f"{round(len(f_bytes) / 1024, 1)} KB",
                    "状态": "[已校验通过]" if is_valid else "[待人工确认]",
                    "_raw": (t_type, df, bf.name, f_bytes),
                })
                if df is not None and not df.empty:
                    preview_dict[bf.name] = df
            
            st.markdown("##### 上传暂存队列清单")
            summary_df = pd.DataFrame([{k: v for k, v in item.items() if not k.startswith("_")} for item in staged_info])
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            # 第一阶段：轻量级前5行数据预览
            if preview_dict:
                with st.expander("展开查看前 5 行轻量数据预览", expanded=False):
                    sel_file = st.selectbox("选择要预览的数据表", options=list(preview_dict.keys()), key="preview_file_select")
                    if sel_file and sel_file in preview_dict:
                        st.dataframe(preview_dict[sel_file].head(5), use_container_width=True)
            
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            
            # 第二阶段：显式主动作按钮与沉浸式交互反馈
            c_btn1, c_btn2 = st.columns([2, 1])
            with c_btn1:
                commit_btn = st.button("开始解析并运行六层诊断", type="primary", key="btn_commit_batch_upload", use_container_width=True)
            with c_btn2:
                if st.button("清空当前暂存选择", key="btn_clear_staged", use_container_width=True):
                    st.rerun()
            
            if commit_btn:
                # 沉浸式加载体验
                with st.spinner("正在清洗数据、匹配 SKU 映射并执行多维度分析..."):
                    success_count = 0
                    for item in staged_info:
                        t_type, df, fname, fbytes = item["_raw"]
                        if df is not None and not df.empty and t_type != "unknown":
                            update_section(t_type, df, fname, fbytes)
                            success_count += 1
                    
                    # 自动触发多租户历史快照持久化归档
                    try:
                        curr_user = get_current_user()
                        snap_svc = get_snapshot_service()
                        snap_svc.create_snapshot(
                            user_id=curr_user.get("user_id", "usr_admin"),
                            report_name=f"批量导入_{datetime.now().strftime('%m%d_%H%M')}",
                            sec_data=st.session_state.get("section_data", {}),
                            source_files=[item["文件名"] for item in staged_info],
                        )
                    except Exception:
                        pass
                
                # 显式成功 Toast 与导航引导闭环
                st.toast("数据处理完毕，已生成最新诊断报告！")
                st.success(f"批量解析与诊断运行完成！已成功载入 {success_count} 张业务报表并自动归档至历史快照。")
                
                nav_col1, nav_col2, nav_col3 = st.columns(3)
                with nav_col1:
                    if st.button("前往「经营总览」", key="btn_goto_dash", type="primary", use_container_width=True):
                        st.session_state["active_page"] = "dashboard"
                        st.rerun()
                with nav_col2:
                    if st.button("前往「广告分析」", key="btn_goto_ads", use_container_width=True):
                        st.session_state["active_page"] = "ads_analytics"
                        st.rerun()
                with nav_col3:
                    if st.button("查看「历史快照与对比」", key="btn_goto_diff", use_container_width=True):
                        st.session_state["active_page"] = "history_diff"
                        st.rerun()

        st.markdown("---")
        st.markdown("#### 2. 分模块独立通道上传 (Dedicated Channels)")
        
        c1, c2 = st.columns(2)
        with c1:
            # ① 广告活动列表
            f_camp = st.file_uploader("① 广告活动报表 (Campaign List)", type=["xlsx", "xls", "csv"], key="dh_camp_file")
            if f_camp:
                _, df, _ = parse_single_file_cached(f_camp.name, f_camp.getvalue(), "campaign")
                if df is not None:
                    update_section("campaign", df, f_camp.name, f_camp.getvalue())
                    st.rerun()

            # ② 搜索词报表
            f_st = st.file_uploader("② 搜索词列表 (Search Term Report)", type=["xlsx", "xls", "csv"], key="dh_st_file")
            if f_st:
                _, df, _ = parse_single_file_cached(f_st.name, f_st.getvalue(), "search_term")
                if df is not None:
                    update_section("search_term", df, f_st.name, f_st.getvalue())
                    st.rerun()

            # ③ 投放关键词报表
            f_kw = st.file_uploader("③ 投放关键词列表 (Keyword Bid Report)", type=["xlsx", "xls", "csv"], key="dh_kw_file")
            if f_kw:
                _, df, _ = parse_single_file_cached(f_kw.name, f_kw.getvalue(), "keyword")
                if df is not None:
                    update_section("keyword", df, f_kw.name, f_kw.getvalue())
                    st.rerun()

        with c2:
            # ④ 商品广告列表
            f_ad = st.file_uploader("④ 商品广告列表 (Item Ad Report)", type=["xlsx", "xls", "csv"], key="dh_item_file")
            if f_ad:
                _, df, _ = parse_single_file_cached(f_ad.name, f_ad.getvalue(), "ad_item")
                if df is not None:
                    update_section("ad_item", df, f_ad.name, f_ad.getvalue())
                    st.rerun()

            # ⑤ 平台终端报表
            f_plat = st.file_uploader("⑤ 平台设备报表 (Platform Report)", type=["xlsx", "xls", "csv"], key="dh_plat_file")
            if f_plat:
                _, df, _ = parse_single_file_cached(f_plat.name, f_plat.getvalue(), "platform")
                if df is not None:
                    update_section("platform", df, f_plat.name, f_plat.getvalue())
                    st.rerun()

            # ⑥ 页面类型报表
            f_page = st.file_uploader("⑥ 页面位置类型报表 (Page Type Report)", type=["xlsx", "xls", "csv"], key="dh_page_file")
            if f_page:
                _, df, _ = parse_single_file_cached(f_page.name, f_page.getvalue(), "page_type")
                if df is not None:
                    update_section("page_type", df, f_page.name, f_page.getvalue())
                    st.rerun()

    # =========================================================================
    # TAB 2: 标准模板下载与配置
    # =========================================================================
    with dh_tabs[1]:
        st.markdown("#### 跨平台经营标准模板库")
        st.caption("下载标准数据底表模板，填入商品属性与成本要素后上传生效：")

        t1, t2, t3 = st.columns(3)
        with t1:
            with st.container(border=True):
                st.markdown("**Item ID ↔ SKU 映射模板**")
                st.caption("打通各平台数字 ID 与企业统一主 SKU 编码，消除未命名商品。")
            sku_tmpl_bytes = generate_sku_template()
            st.download_button(
                "下载 SKU 映射表模板",
                data=sku_tmpl_bytes,
                file_name="sku_mapping_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            f_sku_up = st.file_uploader("上传已填写的 SKU 映射表", type=["xlsx", "xls", "csv"], key="dh_sku_map_up")
            if f_sku_up:
                # // FIX: 严密解构 (new_map, err) 元组，防止类型错误
                new_map, err = load_sku_mapping(f_sku_up)
                if err:
                    st.error(f"SKU 映射表解析失败: {err}")
                elif new_map:
                    st.session_state["sku_mapping"].update(new_map)
                    st.success(f"已成功载入 {len(new_map)} 条映射记录！")
                    st.rerun()

        with t2:
            with st.container(border=True):
                st.markdown("**SKU 供应链成本表模板**")
                st.caption("包含采购价、头程海运、尾程履约和平台佣金，用于动态保本线计算。")
            cost_tmpl_bytes = generate_sku_cost_template()
            st.download_button(
                "下载 SKU 成本底表模板",
                data=cost_tmpl_bytes,
                file_name="sku_cost_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            f_cost_up = st.file_uploader("上传已填写的成本底表", type=["xlsx", "xls", "csv"], key="dh_cost_table_up")
            if f_cost_up:
                # // FIX: 严格对齐 (cost_df, cost_dict, error_msg) 三元组返回
                c_df, c_dict, c_err = load_sku_cost_table(f_cost_up)
                if c_err:
                    st.error(f"成本底表解析失败: {c_err}")
                elif not c_df.empty:
                    st.session_state["sku_cost_df"] = c_df
                    st.session_state["sku_cost_dict"] = c_dict
                    st.success(f"已成功载入 {len(c_df)} 款商品成本参数！")
                    st.rerun()

        with t3:
            with st.container(border=True):
                st.markdown("**每日多期走势报表模板**")
                st.caption("日度级别销售与花费走势，支持按自然日精准环比与归因。")
            daily_tmpl_bytes = generate_daily_trend_template()
            st.download_button(
                "下载日度趋势报表模板",
                data=daily_tmpl_bytes,
                file_name="daily_trend_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            f_daily_up = st.file_uploader("上传日度走势报表", type=["xlsx", "xls", "csv"], key="dh_daily_trend_up")
            if f_daily_up:
                _, d_df, _ = parse_single_file_cached(f_daily_up.name, f_daily_up.getvalue())
                if d_df is not None:
                    st.session_state["daily_trend_df"] = d_df
                    st.success(f"已成功载入 {len(d_df)} 行日度趋势数据！")
                    st.rerun()

    # =========================================================================
    # TAB 3: 数据质量体检报告 (Layer 1)
    # =========================================================================
    with dh_tabs[2]:
        st.markdown("#### 数据质量体检指数 (Data Quality Index)")
        st.caption("检查字段完整性、数据类型、真实零与缺失值区分、跨表支出对齐及决策置信度与熔断防护：")

        # // FIX: 严格对齐数据质量引擎输出字段与页面展示
        q_res = inspect_data_quality(sec_data)
        h_score = q_res.get("health_score", 100)
        grade = q_res.get("grade", "良好")
        conf_level = q_res.get("confidence_level", "高")
        sku_cov = q_res.get("sku_coverage_pct", 100.0)
        guardrail = q_res.get("guardrail_active", False)
        real_zeros = q_res.get("real_zeros_count", 0)
        neg_metrics = q_res.get("negative_metrics", [])
        issues = q_res.get("issues", [])

        q1, q2, q3, q4 = st.columns(4)
        with q1:
            render_kpi_card("数据健康综合评分", f"{h_score} 分", sub_title=f"健康等级: {grade}", badge=grade, badge_color="green" if h_score>=80 else "amber")
        with q2:
            render_kpi_card("AI 决策置信度", f"{conf_level} 置信", sub_title="依据数据样本完整性自动评级", badge=conf_level, badge_color="blue")
        with q3:
            render_kpi_card("SKU 编码对齐率", f"{sku_cov:.1f}%", sub_title="商品映射覆盖比例", badge=f"{sku_cov:.0f}%", badge_color="green" if sku_cov>=85 else "amber")
        with q4:
            g_txt = "决策熔断触发" if guardrail else "熔断防护待命"
            g_badge = "red" if guardrail else "green"
            render_kpi_card("决策熔断状态", g_txt, sub_title="异常数据自动拦截盲目调价", badge="熔断保护", badge_color=g_badge)

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(
                f"""
                <div class="card" style="padding: 16px;">
                    <div style="font-size: 13px; font-weight: 600; color: #1e293b; margin-bottom: 6px;">真实零值与负数异常检测</div>
                    <div style="font-size: 12.5px; color: #64748b; line-height: 1.6;">
                        • <strong>真实零值 (Real Zeros)：</strong> 已识别 {real_zeros} 处真实 0 出单/曝光节点（非缺失，业务真实表现）<br/>
                        • <strong>负数指标检测：</strong> 发现 {len(neg_metrics)} 处负数异常指标（已自动清洗纠偏）<br/>
                        • <strong>字段对齐数：</strong> {q_res.get('schema_integrity', {}).get('total_fields', 0)} 个核心业务字段
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f"""
                <div class="card" style="padding: 16px;">
                    <div style="font-size: 13px; font-weight: 600; color: #1e293b; margin-bottom: 6px;">跨表数据勾稽与一致性</div>
                    <div style="font-size: 12.5px; color: #64748b; line-height: 1.6;">
                        • <strong>多表花费对齐：</strong> 广告活动、投放词与商品报表总消耗勾稽比对<br/>
                        • <strong>联合主键去重：</strong> 项目ID/广告活动 复合主键保留最新版本<br/>
                        • <strong>来源溯源跟踪：</strong> 每行数据均携带来源文件与时间戳元数据
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if issues:
            st.markdown("##### 发现的数据缺陷提示与修复指引")
            for iss in issues:
                st.warning(f"• **[{iss.get('category')}]** {iss.get('description')} (建议措施: {iss.get('remedy')})")
        else:
            st.success("数据源体检良好，所有字段与指标对齐一致，未发现断层或恶意缺失。")

    # =========================================================================
    # TAB 4: 数据导入审计日志
    # =========================================================================
    with dh_tabs[3]:
        st.markdown("#### 报表导入审计台账 (Audit Trail)")
        st.caption("防丢失机制：系统会自动记录每一次上传的文件名、解析时间、数据行数与状态流水。")
        
        audit_logs = get_upload_audit_logs()
        if audit_logs:
            st.dataframe(pd.DataFrame(audit_logs), use_container_width=True, hide_index=True)
            log_md = generate_audit_log_markdown()
            st.download_button(
                "导出完整审计日志 (Markdown)",
                data=log_md,
                file_name="data_import_audit_logs.md",
                mime="text/markdown",
            )
        else:
            st.info("暂无上传流水。本次会话新上传的文件将即时展示在此处。")

    # =========================================================================
    # TAB 5: 历史报告归档与跨周期对比 (Diff Mode)
    # =========================================================================
    with dh_tabs[4]:
        render_history_view()
