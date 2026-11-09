"""
CrossBorder BI · 统一业务数据查询服务 (Unified Business Query Service / Data Access Layer)
职责：
1. 统一对接前端所有业务视图（Dashboard、Sales、Profit、Inventory、AI）；
2. 自动注入顶部全局筛选条件（平台、店铺、日期范围、目标 SKU、类目）；
3. 协调 StorageEngine、AdapterService 与 MetricService，消除视图层中零散的 SQL 与 Groupby 逻辑。
"""

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from .storage_engine import get_storage_engine
from .metric_service import get_metric_service
from .catalog_service import get_catalog_service
from .adapter_service import get_adapter_for_platform


class UnifiedBusinessQueryService:
    """业务数据统一查询门面"""

    def __init__(self):
        self.storage = get_storage_engine()
        self.metrics = get_metric_service()
        self.catalog = get_catalog_service()

    def _apply_filter_to_df(self, df: pd.DataFrame, filters: Optional[Dict[str, Any]]) -> pd.DataFrame:
        """根据全局筛选栏对 DataFrame 进行通用过滤"""
        if df.empty or not filters:
            return df

        out = df.copy()

        # 1. 目标 SKU
        sel_sku = filters.get("sku", "全部 SKU")
        if sel_sku and sel_sku != "全部 SKU":
            sku_col = next((c for c in ["master_sku", "SKU", "sku", "项目ID", "item_id"] if c in out.columns), None)
            if sku_col:
                out = out[out[sku_col].astype(str).str.strip() == str(sel_sku).strip()]

        # 2. 渠道平台
        sel_plat = filters.get("platform", "Walmart")
        if sel_plat and "全部" not in sel_plat:
            plat_clean = sel_plat.split(" ")[0].strip().lower()
            plat_col = next((c for c in ["platform", "平台", "_platform"] if c in out.columns), None)
            if plat_col:
                out = out[out[plat_col].astype(str).str.lower().str.contains(plat_clean, na=True)]

        # 3. 日期范围
        date_range = filters.get("date_range", "最近30天")
        d_col = next((c for c in ["event_date", "日期", "_date", "date"] if c in out.columns), None)
        if d_col and date_range and date_range != "全量报表周期":
            try:
                parsed_d = pd.to_datetime(out[d_col], errors="coerce")
                if parsed_d.notna().any():
                    max_d = parsed_d.max()
                    if "7天" in date_range:
                        out = out[parsed_d >= (max_d - pd.Timedelta(days=7))]
                    elif "14天" in date_range:
                        out = out[parsed_d >= (max_d - pd.Timedelta(days=14))]
                    elif "30天" in date_range:
                        out = out[parsed_d >= (max_d - pd.Timedelta(days=30))]
            except Exception:
                pass

        return out

    def get_dashboard_summary(
        self,
        session_section_data: Dict[str, Any],
        daily_trend_df: Optional[pd.DataFrame] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        获取经营总览页面的标准汇总数据与图表数据源
        """
        platform = filters.get("platform", "walmart") if filters else "walmart"
        adapter = get_adapter_for_platform(platform)

        # 1. 获取并规范化广告数据
        ad_item_df = session_section_data.get("ad_item")
        camp_df = session_section_data.get("campaign")
        
        canonical_ad_df = pd.DataFrame()
        if ad_item_df is not None and not ad_item_df.empty:
            canonical_ad_df = adapter.to_canonical_ad_performance(ad_item_df, store_id=filters.get("store", "default_store") if filters else "default_store")
        elif camp_df is not None and not camp_df.empty:
            canonical_ad_df = adapter.to_canonical_ad_performance(camp_df, store_id=filters.get("store", "default_store") if filters else "default_store")

        filtered_ad_df = self._apply_filter_to_df(canonical_ad_df, filters)

        # 2. 获取并规范化销售数据
        filtered_sales_df = pd.DataFrame()
        if daily_trend_df is not None and not daily_trend_df.empty and "销售额" in daily_trend_df.columns:
            s_work = daily_trend_df.copy()
            s_work["gross_sales"] = pd.to_numeric(s_work["销售额"], errors="coerce").fillna(0.0)
            if "订单量" in s_work.columns:
                s_work["orders"] = pd.to_numeric(s_work["订单量"], errors="coerce").fillna(0)
            filtered_sales_df = self._apply_filter_to_df(s_work, filters)

        # 3. 调用指标服务计算
        kpis = self.metrics.calculate_executive_kpis(filtered_ad_df, filtered_sales_df)

        return {
            "kpis": kpis,
            "filtered_ad_df": filtered_ad_df,
            "filtered_sales_df": filtered_sales_df,
        }


_query_instance: Optional[UnifiedBusinessQueryService] = None

def get_query_service() -> UnifiedBusinessQueryService:
    global _query_instance
    if _query_instance is None:
        _query_instance = UnifiedBusinessQueryService()
    return _query_instance
