"""
指标计算与广告诊断模块
"""

from .metrics import (
    agg_metrics,
    summarize_overview,
    safe_divide,
)
from .campaign_health import (
    analyze_campaign_health,
    summarize_inactive_campaigns,
    ALL_CAMPAIGN_TAGS,
)
from .search_term_miner import (
    mine_search_terms,
)
from .keyword_bidder import (
    analyze_keyword_bids,
)
from .ad_item_diagnosis import (
    diagnose_ad_items,
)
from .placement_analyzer import (
    analyze_placements,
)
from .action_items import (
    build_action_items,
)
from .trend_analyzer import (
    build_sku_trend_data,
    extract_period_label,
)
from .store_product_analysis import (
    generate_store_overview_analysis,
    generate_product_matrix_analysis,
    get_decision_mapping_guide,
)

__all__ = [
    "agg_metrics",
    "summarize_overview",
    "safe_divide",
    "analyze_campaign_health",
    "summarize_inactive_campaigns",
    "ALL_CAMPAIGN_TAGS",
    "mine_search_terms",
    "analyze_keyword_bids",
    "diagnose_ad_items",
    "analyze_placements",
    "build_action_items",
    "build_sku_trend_data",
    "extract_period_label",
    "generate_store_overview_analysis",
    "generate_product_matrix_analysis",
    "get_decision_mapping_guide",
]
