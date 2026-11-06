import io
import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import openpyxl

# 候选列名识别库
ITEM_ID_CANDIDATES = [
    "项目id", "项目ID", "item id", "item_id", "itemid", "item_id(walmart)", 
    "沃尔玛id", "沃尔玛ID", "商品id", "商品ID", "广告项目id", "广告项目ID", "id",
    "listing id", "listing_id", "asin", "item number", "item_number"
]

SKU_CANDIDATES = [
    "sku id", "skuid", "sku_id", "sku", "SKU", "seller sku", "seller_sku", "sellersku", "msku", "MSKU",
    "自定义sku", "自定义SKU", "品名", "商品名称", "商品编码", "内部sku", "erp_sku", "平台sku", "店铺sku"
]

DATE_CANDIDATES = [
    "日期", "统计时间", "时间", "数据日期", "date", "Date", "day", "Day"
]

def _normalize_header(col_name: Any) -> str:
    """标准化列名便于模糊匹配"""
    if col_name is None:
        return ""
    return str(col_name).strip().lower().replace("_", "").replace(" ", "").replace("-", "")

def load_sku_mapping(file_obj: Any) -> Tuple[Dict[str, str], Optional[str]]:
    """
    解析用户上传的 SKU 映射表（支持 .xlsx, .xls, .csv）。
    返回：
        (sku_map, error_msg): 
        sku_map 为 {item_id_str: sku_str} 的映射字典。
    """
    if file_obj is None:
        return {}, None

    try:
        filename = getattr(file_obj, "name", "")
        if isinstance(file_obj, str):
            filename = file_obj
            if filename.endswith(".csv"):
                df = pd.read_csv(file_obj, dtype=str)
            else:
                df = pd.read_excel(file_obj, dtype=str)
        else:
            if hasattr(file_obj, "getvalue"):
                content = file_obj.getvalue()
                bio = io.BytesIO(content)
            else:
                bio = file_obj

            if filename.lower().endswith(".csv"):
                encodings = ["utf-8", "utf-8-sig", "gbk", "gb18030", "latin1"]
                loaded = False
                for enc in encodings:
                    try:
                        bio.seek(0)
                        df = pd.read_csv(bio, dtype=str, encoding=enc)
                        loaded = True
                        break
                    except Exception:
                        continue
                if not loaded:
                    return {}, "无法解析上传的 CSV 文件，请确保编码为 UTF-8 或 GBK。"
            else:
                bio.seek(0)
                df = pd.read_excel(bio, dtype=str)

        if df.empty:
            return {}, "上传的 SKU 映射表为空。"

        item_id_col = None
        sku_col = None

        for col in df.columns:
            norm = _normalize_header(col)
            if not item_id_col:
                for cand in ITEM_ID_CANDIDATES:
                    if _normalize_header(cand) in norm:
                        item_id_col = col
                        break
            if not sku_col:
                for cand in SKU_CANDIDATES:
                    if _normalize_header(cand) in norm:
                        sku_col = col
                        break

        if not item_id_col or not sku_col:
            if len(df.columns) >= 2:
                item_id_col = df.columns[0]
                sku_col = df.columns[1]
            else:
                return {}, f"未识别到 Item ID 与 SKU 列。请确保包含【项目ID】和【SKU】两列（当前列名：{list(df.columns)}）。"

        sku_map = {}
        for _, row in df.iterrows():
            raw_id = row[item_id_col]
            raw_sku = row[sku_col]
            if pd.isna(raw_id) or pd.isna(raw_sku):
                continue
            
            # 强化清洗：去除 .0、前后空格、换行
            id_str = str(raw_id).strip()
            if id_str.endswith(".0"):
                id_str = id_str[:-2]
            id_core = id_str.split(".")[0].strip()
            
            sku_str = str(raw_sku).strip()
            if id_core and id_core != "-" and sku_str and sku_str != "-":
                sku_map[id_core] = sku_str
                sku_map[id_str] = sku_str

        if not sku_map:
            return {}, "映射表中未找到有效的 Item ID 与 SKU 对应行。"

        return sku_map, None

    except Exception as e:
        return {}, f"解析 SKU 映射表失败: {str(e)}"

def apply_sku_mapping(df: pd.DataFrame, sku_map: Dict[str, str], id_col: str = "项目ID") -> pd.DataFrame:
    """
    将 SKU 映射应用到包含 Item ID 的 DataFrame 中。
    增加/更新两列：
    - 'SKU': 映射后的 SKU，未映射则保留原 Item ID
    - 'SKU展示' / 'SKU_Display': 便于展示的形式，如 'SKU (Item ID)'
    """
    if df is None or df.empty:
        return df

    out = df.copy()

    actual_id_col = None
    for cand in [id_col, "项目ID", "项目id", "item_id", "Item ID", "Item Id", "商品ID", "沃尔玛id"]:
        if cand in out.columns:
            actual_id_col = cand
            break

    if not actual_id_col:
        # 如果没有明确的 ID 列，但已有 SKU 列且传入了 sku_map
        if "SKU" in out.columns and sku_map:
            out["SKU"] = out["SKU"].apply(lambda v: sku_map.get(str(v).strip().split(".")[0], str(v).strip()))
            out["SKU展示"] = out["SKU"]
            out["SKU_Display"] = out["SKU"]
        return out

    def _get_sku(val: Any) -> str:
        if pd.isna(val):
            return "未知"
        raw = str(val).strip()
        if raw.endswith(".0"):
            raw = raw[:-2]
        s = raw.split(".")[0].strip()
        if sku_map:
            if s in sku_map:
                return sku_map[s]
            if raw in sku_map:
                return sku_map[raw]
        return s

    def _get_display(row: pd.Series) -> str:
        val = row.get(actual_id_col, "")
        if pd.isna(val):
            return "未知"
        raw = str(val).strip()
        if raw.endswith(".0"):
            raw = raw[:-2]
        s = raw.split(".")[0].strip()
        mapped_sku = row.get("SKU", s)
        if mapped_sku and mapped_sku != s and mapped_sku != "未知":
            return f"{mapped_sku} ({s})"
        return s

    out["SKU"] = out[actual_id_col].apply(_get_sku)
    disp_series = out.apply(_get_display, axis=1)
    out["SKU展示"] = disp_series
    out["SKU_Display"] = disp_series

    return out

def generate_sku_template() -> bytes:
    """
    生成标准的 Excel 模板文件供运营下载填写。
    """
    template_df = pd.DataFrame({
        "项目ID (Item ID)": ["10558959663", "16929360955", "14879556879"],
        "对应SKU (Seller SKU)": ["EM-BED-WHT-FULL", "EM-BED-WHT-KING", "EM-BED-DRW-WHT"],
        "品名备注(选填)": ["全尺寸铁架床-白色", "特大号储物床架-白色", "四抽屉带灯软包床"]
    })
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        template_df.to_excel(writer, index=False, sheet_name="SKU映射表")
    return output.getvalue()

def generate_daily_trend_template() -> bytes:
    """
    生成用于上传【SKU 每日广告数据变化趋势】的标准 Excel 示例模板。
    包含多天多 SKU 的花费、曝光、点击、订单与销售额数据。
    """
    sample_data = [
        {"日期": "2026-10-01", "项目ID": "10558959663", "对应SKU": "EM-BED-WHT-FULL", "广告花费": 25.40, "曝光量": 12500, "点击": 48, "广告订单": 2, "总销售额": 215.98},
        {"日期": "2026-10-02", "项目ID": "10558959663", "对应SKU": "EM-BED-WHT-FULL", "广告花费": 28.60, "曝光量": 13800, "点击": 52, "广告订单": 3, "总销售额": 323.97},
        {"日期": "2026-10-03", "项目ID": "10558959663", "对应SKU": "EM-BED-WHT-FULL", "广告花费": 32.10, "曝光量": 14200, "点击": 59, "广告订单": 4, "总销售额": 431.96},
        {"日期": "2026-10-01", "项目ID": "16929360955", "对应SKU": "EM-BED-WHT-KING", "广告花费": 18.20, "曝光量": 8900, "点击": 35, "广告订单": 1, "总销售额": 139.99},
        {"日期": "2026-10-02", "项目ID": "16929360955", "对应SKU": "EM-BED-WHT-KING", "广告花费": 22.50, "曝光量": 9400, "点击": 41, "广告订单": 0, "总销售额": 0.00},
        {"日期": "2026-10-03", "项目ID": "16929360955", "对应SKU": "EM-BED-WHT-KING", "广告花费": 35.80, "曝光量": 11200, "点击": 62, "广告订单": 0, "总销售额": 0.00},
        {"日期": "2026-10-01", "项目ID": "14879556879", "对应SKU": "EM-BED-DRW-WHT", "广告花费": 12.00, "曝光量": 6500, "点击": 25, "广告订单": 1, "总销售额": 159.00},
        {"日期": "2026-10-02", "项目ID": "14879556879", "对应SKU": "EM-BED-DRW-WHT", "广告花费": 14.50, "曝光量": 7200, "点击": 28, "广告订单": 2, "总销售额": 318.00},
        {"日期": "2026-10-03", "项目ID": "14879556879", "对应SKU": "EM-BED-DRW-WHT", "广告花费": 16.00, "曝光量": 7800, "点击": 31, "广告订单": 3, "总销售额": 477.00},
    ]
    df = pd.DataFrame(sample_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="每日广告数据趋势")
    return output.getvalue()
