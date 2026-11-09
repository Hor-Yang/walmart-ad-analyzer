"""
测试第二阶段前端重构架构与路由调度
"""

import unittest
from frontend.components.navigation import NAV_MODULES
from frontend.views import (
    render_dashboard_view,
    render_ads_view,
    render_sales_view,
    render_inventory_view,
    render_products_view,
    render_profit_view,
    render_ai_view,
    render_data_hub_view,
    render_settings_view,
)


class TestFrontendArchitecture(unittest.TestCase):
    def test_nav_modules_count(self):
        """验证 9 大一级核心业务导航完整性"""
        self.assertEqual(len(NAV_MODULES), 9)
        mod_ids = [m["id"] for m in NAV_MODULES]
        expected_ids = [
            "dashboard",
            "ads_analytics",
            "sales_analytics",
            "inventory",
            "products",
            "profitability",
            "ai_intelligence",
            "data_hub",
            "settings",
        ]
        self.assertEqual(mod_ids, expected_ids)

    def test_view_callables(self):
        """验证所有一级页面视图均具备可执行函数"""
        views = [
            render_dashboard_view,
            render_ads_view,
            render_sales_view,
            render_inventory_view,
            render_products_view,
            render_profit_view,
            render_ai_view,
            render_data_hub_view,
            render_settings_view,
        ]
        for v in views:
            self.assertTrue(callable(v))


if __name__ == "__main__":
    unittest.main()
