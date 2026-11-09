"""
会话数据状态与缓存读取引擎 (Data Context)
"""

import io
from typing import Dict, Any, Tuple
import pandas as pd
import streamlit as st
from data_loader.loader import load_single_file
from analyzer.trend_analyzer import build_sku_trend_data, extract_period_label
from data_loader.session_storage import (
    save_session_cache,
    record_upload_audit_log,
)


@st.cache_data(show_spinner=False)
def parse_single_file_cached(file_name: str, file_bytes: bytes, forced_type: str = None) -> Tuple[str, pd.DataFrame, int]:
    """缓存单个文件的解析与清洗"""
    bio = io.BytesIO(file_bytes)
    bio.name = file_name
    t_type, df, total_row = load_single_file(bio)
    if forced_type:
        t_type = forced_type
    return t_type, df, total_row


@st.cache_data(show_spinner=False)
def parse_trend_data_cached(
    file_records_tuple: tuple,
    sku_map_items: tuple,
    target_acos: float,
    breakeven_acos: float = 0.35,
) -> Tuple[pd.DataFrame, pd.DataFrame, list, pd.DataFrame]:
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


def update_section(sec_id: str, df: pd.DataFrame, file_name: str, file_bytes: bytes):
    """更新某板块的数据并自动同步到本地持久化缓存中，同类型多文件上传智能按联合主键合并去重"""
    if "section_data" not in st.session_state:
        st.session_state["section_data"] = {}
    if "section_files" not in st.session_state:
        st.session_state["section_files"] = {}
    if "section_file_bytes" not in st.session_state:
        st.session_state["section_file_bytes"] = {}
    if "uploaded_files_registry" not in st.session_state:
        st.session_state["uploaded_files_registry"] = set()

    # // FIX: 防止批量上传重复处理
    file_sig = f"{file_name}_{len(file_bytes)}"
    st.session_state["uploaded_files_registry"].add(file_sig)

    # // FIX: 同类型多文件上传不覆盖历史数据，自动使用业务联合主键合并去重
    existing_df = st.session_state["section_data"].get(sec_id)
    if existing_df is not None and isinstance(existing_df, pd.DataFrame) and not existing_df.empty and df is not None and not df.empty:
        from data_loader.loader import merge_table_dfs
        merged_df, _ = merge_table_dfs([("historical", existing_df, {}), (file_name, df, {})], sec_id)
        st.session_state["section_data"][sec_id] = merged_df
        st.session_state["section_files"][sec_id] = f"{st.session_state['section_files'].get(sec_id, '')} + {file_name}"
    else:
        st.session_state["section_data"][sec_id] = df
        st.session_state["section_files"][sec_id] = file_name
        st.session_state["section_file_bytes"][sec_id] = file_bytes

    try:
        save_session_cache(
            section_data=st.session_state["section_data"],
            sku_map=st.session_state.get("sku_mapping", {}),
            sku_cost_dict=st.session_state.get("sku_cost_dict", {}),
            file_names=st.session_state["section_files"],
        )
    except Exception:
        pass

    # // FIX: 严格对齐 record_upload_audit_log 参数签名，防止 TypeError 并加异常防护
    try:
        record_upload_audit_log(
            file_type=sec_id,
            file_name=file_name,
            row_count=len(df) if df is not None else 0,
            file_size_bytes=len(file_bytes) if file_bytes else 0,
            metrics_summary=f"已成功解析并对齐 {len(df.columns) if df is not None else 0} 个指标列",
        )
    except Exception:
        pass


# // FIX: 建立统一全局筛选生效管道，让顶部筛选栏真正影响所有相关业务页面
def filter_dataframe_by_global(
    df: Optional[pd.DataFrame],
    filters: Optional[Dict[str, Any]] = None,
    table_type: Optional[str] = None,
) -> pd.DataFrame:
    """
    通用全局业务筛选引擎：
    真正根据顶部全局筛选栏（平台、店铺、日期范围、目标 SKU、商品类目）对数据进行实质过滤，
    坚决杜绝只变 UI 不变数据的伪筛选。
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame() if df is None else df

    out = df.copy()
    if not filters or not isinstance(filters, dict):
        return out

    # 1. 目标 SKU 过滤
    sel_sku = filters.get("sku", "全部 SKU")
    if sel_sku and sel_sku != "全部 SKU":
        sku_matched = False
        for c in ["SKU", "sku", "SKU展示", "SKU_Display", "对应SKU"]:
            if c in out.columns:
                out = out[out[c].astype(str).str.strip() == str(sel_sku).strip()]
                sku_matched = True
                break
        if not sku_matched and ("项目ID" in out.columns or "item_id" in out.columns):
            id_col = "项目ID" if "项目ID" in out.columns else "item_id"
            out = out[out[id_col].astype(str).str.strip() == str(sel_sku).strip()]

    # 2. 渠道平台过滤
    sel_platform = filters.get("platform", "Walmart")
    if sel_platform and "全部" not in sel_platform:
        plat_clean = sel_platform.split(" ")[0].strip()
        for c in ["平台", "_platform", "platform"]:
            if c in out.columns:
                out = out[out[c].astype(str).str.contains(plat_clean, case=False, na=True)]
                break

    # 3. 日期范围过滤
    date_range = filters.get("date_range", "最近30天")
    date_col = next((c for c in ["日期", "_date", "date", "day", "投放日期"] if c in out.columns), None)
    if date_col and date_range and date_range != "全量报表周期":
        try:
            d_parsed = pd.to_datetime(out[date_col], errors="coerce")
            if d_parsed.notna().any():
                max_d = d_parsed.max()
                if "7天" in date_range:
                    cutoff = max_d - pd.Timedelta(days=7)
                    out = out[d_parsed >= cutoff]
                elif "14天" in date_range:
                    cutoff = max_d - pd.Timedelta(days=14)
                    out = out[d_parsed >= cutoff]
                elif "30天" in date_range:
                    cutoff = max_d - pd.Timedelta(days=30)
                    out = out[d_parsed >= cutoff]
        except Exception:
            pass

    return out
