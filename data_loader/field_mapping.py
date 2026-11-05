from typing import Any, Dict, List, Optional
import pandas as pd

# 全局标准字段别名映射库
FIELD_MAPPING: Dict[str, List[str]] = {
    "search_term": [
        "搜索词", "customer search term", "search term", "search_term", "query", "客户搜索词"
    ],
    "keyword": [
        "关键词", "keyword", "keywords", "kw", "投放词", "targeting", "投放关键词"
    ],
    "campaign": [
        "广告活动", "广告活动名称", "campaign name", "campaign", "活动名称", "活动名"
    ],
    "ad_group": [
        "广告组", "广告组名称", "ad group", "ad_group", "adgroup", "ad group name"
    ],
    "status": [
        "广告活动状态", "关键词状态", "状态", "status", "state", "campaign status", "keyword status"
    ],
    "match_type": [
        "匹配方式", "match type", "match_type", "matchtype", "匹配类型"
    ],
    "spend": [
        "广告花费", "花费", "spend", "cost", "ad spend", "总花费"
    ],
    "impressions": [
        "曝光量", "曝光", "impressions", "impression", "impr"
    ],
    "clicks": [
        "点击", "点击量", "clicks", "click"
    ],
    "orders": [
        "广告订单", "订单", "orders", "order", "conversions", "转化数", "14天订单数"
    ],
    "sales": [
        "总销售额", "销售额", "sales", "total sales", "attributed sales", "广告销售额", "14天销售额"
    ],
    "actual_bid": [
        "当前竞价", "广告竞价", "实际出价", "实际竞价", "关键词竞价", "出价", "bid", "current bid", "current_bid"
    ],
    "suggested_bid": [
        "建议竞价", "领星建议竞价", "系统建议竞价", "suggested bid", "suggested_bid", "recommended bid"
    ],
    "item_id": [
        "项目ID", "item id", "item_id", "商品ID", "listing id", "asin", "itemid"
    ],
    "sku": [
        "sku", "平台sku", "店铺sku", "seller sku", "sellersku"
    ],
    "date": [
        "日期", "date", "day", "周期", "投放日期", "time", "统计日期"
    ],
    "daily_budget": [
        "每日预算", "日预算", "daily budget", "daily_budget", "预算", "budget", "总预算"
    ],
    "platform": [
        "平台", "platform", "设备", "device", "渠道"
    ],
    "page_type": [
        "页面类型", "page type", "page_type", "placement", "广告位", "位置"
    ],
}

# 中文标准显示名称
CANONICAL_NAMES: Dict[str, str] = {
    "search_term": "搜索词",
    "keyword": "关键词",
    "campaign": "广告活动",
    "ad_group": "广告组",
    "status": "状态",
    "match_type": "匹配方式",
    "spend": "广告花费",
    "impressions": "曝光量",
    "clicks": "点击",
    "orders": "广告订单",
    "sales": "总销售额",
    "actual_bid": "实际竞价",
    "suggested_bid": "建议竞价",
    "item_id": "项目ID",
    "sku": "SKU",
    "date": "日期",
    "daily_budget": "每日预算",
    "platform": "平台",
    "page_type": "页面类型",
}

def resolve_column(df: pd.DataFrame, canonical_key: str) -> Optional[str]:
    """在 DataFrame 中智能查找匹配全局映射字段的真实列名"""
    if df is None or df.empty:
        return None
    aliases = FIELD_MAPPING.get(canonical_key, [])
    # 优先精确匹配
    for col in df.columns:
        c_clean = str(col).strip().lower()
        # 实际出价需特殊防护，严禁匹配任何包含建议/suggest的列
        if canonical_key == "actual_bid" and any(ex in c_clean for ex in ["建议", "suggest", "recommend"]):
            continue
        for al in aliases:
            if al == c_clean:
                return col
    # 再次子串匹配
    for col in df.columns:
        c_clean = str(col).strip().lower()
        if canonical_key == "actual_bid" and any(ex in c_clean for ex in ["建议", "suggest", "recommend"]):
            continue
        for al in aliases:
            if al in c_clean:
                return col
    return None

def standardize_dataframe_columns(df: pd.DataFrame, keys: Optional[List[str]] = None) -> pd.DataFrame:
    """批量根据全局映射字典将 DataFrame 列名重命名为中文标准列名"""
    if df is None or df.empty:
        return df
    res = df.copy()
    target_keys = keys if keys else list(FIELD_MAPPING.keys())
    rename_dict = {}
    for k in target_keys:
        found_col = resolve_column(res, k)
        std_name = CANONICAL_NAMES.get(k, k)
        if found_col and found_col != std_name:
            if std_name in res.columns:
                res = res.drop(columns=[std_name])
            rename_dict[found_col] = std_name
    if rename_dict:
        res = res.rename(columns=rename_dict)
    return res
