"""
CrossBorder BI · 统一语义指标计算服务 (Semantic Metric Service)
职责：
1. 统一全系统经营指标公式（GMV、归因销售额、TACoS、单位经济学、保本 ACoS、DOS）；
2. 严肃保证统计口径隔离：严禁将广告归因销售额当成店铺 GMV；
3. 缺失关键成本要素时，坚决不伪造净利润结论。
"""

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


class SemanticMetricService:
    """企业级跨境电商指标计算中枢"""

    @staticmethod
    def safe_div(num: float, den: float, default: float = 0.0) -> float:
        try:
            n = float(num)
            d = float(den)
            return (n / d) if d != 0.0 else default
        except Exception:
            return default

    @classmethod
    def calculate_executive_kpis(
        cls,
        fact_ad_df: Optional[pd.DataFrame],
        fact_sales_df: Optional[pd.DataFrame] = None,
        fact_inv_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        计算管理层总览看板核心 4 大 KPI：
        - 销售额 (区分店铺真实 GMV vs 广告归因销售额)
        - 广告总支出
        - 产出比 (ROAS)
        - 库存/出单概况
        """
        spend = 0.0
        ad_sales = 0.0
        ad_orders = 0
        ad_clicks = 0
        ad_impressions = 0

        if fact_ad_df is not None and not fact_ad_df.empty:
            spend = float(pd.to_numeric(fact_ad_df["spend"], errors="coerce").fillna(0).sum())
            ad_sales = float(pd.to_numeric(fact_ad_df["attributed_sales"], errors="coerce").fillna(0).sum())
            ad_orders = int(pd.to_numeric(fact_ad_df["orders"], errors="coerce").fillna(0).sum())
            ad_clicks = int(pd.to_numeric(fact_ad_df["clicks"], errors="coerce").fillna(0).sum())
            ad_impressions = int(pd.to_numeric(fact_ad_df["impressions"], errors="coerce").fillna(0).sum())

        has_store_gmv = False
        store_gmv = 0.0
        total_orders = ad_orders

        if fact_sales_df is not None and not fact_sales_df.empty:
            store_gmv = float(pd.to_numeric(fact_sales_df["gross_sales"], errors="coerce").fillna(0).sum())
            if store_gmv > 0:
                has_store_gmv = True
            if "orders" in fact_sales_df.columns:
                total_orders = int(pd.to_numeric(fact_sales_df["orders"], errors="coerce").fillna(0).sum())

        roas = cls.safe_div(ad_sales, spend, default=0.0)
        acos = cls.safe_div(spend, ad_sales, default=0.0)
        cpc = cls.safe_div(spend, ad_clicks, default=0.0)
        ctr = cls.safe_div(ad_clicks, ad_impressions, default=0.0)

        # TACoS (Total ACoS) 综合广告占销比 (仅当具备店铺总 GMV 时计算)
        tacos = cls.safe_div(spend, store_gmv, default=0.0) if has_store_gmv else None

        display_sales = store_gmv if has_store_gmv else ad_sales
        sales_title = "店铺真实总 GMV" if has_store_gmv else "广告归因销售额"

        return {
            "has_real_data": (spend > 0) or (ad_sales > 0) or has_store_gmv,
            "has_store_gmv": has_store_gmv,
            "display_sales": display_sales,
            "sales_title": sales_title,
            "store_gmv": store_gmv,
            "ad_sales": ad_sales,
            "spend": spend,
            "total_orders": total_orders,
            "ad_orders": ad_orders,
            "roas": roas,
            "acos": acos,
            "tacos": tacos,
            "cpc": cpc,
            "ctr": ctr,
        }

    @classmethod
    def calculate_sku_profit_analytics(
        cls,
        sku_ad_df: pd.DataFrame,
        cost_dict: Optional[Dict[str, Dict[str, float]]] = None,
        target_acos_ratio: float = 0.80,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        SKU 级全成本真实利润核算 (严格遵循先聚合后核算、缺失成本不伪造净利原则)
        """
        from analyzer.sku_profit_model import calculate_sku_profit_analytics
        return calculate_sku_profit_analytics(sku_ad_df, cost_dict=cost_dict, target_acos_ratio=target_acos_ratio)


_metric_instance: Optional[SemanticMetricService] = None

def get_metric_service() -> SemanticMetricService:
    global _metric_instance
    if _metric_instance is None:
        _metric_instance = SemanticMetricService()
    return _metric_instance
