"""
CrossBorder BI · 多平台表格数据适配器 (Multi-Platform Tabular Adapter Engine)
职责：
1. 统一处理跨平台（Walmart、Amazon、Wayfair 等）通过文件导入的异构业务报表；
2. 依据各平台官方口径提取归因窗口（如 Walmart 14天 Last Touch、Amazon 7天归因）；
3. 规范化映射字段至 CDM 标准事实模型 (Canonical Data Model)。
"""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


class BaseReportAdapter(ABC):
    """跨平台表格数据适配器基准抽象类"""

    @abstractmethod
    def get_platform_name(self) -> str:
        """平台标识"""
        pass

    @abstractmethod
    def get_attribution_window_days(self) -> int:
        """平台默认广告归因窗口天数"""
        pass

    @abstractmethod
    def sniff_report_type(self, filename: str, df: pd.DataFrame) -> str:
        """根据文件名与字段特征识别具体报表类型"""
        pass

    @abstractmethod
    def to_canonical_ad_performance(
        self,
        raw_df: pd.DataFrame,
        store_id: str = "default_store",
        source_file: str = "",
        date_str: str = "全周期",
    ) -> pd.DataFrame:
        """将原始表格转换为统一标准广告事实表"""
        pass


class WalmartTabularAdapter(BaseReportAdapter):
    """Walmart 官方与领星导出报表适配器"""

    def get_platform_name(self) -> str:
        return "walmart"

    def get_attribution_window_days(self) -> int:
        return 14  # Walmart 平台标准 14 天归因

    def sniff_report_type(self, filename: str, df: pd.DataFrame) -> str:
        fn = str(filename).lower()
        cols = [str(c).strip().lower() for c in df.columns]

        if "search_term" in fn or "搜索词" in fn or any(c in cols for c in ["搜索词", "customer search term"]):
            return "search_term"
        if "keyword" in fn or "关键词" in fn or any(c in cols for c in ["关键词", "keyword"]):
            return "keyword"
        if "item" in fn or "商品广告" in fn or any(c in cols for c in ["项目id", "item id"]):
            return "ad_item"
        if "campaign" in fn or "广告活动" in fn:
            return "campaign"
        if "platform" in fn or "终端" in fn or "平台" in fn:
            return "platform"
        if "page" in fn or "页面类型" in fn:
            return "page_type"
        return "ad_item"

    def to_canonical_ad_performance(
        self,
        raw_df: pd.DataFrame,
        store_id: str = "default_store",
        source_file: str = "",
        date_str: str = "全周期",
    ) -> pd.DataFrame:
        if raw_df.empty:
            return pd.DataFrame()

        df = raw_df.copy()
        
        # 字段映射
        item_col = next((c for c in ["项目ID", "item_id", "Item ID", "商品ID"] if c in df.columns), None)
        camp_col = next((c for c in ["广告活动", "活动名", "campaign", "Campaign"] if c in df.columns), None)
        spend_col = next((c for c in ["广告花费", "花费", "spend", "cost"] if c in df.columns), None)
        sales_col = next((c for c in ["总销售额", "销售额", "sales", "attributed sales"] if c in df.columns), None)
        ord_col = next((c for c in ["广告订单", "订单量", "订单", "orders"] if c in df.columns), None)
        clk_col = next((c for c in ["点击", "点击量", "clicks"] if c in df.columns), None)
        imp_col = next((c for c in ["曝光", "曝光量", "impressions"] if c in df.columns), None)
        date_col = next((c for c in ["日期", "date", "day", "统计时间"] if c in df.columns), None)

        rows = []
        from .catalog_service import get_catalog_service
        catalog = get_catalog_service()

        for idx, r in df.iterrows():
            raw_id = str(r[item_col]).split(".")[0].strip() if item_col else f"WM-ITEM-{idx+1}"
            if raw_id in ("-", "", "nan", "None"):
                continue
            master_sku = catalog.resolve_master_sku(raw_id, fallback=raw_id)
            
            spend = float(pd.to_numeric(r[spend_col], errors="coerce")) if spend_col else 0.0
            sales = float(pd.to_numeric(r[sales_col], errors="coerce")) if sales_col else 0.0
            orders = int(pd.to_numeric(r[ord_col], errors="coerce")) if ord_col else 0
            clicks = int(pd.to_numeric(r[clk_col], errors="coerce")) if clk_col else 0
            impressions = int(pd.to_numeric(r[imp_col], errors="coerce")) if imp_col else 0
            e_date = str(r[date_col]).strip() if (date_col and pd.notna(r[date_col])) else date_str

            row_id = f"wm_{store_id}_{raw_id}_{e_date}_{idx}"
            rows.append({
                "id": row_id,
                "event_date": e_date,
                "platform": "walmart",
                "store_id": store_id,
                "master_sku": master_sku,
                "platform_item_id": raw_id,
                "campaign_name": str(r[camp_col]) if camp_col else "默认活动",
                "entity_type": "ad_item",
                "spend": spend,
                "attributed_sales": sales,
                "orders": orders,
                "clicks": clicks,
                "impressions": impressions,
                "source_file": source_file,
                "granularity": "daily" if len(e_date) == 10 and "-" in e_date else "period_summary",
            })

        return pd.DataFrame(rows)


class AmazonTabularAdapter(BaseReportAdapter):
    """Amazon 官方报表适配器 (Sponsored Products / 7天归因)"""

    def get_platform_name(self) -> str:
        return "amazon"

    def get_attribution_window_days(self) -> int:
        return 7  # 亚马逊 SP 标准 7 天归因

    def sniff_report_type(self, filename: str, df: pd.DataFrame) -> str:
        fn = str(filename).lower()
        cols = [str(c).strip().lower() for c in df.columns]

        if "search term" in fn or "customer search term" in cols:
            return "search_term"
        if "targeting" in fn or "targeting" in cols:
            return "keyword"
        if "advertised product" in fn or "asin" in cols or "sku" in cols:
            return "ad_item"
        return "ad_item"

    def to_canonical_ad_performance(
        self,
        raw_df: pd.DataFrame,
        store_id: str = "default_store",
        source_file: str = "",
        date_str: str = "全周期",
    ) -> pd.DataFrame:
        if raw_df.empty:
            return pd.DataFrame()

        df = raw_df.copy()
        
        asin_col = next((c for c in ["ASIN", "Advertised ASIN", "asin", "sku", "SKU"] if c in df.columns), None)
        camp_col = next((c for c in ["Campaign Name", "campaign_name", "广告活动"] if c in df.columns), None)
        spend_col = next((c for c in ["Spend", "spend", "花费", "Cost"] if c in df.columns), None)
        sales_col = next((c for c in ["7 Day Total Sales ($)", "7 Day Total Sales", "sales", "总销售额"] if c in df.columns), None)
        ord_col = next((c for c in ["7 Day Total Orders (#)", "7 Day Total Orders", "orders", "订单量"] if c in df.columns), None)
        clk_col = next((c for c in ["Clicks", "clicks", "点击"] if c in df.columns), None)
        imp_col = next((c for c in ["Impressions", "impressions", "曝光"] if c in df.columns), None)
        date_col = next((c for c in ["Date", "date", "日期"] if c in df.columns), None)

        rows = []
        from .catalog_service import get_catalog_service
        catalog = get_catalog_service()

        for idx, r in df.iterrows():
            raw_id = str(r[asin_col]).strip() if asin_col else f"AMZ-ITEM-{idx+1}"
            master_sku = catalog.resolve_master_sku(raw_id, fallback=raw_id)
            
            spend = float(pd.to_numeric(str(r[spend_col]).replace("$", "").replace(",", ""), errors="coerce")) if spend_col else 0.0
            sales = float(pd.to_numeric(str(r[sales_col]).replace("$", "").replace(",", ""), errors="coerce")) if sales_col else 0.0
            orders = int(pd.to_numeric(r[ord_col], errors="coerce")) if ord_col else 0
            clicks = int(pd.to_numeric(r[clk_col], errors="coerce")) if clk_col else 0
            impressions = int(pd.to_numeric(r[imp_col], errors="coerce")) if imp_col else 0
            e_date = str(r[date_col]).strip() if (date_col and pd.notna(r[date_col])) else date_str

            row_id = f"amz_{store_id}_{raw_id}_{e_date}_{idx}"
            rows.append({
                "id": row_id,
                "event_date": e_date,
                "platform": "amazon",
                "store_id": store_id,
                "master_sku": master_sku,
                "platform_item_id": raw_id,
                "campaign_name": str(r[camp_col]) if camp_col else "Amazon Campaign",
                "entity_type": "ad_item",
                "spend": spend,
                "attributed_sales": sales,
                "orders": orders,
                "clicks": clicks,
                "impressions": impressions,
                "source_file": source_file,
                "granularity": "daily" if len(e_date) == 10 and "-" in e_date else "period_summary",
            })

        return pd.DataFrame(rows)


def get_adapter_for_platform(platform: str) -> BaseReportAdapter:
    """适配器工厂方法"""
    p = str(platform).lower().strip()
    if "amazon" in p or "亚马逊" in p:
        return AmazonTabularAdapter()
    return WalmartTabularAdapter()
