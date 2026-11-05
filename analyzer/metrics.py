import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Union

# 基础加总指标列
BASE_SUM_COLS = [
    "曝光量",
    "点击",
    "广告花费",
    "广告订单",
    "广告销量",
    "总销售额",
    "品牌新买家订单",
]

def safe_divide(
    numerator: Union[pd.Series, float, int],
    denominator: Union[pd.Series, float, int],
) -> Union[pd.Series, Optional[float]]:
    """
    安全除法：
    分母为 0、NaN 或空时返回 None（Series模式下返回 np.nan/None），
    严格避免 ZeroDivisionError。
    """
    if isinstance(numerator, pd.Series) or isinstance(denominator, pd.Series):
        den_clean = pd.Series(denominator).replace(0, np.nan)
        res = pd.Series(numerator) / den_clean
        res = res.replace([np.inf, -np.inf], np.nan)
        # 将 NaN 替换为 None 对象以便前端或字典使用
        return res.where(res.notna(), None)
    
    # 标量模式
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return None
    if numerator is None or pd.isna(numerator):
        return 0.0
    return float(numerator) / float(denominator)

def agg_metrics(
    df: pd.DataFrame,
    group_col: Optional[Union[str, List[str]]] = None,
) -> pd.DataFrame:
    """
    通用指标聚合计算模块：
    核心原则：所有比率指标必须用【分子分母先加总再相除】重算，禁止对表内现成比率列求平均。

    参数：
    - df: 包含明细数据的 DataFrame
    - group_col: 分组列名（可选）。若指定按该列 groupby；否则进行全表整体汇总。

    输出字段：
    - 绝对值：曝光量、点击、广告花费、广告订单、广告销量、总销售额、（品牌新买家订单）
    - 比率指标：
        CTR = 点击 / 曝光量
        CPC = 广告花费 / 点击
        CVR = 广告订单 / 点击
        CPA = 广告花费 / 广告订单
        ROAS = 总销售额 / 广告花费
        ACOS = 广告花费 / 总销售额
        AOV = 总销售额 / 广告订单
        品牌新买家订单占比 = 品牌新买家订单 / 广告订单
    分母为 0 时对应比率返回 None（在 DataFrame 中表现为 None/NaN，前端显示 N/A）。
    """
    if df is None or df.empty:
        empty_cols = (
            ([group_col] if isinstance(group_col, str) else list(group_col or []))
            + BASE_SUM_COLS
            + [
                "CTR", "CPC", "CVR", "CPA",
                "ROAS", "ACOS", "AOV", "品牌新买家订单占比"
            ]
        )
        return pd.DataFrame(columns=empty_cols)

    # 确保所需加总字段存在（不存在则补 0）
    work_df = df.copy()
    for col in BASE_SUM_COLS:
        if col not in work_df.columns:
            work_df[col] = 0.0

    # 1. 先进行分子分母的绝对值求和
    if group_col is not None:
        grouped = work_df.groupby(group_col, as_index=False)[BASE_SUM_COLS].sum()
    else:
        sums = work_df[BASE_SUM_COLS].sum()
        grouped = pd.DataFrame([sums])

    # 2. 分子分母先加总、再相除重算比率
    grouped["CTR"] = safe_divide(grouped["点击"], grouped["曝光量"])
    grouped["CPC"] = safe_divide(grouped["广告花费"], grouped["点击"])
    grouped["CVR"] = safe_divide(grouped["广告订单"], grouped["点击"])
    grouped["CPA"] = safe_divide(grouped["广告花费"], grouped["广告订单"])
    grouped["ROAS"] = safe_divide(grouped["总销售额"], grouped["广告花费"])
    grouped["ACOS"] = safe_divide(grouped["广告花费"], grouped["总销售额"])
    grouped["AOV"] = safe_divide(grouped["总销售额"], grouped["广告订单"])
    grouped["品牌新买家订单占比"] = safe_divide(grouped["品牌新买家订单"], grouped["广告订单"])

    # 规范输出列顺序
    out_cols = []
    if group_col is not None:
        if isinstance(group_col, list):
            out_cols.extend(group_col)
        else:
            out_cols.append(group_col)
    
    out_cols.extend([
        "曝光量", "点击", "广告花费", "广告订单", "广告销量", "总销售额",
        "CTR", "CPC", "CVR", "CPA", "ROAS", "ACOS", "AOV", "品牌新买家订单占比"
    ])

    return grouped[out_cols]

def summarize_overview(data_dict: Dict[str, Optional[pd.DataFrame]]) -> Dict[str, Any]:
    """
    汇总 6 张表里最全的 campaign 广告活动表（若无则依次 fallback 到 platform、ad_item），
    返回大盘整体宏观指标字典：
    - 大盘总花费
    - 总销售额
    - 总订单
    - 整体ROAS
    - 整体CTR
    - CPC
    - CVR
    - CPA
    - AOV
    - 新客占比
    分母为 0 时对应比率返回 None。
    """
    # 优先选取最全面的 campaign 表
    df = data_dict.get("campaign")
    if df is None or df.empty:
        df = data_dict.get("platform")
    if df is None or df.empty:
        df = data_dict.get("ad_item")
    
    if df is None or df.empty:
        return {
            "大盘总花费": 0.0,
            "总销售额": 0.0,
            "总订单": 0,
            "整体ROAS": None,
            "整体CTR": None,
            "CPC": None,
            "CVR": None,
            "CPA": None,
            "AOV": None,
            "新客占比": None,
            "曝光量": 0,
            "点击": 0,
            "广告销量": 0,
            "ACOS": None,
        }

    # 使用分子分母整体加总原则
    impressions = float(df["曝光量"].sum()) if "曝光量" in df.columns else 0.0
    clicks = float(df["点击"].sum()) if "点击" in df.columns else 0.0
    spend = float(df["广告花费"].sum()) if "广告花费" in df.columns else 0.0
    orders = float(df["广告订单"].sum()) if "广告订单" in df.columns else 0.0
    sales_units = float(df["广告销量"].sum()) if "广告销量" in df.columns else 0.0
    total_sales = float(df["总销售额"].sum()) if "总销售额" in df.columns else 0.0
    new_buyer_orders = float(df["品牌新买家订单"].sum()) if "品牌新买家订单" in df.columns else 0.0

    return {
        "大盘总花费": spend,
        "总销售额": total_sales,
        "总订单": int(orders),
        "整体ROAS": safe_divide(total_sales, spend),
        "整体CTR": safe_divide(clicks, impressions),
        "CPC": safe_divide(spend, clicks),
        "CVR": safe_divide(orders, clicks),
        "CPA": safe_divide(spend, orders),
        "AOV": safe_divide(total_sales, orders),
        "新客占比": safe_divide(new_buyer_orders, orders),
        "曝光量": int(impressions),
        "点击": int(clicks),
        "广告销量": int(sales_units),
        "ACOS": safe_divide(spend, total_sales),
    }
