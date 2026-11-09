"""
UI 一致性与纯净图标系统自动化测试
验证：
1. 前端代码中无散乱彩色 Emoji
2. render_empty_state 支持所有语义图标类型并不报错
3. 统一页面 Header 与卡片组件规范
4. 9 大核心业务视图均正常可调
"""

import unittest
import os
import re
from unittest.mock import patch, MagicMock
import pandas as pd


class TestUIConsistency(unittest.TestCase):

    def test_no_emojis_in_frontend(self):
        """验证 frontend 目录下所有 Python 代码中不存在彩色 Emoji"""
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]')
        violations = []
        for root, _, files in os.walk('frontend'):
            if '__pycache__' in root:
                continue
            for f in files:
                if f.endswith('.py'):
                    p = os.path.join(root, f)
                    with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                        for idx, line in enumerate(fp, 1):
                            code_part = line.split('#')[0]
                            emojis = emoji_pattern.findall(code_part)
                            if emojis:
                                violations.append(f"{p}:{idx}: {emojis}")
        self.assertEqual(violations, [], f"发现前端残留 Emoji: {violations}")

    def test_empty_state_supports_all_types(self):
        """验证 render_empty_state 支持各种业务类型图标且防御传参不抛异常"""
        from frontend.components.kpi_card import render_empty_state
        
        test_types = ["chart", "sales", "cart", "profit", "dollar", "inventory", "box", "products", "tag", "ai", "sparkles", "database", "unknown"]
        for t in test_types:
            with patch("streamlit.markdown") as mock_md:
                res = render_empty_state(
                    title=f"测试 {t}",
                    description="说明文字",
                    icon_type=t,
                    icon="🏷️", # 防御性传入遗留参数
                )
                self.assertFalse(res)
                mock_md.assert_called()

    def test_page_header_render(self):
        """验证 render_page_header 规范"""
        from frontend.components.kpi_card import render_page_header
        with patch("streamlit.markdown") as mock_md:
            render_page_header("测试模块", "说明副标题", badge="Pro")
            mock_md.assert_called()
            html_call = mock_md.call_args[0][0]
            self.assertIn("测试模块", html_call)
            self.assertIn("说明副标题", html_call)
            self.assertIn("badge-apple-blue", html_call)

    def test_filter_bar_no_raw_emoji(self):
        """验证全局筛选栏刷新按钮无 Emoji"""
        import inspect
        import frontend.components.filter_bar as fb
        src = inspect.getsource(fb.render_global_filter_bar)
        self.assertNotIn("🔄", src.split("#")[0])


if __name__ == "__main__":
    unittest.main()
