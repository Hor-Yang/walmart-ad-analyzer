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
    """更新某板块的数据并自动同步到本地持久化缓存中"""
    if "section_data" not in st.session_state:
        st.session_state["section_data"] = {}
    if "section_files" not in st.session_state:
        st.session_state["section_files"] = {}
    if "section_file_bytes" not in st.session_state:
        st.session_state["section_file_bytes"] = {}

    st.session_state["section_data"][sec_id] = df
    st.session_state["section_files"][sec_id] = file_name
    st.session_state["section_file_bytes"][sec_id] = file_bytes

    save_session_cache(
        st.session_state["section_data"],
        st.session_state["section_files"],
        st.session_state["section_file_bytes"],
    )
    record_upload_audit_log(
        file_name=file_name,
        section_id=sec_id,
        table_type=sec_id,
        row_count=len(df),
        columns=list(df.columns),
        status="成功",
    )
