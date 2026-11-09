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
try:
    from .sku_profit_model import (
        generate_sku_cost_template,
        load_sku_cost_table,
        calculate_sku_profit_analytics,
    )
except ImportError:
    generate_sku_cost_template = None
    load_sku_cost_table = None
    calculate_sku_profit_analytics = None

try:
    from .decision_engine import AdDecisionEngine
except ImportError:
    AdDecisionEngine = None

try:
    from .data_quality import inspect_data_quality
except ImportError:
    def inspect_data_quality(*args, **kwargs):
        return {"health_score": 100, "grade": "良好", "confidence_level": "高", "issues": [], "summary": "基础数据检查"}

try:
    from .traffic_structure import analyze_traffic_structure
except ImportError:
    def analyze_traffic_structure(*args, **kwargs):
        return {"auto_manual": {}, "match_type": {}, "cannibalization": [], "alerts": []}

try:
    from .diagnosis_12_issues import diagnose_12_advertising_issues
except ImportError:
    def diagnose_12_advertising_issues(*args, **kwargs):
        return []

try:
    from .effect_tracker import (
        log_optimization_actions,
        load_tracking_history,
        generate_tracking_summary,
        clear_tracking_history,
    )
except ImportError:
    def log_optimization_actions(*args, **kwargs): return []
    def load_tracking_history(*args, **kwargs): return []
    def generate_tracking_summary(*args, **kwargs): return {}
    def clear_tracking_history(*args, **kwargs): return True

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
    "generate_sku_cost_template",
    "load_sku_cost_table",
    "calculate_sku_profit_analytics",
    "AdDecisionEngine",
    "inspect_data_quality",
    "analyze_traffic_structure",
    "diagnose_12_advertising_issues",
    "log_optimization_actions",
    "load_tracking_history",
    "generate_tracking_summary",
    "clear_tracking_history",
]
