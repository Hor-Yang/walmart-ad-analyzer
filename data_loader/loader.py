import io
import os
import re
import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd
import warnings

# 忽略 openpyxl 的样式警告
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# 6 种报表类型定义及其特征维度列
TABLE_CONFIG: Dict[str, Dict[str, str]] = {
    "search_term": {
        "name": "搜索词报表",
        "keyword": "搜索词",
        "dim_col": "搜索词",
    },
    "keyword": {
        "name": "关键词报表",
        "keyword": "关键词",
        "dim_col": "关键词",
    },
    "campaign": {
        "name": "广告活动报表",
        "keyword": "广告活动",
        "dim_col": "广告活动",
    },
    "page_type": {
        "name": "页面类型报表",
        "keyword": "页面类型",
        "dim_col": "页面类型",
    },
    "platform": {
        "name": "平台报表",
        "keyword": "平台",
        "dim_col": "平台",
    },
    "ad_item": {
        "name": "商品广告列表",
        "keyword": "广告列表",
        "dim_col": "项目ID",
    },
}

# 文本/维度类列名单（这些列保持字符串格式，不强转数值）
DIMENSION_COLUMNS = {
    "广告账号", "广告活动状态", "关键词状态", "广告活动", "关键词", "匹配方式", "广告组",
    "创建日期", "开始时间", "结束时间", "预算类型", "广告状态", "项目ID",
    "广告", "审核状态", "活动类型", "搜索词", "平台", "页面类型"
}

def identify_table_type(filename: str) -> Optional[str]:
    """
    根据文件名关键词识别报表类型：
    - "搜索词" / "search_term" -> search_term
    - "关键词" / "keyword" -> keyword
    - "广告活动" / "campaign" -> campaign
    - "页面类型" / "page_type" -> page_type
    - "平台" / "platform" -> platform
    - "广告列表" / "item" / "sku" / "product" / "趋势" / "trend" / "daily" -> ad_item
    """
    fn = os.path.basename(str(filename))
    fn_lower = fn.lower()

    if "搜索词" in fn or "search_term" in fn_lower or "searchterm" in fn_lower:
        return "search_term"
    elif "关键词" in fn or "keyword" in fn_lower:
        return "keyword"
    elif "广告活动" in fn or "campaign" in fn_lower:
        return "campaign"
    elif "页面类型" in fn or "page_type" in fn_lower or "pagetype" in fn_lower:
        return "page_type"
    elif "平台" in fn or "platform" in fn_lower:
        return "platform"
    elif ("广告列表" in fn or "item" in fn_lower or "sku" in fn_lower or "product" in fn_lower or "趋势" in fn or "trend" in fn_lower or "daily" in fn_lower) and "广告活动" not in fn:
        return "ad_item"
    return None

def identify_table_type_from_columns(columns: Any) -> Optional[str]:
    """
    当文件名无法判断时，根据表格表头特征列智能推断报表类型（支持中英文双语特征列）。
    """
    col_str = " ".join([str(c).lower().strip() for c in columns])
    
    if "search term" in col_str or "搜索词" in col_str:
        return "search_term"
    if "item id" in col_str or "sku id" in col_str or "项目id" in col_str or "广告列表" in col_str or "item name" in col_str:
        return "ad_item"
    if "keyword" in col_str or "关键词" in col_str or "建议竞价" in col_str:
        return "keyword"
    if "page type" in col_str or "页面类型" in col_str:
        return "page_type"
    if "platform" in col_str or "平台" in col_str:
        return "platform"
    if "campaign" in col_str or "广告活动" in col_str:
        return "campaign"
    return None

def clean_numeric_value(val: Any) -> float:
    """清理单个数值字符串，支持带%、货币符号、短横线或空值"""
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    
    s = str(val).strip()
    if s in ("", "-", "None", "nan", "--"):
        return 0.0
    
    is_pct = s.endswith("%")
    if is_pct:
        s = s[:-1].strip()
    
    # 移除千分位逗号与货币符号
    s = re.sub(r"[,$￥ ]", "", s)
    try:
        num = float(s)
        return num / 100.0 if is_pct else num
    except (ValueError, TypeError):
        return 0.0

def clean_numeric_series(series: pd.Series) -> pd.Series:
    """批量清洗数值列，空值/'-'转为 0.0"""
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0.0)
    return series.apply(clean_numeric_value)

def parse_and_clean_table(
    raw_df: pd.DataFrame, table_type: str
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    解析清洗单张报表：
    1. 提取第 1 行领星汇总行（存入 total_row）
    2. 过滤掉所有汇总行（包括领星分页导出重复出现的汇总行）
    3. 数值列标准化（转为 float，空值和'-'填充为 0）
    4. 销售口径修正：计算并新增 '总销售额' = 直接销售额 + 关联销量额
    5. 将校验元数据存入 df.attrs
    """
    if raw_df.empty:
        empty_df = pd.DataFrame()
        empty_df.attrs["total_row"] = {}
        empty_df.attrs["validation"] = {
            "total_spend": 0.0,
            "detail_spend": 0.0,
            "diff_abs": 0.0,
            "diff_pct": 0.0,
            "is_valid": True,
            "row_count": 0,
        }
        return empty_df, {}

    # 0. 自动标准化中英文列名
    from analyzer.trend_analyzer import normalize_columns
    raw_df = normalize_columns(raw_df)

    first_col = raw_df.columns[0]
    dim_col = TABLE_CONFIG.get(table_type, {}).get("dim_col")

    # 1. 检查首行是否为领星汇总行（以 '-' 为特征）
    has_total_row = (str(raw_df[first_col].iloc[0]).strip() == "-")
    if not has_total_row and dim_col and dim_col in raw_df.columns:
        has_total_row = (str(raw_df[dim_col].iloc[0]).strip() == "-")

    if has_total_row:
        total_row = raw_df.iloc[0].to_dict()
        is_total_mask = raw_df[first_col].astype(str).str.strip() == "-"
        if dim_col and dim_col in raw_df.columns:
            is_total_mask = is_total_mask | (raw_df[dim_col].astype(str).str.strip() == "-")
        detail_df = raw_df[~is_total_mask].copy()
    else:
        total_row = {}
        detail_df = raw_df.copy()

    # 2. 数值列标准化
    for col in detail_df.columns:
        if col not in DIMENSION_COLUMNS and col not in ["SKU", "日期", "周期"]:
            detail_df[col] = clean_numeric_series(detail_df[col])

    # 3. 销售口径修正：统一生成 '总销售额'
    if "总销售额" not in detail_df.columns or detail_df["总销售额"].sum() == 0:
        direct_sales_col = "直接销售额" if "直接销售额" in detail_df.columns else None
        assoc_sales_col = (
            "关联销量额"
            if "关联销量额" in detail_df.columns
            else ("关联销售额" if "关联销售额" in detail_df.columns else None)
        )
        if direct_sales_col and assoc_sales_col:
            detail_df["总销售额"] = detail_df[direct_sales_col] + detail_df[assoc_sales_col]
        elif direct_sales_col:
            detail_df["总销售额"] = detail_df[direct_sales_col]
        elif "广告销售额" in detail_df.columns:
            detail_df["总销售额"] = detail_df["广告销售额"]
        else:
            detail_df["总销售额"] = 0.0

    # 4. 计算花费校验
    detail_spend = float(detail_df["广告花费"].sum()) if "广告花费" in detail_df.columns else 0.0
    if has_total_row:
        total_spend = clean_numeric_value(total_row.get("广告花费", 0.0))
        diff_abs = abs(detail_spend - total_spend)
        diff_pct = (diff_abs / total_spend * 100.0) if total_spend > 0 else 0.0
        is_valid = diff_pct <= 1.0
    else:
        total_spend = detail_spend
        diff_abs = 0.0
        diff_pct = 0.0
        is_valid = True

    validation_info = {
        "table_type": table_type,
        "table_name": TABLE_CONFIG.get(table_type, {}).get("name", table_type),
        "total_spend": round(total_spend, 2),
        "detail_spend": round(detail_spend, 2),
        "diff_abs": round(diff_abs, 2),
        "diff_pct": round(diff_pct, 4),
        "is_valid": is_valid,
        "row_count": len(detail_df),
        "has_total_row": has_total_row,
    }

    detail_df.attrs["total_row"] = total_row
    detail_df.attrs["validation"] = validation_info

    return detail_df, total_row

def load_single_file(file_obj: Any) -> Tuple[Optional[str], Optional[pd.DataFrame], Dict[str, Any]]:
    """
    读取单个文件（支持本地文件路径字符串/Path 或 Streamlit UploadedFile，支持 .xlsx, .xls, .csv），
    返回 (table_type, detail_df, total_row)。
    """
    if isinstance(file_obj, (str, Path)):
        filename = os.path.basename(str(file_obj))
        table_type = identify_table_type(filename)
        if str(file_obj).lower().endswith(".csv"):
            raw_df = pd.DataFrame()
            for enc in ["utf-8", "utf-8-sig", "gbk", "latin1"]:
                try:
                    raw_df = pd.read_csv(file_obj, encoding=enc)
                    break
                except Exception:
                    continue
        else:
            raw_df = pd.read_excel(file_obj)
        
        if not table_type and not raw_df.empty:
            table_type = identify_table_type_from_columns(raw_df.columns)
        if not table_type:
            return None, None, {}
    else:
        # Streamlit UploadedFile 对象
        filename = getattr(file_obj, "name", "unknown.xlsx")
        table_type = identify_table_type(filename)
        
        is_csv = filename.lower().endswith(".csv")
        if hasattr(file_obj, "getvalue"):
            content = file_obj.getvalue()
            if is_csv:
                loaded = False
                for enc in ["utf-8", "utf-8-sig", "gbk", "latin1"]:
                    try:
                        raw_df = pd.read_csv(io.BytesIO(content), encoding=enc)
                        loaded = True
                        break
                    except Exception:
                        continue
                if not loaded:
                    raw_df = pd.DataFrame()
            else:
                raw_df = pd.read_excel(io.BytesIO(content))
        else:
            if is_csv:
                raw_df = pd.read_csv(file_obj)
            else:
                raw_df = pd.read_excel(file_obj)

        if not table_type and not raw_df.empty:
            table_type = identify_table_type_from_columns(raw_df.columns)
        if not table_type:
            return None, None, {}

    detail_df, total_row = parse_and_clean_table(raw_df, table_type)
    return table_type, detail_df, total_row

def load_all(
    uploaded_files: List[Any],
    sku_map: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    统一数据读取函数：
    接收上传的文件列表（或本地文件路径列表），
    返回字典 {'search_term': df, 'keyword': df, 'campaign': df, 'ad_item': df, 'platform': df, 'page_type': df}，
    缺失的表对应值为 None。
    额外支持多期广告列表记录 tables['_ad_item_records'] = [{'filename': ..., 'period': ..., 'df': ...}, ...]。
    如果传入 sku_map，自动为 ad_item 映射 SKU。
    """
    tables: Dict[str, Any] = {
        "search_term": None,
        "keyword": None,
        "campaign": None,
        "ad_item": None,
        "platform": None,
        "page_type": None,
        "_ad_item_records": [],
    }

    if not uploaded_files:
        return tables

    # 如果传入的是目录路径字符串或 Path 对象，自动读取该目录下所有表格文件
    if isinstance(uploaded_files, (str, Path)) and os.path.isdir(str(uploaded_files)):
        dir_path = str(uploaded_files)
        files = []
        for ext in ("*.xlsx", "*.xls", "*.csv"):
            files.extend(glob.glob(os.path.join(dir_path, ext)))
        uploaded_files = files
    elif isinstance(uploaded_files, (str, Path)):
        uploaded_files = [str(uploaded_files)]

    from .sku_mapper import apply_sku_mapping

    for file_obj in uploaded_files:
        table_type, df, total_row = load_single_file(file_obj)
        if not table_type:
            continue

        fname = getattr(file_obj, "name", os.path.basename(str(file_obj)) if isinstance(file_obj, (str, Path)) else "")

        if table_type == "ad_item" and df is not None:
            # 记录每一次上传的广告列表报表（用于多期/每日趋势分析）
            tables["_ad_item_records"].append({
                "filename": fname,
                "df": df.copy(),
            })

        if table_type in tables:
            # 若同一个类型上传了多个文件，保留最新的或首个
            if tables[table_type] is None:
                tables[table_type] = df
            else:
                # 若已存在且是 ad_item，则合并或由多期看板处理
                pass

    # 应用 SKU 映射
    if tables["ad_item"] is not None and sku_map:
        tables["ad_item"] = apply_sku_mapping(tables["ad_item"], sku_map)

    return tables

def get_validation_summary(tables: Dict[str, Optional[pd.DataFrame]]) -> List[Dict[str, Any]]:
    """
    汇总所有已识别报表的校验信息
    """
    summary = []
    for key, cfg in TABLE_CONFIG.items():
        df = tables.get(key)
        if df is not None:
            val = df.attrs.get("validation", {})
            summary.append(val)
        else:
            summary.append({
                "table_type": key,
                "table_name": cfg["name"],
                "total_spend": 0.0,
                "detail_spend": 0.0,
                "diff_abs": 0.0,
                "diff_pct": 0.0,
                "is_valid": False,
                "row_count": 0,
                "missing": True,
            })
    return summary
