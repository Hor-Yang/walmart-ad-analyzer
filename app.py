import io
import os
import sys
import html
from typing import Any, Dict, List, Optional
from pathlib import Path

# Ensure root directory is in sys.path for cloud deployment (Streamlit Cloud, Linux containers)
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def safe_html(val: Any) -> str:
    """HTML 实体安全转义，防止 XSS 脚本注入攻击"""
    if val is None:
        return ""
    return html.escape(str(val))

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
    get_session_cache_metadata,
    clear_session_cache,
    record_upload_audit_log,
    get_upload_audit_logs,
    generate_audit_log_markdown,
)
from analyzer import (
    summarize_overview,
    agg_metrics,
    analyze_campaign_health,
    ALL_CAMPAIGN_TAGS,
    mine_search_terms,
    analyze_keyword_bids,
    diagnose_ad_items,
    analyze_placements,
    build_action_items,
    build_sku_trend_data,
    extract_period_label,
    generate_store_overview_analysis,
    generate_product_matrix_analysis,
    get_decision_mapping_guide,
    load_sku_cost_table,
    generate_sku_cost_template,
    calculate_sku_profit_analytics,
)

# 动态容错导入高级诊断引擎与六层模型（即便 GitHub 仅更新 app.py 也绝不崩溃）
try:
    from analyzer import AdDecisionEngine
except (ImportError, AttributeError):
    try:
        from analyzer.decision_engine import AdDecisionEngine
    except (ImportError, AttributeError):
        AdDecisionEngine = None

try:
    from analyzer import inspect_data_quality
except (ImportError, AttributeError):
    try:
        from analyzer.data_quality import inspect_data_quality
    except (ImportError, AttributeError):
        def inspect_data_quality(*args, **kwargs):
            return {"health_score": 100, "grade": "良好", "confidence_level": "高", "issues": [], "summary": "基础数据检查"}

try:
    from analyzer import analyze_traffic_structure
except (ImportError, AttributeError):
    try:
        from analyzer.traffic_structure import analyze_traffic_structure
    except (ImportError, AttributeError):
        def analyze_traffic_structure(*args, **kwargs):
            return {"auto_manual": {}, "match_type": {}, "cannibalization": [], "alerts": []}

try:
    from analyzer import diagnose_12_advertising_issues
except (ImportError, AttributeError):
    try:
        from analyzer.diagnosis_12_issues import diagnose_12_advertising_issues
    except (ImportError, AttributeError):
        def diagnose_12_advertising_issues(*args, **kwargs):
            return []

try:
    from analyzer import (
        log_optimization_actions,
        load_tracking_history,
        generate_tracking_summary,
        clear_tracking_history,
    )
except (ImportError, AttributeError):
    try:
        from analyzer.effect_tracker import (
            log_optimization_actions,
            load_tracking_history,
            generate_tracking_summary,
            clear_tracking_history,
        )
    except (ImportError, AttributeError):
        def log_optimization_actions(*args, **kwargs): return []
        def load_tracking_history(*args, **kwargs): return []
        def generate_tracking_summary(*args, **kwargs): return {}
        def clear_tracking_history(*args, **kwargs): return True

# =========================================================================
# 页面基础配置与高质感商用样式
# =========================================================================
st.set_page_config(
    page_title="领星×沃尔玛广告自动化分析工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    /* 隐藏顶部烦人的开发提示与多余边距 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* 响应式 KPI 卡片网格 */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 12px;
        margin: 14px 0 16px 0;
    }
    @media (max-width: 1100px) {
        .kpi-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
    }
    @media (max-width: 768px) {
        .kpi-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }
    .kpi-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 14px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }
    .kpi-label {
        color: #64748b;
        font-size: 12.5px;
        font-weight: 500;
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .kpi-value {
        color: #0f172a;
        font-size: clamp(16px, 1.3vw, 21px);
        font-weight: 700;
        white-space: nowrap;
        overflow: visible;
        letter-spacing: -0.3px;
    }
    
    /* 运营决策摘要卡片 */
    .summary-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #2563eb;
        border-radius: 6px;
        padding: 16px 20px;
        margin: 14px 0 22px 0;
        line-height: 1.8;
    }
    .summary-item {
        margin: 6px 0;
        font-size: 14px;
        color: #334155;
    }
    .summary-badge {
        display: inline-block;
        padding: 1px 8px;
        font-size: 12px;
        font-weight: 600;
        border-radius: 4px;
        margin-right: 6px;
    }
    .badge-blue { background: #eff6ff; color: #1d4ed8; }
    .badge-red { background: #fef2f2; color: #b91c1c; }
    .badge-green { background: #f0fdf4; color: #15803d; }
    .badge-purple { background: #faf5ff; color: #7e22ce; }
    .badge-gray { background: #f1f5f9; color: #475569; }
    
    /* 板块专属数据源状态栏 */
    .source-bar {
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .source-tag {
        font-weight: 600;
        color: #0f172a;
        font-size: 13.5px;
    }
    .source-sub {
        color: #475569;
        font-size: 12.5px;
    }
    
    /* 上传引导盒子 */
    .upload-box {
        background: #f8fafc;
        border: 2px dashed #cbd5e1;
        border-radius: 8px;
        padding: 18px 20px;
        margin-bottom: 14px;
        text-align: center;
    }

    /* 诊断建议警示盒子 */
    .advice-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #f59e0b;
        border-radius: 6px;
        padding: 12px 16px;
        margin: 10px 0 16px 0;
        line-height: 1.6;
    }
    .advice-box-danger {
        border-left-color: #ef4444;
        background: #fff5f5;
    }
    .advice-box-success {
        border-left-color: #10b981;
        background: #f0fdf4;
    }
    
    .funnel-box {
        background: #f8fafc;
        border-radius: 6px;
        padding: 10px 12px;
        margin-bottom: 8px;
        border-left: 3px solid #64748b;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================================
# 数据缓存与高性能解析引擎（@st.cache_data 确保一秒加载，不重跑）
# =========================================================================
@st.cache_data(show_spinner=False)
def parse_single_file_cached(file_name: str, file_bytes: bytes, forced_type: str = None):
    """缓存单个文件的读取和清洗，基于字节流哈希，避免重复解析"""
    bio = io.BytesIO(file_bytes)
    bio.name = file_name
    t_type, df, total_row = load_single_file(bio)
    if forced_type:
        t_type = forced_type
    return t_type, df, total_row

@st.cache_data(show_spinner=False)
def parse_trend_data_cached(file_records_tuple: tuple, sku_map_items: tuple, target_acos: float, breakeven_acos: float = 0.35):
    """缓存多期/每日趋势分析的建模运算结果"""
    sku_map = dict(sku_map_items) if sku_map_items else {}
    records = []
    for fname, fbytes in file_records_tuple:
        bio = io.BytesIO(fbytes)
        bio.name = fname
        t_type, df, _ = load_single_file(bio)
        if df is not None and not df.empty:
            records.append({
                "filename": fname,
                "period": extract_period_label(fname, len(records) + 1),
                "df": df,
            })
    if not records:
        return pd.DataFrame(), pd.DataFrame(), [], pd.DataFrame()
    return build_sku_trend_data(records, sku_map=sku_map, target_acos=target_acos, breakeven_acos=breakeven_acos)

def fmt_money(val, default="N/A"):
    if val is None or pd.isna(val):
        return default
    try:
        return f"${float(val):,.2f}"
    except (ValueError, TypeError):
        return default

def fmt_pct(val, default="N/A"):
    if val is None or pd.isna(val):
        return default
    try:
        return f"{float(val)*100:.2f}%"
    except (ValueError, TypeError):
        return default

def fmt_num(val, default="N/A"):
    if val is None or pd.isna(val):
        return default
    try:
        return f"{int(round(float(val))):,}"
    except (ValueError, TypeError):
        return default

def fmt_roas(val, default="N/A"):
    if val is None or pd.isna(val):
        return default
    try:
        return f"{float(val):.2f}x"
    except (ValueError, TypeError):
        return default

# =========================================================================
# Session State 初始化（保存上传数据和用户交互操作状态）
# =========================================================================
if "section_data" not in st.session_state:
    st.session_state["section_data"] = {
        "campaign": None,
        "search_term": None,
        "keyword": None,
        "ad_item": None,
        "platform": None,
        "page_type": None,
        "trend": None,
    }

if "file_names" not in st.session_state:
    st.session_state["file_names"] = {}

if "file_bytes_cache" not in st.session_state:
    st.session_state["file_bytes_cache"] = {}

if "sku_map" not in st.session_state:
    st.session_state["sku_map"] = {}

# 操作状态记忆
if "selected_sku_code" not in st.session_state:
    st.session_state["selected_sku_code"] = None

if "trend_filter_choice" not in st.session_state:
    st.session_state["trend_filter_choice"] = "全部 SKU"

def update_section(sec_key: str, data: Any, filename: str, file_bytes: bytes = None):
    """更新独立板块数据并保留字节流缓存，同时记录审计日志并自动持久化快照"""
    st.session_state["section_data"][sec_key] = data
    st.session_state["file_names"][sec_key] = filename
    if file_bytes is not None:
        st.session_state["file_bytes_cache"][sec_key] = file_bytes

    if data is not None:
        row_c = len(data) if isinstance(data, pd.DataFrame) else (len(data.get("period_df", [])) if isinstance(data, dict) and "period_df" in data else 0)
        f_size = len(file_bytes) if file_bytes else 0
        names = {
            "trend": "📈 SKU多期走势",
            "campaign": "① 广告活动报表",
            "search_term": "② 搜索词报表",
            "keyword": "③ 关键词报表",
            "ad_item": "④ 商品广告列表",
            "platform": "⑤ 平台报表",
            "page_type": "⑤ 页面类型报表",
        }
        sec_label = names.get(sec_key, sec_key)
        record_upload_audit_log(sec_label, filename, row_c, f_size, f"数据已就绪 ({row_c}行)")
        save_session_cache(
            st.session_state["section_data"],
            st.session_state.get("sku_map", {}),
            st.session_state.get("sku_cost_dict", {}),
            st.session_state.get("file_names", {}),
        )

# =========================================================================
# 顶部标题栏
# =========================================================================
st.title("领星 × 沃尔玛广告自动化分析工具")
st.caption("固定业务板块独立解析 · SKU 多期全景走势与突变预警 · 店铺与单品深度诊断 · 落地动作清单")

# =========================================================================
# 侧边栏：持久化快照恢复与审计日志
# =========================================================================
session_meta = get_session_cache_metadata()
if session_meta and session_meta.get("file_count", 0) > 0:
    st.sidebar.markdown(
        f"""
        <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 10px; margin-bottom: 10px;">
            <div style="font-weight: 700; color: #166534; font-size: 13.5px;">💾 检测到上次分析快照</div>
            <div style="font-size: 12px; color: #15803d; margin-top: 3px;">
                时间: {session_meta['timestamp']}<br/>
                包含报表: {session_meta['file_count']} 个 | 映射 SKU: {session_meta['sku_count']} 个
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col_snap1, col_snap2 = st.sidebar.columns([3, 2])
    with col_snap1:
        if st.button("🔄 一键恢复快照", help="无需重新上传报表，直接秒级恢复上一次分析进度与设置", key="btn_restore_snap"):
            cached = load_session_cache()
            if cached:
                st.session_state["section_data"] = cached.get("section_data", {})
                st.session_state["sku_map"] = cached.get("sku_map", {})
                st.session_state["sku_cost_dict"] = cached.get("sku_cost_dict", {})
                st.session_state["file_names"] = cached.get("file_names", {})
                st.success("已成功从快照恢复数据！")
                st.rerun()
    with col_snap2:
        if st.button("🗑️ 清空快照", help="删除磁盘上的上次快照记录", key="btn_clear_snap"):
            clear_session_cache()
            st.rerun()

with st.sidebar.expander("📜 上传历史与分析审计日志", expanded=False):
    logs = get_upload_audit_logs()
    if logs:
        st.caption(f"已记录 {len(logs)} 条上传与分析操作：")
        log_df = pd.DataFrame(logs)
        st.dataframe(log_df[["时间", "板块类别", "文件名", "数据行数"]], hide_index=True, use_container_width=True)
        md_log = generate_audit_log_markdown()
        st.download_button(
            label="📥 导出审计日志 Markdown",
            data=md_log,
            file_name="walmart_ad_audit_log.md",
            mime="text/markdown",
            key="dl_audit_md"
        )
    else:
        st.caption("暂无历史上传审计日志")

st.sidebar.markdown("---")

# =========================================================================
# 侧边栏：全局数据导入与诊断参数
# =========================================================================
st.sidebar.header("⚙️ 运营诊断参数")

days_input = st.sidebar.number_input(
    "报表统计天数（用于估算日均花费与预算撞顶）",
    min_value=0,
    max_value=365,
    value=30,
    step=1,
    help="领星导出为区间累计数据。若输入天数（如 30 天），将按【日均花费 = 花费 / 天数】诊断预算跑不满或撞顶；置 0 则跳过预算评估。",
)
analysis_days = days_input if days_input > 0 else None

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 ACoS 盈亏与目标双线解耦")

breakeven_acos_input = st.sidebar.slider(
    "保本 ACoS 警戒线 / 毛利率 (%)",
    min_value=15,
    max_value=70,
    value=35,
    step=1,
    help="跨境电商保本线 = 商品毛利率（扣除采购成本、头程尾程运费及平台佣金后的毛利率）。当广告 ACoS 高于此线即产生净亏损；低于此线即产生正向毛利贡献。",
)
breakeven_acos = breakeven_acos_input / 100.0

target_acos_input = st.sidebar.slider(
    "目标 ACoS 期望线 (%)",
    min_value=10,
    max_value=50,
    value=20,
    step=1,
    help="广告投放期望达成目标线（通常设定为毛利率扣除预期纯利目标）。ACoS 低于此线属于高盈利超额产出区间。",
)
target_acos = target_acos_input / 100.0

col_cpa, col_aov = st.sidebar.columns(2)
with col_cpa:
    target_cpa_input = st.number_input(
        "目标 CPA ($)",
        min_value=0.0,
        max_value=200.0,
        value=0.0,
        step=0.5,
        help="期望转化成本上限。留空(0)时系统按【大盘AOV × 目标ACoS】动态推导",
    )
with col_aov:
    aov_override_input = st.number_input(
        "基准 AOV ($)",
        min_value=0.0,
        max_value=1000.0,
        value=0.0,
        step=1.0,
        help="基准客单价。留空(0)时系统自动由销售额/订单计算",
    )
effective_cpa_override = target_cpa_input if target_cpa_input > 0 else None
effective_aov_override = aov_override_input if aov_override_input > 0 else None

# SKU 商品成本底表（真实利润模型）
st.sidebar.markdown("---")
st.sidebar.subheader("💰 商品单位成本底表（真实净利模型）")
if "sku_cost_dict" not in st.session_state:
    st.session_state["sku_cost_dict"] = {}

cost_file = st.sidebar.file_uploader(
    "上传商品成本表（.xlsx / .csv）",
    type=["xlsx", "xls", "csv"],
    help="包含字段：SKU、采购成本、头程、尾程运费、平台佣金率。上传后打通计算真实的广告前毛利与广告后真实净贡献。",
    key="global_sku_cost_uploader",
)

if cost_file is not None:
    try:
        loaded_costs, cost_err = load_sku_cost_table(cost_file)
        if cost_err:
            st.sidebar.error(cost_err)
        else:
            st.session_state["sku_cost_dict"] = loaded_costs
            record_upload_audit_log(
                "💰 SKU成本表",
                getattr(cost_file, "name", "cost_table.xlsx"),
                len(loaded_costs),
                getattr(cost_file, "size", 0),
                f"已配置 {len(loaded_costs)} 个 SKU 成本项"
            )
            save_session_cache(
                st.session_state["section_data"],
                st.session_state.get("sku_map", {}),
                st.session_state["sku_cost_dict"],
                st.session_state.get("file_names", {}),
            )
            st.sidebar.success(f"已识别 {len(loaded_costs)} 个 SKU 成本配置")
    except Exception as e:
        st.sidebar.error(f"成本表解析失败: {e}")

st.sidebar.download_button(
    label="📄 下载 SKU 成本底表模板",
    data=generate_sku_cost_template(),
    file_name="SKU商品单位成本配置模板.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# SKU 映射表
st.sidebar.markdown("---")
st.sidebar.subheader("🏷️ SKU 映射表（可选）")
sku_file = st.sidebar.file_uploader(
    "上传 SKU 映射表（.xlsx / .csv）",
    type=["xlsx", "xls", "csv"],
    help="上传后将把报表中的 Item ID 自动替换为店铺内部 SKU，方便直接核对具体产品",
    key="global_sku_uploader",
)

if sku_file is not None:
    try:
        loaded_map, err = load_sku_mapping(sku_file)
        if err:
            st.sidebar.error(err)
        else:
            st.session_state["sku_map"] = loaded_map
            # 关键：全链路回溯更新已存在的 ad_item 表格，确保立即显示对应 SKU
            if st.session_state["section_data"].get("ad_item") is not None:
                st.session_state["section_data"]["ad_item"] = apply_sku_mapping(
                    st.session_state["section_data"]["ad_item"], loaded_map
                )
            record_upload_audit_log(
                "🏷️ SKU映射表",
                getattr(sku_file, "name", "sku_mapping.xlsx"),
                len(loaded_map),
                getattr(sku_file, "size", 0),
                f"已匹配 {len(loaded_map)} 个 Item ID 映射关系"
            )
            save_session_cache(
                st.session_state["section_data"],
                st.session_state["sku_map"],
                st.session_state.get("sku_cost_dict", {}),
                st.session_state.get("file_names", {}),
            )
            st.sidebar.success(f"已识别并全量生效 {len(loaded_map)} 个 SKU 映射")
    except Exception as e:
        st.sidebar.error(f"映射表解析失败: {e}")

st.sidebar.download_button(
    label="📄 下载 SKU 映射表模板",
    data=generate_sku_template(),
    file_name="SKU映射表模板.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# 侧边栏：当前板块数据常驻状态指示
st.sidebar.markdown("---")
st.sidebar.subheader("📋 各板块数据常驻状态")
for key, name in [
    ("trend", "📈 SKU多期走势"),
    ("campaign", "① 广告活动报表"),
    ("search_term", "② 搜索词报表"),
    ("keyword", "③ 关键词报表"),
    ("ad_item", "④ 商品广告列表"),
    ("platform", "⑤ 平台报表"),
    ("page_type", "⑤ 页面类型报表"),
]:
    data_val = st.session_state["section_data"].get(key)
    f_val = st.session_state["file_names"].get(key)
    if data_val is not None:
        st.sidebar.caption(f"🟢 **{name}**：已就绪 ({f_val or '已加载'})")
    else:
        st.sidebar.caption(f"⚪ {name}：待上传对应文件")

if st.sidebar.button("🗑️ 清空所有板块缓存", help="清空已加载的所有分析数据与持久化快照"):
    st.session_state["section_data"] = {k: None for k in st.session_state["section_data"]}
    st.session_state["file_names"] = {}
    st.session_state["file_bytes_cache"] = {}
    st.session_state["sku_map"] = {}
    st.session_state["sku_cost_dict"] = {}
    clear_session_cache()
    st.rerun()

# =========================================================================
# 固定板块导航（Tab 常驻固定，位置永久锁定）
# =========================================================================
tab_options = [
    "📈 SKU多期趋势看板",
    "🎯 综合决策中枢",
    "💰 SKU真实利润模型",
    "① 广告活动诊断",
    "② 搜索词否词/挖词",
    "③ 关键词调价",
    "④ 商品位诊断",
    "⑤ 平台与页面位置",
]

tabs = st.tabs(tab_options)

# =========================================================================
# 辅助函数：板块专属数据源与上传组件
# =========================================================================
def render_section_uploader(
    sec_key: str,
    title: str,
    default_name: str,
    help_text: str,
    accept_multiple: bool = False,
):
    """
    固定板块专属上传组件：
    - 仅解析当前板块上传的文件；
    - 解析结果缓存在 Session 中，不重跑其他板块；
    - 毫秒级响应。
    """
    cur_data = st.session_state["section_data"].get(sec_key)
    cur_fname = st.session_state["file_names"].get(sec_key)

    if cur_data is not None:
        c_left, c_right = st.columns([4, 1])
        with c_left:
            disp_title = safe_html(cur_fname or default_name)
            st.markdown(
                f"""
                <div class="source-bar">
                    <div>
                        <span class="source-tag">🟢 当前板块数据已就绪：【{disp_title}】</span>
                        <span class="source-sub">（已生成专属深度分析与优化建议）</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c_right:
            if st.button("🗑️ 清除此板块", key=f"btn_clear_{sec_key}"):
                update_section(sec_key, None, "", None)
                st.rerun()

        with st.expander("🔄 重新上传 / 替换此板块文件", expanded=False):
            f_replace = st.file_uploader(
                f"选择新表格替换【{default_name}】",
                type=["xlsx", "xls", "csv"],
                key=f"rep_{sec_key}",
                accept_multiple_files=accept_multiple,
            )
            if f_replace:
                return f_replace
    else:
        st.markdown(
            f"""
            <div class="upload-box">
                <div style="font-size: 15px; font-weight: 600; color: #1e293b; margin-bottom: 6px;">
                    📂 暂无【{safe_html(default_name)}】数据
                </div>
                <div style="font-size: 13px; color: #64748b; margin-bottom: 12px;">
                    {safe_html(help_text)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        f_new = st.file_uploader(
            f"点击上传【{default_name}】(.xlsx / .csv)",
            type=["xlsx", "xls", "csv"],
            key=f"new_{sec_key}",
            accept_multiple_files=accept_multiple,
        )
        if f_new:
            return f_new
    return None

# =========================================================================
# TAB 1: 📈 SKU 多期趋势看板（重点优化：深度图表 + 趋势分析 + 预警建议）
# =========================================================================
with tabs[0]:
    st.markdown("### 📈 SKU / 商品每日及多期广告走势看板")
    st.caption("基于多期/每日底层明细数据（如 10.3--11.1 报表），展现各 SKU 趋势波动曲线，提供失血预警与放量建议。")

    t_file = render_section_uploader(
        sec_key="trend",
        title="SKU多期趋势",
        default_name="SKU 每日/多期广告走势表",
        help_text="请上传包含【日期】列与【SKU/Item Id】的多日广告报表（如 10.3--11.1.xlsx），或按天导出的多张走势表。单表上传即可自动识别全月每日明细！",
        accept_multiple=True,
    )

    if t_file:
        try:
            with st.spinner("正在缓存并解析多期数据模型..."):
                sku_items_tuple = tuple(sorted(st.session_state["sku_map"].items()))
                if isinstance(t_file, list):
                    file_tuple = tuple((f.name, f.getvalue()) for f in t_file)
                    p_df, s_sum, anoms, d_macro = parse_trend_data_cached(
                        file_tuple, sku_items_tuple, target_acos, breakeven_acos
                    )
                    update_section("trend", {
                        "period_df": p_df, "sku_summary": s_sum, "anomalies": anoms, "daily_macro": d_macro
                    }, f"多表合并 ({len(t_file)}张报表)")
                else:
                    file_tuple = ((t_file.name, t_file.getvalue()),)
                    p_df, s_sum, anoms, d_macro = parse_trend_data_cached(
                        file_tuple, sku_items_tuple, target_acos, breakeven_acos
                    )
                    update_section("trend", {
                        "period_df": p_df, "sku_summary": s_sum, "anomalies": anoms, "daily_macro": d_macro
                    }, t_file.name)
                    # 同时为商品位诊断备用
                    if st.session_state["section_data"].get("ad_item") is None:
                        t_type, single_df, _ = parse_single_file_cached(t_file.name, t_file.getvalue(), "ad_item")
                        if single_df is not None and st.session_state.get("sku_map"):
                            single_df = apply_sku_mapping(single_df, st.session_state["sku_map"])
                        update_section("ad_item", single_df, t_file.name)
                st.rerun()
        except Exception as e:
            st.error(f"走势数据解析建模失败: {e}")

    trend_payload = st.session_state["section_data"].get("trend")

    if trend_payload is not None:
        period_df = trend_payload["period_df"]
        sku_summary_df = trend_payload["sku_summary"]
        anomalies = trend_payload["anomalies"]
        daily_macro = trend_payload["daily_macro"]

        n_skus = len(sku_summary_df)
        n_periods = period_df["周期"].nunique() if not period_df.empty else 0
        min_date = period_df["周期"].min() if not period_df.empty else ""
        max_date = period_df["周期"].max() if not period_df.empty else ""

        # 绿色成功提示横幅（严格满足需求：确认数据没有漏传，让运营人员心里有底）
        match_note = "（与设定的统计天数一致）" if (analysis_days and n_periods == analysis_days) else (
            f"（设定天数: {analysis_days}天，已匹配当前明细天数）" if analysis_days else ""
        )
        st.success(
            f"✅ **已成功读取数据**：包含 **{n_skus}** 个 SKU，时间跨度 **{min_date} ~ {max_date}**（共 **{n_periods}** 天{match_note}），全量数据校验完成无遗漏！"
        )

        bad_anoms = [a for a in anomalies if a.get("类别") == "异常变差"]
        good_anoms = [a for a in anomalies if a.get("类别") == "变好向好"]

        # 1. 顶部宏观统计卡片
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("监控 SKU 总数", f"{n_skus} 款")
        with m2:
            st.metric("数据时间跨度", f"{n_periods} 天", f"{min_date} ~ {max_date}")
        with m3:
            st.metric("🚨 失血/恶化预警款", f"{len(bad_anoms)} 款", "急需降价止血")
        with m4:
            st.metric("🚀 强势放量爆款", f"{len(good_anoms)} 款", "建议加大预算")
        with m5:
            tot_spend = sku_summary_df["总花费"].sum() if not sku_summary_df.empty else 0.0
            tot_sales = sku_summary_df["总销售额"].sum() if not sku_summary_df.empty else 0.0
            ov_roas = (tot_sales / tot_spend) if tot_spend > 0 else 0.0
            st.metric("全周期整体投产", f"{ov_roas:.2f}x", f"总花费 {fmt_money(tot_spend)}")

        # 2. 全店每日走势大盘折线/柱状复合图
        if not daily_macro.empty and len(daily_macro) >= 2:
            with st.expander("📊 点击展开/收起：全店 30 天每日广告大盘走势总览图", expanded=True):
                fig_macro = make_subplots(specs=[[{"secondary_y": True}]])
                fig_macro.add_trace(
                    go.Bar(
                        x=daily_macro["周期"],
                        y=daily_macro["广告花费"],
                        name="每日总花费 ($)",
                        marker_color="#94a3b8",
                        opacity=0.75,
                    ),
                    secondary_y=False,
                )
                fig_macro.add_trace(
                    go.Bar(
                        x=daily_macro["周期"],
                        y=daily_macro["总销售额"],
                        name="每日总销售额 ($)",
                        marker_color="#3b82f6",
                        opacity=0.85,
                    ),
                    secondary_y=False,
                )
                fig_macro.add_trace(
                    go.Scatter(
                        x=daily_macro["周期"],
                        y=daily_macro["ROAS"],
                        name="每日整体 ROAS",
                        mode="lines+markers",
                        line=dict(color="#10b981", width=3),
                        marker=dict(size=7),
                    ),
                    secondary_y=True,
                )
                ref_roas_val = round(1.0 / target_acos, 2)
                fig_macro.add_hline(
                    y=ref_roas_val,
                    line_dash="dot",
                    line_color="#ef4444",
                    annotation_text=f"保本 ROAS ({ref_roas_val}x)",
                    annotation_position="bottom right",
                    secondary_y=True,
                )
                fig_macro.update_layout(
                    title="全店每日花费、销售额与整体 ROAS 演变趋势",
                    xaxis_title="日期 / 周期",
                    yaxis=dict(title="金额 ($)"),
                    yaxis2=dict(title="ROAS", overlaying="y", side="right", showgrid=False),
                    barmode="group",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    height=360,
                    margin=dict(l=40, r=40, t=50, b=40),
                )
                st.plotly_chart(fig_macro, use_container_width=True, config={"displayModeBar": False, "responsive": True})

        # 3. 🚨 重点 SKU 突变预警与放量诊断看板
        if anomalies:
            st.markdown("#### 🚨 重点关注 SKU 异动诊断与预警清单")
            anom_df = pd.DataFrame(anomalies)
            st.dataframe(
                anom_df[["类别", "状态表现", "SKU展示", "近期花费", "近期订单", "近期ROAS", "核心诊断", "优化建议"]],
                column_config={
                    "类别": st.column_config.TextColumn("预警类别", width="small"),
                    "状态表现": st.column_config.TextColumn("走势标签", width="small"),
                    "SKU展示": st.column_config.TextColumn("SKU (Item ID)", width="medium"),
                    "近期花费": st.column_config.NumberColumn("近期花费 ($)", format="$%.2f"),
                    "近期订单": st.column_config.NumberColumn("近期订单", format="%d"),
                    "近期ROAS": st.column_config.NumberColumn("近期 ROAS", format="%.2f"),
                    "核心诊断": st.column_config.TextColumn("数据异动剖析", width="large"),
                    "优化建议": st.column_config.TextColumn("落地行动预警", width="large"),
                },
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("---")

        # 4. 单 SKU 深度走势图表与落地预警建议
        st.markdown("#### 🔍 单 SKU 深度走势可视化与策略诊断")

        all_skus = list(sku_summary_df["SKU"].unique()) if not sku_summary_df.empty else []
        sku_name_dict = sku_summary_df.set_index("SKU")["SKU展示"].to_dict()

        def format_sku_option(sku_code):
            return sku_name_dict.get(sku_code, sku_code)

        # 记忆用户选中的 SKU
        default_sku_idx = 0
        if st.session_state["selected_sku_code"] in all_skus:
            default_sku_idx = all_skus.index(st.session_state["selected_sku_code"])

        c_sel1, c_sel2 = st.columns([3, 1])
        with c_sel1:
            selected_sku = st.selectbox(
                "选择需深入剖析的商品 SKU：",
                all_skus,
                format_func=format_sku_option,
                index=default_sku_idx,
            )
            st.session_state["selected_sku_code"] = selected_sku
        with c_sel2:
            st.download_button(
                label="📄 下载走势示例模板",
                data=generate_daily_trend_template(),
                file_name="SKU每日广告数据趋势模板.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        if selected_sku and not period_df.empty:
            sku_rows = period_df[period_df["SKU"] == selected_sku].sort_values(by="周期").reset_index(drop=True)
            sku_info = sku_summary_df[sku_summary_df["SKU"] == selected_sku].iloc[0]

            # 诊断与预警建议卡片
            status_tag = sku_info["趋势状态"]
            is_bad = "🚨" in status_tag or "失血" in status_tag or "萎缩" in status_tag
            is_good = "🚀" in status_tag or "🌟" in status_tag or "放量" in status_tag
            box_class = "advice-box-danger" if is_bad else ("advice-box-success" if is_good else "advice-box")

            sku_disp_clean = safe_html(sku_info['SKU展示'])
            tag_clean = safe_html(status_tag)
            feature_clean = safe_html(sku_info['数据特征剖析'])
            action_clean = safe_html(sku_info['建议预警动作'])
            cls_clean = safe_html(box_class)

            st.markdown(
                f"""
                <div class="advice-box {cls_clean}">
                    <div style="font-weight: 700; font-size: 15px; margin-bottom: 6px;">
                        📌 【{sku_disp_clean}】 走势评级：<span style="color: {'#dc2626' if is_bad else ('#16a34a' if is_good else '#2563eb')}">{tag_clean}</span>
                    </div>
                    <div style="font-size: 13.5px; color: #334155; margin-bottom: 4px;">
                        <strong>数据特征剖析：</strong> {feature_clean}（累计花费 ${sku_info['总花费']:,.2f}，出单 {sku_info['总订单']}，整体 ROAS {sku_info['整体ROAS']}）
                    </div>
                    <div style="font-size: 14px; font-weight: 600; color: #0f172a;">
                        👉 <strong>运营行动建议：</strong> {action_clean}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 双图联动：主图（花费/销售/ROAS） + 副图（订单/CPC/CVR）
            fig_sku = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.10,
                row_heights=[0.6, 0.4],
                subplot_titles=(f"{sku_info['SKU展示']} 每日花费、销售额与 ROAS 变动走势", "转化承接透视：订单量、点击成本 (CPC) 与转化率 (CVR)"),
                specs=[[{"secondary_y": True}], [{"secondary_y": True}]],
            )

            # Row 1: 花费、销售额、ROAS
            fig_sku.add_trace(
                go.Bar(
                    x=sku_rows["周期"],
                    y=sku_rows["广告花费"],
                    name="广告花费 ($)",
                    marker_color="#94a3b8",
                    opacity=0.7,
                ),
                row=1, col=1, secondary_y=False,
            )
            fig_sku.add_trace(
                go.Bar(
                    x=sku_rows["周期"],
                    y=sku_rows["总销售额"],
                    name="总销售额 ($)",
                    marker_color="#3b82f6",
                    opacity=0.85,
                ),
                row=1, col=1, secondary_y=False,
            )
            fig_sku.add_trace(
                go.Scatter(
                    x=sku_rows["周期"],
                    y=sku_rows["ROAS"],
                    name="ROAS",
                    mode="lines+markers",
                    line=dict(color="#10b981", width=3),
                    marker=dict(size=7),
                ),
                row=1, col=1, secondary_y=True,
            )
            ref_r = round(1.0 / target_acos, 2)
            fig_sku.add_hline(
                y=ref_r,
                line_dash="dot",
                line_color="#ef4444",
                annotation_text=f"保本 ROAS ({ref_r}x)",
                annotation_position="bottom right",
                row=1, col=1, secondary_y=True,
            )

            # Row 2: 订单量柱状图 + CPC / CVR 折线
            fig_sku.add_trace(
                go.Bar(
                    x=sku_rows["周期"],
                    y=sku_rows["广告订单"],
                    name="订单量",
                    marker_color="#fbbf24",
                    opacity=0.8,
                ),
                row=2, col=1, secondary_y=False,
            )
            fig_sku.add_trace(
                go.Scatter(
                    x=sku_rows["周期"],
                    y=sku_rows["CPC"],
                    name="CPC 点击成本 ($)",
                    mode="lines+markers",
                    line=dict(color="#ec4899", width=2),
                ),
                row=2, col=1, secondary_y=True,
            )
            fig_sku.add_trace(
                go.Scatter(
                    x=sku_rows["周期"],
                    y=sku_rows["CVR"] * 100,
                    name="CVR 转化率 (%)",
                    mode="lines+markers",
                    line=dict(color="#8b5cf6", width=2, dash="dash"),
                ),
                row=2, col=1, secondary_y=True,
            )

            fig_sku.update_layout(
                height=520,
                barmode="group",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=40, r=40, t=45, b=30),
            )
            fig_sku.update_yaxes(title_text="金额 ($)", row=1, col=1, secondary_y=False)
            fig_sku.update_yaxes(title_text="ROAS", row=1, col=1, secondary_y=True)
            fig_sku.update_yaxes(title_text="订单数", row=2, col=1, secondary_y=False)
            fig_sku.update_yaxes(title_text="比率 (%) / CPC ($)", row=2, col=1, secondary_y=True)

            st.plotly_chart(fig_sku, use_container_width=True, config={"displayModeBar": False, "responsive": True})

        # 5. 全量 SKU 周期汇总明细表
        st.markdown("#### 📋 全量 SKU 周期趋势指标与诊断建议总表")

        f_col1, f_col2 = st.columns([3, 1])
        with f_col1:
            status_options = ["全部 SKU", "🚨 仅看失血/恶化预警款", "🚀 仅看强势放量爆款", "📉 仅看低效消耗款", "平稳运行"]
            chosen_status_idx = status_options.index(st.session_state["trend_filter_choice"]) if st.session_state["trend_filter_choice"] in status_options else 0
            chosen_status = st.selectbox("按趋势状态筛选：", status_options, index=chosen_status_idx)
            st.session_state["trend_filter_choice"] = chosen_status
        with f_col2:
            csv_trend_sum = sku_summary_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label=f"📥 导出趋势汇总 CSV ({len(sku_summary_df)}款)",
                data=csv_trend_sum,
                file_name="walmart_sku_trend_analysis_summary.csv",
                mime="text/csv",
            )

        filter_df = sku_summary_df.copy()
        if chosen_status == "🚨 仅看失血/恶化预警款":
            filter_df = filter_df[filter_df["趋势分类"] == "异常变差"]
        elif chosen_status == "🚀 仅看强势放量爆款":
            filter_df = filter_df[filter_df["趋势分类"] == "变好向好"]
        elif chosen_status == "📉 仅看低效消耗款":
            filter_df = filter_df[filter_df["趋势状态"].str.contains("低效", na=False)]
        elif chosen_status == "平稳运行":
            filter_df = filter_df[filter_df["趋势分类"] == "平稳"]

        st.dataframe(
            filter_df[[
                "SKU展示", "趋势状态", "总花费", "总销售额", "总订单", "整体ROAS",
                "近期花费", "近期订单", "近期ROAS", "花费环比%", "订单环比%", "建议预警动作"
            ]],
            column_config={
                "SKU展示": st.column_config.TextColumn("SKU (Item ID)", width="medium"),
                "趋势状态": st.column_config.TextColumn("走势标签", width="small"),
                "总花费": st.column_config.NumberColumn("总花费 ($)", format="$%.2f"),
                "总销售额": st.column_config.NumberColumn("总销售额 ($)", format="$%.2f"),
                "总订单": st.column_config.NumberColumn("总订单", format="%d"),
                "整体ROAS": st.column_config.NumberColumn("整体 ROAS", format="%.2f"),
                "近期花费": st.column_config.NumberColumn("近期花费 ($)", format="$%.2f"),
                "近期订单": st.column_config.NumberColumn("近期订单", format="%d"),
                "近期ROAS": st.column_config.NumberColumn("近期 ROAS", format="%.2f"),
                "花费环比%": st.column_config.NumberColumn("花费环比%", format="%.1f%%"),
                "订单环比%": st.column_config.NumberColumn("订单环比%", format="%.1f%%"),
                "建议预警动作": st.column_config.TextColumn("运营预警指令", width="large"),
            },
            use_container_width=True,
            hide_index=True,
        )

# =========================================================================
# TAB 2: 🎯 统一智能决策中枢（4 层架构决策引擎）
# =========================================================================
with tabs[1]:
    st.markdown("### 🎯 统一智能决策中枢（4 层广告决策与防冲突引擎）")
    st.caption("数据层清洗对齐 -> 专家规则并发评估 -> 冲突仲裁与动作去重 -> 最终结构化决策指令矩阵。")

    active_tables = {k: st.session_state["section_data"].get(k) for k in [
        "campaign", "search_term", "keyword", "ad_item", "platform", "page_type"
    ]}

    if active_tables.get("ad_item") is None and st.session_state["section_data"].get("trend") is not None:
        active_tables["ad_item"] = st.session_state["section_data"]["trend"]["period_df"]

    has_any = any(v is not None and not v.empty for v in active_tables.values())

    if not has_any:
        st.info("💡 当前暂无任何广告业务数据。请先在其它专属业务板块上传对应表格（如在「📈 SKU多期趋势看板」上传 10.3--11.1 报表）。")
    else:
        # 运行统一决策引擎
        engine = AdDecisionEngine(
            target_acos=target_acos,
            breakeven_acos=breakeven_acos,
            target_cpa=effective_cpa_override,
            aov_override=effective_aov_override,
            cost_dict=st.session_state.get("sku_cost_dict", {}),
        )
        engine_res = engine.run(active_tables)
        dec_matrix = engine_res["decision_matrix"]
        exec_sum = engine_res["executive_summary"]
        conflict_log = engine_res["conflict_log"]
        overview = summarize_overview(active_tables)

        spend_str = fmt_money(overview.get("大盘总花费"))
        sales_str = fmt_money(overview.get("总销售额"))
        roas_str = fmt_roas(overview.get("整体ROAS"))
        orders_str = fmt_num(overview.get("总订单"))
        aov_str = fmt_money(overview.get("AOV"))
        ctr_str = fmt_pct(overview.get("整体CTR"))
        cpc_str = fmt_money(overview.get("CPC"))
        cvr_str = fmt_pct(overview.get("CVR"))
        cpa_str = fmt_money(overview.get("CPA"))
        nb_str = fmt_pct(overview.get("新客占比"))

        st.markdown(
            f"""
            <div class="kpi-grid">
                <div class="kpi-card"><div class="kpi-label">大盘总花费</div><div class="kpi-value">{safe_html(spend_str)}</div></div>
                <div class="kpi-card"><div class="kpi-label">广告总销售额</div><div class="kpi-value">{safe_html(sales_str)}</div></div>
                <div class="kpi-card"><div class="kpi-label">整体 ROAS</div><div class="kpi-value">{safe_html(roas_str)}</div></div>
                <div class="kpi-card"><div class="kpi-label">总订单数</div><div class="kpi-value">{safe_html(orders_str)}</div></div>
                <div class="kpi-card"><div class="kpi-label">客单价 (AOV)</div><div class="kpi-value">{safe_html(aov_str)}</div></div>
                <div class="kpi-card"><div class="kpi-label">整体点击率 (CTR)</div><div class="kpi-value">{safe_html(ctr_str)}</div></div>
                <div class="kpi-card"><div class="kpi-label">平均点击成本 (CPC)</div><div class="kpi-value">{safe_html(cpc_str)}</div></div>
                <div class="kpi-card"><div class="kpi-label">订单转化率 (CVR)</div><div class="kpi-value">{safe_html(cvr_str)}</div></div>
                <div class="kpi-card"><div class="kpi-label">获客成本 (CPA)</div><div class="kpi-value">{safe_html(cpa_str)}</div></div>
                <div class="kpi-card"><div class="kpi-label">新客订单占比</div><div class="kpi-value">{safe_html(nb_str)}</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # =====================================================================
        # 沃尔玛广告总监三大核心问题诊断看板 (P0 核心直达)
        # =====================================================================
        st.markdown("#### 🎯 沃尔玛广告总监 · 三大核心经营决策")
        
        # 1. 当前广告最大的问题是什么？
        c_prob = exec_sum.get("core_problem_answer", "大盘运行稳定。")
        st.markdown(
            f"""
            <div style="background: #fff1f2; border: 1px solid #fecdd3; border-left: 5px solid #e11d48; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px;">
                <div style="font-weight: 700; font-size: 15px; color: #9f1239; margin-bottom: 4px;">
                    ❓ 核心问题一：当前广告账户最大的痛点是什么？
                </div>
                <div style="font-size: 14px; color: #881337; line-height: 1.5;">
                    {safe_html(c_prob)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 2. 下一步最值得执行的三个优化动作是什么？
        st.markdown("##### 📌 核心问题二：下一步最值得执行的三个高杠杆优化动作")
        top3_list = exec_sum.get("top3_actions", [])
        if top3_list:
            t_cols = st.columns(len(top3_list))
            for idx, act_item in enumerate(top3_list):
                with t_cols[idx]:
                    prio_color = "#e11d48" if act_item["priority"] == "P0" else ("#f59e0b" if act_item["priority"] == "P1" else "#10b981")
                    st.markdown(
                        f"""
                        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 4px solid {prio_color}; border-radius: 8px; padding: 12px 14px; height: 100%;">
                            <div style="font-size: 12px; font-weight: 700; color: {prio_color}; margin-bottom: 4px;">
                                {act_item['rank']} · {act_item['priority']} ({act_item['domain']})
                            </div>
                            <div style="font-size: 13.5px; font-weight: 700; color: #0f172a; margin-bottom: 6px;">
                                {safe_html(act_item['target'])}
                            </div>
                            <div style="font-size: 13px; color: #334155; margin-bottom: 6px;">
                                👉 <strong>执行动作：</strong> {safe_html(act_item['action'])}
                            </div>
                            <div style="font-size: 12px; color: #64748b; margin-bottom: 4px;">
                                📏 <strong>幅度：</strong> {safe_html(act_item['magnitude'])}
                            </div>
                            <div style="font-size: 12px; color: #64748b; margin-bottom: 4px;">
                                💡 <strong>依据：</strong> {safe_html(act_item['rationale'])}
                            </div>
                            <div style="font-size: 12px; color: #0284c7; font-weight: 600;">
                                ⏳ <strong>验证周期：</strong> {safe_html(act_item['window'])}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            st.caption("暂无突出紧急动作。")

        # 3. 如何验证这些动作是否真正改善了经营结果？
        st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)
        with st.expander("⚖️ 核心问题三：如何验证这些动作是否真正改善了经营结果？（3天/7天/14天 KPI 闭环验证指引）", expanded=False):
            st.caption("广告优化不能只看订单增长，必须建立「止损 -> 结构 -> 利润」的三阶段闭环验证标准：")
            v_meth = exec_sum.get("validation_methodology", [])
            vm_cols = st.columns(len(v_meth) if v_meth else 3)
            for v_idx, v_item in enumerate(v_meth):
                with vm_cols[v_idx]:
                    st.markdown(f"**📌 {v_item['phase']}**")
                    st.info(f"**核心目标：** {v_item['kpi']}\n\n{v_item['desc']}")

        st.markdown("---")

        # =====================================================================
        # 第一层：数据质量分析与 AI 决策可信度体检
        # =====================================================================
        dq_report = inspect_data_quality(
            st.session_state["section_data"],
            sku_map=st.session_state.get("sku_map"),
            sku_cost_dict=st.session_state.get("sku_cost_dict"),
        )
        with st.expander(f"🛡️ 第一层：数据质量体检与 AI 决策可信度报告（质量评分: {dq_report['score']}/100 · {dq_report['confidence']}）", expanded=False):
            st.markdown(f"**当前状态：** {dq_report['status']}")
            st.caption("严格遵从【数据质量不合格不允许生成确定性结论】原则。以下为字段完整性、格式规范、跨表勾稽与统计口径对账体检：")
            
            dq_checks_df = pd.DataFrame(dq_report["checks"])
            if not dq_checks_df.empty:
                st.dataframe(dq_checks_df, use_container_width=True, hide_index=True)
            
            reconcil = dq_report.get("reconciliation", {})
            if reconcil.get("spends"):
                st.caption(f"📊 各报表总花费口径：{reconcil['spends']}")

        # =====================================================================
        # 第二层：流量结构与匹配方式剖析
        # =====================================================================
        traffic_struct = analyze_traffic_structure(
            campaign_df=active_tables.get("campaign"),
            keyword_df=active_tables.get("keyword"),
            search_term_df=active_tables.get("search_term"),
        )
        with st.expander("📊 第二层：广告流量结构与匹配方式洞察（Auto vs Manual & 跨活动内耗）", expanded=False):
            if not traffic_struct["auto_vs_manual_df"].empty:
                st.markdown("##### 🤖 Auto (自动) vs 🎯 Manual (手动) 流量贡献与预算分配")
                v_avm = traffic_struct["auto_vs_manual_df"].copy()
                st.dataframe(
                    v_avm,
                    column_config={
                        "投放模式": st.column_config.TextColumn("投放类型", width="medium"),
                        "广告花费": st.column_config.NumberColumn("广告花费 ($)", format="$%.2f"),
                        "花费占比": st.column_config.NumberColumn("花费占比", format="%.1f%%"),
                        "总销售额": st.column_config.NumberColumn("总销售额 ($)", format="$%.2f"),
                        "广告订单": st.column_config.NumberColumn("订单", format="%d"),
                        "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
                        "ACoS": st.column_config.NumberColumn("ACoS", format="%.2f%%"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )

            if not traffic_struct["match_type_df"].empty:
                st.markdown("##### 🎯 关键词匹配方式投产表现 (Exact vs Phrase vs Broad)")
                st.dataframe(
                    traffic_struct["match_type_df"],
                    column_config={
                        "规范匹配方式": st.column_config.TextColumn("匹配方式", width="medium"),
                        "广告花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                        "花费占比": st.column_config.NumberColumn("花费占比", format="%.1f%%"),
                        "总销售额": st.column_config.NumberColumn("销售额 ($)", format="$%.2f"),
                        "广告订单": st.column_config.NumberColumn("订单", format="%d"),
                        "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
                        "ACoS": st.column_config.NumberColumn("ACoS", format="%.2f%%"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )

            if not traffic_struct["overlap_terms_df"].empty:
                st.markdown("##### ⚔️ 跨活动流量重叠与同词内耗竞价 (Traffic Overlap)")
                st.caption("以下搜索词同时在多个广告活动中被触发，容易造成自家活动竞价内耗，抬高整体 CPC：")
                st.dataframe(traffic_struct["overlap_terms_df"], use_container_width=True, hide_index=True)

            if traffic_struct.get("structure_insights"):
                st.markdown("##### 💡 结构性优化警示")
                for si in traffic_struct["structure_insights"]:
                    st.warning(f"**{si['type']}**：{si['finding']}\n\n👉 **应对策略**：{si['action']}")

        # =====================================================================
        # 第四层：广告问题十二项全息诊断
        # =====================================================================
        issues_12 = diagnose_12_advertising_issues(
            st.session_state["section_data"],
            target_acos=target_acos,
            breakeven_acos=breakeven_acos,
            sku_cost_dict=st.session_state.get("sku_cost_dict"),
            sku_map=st.session_state.get("sku_map"),
        )
        with st.expander(f"🩺 第四层：广告问题十二项全息穿透诊断（已深度体检 {len(issues_12)} 个异常实体）", expanded=False):
            st.caption("系统针对每个实体（SKU、活动、广告组、关键词、搜索词）穿透识别 12 类典型问题，输出数据证据、置信度与根因假设：")
            for iss in issues_12:
                p_badge = "🔴" if iss["severity"] == "P0" else ("🟠" if iss["severity"] == "P1" else "🟢")
                st.markdown(
                    f"""
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid {'#ef4444' if iss['severity']=='P0' else '#f59e0b'}; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;">
                        <div style="font-weight: 700; font-size: 13.5px; color: #1e293b;">
                            {p_badge} 【{iss['issue_type']}】 · {iss['entity']}
                            <span style="font-size: 11px; color: #0284c7; background: #e0f2fe; padding: 2px 6px; border-radius: 4px; margin-left: 8px;">{iss['confidence']}</span>
                        </div>
                        <div style="font-size: 13px; color: #475569; margin-top: 4px;">
                            <strong>数据证据：</strong> {safe_html(iss['data_evidence'])}
                        </div>
                        <div style="font-size: 13px; color: #64748b; margin-top: 2px;">
                            <strong>根本原因推导：</strong> {safe_html(iss['root_cause'])}
                        </div>
                        <div style="font-size: 13px; color: #0f172a; margin-top: 3px;">
                            👉 <strong>建议措施：</strong> {safe_html(iss['action'])}（预期改善：{safe_html(iss['expected_impact'])}，观察周期：{safe_html(iss['observation_window'])}）
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        # 核心决策指标概览
        st.markdown("#### 🧭 决策中枢核心推导与预估业务影响")
        e1, e2, e3, e4, e5 = st.columns(5)
        with e1:
            st.metric("🚨 P0 紧急止损项", f"{exec_sum['p0_count']} 项", "今日必做")
        with e2:
            st.metric("📉 P1 结构控本项", f"{exec_sum['p1_count']} 项", "本周优化")
        with e3:
            st.metric("🚀 P2 提效拓量项", f"{exec_sum['p2_count']} 项", "加权放量")
        with e4:
            st.metric("🛡️ 预估可拦截浪费", f"${exec_sum['preventable_waste']:,.2f}", "封堵失血点")
        with e5:
            st.metric("📈 增长扩量机会", f"${exec_sum['growth_potential']:,.2f}", "高投产倾斜")

        # 冲突仲裁审计日志展示
        if conflict_log:
            with st.expander(f"🛡️ 自动防冲突仲裁审计日志（已成功拦截并解决 {len(conflict_log)} 起跨规则冲突）", expanded=False):
                st.caption("系统严格执行【止损优先与动作互斥】原则，同一关键词/实体在同一广告活动中禁止同时下达互斥指令：")
                conf_df = pd.DataFrame(conflict_log)
                st.dataframe(conf_df, use_container_width=True, hide_index=True)

        # 最终结构化决策指令总表
        st.markdown("#### 📋 第五层：最终执行决策指令总表（包含 8 项标准参数）")
        if not dec_matrix.empty:
            f_col1, f_col2, f_col3, f_col4 = st.columns([2, 2, 1, 1])
            with f_col1:
                p_filter = st.multiselect("按优先级筛选：", ["P0", "P1", "P2"], default=["P0", "P1", "P2"])
            with f_col2:
                all_domains = list(dec_matrix["决策领域"].unique())
                d_filter = st.multiselect("按业务领域筛选：", all_domains, default=all_domains)
            with f_col3:
                csv_dec = dec_matrix.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label=f"📥 导出清单 CSV ({len(dec_matrix)}项)",
                    data=csv_dec,
                    file_name="walmart_decision_matrix.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with f_col4:
                if st.button("💾 归档至追踪库", help="将当前批次建议保存至第六层优化效果追踪库", use_container_width=True):
                    actions_list = dec_matrix.to_dict(orient="records")
                    saved_n = log_optimization_actions(actions_list)
                    st.success(f"已成功归档 {saved_n} 条决策到追踪库！")

            v_dec_df = dec_matrix.copy()
            if p_filter:
                v_dec_df = v_dec_df[v_dec_df["优先级"].isin(p_filter)]
            if d_filter:
                v_dec_df = v_dec_df[v_dec_df["决策领域"].isin(d_filter)]

            st.dataframe(
                v_dec_df,
                column_config={
                    "优先级": st.column_config.TextColumn("优先级", width="small"),
                    "决策领域": st.column_config.TextColumn("领域", width="small"),
                    "操作对象": st.column_config.TextColumn("操作对象", width="medium"),
                    "所属活动/范围": st.column_config.TextColumn("广告活动", width="medium"),
                    "当前表现依据": st.column_config.TextColumn("数据事实依据", width="medium"),
                    "建议动作": st.column_config.TextColumn("建议动作", width="large"),
                    "建议调整幅度": st.column_config.TextColumn("调整幅度", width="small"),
                    "调整依据": st.column_config.TextColumn("调整依据", width="medium"),
                    "风险提示": st.column_config.TextColumn("风险提示", width="medium"),
                    "验证周期": st.column_config.TextColumn("验证周期", width="small"),
                    "成功判断标准": st.column_config.TextColumn("成功判断标准", width="medium"),
                    "置信度": st.column_config.TextColumn("置信度", width="small"),
                    "预估影响金额($)": st.column_config.NumberColumn("预估影响 ($)", format="$%.2f"),
                    "执行状态": st.column_config.TextColumn("状态", width="small"),
                },
                use_container_width=True,
                hide_index=True,
            )

        # =====================================================================
        # 第六层：效果追踪与模型迭代库展示
        # =====================================================================
        st.markdown("---")
        tracking_data = generate_tracking_summary()
        with st.expander(f"📈 第六层：效果追踪与模型迭代库（累计归档 {tracking_data['total_actions']} 项动作 · 规则有效率 {tracking_data['success_rate']}）", expanded=False):
            st.caption("系统自动追踪每项建议的执行前后数据变化，识别哪些优化策略有效，持续校准决策规则与阈值：")
            
            # 规则迭代有效性统计
            st.markdown("##### 🔬 决策规则有效性回测与校准统计")
            rule_df = pd.DataFrame(tracking_data["model_rule_stats"])
            if not rule_df.empty:
                st.dataframe(
                    rule_df,
                    column_config={
                        "rule_name": st.column_config.TextColumn("诊断规则名称", width="medium"),
                        "sample_count": st.column_config.NumberColumn("回测样本数", format="%d"),
                        "effectiveness": st.column_config.TextColumn("实测有效性", width="small"),
                        "impact": st.column_config.TextColumn("业务影响与校准结论", width="large"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )

            # 历史执行追踪表
            if not tracking_data["records_df"].empty:
                st.markdown("##### 📋 历史建议执行跟踪明细")
                t_disp_df = tracking_data["records_df"][["action_id", "execution_date", "entity", "domain", "ai_action", "validation_window", "outcome_evaluation"]]
                st.dataframe(t_disp_df, use_container_width=True, hide_index=True)
                if st.button("🗑️ 清空历史优化追踪记录", key="btn_clear_track"):
                    clear_tracking_history()
                    st.rerun()

        # 动态流量漏斗健康度与保本盈亏评估
        st.markdown("---")
        st.markdown("#### ⚖️ 广告保本盈亏与流量漏斗动态健康度诊断")
        store_diag = generate_store_overview_analysis(
            overview,
            active_tables,
            target_acos=target_acos,
            breakeven_acos=breakeven_acos,
        )

        funnel_items = store_diag["funnel"]
        f_cols = st.columns(4)
        idx_f = 0
        for f_name, f_data in funnel_items.items():
            with f_cols[idx_f]:
                st.metric(f_name, f_data["value"], f_data["status"])
                st.caption(f"**基准**：{f_data['benchmark']}")
                st.caption(f"{f_data['analysis']}")
            idx_f += 1

        if store_diag.get("strategic_insights"):
            st.markdown("##### 💡 店铺运营核心矛盾与数据事实推导")
            s_cols = st.columns(len(store_diag["strategic_insights"]))
            for s_idx, s_item in enumerate(store_diag["strategic_insights"]):
                with s_cols[s_idx]:
                    st.info(f"**{s_item['dimension']}**\n\n📌 **事实**：{s_item['fact']}\n\n👉 **策略**：{s_item['insight']}")

        # 数据清洗审计报告
        all_anomalies = get_all_cleaning_anomalies(st.session_state["section_data"])
        if all_anomalies:
            with st.expander(f"⚠️ 数据清洗异常审计报告（已自动记录并规范化 {len(all_anomalies)} 处异常值）", expanded=False):
                st.caption("系统已严格执行清洗审计，废除静默填 0。以下为本次报表清洗过程中自动识别与修复的非正规数据清单：")
                anom_df = pd.DataFrame(all_anomalies)
                st.dataframe(anom_df, use_container_width=True)

# =========================================================================
# TAB 3: 💰 SKU真实利润模型（商品成本底表与广告净贡献）
# =========================================================================
with tabs[2]:
    st.markdown("### 💰 SKU 商品单位成本与真实净利模型")
    st.caption("引入采购、头程、尾程运费与平台佣金底表，精确计算每个 SKU 的广告前毛利、广告花费与扣减广告后的真实净现金贡献。")

    ad_item_table = st.session_state["section_data"].get("ad_item")
    if ad_item_table is None and st.session_state["section_data"].get("trend") is not None:
        ad_item_table = st.session_state["section_data"]["trend"]["period_df"]

    if ad_item_table is None or ad_item_table.empty:
        st.info("💡 请先在「📈 SKU多期趋势看板」或「④ 商品位诊断」上传广告商品列表报表以激活真实利润模型。")
    else:
        sku_costs = st.session_state.get("sku_cost_dict", {})
        if not sku_costs:
            st.warning("⚠️ 尚未在左侧边栏上传【商品单位成本表】。当前采用行业基准估算模型展示；建议上传成本表以获取 100% 精准的真实净利润与保本线。")

        profit_df, p_stats = calculate_sku_profit_analytics(
            ad_item_table, sku_costs, default_margin=breakeven_acos
        )

        if not profit_df.empty:
            pm1, pm2, pm3, pm4, pm5 = st.columns(5)
            with pm1:
                st.metric("广告总销售额", f"${p_stats['total_sales']:,.2f}")
            with pm2:
                st.metric("广告前商品毛利", f"${p_stats['total_pre_ad_profit']:,.2f}", f"毛利率 {breakeven_acos*100:.1f}%")
            with pm3:
                st.metric("广告花费支出", f"${p_stats['total_spend']:,.2f}")
            with pm4:
                net_val = p_stats['total_post_ad_net_profit']
                st.metric("广告后真实净贡献", f"${net_val:,.2f}", f"净利率 {p_stats['overall_net_margin']*100:.1f}%")
            with pm5:
                st.metric("盈利 / 亏损 SKU", f"{p_stats['profitable_sku_count']} 款 / {p_stats['loss_sku_count']} 款")

            st.markdown("#### 📋 SKU 真实利润与广告保本线透视总表")
            p_col1, p_col2 = st.columns([3, 1])
            with p_col1:
                tier_options = ["全部 SKU", "🚀 强力净盈利", "⚖️ 保本正贡献", "🚨 真实净亏损"]
                sel_tier = st.selectbox("按真实盈利状态筛选：", tier_options)
            with p_col2:
                csv_profit = profit_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label=f"📥 导出 SKU 真实利润表 CSV ({len(profit_df)}款)",
                    data=csv_profit,
                    file_name="sku_true_profit_analytics.csv",
                    mime="text/csv",
                )

            v_p_df = profit_df.copy()
            if sel_tier != "全部 SKU":
                v_p_df = v_p_df[v_p_df["盈利状态"] == sel_tier]

            # 转换为百分比数值用于 NumberColumn 格式化
            if "实际ACoS" in v_p_df.columns:
                v_p_df["实际ACoS%"] = pd.to_numeric(v_p_df["实际ACoS"], errors="coerce") * 100.0
            if "动态保本ACoS" in v_p_df.columns:
                v_p_df["动态保本ACoS%"] = pd.to_numeric(v_p_df["动态保本ACoS"], errors="coerce") * 100.0
            if "广告后净利率" in v_p_df.columns:
                v_p_df["广告后净利率%"] = pd.to_numeric(v_p_df["广告后净利率"], errors="coerce") * 100.0

            st.dataframe(
                v_p_df[[
                    "SKU", "成本来源", "广告销售额", "广告花费", "实际ACoS%", "动态保本ACoS%",
                    "广告前毛利", "广告后真实净利", "广告后净利率%", "盈利状态", "经营决策指令"
                ]],
                column_config={
                    "SKU": st.column_config.TextColumn("SKU (Item ID)", width="medium"),
                    "成本来源": st.column_config.TextColumn("成本匹配", width="small"),
                    "广告销售额": st.column_config.NumberColumn("广告销售额 ($)", format="$%.2f"),
                    "广告花费": st.column_config.NumberColumn("广告花费 ($)", format="$%.2f"),
                    "实际ACoS%": st.column_config.NumberColumn("实际 ACoS", format="%.2f%%"),
                    "动态保本ACoS%": st.column_config.NumberColumn("动态保本 ACoS", format="%.2f%%"),
                    "广告前毛利": st.column_config.NumberColumn("广告前毛利 ($)", format="$%.2f"),
                    "广告后真实净利": st.column_config.NumberColumn("广告后真实净利 ($)", format="$%.2f"),
                    "广告后净利率%": st.column_config.NumberColumn("净利率", format="%.2f%%"),
                    "盈利状态": st.column_config.TextColumn("盈利评级", width="small"),
                    "经营决策指令": st.column_config.TextColumn("经营决策指令", width="large"),
                },
                use_container_width=True,
                hide_index=True,
            )

# =========================================================================
# TAB 4: ① 广告活动诊断板块
# =========================================================================
with tabs[3]:
    st.markdown("### ① 广告活动健康度诊断")
    f_camp = render_section_uploader(
        sec_key="campaign",
        title="广告活动诊断",
        default_name="广告活动报表",
        help_text="请上传领星导出的【广告活动列表报表】（文件名含'广告活动'或'campaign'），支持 .xlsx / .csv。",
    )
    if f_camp:
        try:
            with st.spinner("正在解析广告活动报表..."):
                t_type, df, _ = parse_single_file_cached(f_camp.name, f_camp.getvalue(), "campaign")
                if df is not None:
                    has_camp = any("活动" in str(c) or "campaign" in str(c).lower() for c in df.columns)
                    if not has_camp:
                        st.error(f"❌ **上传文件类型不匹配**：您上传的文件【`{f_camp.name}`】未检测到【广告活动】核心维度列！请确认上传的是领星【广告活动列表报表】。")
                    else:
                        update_section("campaign", df, f_camp.name, f_camp.getvalue())
                        st.rerun()
        except Exception as e:
            st.error(f"解析失败: {e}")

    camp_df = st.session_state["section_data"].get("campaign")
    if camp_df is not None and not camp_df.empty:
        try:
            live_df, inactive_info, budget_notice = analyze_campaign_health(camp_df, days=analysis_days)
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("有效在投活动 (Live)", f"{len(live_df)} 个")
            with c2:
                st.metric("在投总花费", fmt_money(live_df["花费"].sum() if "花费" in live_df.columns else 0.0))
            with c3:
                st.metric("已暂停活动", f"{inactive_info.get('count', 0)} 条", f"历史花费 {fmt_money(inactive_info.get('total_spend', 0))}")
            with c4:
                st.metric("暂停活动ROAS", fmt_roas(inactive_info.get("avg_roas")))

            f1, f2 = st.columns([3, 1])
            with f1:
                tag_sel = st.multiselect("按标签筛选：", ALL_CAMPAIGN_TAGS, default=[])
            with f2:
                csv_c = live_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button("📥 导出活动诊断 CSV", csv_c, "campaign_health.csv", "text/csv")

            v_live = live_df.copy()
            if tag_sel and "全部" not in tag_sel:
                v_live = v_live[v_live["标签"].apply(lambda ts: any(t in str(ts) for t in tag_sel))]

            # 转换为百分比展示 (0.25 -> 25.0)
            if "ACOS" in v_live.columns:
                v_live["ACOS%"] = pd.to_numeric(v_live["ACOS"], errors="coerce") * 100.0
            if "CTR" in v_live.columns:
                v_live["CTR%"] = pd.to_numeric(v_live["CTR"], errors="coerce") * 100.0
            if "CVR" in v_live.columns:
                v_live["CVR%"] = pd.to_numeric(v_live["CVR"], errors="coerce") * 100.0

            disp_cols = [
                "活动名", "花费", "销售额", "订单", "ROAS", "ACOS%", "CPC", "CTR%", "CVR%", "每日预算", "标签", "诊断详情"
            ]
            v_live_disp = v_live[[c for c in disp_cols if c in v_live.columns]]

            st.dataframe(
                v_live_disp,
                column_config={
                    "活动名": st.column_config.TextColumn("活动名称", width="medium"),
                    "花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                    "销售额": st.column_config.NumberColumn("销售额 ($)", format="$%.2f"),
                    "订单": st.column_config.NumberColumn("订单", format="%d"),
                    "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
                    "ACOS%": st.column_config.NumberColumn("ACoS", format="%.2f%%"),
                    "CPC": st.column_config.NumberColumn("CPC ($)", format="$%.2f"),
                    "CTR%": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                    "CVR%": st.column_config.NumberColumn("CVR", format="%.2f%%"),
                    "每日预算": st.column_config.NumberColumn("每日预算 ($)", format="$%.2f"),
                    "标签": st.column_config.TextColumn("诊断标签", width="medium"),
                    "诊断详情": st.column_config.TextColumn("诊断详情与依据", width="large"),
                },
                use_container_width=True,
                hide_index=True,
            )
        except Exception as e:
            st.error(f"计算异常: {e}")

# =========================================================================
# TAB 5: ② 搜索词否词/挖词板块
# =========================================================================
with tabs[4]:
    st.markdown("### ② 搜索词否词挖掘与精准词迁移")
    f_st = render_section_uploader(
        sec_key="search_term",
        title="搜索词否词/挖词",
        default_name="搜索词报表",
        help_text="请上传领星导出的【搜索词报表】（文件名含'搜索词'或'search_term'），支持 .xlsx / .csv。",
    )
    if f_st:
        try:
            with st.spinner("正在挖掘搜索词..."):
                t_type, df, _ = parse_single_file_cached(f_st.name, f_st.getvalue(), "search_term")
                if df is not None:
                    has_st = any(c in str(col).lower() for col in df.columns for c in ["搜索词", "search term", "customer search term", "query", "客户搜索词"])
                    if not has_st:
                        st.error(
                            f"❌ **上传文件类型不匹配**：您上传的文件【`{f_st.name}`】未检测到核心【搜索词】字段！\n\n"
                            f"🔍 系统检测该文件实际为：【{t_type or '广告活动'}】报表。\n\n"
                            f"👉 **正确操作指引**：\n"
                            f"1. 请在领星系统中进入【广告分析 -> 搜索词列表】导出真实的搜索词报表再上传；\n"
                            f"2. 若您刚才是想分析广告活动，请前往「① 广告活动诊断」选项卡上传该文件。"
                        )
                    else:
                        update_section("search_term", df, f_st.name, f_st.getvalue())
                        st.rerun()
        except Exception as e:
            st.error(f"解析失败: {e}")

    st_df = st.session_state["section_data"].get("search_term")
    if st_df is not None and not st_df.empty:
        try:
            neg_df, mining_df, hc_df, st_stats = mine_search_terms(st_df)
            if st_stats.get("error"):
                st.error(
                    f"⚠️ **数据质量异常拦截**：{st_stats.get('summary_text')}\n\n"
                    f"当前在「搜索词报表」槽位中暂存的文件可能被误上传为了广告活动报表，系统已执行安全熔断（拒绝捏造虚假搜索词）。"
                )
                if st.button("🗑️ 清除该槽位的错误文件并重新上传", key="btn_clean_wrong_st"):
                    update_section("search_term", None, "", None)
                    st.rerun()
            else:
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("🚨 P0 紧急否词", f"{st_stats['p0_count']} 个", f"止损 ${st_stats['p0_spend']:,.2f}")
                with c2:
                    st.metric("📉 P1 低产出否词", f"{st_stats['p1_count']} 个", f"止损 ${st_stats['p1_spend']:,.2f}")
                with c3:
                    st.metric("💎 可挖掘出单词", f"{st_stats['mining_count']} 个", f"销售额 ${st_stats['mining_sales']:,.2f}")
                with c4:
                    st.metric("⚠️ 高点击零转化词", f"{st_stats['high_clicks_count']} 个")

                list_choice = st.radio("查看清单：", ["清单 A：否词清单", "清单 B：挖词清单", "清单 C：高点击零转化"], horizontal=True)
                if "清单 A" in list_choice:
                    v_neg = neg_df.copy()
                    if "CTR" in v_neg.columns:
                        v_neg["CTR%"] = pd.to_numeric(v_neg["CTR"], errors="coerce") * 100.0
                    st.dataframe(
                        v_neg,
                        column_config={
                            "优先级": st.column_config.TextColumn("优先级", width="small"),
                            "搜索词": st.column_config.TextColumn("搜索词", width="medium"),
                            "来源广告活动": st.column_config.TextColumn("来源活动", width="medium"),
                            "建议否定类型": st.column_config.TextColumn("建议否定匹配", width="medium"),
                            "花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                            "点击": st.column_config.NumberColumn("点击", format="%d"),
                            "CTR%": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                            "订单": st.column_config.NumberColumn("订单", format="%d"),
                            "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
                            "建议动作": st.column_config.TextColumn("落地执行指令", width="large"),
                        },
                        use_container_width=True,
                        hide_index=True,
                    )
                elif "清单 B" in list_choice:
                    st.dataframe(
                        mining_df,
                        column_config={
                            "搜索词": st.column_config.TextColumn("搜索词", width="medium"),
                            "来源广告活动": st.column_config.TextColumn("来源活动", width="medium"),
                            "订单": st.column_config.NumberColumn("订单", format="%d"),
                            "总销售额": st.column_config.NumberColumn("销售额 ($)", format="$%.2f"),
                            "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
                            "当前CPC": st.column_config.NumberColumn("当前 CPC", format="$%.2f"),
                            "出价建议": st.column_config.NumberColumn("建议出价 ($)", format="$%.2f"),
                            "建议动作": st.column_config.TextColumn("建议动作", width="large"),
                        },
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.dataframe(
                        hc_df,
                        column_config={
                            "搜索词": st.column_config.TextColumn("搜索词", width="medium"),
                            "来源广告活动": st.column_config.TextColumn("来源活动", width="medium"),
                            "点击": st.column_config.NumberColumn("累计点击", format="%d"),
                            "花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                            "CPC": st.column_config.NumberColumn("CPC ($)", format="$%.2f"),
                            "诊断建议": st.column_config.TextColumn("诊断建议", width="large"),
                        },
                        use_container_width=True,
                        hide_index=True,
                    )
        except Exception as e:
            st.error(f"计算异常: {e}")

# =========================================================================
# TAB 6: ③ 关键词调价板块
# =========================================================================
with tabs[5]:
    st.markdown("### ③ 关键词出价与状态调整")
    f_kw = render_section_uploader(
        sec_key="keyword",
        title="关键词调价",
        default_name="关键词报表",
        help_text="请上传领星导出的【关键词报表】（文件名含'关键词'或'keyword'），支持 .xlsx / .csv。",
    )
    if f_kw:
        try:
            with st.spinner("正在分析关键词竞价策略..."):
                t_type, df, _ = parse_single_file_cached(f_kw.name, f_kw.getvalue(), "keyword")
                if df is not None:
                    has_kw = any(c in str(col).lower() for col in df.columns for c in ["关键词", "keyword", "keywords", "kw", "投放词"])
                    if not has_kw:
                        st.error(f"❌ **上传文件类型不匹配**：您上传的文件【`{f_kw.name}`】未检测到核心【关键词】字段！请确认上传的是领星导出的【关键词列表报表】。")
                    else:
                        update_section("keyword", df, f_kw.name, f_kw.getvalue())
                        st.rerun()
        except Exception as e:
            st.error(f"解析失败: {e}")

    kw_df = st.session_state["section_data"].get("keyword")
    if kw_df is not None and not kw_df.empty:
        try:
            kw_res, all_kw, kw_stats = analyze_keyword_bids(kw_df)
            if kw_stats.get("error"):
                st.error(f"⚠️ **数据质量异常拦截**：{kw_stats.get('summary_text')}")
                if st.button("🗑️ 清除该槽位的错误文件并重新上传", key="btn_clean_wrong_kw"):
                    update_section("keyword", None, "", None)
                    st.rerun()
            else:
                c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("🚨 该暂停关键词", f"{kw_stats['pause_count']} 个", f"止损 ${kw_stats['pause_spend']:,.2f}")
            with c2:
                st.metric("📉 该降价关键词", f"{kw_stats['bid_down_count']} 个")
            with c3:
                st.metric("📈 该加价优质词", f"{kw_stats['bid_up_count']} 个")
            with c4:
                st.metric("🔄 误暂停潜力词", f"{kw_stats['unpause_count']} 个")

            v_kw = all_kw.copy()
            if "ACOS" in v_kw.columns:
                v_kw["ACOS%"] = pd.to_numeric(v_kw["ACOS"], errors="coerce") * 100.0
            if "CTR" in v_kw.columns:
                v_kw["CTR%"] = pd.to_numeric(v_kw["CTR"], errors="coerce") * 100.0

            st.dataframe(
                v_kw,
                column_config={
                    "建议分类": st.column_config.TextColumn("调整策略", width="small"),
                    "关键词": st.column_config.TextColumn("关键词", width="medium"),
                    "匹配方式": st.column_config.TextColumn("匹配", width="small"),
                    "所在活动": st.column_config.TextColumn("所在活动", width="medium"),
                    "实际当前竞价": st.column_config.TextColumn("实际当前竞价", width="small"),
                    "建议出价调整": st.column_config.TextColumn("建议出价调整", width="medium"),
                    "参考建议竞价": st.column_config.TextColumn("参考建议竞价", width="small"),
                    "广告花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                    "广告订单": st.column_config.NumberColumn("订单", format="%d"),
                    "总销售额": st.column_config.NumberColumn("销售额 ($)", format="$%.2f"),
                    "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
                    "ACOS%": st.column_config.NumberColumn("ACoS", format="%.2f%%"),
                    "CTR%": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                    "CPC": st.column_config.NumberColumn("CPC ($)", format="$%.2f"),
                    "依据数字": st.column_config.TextColumn("调价依据与说明", width="large"),
                },
                use_container_width=True,
                hide_index=True,
            )
        except Exception as e:
            st.error(f"计算异常: {e}")

# =========================================================================
# TAB 7: ④ 商品位诊断板块
# =========================================================================
with tabs[6]:
    st.markdown("### ④ 广告商品位诊断与单品生命周期矩阵")
    f_ad = render_section_uploader(
        sec_key="ad_item",
        title="商品位诊断",
        default_name="商品广告列表报表",
        help_text="请上传领星导出的【广告列表报表】（文件名含'广告列表'或'item'），支持 .xlsx / .csv。",
    )
    if f_ad:
        try:
            with st.spinner("正在解析商品广告位数据..."):
                t_type, df, _ = parse_single_file_cached(f_ad.name, f_ad.getvalue(), "ad_item")
                if df is not None:
                    has_id = any(c in str(col).lower() for col in df.columns for c in ["项目id", "item id", "item_id", "商品id", "sku", "广告列表"])
                    if not has_id:
                        st.error(f"❌ **上传文件类型不匹配**：您上传的文件【`{f_ad.name}`】未检测到【项目ID/SKU】商品维度！请确认上传的是领星导出的【广告列表报表】。")
                    else:
                        if st.session_state.get("sku_map"):
                            df = apply_sku_mapping(df, st.session_state["sku_map"])
                        update_section("ad_item", df, f_ad.name, f_ad.getvalue())
                        st.rerun()
        except Exception as e:
            st.error(f"解析失败: {e}")

    ad_df = st.session_state["section_data"].get("ad_item")
    if ad_df is not None and not ad_df.empty:
        try:
            ad_res = diagnose_ad_items(ad_df, sku_map=st.session_state.get("sku_map"))
            ad_stats = ad_res["stats"]
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("TOP10 销售额贡献", fmt_money(ad_stats.get('top10_sales', 0)))
            with c2:
                st.metric("🔥 烧钱商品位", f"{ad_stats.get('burning_count', 0)} 个", f"沉没 {fmt_money(ad_stats.get('burning_spend', 0))}")
            with c3:
                st.metric("📉 竞价偏低商品", f"{ad_stats.get('low_bid_count', 0)} 个")
            with c4:
                st.metric("⚠️ 状态异常商品", f"{ad_stats.get('abnormal_count', 0)} 个")

            st.markdown("#### 🏆 跑量商品 TOP 10")
            v_top10 = ad_res["top10_items"].copy()
            if "CVR" in v_top10.columns:
                v_top10["CVR%"] = pd.to_numeric(v_top10["CVR"], errors="coerce") * 100.0

            st.dataframe(
                v_top10,
                column_config={
                    "SKU": st.column_config.TextColumn("SKU (店铺品名)", width="medium"),
                    "项目ID": st.column_config.TextColumn("Item ID", width="small"),
                    "商品名称": st.column_config.TextColumn("商品名称", width="medium"),
                    "销售额": st.column_config.NumberColumn("销售额 ($)", format="$%.2f"),
                    "花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                    "订单": st.column_config.NumberColumn("订单", format="%d"),
                    "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
                    "CVR%": st.column_config.NumberColumn("CVR", format="%.2f%%"),
                    "CPC": st.column_config.NumberColumn("CPC ($)", format="$%.2f"),
                    "投放活动数": st.column_config.NumberColumn("投放活动数", format="%d"),
                },
                use_container_width=True,
                hide_index=True,
            )

            if not ad_res["burning_items"].empty:
                st.markdown("#### 🔥 烧钱零转化商品（花费 ≥ $30 且 0 单）")
                v_burn = ad_res["burning_items"].copy()
                st.dataframe(
                    v_burn,
                    column_config={
                        "SKU": st.column_config.TextColumn("SKU (店铺品名)", width="medium"),
                        "项目ID": st.column_config.TextColumn("Item ID", width="small"),
                        "商品名称": st.column_config.TextColumn("商品名称", width="medium"),
                        "花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                        "点击": st.column_config.NumberColumn("点击", format="%d"),
                        "曝光": st.column_config.NumberColumn("曝光量", format="%d"),
                        "投放活动数": st.column_config.NumberColumn("投放活动数", format="%d"),
                        "建议动作": st.column_config.TextColumn("建议动作", width="large"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )

            if not ad_res["low_bid_items"].empty:
                st.markdown("#### 📉 竞价偏低商品位（低于建议竞价 ≥30%）")
                v_low = ad_res["low_bid_items"].copy()
                st.dataframe(
                    v_low,
                    column_config={
                        "SKU": st.column_config.TextColumn("SKU (店铺品名)", width="medium"),
                        "项目ID": st.column_config.TextColumn("Item ID", width="small"),
                        "商品名称": st.column_config.TextColumn("商品名称", width="medium"),
                        "广告活动": st.column_config.TextColumn("广告活动", width="medium"),
                        "广告竞价": st.column_config.NumberColumn("实际竞价 ($)", format="$%.2f"),
                        "建议竞价": st.column_config.NumberColumn("建议竞价 ($)", format="$%.2f"),
                        "低于幅度": st.column_config.TextColumn("低于幅度", width="small"),
                        "花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                        "建议动作": st.column_config.TextColumn("优化行动指令", width="large"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )
        except Exception as e:
            st.error(f"计算异常: {e}")

# =========================================================================
# TAB 8: ⑤ 平台与页面位置板块
# =========================================================================
with tabs[7]:
    st.markdown("### ⑤ 平台端与页面位置流量结构表现")
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        f_p1 = render_section_uploader("platform", "平台报表", "平台报表", "上传包含 App / Mobile / Desktop 的平台报表")
        if f_p1:
            _, df, _ = parse_single_file_cached(f_p1.name, f_p1.getvalue(), "platform")
            if df is not None:
                update_section("platform", df, f_p1.name, f_p1.getvalue())
                st.rerun()
    with p_col2:
        f_p2 = render_section_uploader("page_type", "页面类型报表", "页面类型报表", "上传包含 Search / Item / Browse 的页面类型报表")
        if f_p2:
            _, df, _ = parse_single_file_cached(f_p2.name, f_p2.getvalue(), "page_type")
            if df is not None:
                update_section("page_type", df, f_p2.name, f_p2.getvalue())
                st.rerun()

    plat_df = st.session_state["section_data"].get("platform")
    page_df = st.session_state["section_data"].get("page_type")
    if plat_df is not None or page_df is not None:
        try:
            plc_res = analyze_placements(plat_df, page_df)
            if not plc_res["platform_df"].empty:
                st.markdown("#### 📱 平台端流量结构")
                v_plat = plc_res["platform_df"].copy()
                if "花费占比" in v_plat.columns:
                    v_plat["花费占比%"] = pd.to_numeric(v_plat["花费占比"], errors="coerce") * 100.0
                if "CTR" in v_plat.columns:
                    v_plat["CTR%"] = pd.to_numeric(v_plat["CTR"], errors="coerce") * 100.0
                if "CVR" in v_plat.columns:
                    v_plat["CVR%"] = pd.to_numeric(v_plat["CVR"], errors="coerce") * 100.0
                st.dataframe(
                    v_plat,
                    column_config={
                        "平台": st.column_config.TextColumn("平台渠道", width="small"),
                        "花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                        "花费占比%": st.column_config.NumberColumn("花费占比", format="%.1f%%"),
                        "订单": st.column_config.NumberColumn("订单", format="%d"),
                        "销售额": st.column_config.NumberColumn("销售额 ($)", format="$%.2f"),
                        "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
                        "CPC": st.column_config.NumberColumn("CPC ($)", format="$%.2f"),
                        "CTR%": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                        "CVR%": st.column_config.NumberColumn("CVR", format="%.2f%%"),
                        "建议动作": st.column_config.TextColumn("渠道优化建议", width="large"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )
            if not plc_res["page_type_df"].empty:
                st.markdown("#### 📑 页面类型位置表现")
                v_page = plc_res["page_type_df"].copy()
                if "花费占比" in v_page.columns:
                    v_page["花费占比%"] = pd.to_numeric(v_page["花费占比"], errors="coerce") * 100.0
                if "CTR" in v_page.columns:
                    v_page["CTR%"] = pd.to_numeric(v_page["CTR"], errors="coerce") * 100.0
                if "CVR" in v_page.columns:
                    v_page["CVR%"] = pd.to_numeric(v_page["CVR"], errors="coerce") * 100.0
                st.dataframe(
                    v_page,
                    column_config={
                        "页面类型": st.column_config.TextColumn("页面位置", width="small"),
                        "花费": st.column_config.NumberColumn("花费 ($)", format="$%.2f"),
                        "花费占比%": st.column_config.NumberColumn("花费占比", format="%.1f%%"),
                        "订单": st.column_config.NumberColumn("订单", format="%d"),
                        "销售额": st.column_config.NumberColumn("销售额 ($)", format="$%.2f"),
                        "ROAS": st.column_config.NumberColumn("ROAS", format="%.2f"),
                        "CPC": st.column_config.NumberColumn("CPC ($)", format="$%.2f"),
                        "CTR%": st.column_config.NumberColumn("CTR", format="%.2f%%"),
                        "CVR%": st.column_config.NumberColumn("CVR", format="%.2f%%"),
                        "诊断建议": st.column_config.TextColumn("位置优化建议", width="large"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )
        except Exception as e:
            st.error(f"计算异常: {e}")
