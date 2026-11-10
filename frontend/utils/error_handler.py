"""
CrossBorder BI · 全局生产级异常处理与安全渲染中间件 (Safe View Render & Error Boundary)
遵循规范：
1. 全局/模块级异常兜底：提供 @safe_view_render 装饰器与安全调用函数
2. 生产级错误脱敏：严禁向终端用户直接展示原生 Python 代码堆栈 (Traceback)
3. 友好指引与排查支持：统一渲染可折叠技术日志与标准 Python Logging 输出
"""

import functools
import logging
import traceback
from typing import Callable, Any, Optional
import streamlit as st

# 配置标准带时间戳的 Python 日志输出
logger = logging.getLogger("CrossBorderBI.UI")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def render_friendly_error(
    view_name: str,
    error: Exception,
    custom_guidance: Optional[str] = None,
):
    """
    // FIX: 渲染生产级脱敏错误提示卡片，严禁裸露 Traceback，仅在 expander 中提供技术排查支持
    """
    error_msg = str(error)
    tb_str = traceback.format_exc()
    logger.error("视图 [%s] 执行异常: %s\n%s", view_name, error_msg, tb_str)

    guidance = custom_guidance or (
        "可能原因：当前会话中尚未导入完整业务报表，或上传的表格缺少关键列（如：花费、销售额、广告活动、项目ID/SKU），亦或数据类型格式存在异常。\n\n"
        "[建议操作] 请前往「数据中心」重新上传对应的标准报表或检查底表模板格式。"
    )

    st.markdown(
        f"""
        <div class="card" style="margin-top: 10px; border-left: 4px solid #FF3B30; padding: 20px 24px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                <div style="font-size: 16px; font-weight: 600; color: #1D1D1F;">
                    [异常拦截] 【{view_name}】模块数据解析与渲染受阻
                </div>
                <span class="apple-badge badge-apple-red">运行时防护拦截</span>
            </div>
            <div style="font-size: 13.5px; color: #4B5563; line-height: 1.6; margin-bottom: 12px; white-space: pre-line;">
                {guidance}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("查看技术诊断日志 (供开发人员排查)", expanded=False):
        st.caption("以下为系统底层执行堆栈，已自动同步记录至后台运行日志中：")
        st.code(f"Exception Type: {type(error).__name__}\nDetails: {error_msg}\n\nTraceback:\n{tb_str}", language="python")
        if st.button("重新加载本模块", key=f"retry_view_{view_name}"):
            st.rerun()


def safe_view_render(view_name: str, custom_guidance: Optional[str] = None) -> Callable:
    """
    // FIX: 全局/模块级异常兜底装饰器，包裹各 View 主入口
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                render_friendly_error(view_name=view_name, error=e, custom_guidance=custom_guidance)
                return None
        return wrapper
    return decorator
