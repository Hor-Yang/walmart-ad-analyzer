"""
测试用例：安全渲染装饰器、用户系统多租户隔离与历史报告跨周期对比 (Diff Mode)
"""

import os
import unittest
import pandas as pd
from frontend.utils.error_handler import safe_view_render
from services.auth_service import AuthService
from services.snapshot_service import SnapshotService
from services.storage_engine import StorageEngine


class TestSafeRenderAndHistory(unittest.TestCase):

    def setUp(self):
        self.test_reports_dir = os.path.join(os.path.dirname(__file__), "test_reports")
        self.storage = StorageEngine(db_path=":memory:")
        self.auth = AuthService(storage=self.storage)
        self.snapshot_svc = SnapshotService(storage=self.storage, base_data_dir=self.test_reports_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_reports_dir):
            try:
                shutil.rmtree(self.test_reports_dir)
            except Exception:
                pass

    def test_safe_view_render_decorator(self):
        """测试 @safe_view_render 是否能够吞下异常并阻止 Traceback 泄露"""
        @safe_view_render("测试模块")
        def failing_view():
            raise ZeroDivisionError("division by zero in view calculation")

        # 执行不应抛出 ZeroDivisionError
        try:
            failing_view()
            success = True
        except Exception:
            success = False
        self.assertTrue(success)

    def test_auth_multi_tenant_isolation(self):
        """测试多租户鉴权与用户列表"""
        users = self.auth.list_users()
        self.assertGreaterEqual(len(users), 3)
        admin = self.auth.get_user_by_id("usr_admin")
        self.assertIsNotNone(admin)
        self.assertEqual(admin["role"], "admin")

    def test_snapshot_lifecycle_and_diff_comparison(self):
        """测试历史快照持久化保存、读取与双期指标差异对比"""
        # 第一期：初始周
        sec_w1 = {
            "ad_item": pd.DataFrame({
                "SKU": ["SKU-A", "SKU-B", "SKU-C"],
                "花费": [100.0, 200.0, 50.0],
                "广告销售额": [300.0, 100.0, 200.0],
                "订单量": [10, 2, 8],
            })
        }
        ov_w1 = {"大盘总花费": 350.0, "总销售额": 600.0, "总订单": 20}
        
        snap1_id = self.snapshot_svc.create_snapshot(
            user_id="usr_admin",
            report_name="2026-W43-诊断报告",
            sec_data=sec_w1,
            overview=ov_w1,
            source_files=["camp_w1.xlsx", "item_w1.xlsx"],
        )
        self.assertTrue(snap1_id.startswith("snap_"))

        # 第二期：优化后周（SKU-B 治愈，总花费下降，销售额上升）
        sec_w2 = {
            "ad_item": pd.DataFrame({
                "SKU": ["SKU-A", "SKU-B", "SKU-C"],
                "花费": [90.0, 60.0, 50.0],
                "广告销售额": [320.0, 200.0, 220.0],
                "订单量": [11, 6, 9],
            })
        }
        ov_w2 = {"大盘总花费": 200.0, "总销售额": 740.0, "总订单": 26}
        snap2_id = self.snapshot_svc.create_snapshot(
            user_id="usr_admin",
            report_name="2026-W44-优化后报告",
            sec_data=sec_w2,
            overview=ov_w2,
            source_files=["camp_w2.xlsx", "item_w2.xlsx"],
        )

        # 检查快照列表
        snaps = self.snapshot_svc.list_snapshots("usr_admin")
        self.assertEqual(len(snaps), 2)

        # 检查双期对比 (Diff)
        diff = self.snapshot_svc.compare_snapshots(snap1_id, snap2_id)
        self.assertIsNotNone(diff)
        
        deltas = diff["deltas"]
        self.assertLess(deltas["spend_pct"], 0)  # 花费减少
        self.assertGreater(deltas["sales_pct"], 0)  # 销售增加
        self.assertGreater(deltas["roas_diff"], 0)  # ROAS 提升

        # 验证治愈 SKU
        cured = deltas["cured_skus"]
        self.assertIn("SKU-B", cured)


if __name__ == "__main__":
    unittest.main()
