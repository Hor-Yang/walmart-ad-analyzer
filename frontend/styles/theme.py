"""
Apple 风格统一视觉设计系统 (Apple Design System)
设计哲学：极简纯净、高通透感、拟态微阴影、圆角精修、专注数据
"""

SAAS_THEME_CSS = """
<style>
/* 引入 Apple 官方同款英文字体族 */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

:root {
    --apple-bg: #f5f6f8;
    --apple-surface: #ffffff;
    --apple-text-primary: #1d1d1f;
    --apple-text-secondary: #86868b;
    --apple-text-tertiary: #a1a1a6;
    --apple-border: rgba(0, 0, 0, 0.06);
    --apple-blue: #0071e3;
    --apple-blue-light: #e8f2fe;
    --apple-green: #34c759;
    --apple-green-light: #e6f7ed;
    --apple-red: #ff3b30;
    --apple-red-light: #feeceb;
    --apple-radius-sm: 8px;
    --apple-radius-md: 14px;
    --apple-radius-lg: 20px;
}

/* 全局字体与平滑渲染 */
html, body, [class*="css"], [class*="st-"] {
    font-family: -apple-system, BlinkMacSystemFont, "Plus Jakarta Sans", "SF Pro Text", "SF Pro Display", "PingFang SC", "Hiragino Sans GB", "Helvetica Neue", Arial, sans-serif !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    color: var(--apple-text-primary);
}

/* 全局工作台底色 */
.stApp {
    background-color: var(--apple-bg) !important;
}

/* 隐藏无关杂项，保留头部控制栏与侧边栏展开按钮 */
#MainMenu { visibility: hidden !important; display: none !important; }
footer { visibility: hidden !important; display: none !important; }
.stDeployButton { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }

/* =========================================================================
   1. 解决侧边栏收起后按钮丢失 Bug：永久确保展开按钮（stExpandSidebarButton）常驻高亮
   ========================================================================= */
header[data-testid="stHeader"] {
    background: transparent !important;
    pointer-events: none !important;
    z-index: 99999 !important;
    display: flex !important;
    height: 48px !important;
}

[data-testid="stToolbar"],
.stAppToolbar {
    pointer-events: auto !important;
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    background: transparent !important;
}

/* 无论现代版本 (stExpandSidebarButton) 还是旧版本 (collapsedControl)，均强制置顶展示为 Apple 悬浮按钮 */
[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
button[aria-label="Expand sidebar"],
button[aria-label="Open sidebar"],
header button:not(#MainMenu):not(.stDeployButton) {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    position: fixed !important;
    top: 14px !important;
    left: 14px !important;
    z-index: 9999999 !important;
    width: 40px !important;
    height: 40px !important;
    min-width: 40px !important;
    min-height: 40px !important;
    background: rgba(255, 255, 255, 0.98) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(0, 0, 0, 0.12) !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.10), 0 1px 3px rgba(0, 0, 0, 0.05) !important;
    color: #1d1d1f !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

[data-testid="stExpandSidebarButton"]:hover,
[data-testid="collapsedControl"]:hover,
button[aria-label="Expand sidebar"]:hover,
button[aria-label="Open sidebar"]:hover {
    background: #ffffff !important;
    transform: scale(1.08) !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.16) !important;
    border-color: rgba(0, 113, 227, 0.4) !important;
}

[data-testid="stExpandSidebarButton"] svg,
[data-testid="collapsedControl"] svg,
button[aria-label="Expand sidebar"] svg,
button[aria-label="Open sidebar"] svg {
    color: #1d1d1f !important;
    fill: #1d1d1f !important;
    stroke: #1d1d1f !important;
    width: 20px !important;
    height: 20px !important;
}

/* 主工作区内边距优化 */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 100% !important;
}

/* =========================================================================
   2. Apple 风格侧边栏 (Light Frosted macOS Style)
   ========================================================================= */
[data-testid="stSidebar"] {
    background-color: #f7f8fa !important;
    border-right: 1px solid rgba(0, 0, 0, 0.06) !important;
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.5rem !important;
    padding-left: 1.2rem !important;
    padding-right: 1.2rem !important;
}

/* 侧边栏按钮胶囊化 */
[data-testid="stSidebar"] .stButton > button {
    border-radius: 12px !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 10px 14px !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    border: 1px solid transparent !important;
}

/* 非激活项 */
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    background: transparent !important;
    color: #4b5563 !important;
}

[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
    background: rgba(0, 0, 0, 0.04) !important;
    color: #111827 !important;
}

/* 激活选中项 (Apple White Floating Pill) */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #ffffff !important;
    color: #0f172a !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    border: 1px solid rgba(0, 0, 0, 0.05) !important;
}

/* =========================================================================
   3. 顶部 Apple 胶囊全局筛选栏
   ========================================================================= */
.apple-filter-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 22px;
}

/* Streamlit 下拉选框美化 (Apple Segmented Look) */
div[data-baseweb="select"] {
    border-radius: 12px !important;
    background: #ffffff !important;
    border: 1px solid rgba(0, 0, 0, 0.08) !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
    transition: all 0.2s ease !important;
}

div[data-baseweb="select"]:hover {
    border-color: rgba(0, 0, 0, 0.16) !important;
}

div[data-baseweb="select"] > div {
    border-radius: 12px !important;
    background: transparent !important;
    border: none !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}

/* =========================================================================
   4. Apple 级精修 KPI 卡片 (Pure White, Round, Subtle Glow)
   ========================================================================= */
.apple-kpi-card {
    background: #ffffff;
    border-radius: 18px;
    padding: 22px 24px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.03), 0 1px 3px rgba(0, 0, 0, 0.02);
    border: 1px solid rgba(0, 0, 0, 0.04);
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease;
    height: 100%;
}

.apple-kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05), 0 2px 6px rgba(0, 0, 0, 0.02);
}

.apple-kpi-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.apple-kpi-label {
    font-size: 14px;
    font-weight: 500;
    color: #4b5563;
}

.apple-kpi-value {
    font-size: 32px;
    font-weight: 700;
    color: #111827;
    letter-spacing: -0.03em;
    line-height: 1.15;
}

/* Apple 专属胶囊微徽章 */
.apple-badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 9px;
    border-radius: 9999px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: -0.01em;
}

.badge-apple-green {
    background-color: #e6f7ed;
    color: #00a854;
}

.badge-apple-red {
    background-color: #feeceb;
    color: #f5222d;
}

.badge-apple-blue {
    background-color: #e8f2fe;
    color: #0071e3;
}

.badge-apple-gray {
    background-color: #f3f4f6;
    color: #6b7280;
}

/* =========================================================================
   5. Apple 白板容器卡片 (White Surface Container)
   ========================================================================= */
.apple-panel {
    background: #ffffff;
    border-radius: 20px;
    padding: 24px 26px;
    box-shadow: 0 2px 14px rgba(0, 0, 0, 0.03), 0 1px 3px rgba(0, 0, 0, 0.02);
    border: 1px solid rgba(0, 0, 0, 0.04);
    margin-bottom: 20px;
}

.apple-panel-title {
    font-size: 17px;
    font-weight: 600;
    color: #111827;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* 数据表格与选项卡 Apple 化 */
.stTabs [data-baseweb="tab-list"] {
    background: #ebecef !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 4px !important;
    border-bottom: none !important;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 9px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    border: none !important;
    color: #6b7280 !important;
}

.stTabs [aria-selected="true"] {
    background: #ffffff !important;
    color: #111827 !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06) !important;
}
</style>
"""


def inject_saas_theme():
    import streamlit as st
    st.markdown(SAAS_THEME_CSS, unsafe_allow_html=True)
