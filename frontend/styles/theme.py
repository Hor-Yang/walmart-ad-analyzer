"""
Apple macOS 极简高端统一设计系统规范 (Apple macOS Design System)
涵盖：
1. 全局 CSS 变量系统 (CSS Custom Properties)
2. 彻底修复侧边栏折叠与展开按钮泄漏文本 (keyboard_double)，替换为显式黑色描边的高精矢量 SVG 蒙版
3. 统一单色线条图标系统 (Lucide / Feather Icons) 代替杂乱彩色 Emoji
4. 统一 .card 容器规范：border-radius: 16px, background: #FFFFFF, 弥散阴影, 呼吸感留白 (padding >= 24px)
5. 统一字体排版层级 (SF Pro / Inter)，图表去噪规范
6. 客户端自动展开与悬浮胶囊防护逻辑
"""

SAAS_THEME_CSS = """
<style>
/* 引入 SF Pro / Inter 级优雅英文字体 */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* =========================================================================
   1. 全局设计规范：CSS 变量系统 (Apple Design System Tokens)
   ========================================================================= */
:root {
    /* 基础环境与容器底色 */
    --apple-bg: #F5F5F7;               /* 极浅灰白底色，衬托纯白卡片 */
    --apple-surface: #FFFFFF;          /* 纯白卡片容器底色 */
    --apple-surface-subtle: #FAFAFC;   /* 次级卡片底色 */
    --apple-sidebar-bg: #F8F9FA;       /* 侧边栏通透浅色背景 */
    
    /* 统一文字排版与颜色层级 */
    --apple-text-primary: #1D1D1F;     /* 重要数据/主标题 (深灰近黑) */
    --apple-text-secondary: #86868B;   /* 辅助说明/副标题 (浅灰) */
    --apple-text-tertiary: #A1A1A6;    /* 占位提示/微型标注 (极浅灰) */
    
    /* 核心交互与主题强调色 */
    --apple-blue: #0071E3;             /* 经典 Apple 交互蓝 */
    --apple-blue-subtle: #E8F2FE;      /* 导航选中态高亮浅蓝 */
    --apple-green: #34C759;            /* 正向健康绿 */
    --apple-green-subtle: #E6F7ED;     /* 浅绿药丸背景 */
    --apple-red: #FF3B30;              /* 异常预警红 */
    --apple-red-subtle: #FEECEB;       /* 浅红药丸背景 */
    
    /* 卡片与容器规范 */
    --apple-radius-card: 16px;         /* 统一圆角 16px */
    --apple-radius-button: 12px;       /* 按钮/控件圆角 12px */
    --apple-radius-pill: 9999px;       /* 药丸徽章全圆角 */
    --apple-padding-card: 24px;        /* 呼吸感内边距 (>=24px) */
    --apple-shadow-card: 0 4px 20px rgba(0, 0, 0, 0.04); /* 极柔和弥散阴影 */
    --apple-shadow-hover: 0 10px 28px rgba(0, 0, 0, 0.07);
    --apple-border: 1px solid rgba(0, 0, 0, 0.04);       /* 极浅无感描边 */
}

/* 全局字体：优先采用苹果系统原生字体族 */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", "PingFang SC", "Hiragino Sans GB", "Helvetica Neue", sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    color: var(--apple-text-primary);
}

/* 全局工作台底色 */
.stApp {
    background-color: var(--apple-bg) !important;
}

/* 隐藏 Streamlit 冗余干扰控件 */
#MainMenu { visibility: hidden !important; display: none !important; }
footer { visibility: hidden !important; display: none !important; }
.stDeployButton { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }

/* 头部透明化并保持穿透，同时确保侧边栏展开按钮始终可点击 */
header[data-testid="stHeader"] {
    background: transparent !important;
    pointer-events: none !important;
    z-index: 99999 !important;
    display: flex !important;
    height: 48px !important;
}

header[data-testid="stHeader"] > * {
    pointer-events: auto !important;
}

[data-testid="stToolbar"],
.stAppToolbar {
    pointer-events: auto !important;
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    background: transparent !important;
}

/* 隐藏辅助 iframe */
iframe[title="streamlit.components.v1.html"],
iframe[srcdoc*="checkAndExpandSidebar"] {
    display: none !important;
    position: absolute !important;
    width: 0 !important;
    height: 0 !important;
    border: none !important;
}

/* =========================================================================
   2. 修复 Bug：彻底解决侧边栏折叠与展开按钮，显式黑色描边 SVG 蒙版
   ========================================================================= */
/* 彻底隐藏折叠按钮内原始文字/图标 */
[data-testid="stSidebarCollapseButton"] button span,
[data-testid="stSidebarCollapseButton"] button div,
[data-testid="stSidebarCollapseButton"] button svg {
    display: none !important;
}

[data-testid="stSidebarCollapseButton"] button {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 32px !important;
    height: 32px !important;
    min-width: 32px !important;
    min-height: 32px !important;
    border-radius: 8px !important;
    background: transparent !important;
    border: none !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    position: relative !important;
}

[data-testid="stSidebarCollapseButton"] button:hover {
    background: rgba(0, 0, 0, 0.05) !important;
}

/* 替换为 Lucide 风格的 ChevronsLeft 矢量折叠图标 (显式 stroke='black' 蒙版) */
[data-testid="stSidebarCollapseButton"] button::after {
    content: "" !important;
    display: block !important;
    width: 18px !important;
    height: 18px !important;
    min-width: 18px !important;
    min-height: 18px !important;
    background-color: var(--apple-text-secondary) !important;
    -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='11 17 6 12 11 7'%3E%3C/polyline%3E%3Cpolyline points='18 17 13 12 18 7'%3E%3C/polyline%3E%3C/svg%3E") no-repeat center / contain !important;
    mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='11 17 6 12 11 7'%3E%3C/polyline%3E%3Cpolyline points='18 17 13 12 18 7'%3E%3C/polyline%3E%3C/svg%3E") no-repeat center / contain !important;
}

[data-testid="stSidebarCollapseButton"] button:hover::after {
    background-color: var(--apple-text-primary) !important;
}

/* 侧边栏展开悬浮胶囊按钮 (Apple 独立悬浮胶囊) */
[data-testid="stExpandSidebarButton"],
[data-testid="stExpandSidebarButton"] button,
button[aria-label="Expand sidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
    display: inline-flex !important;
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
    background: #FFFFFF !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(0, 0, 0, 0.12) !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12) !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

[data-testid="stExpandSidebarButton"]:hover,
[data-testid="stExpandSidebarButton"] button:hover,
button[aria-label="Expand sidebar"]:hover {
    background: #F5F5F7 !important;
    transform: scale(1.06) !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.18) !important;
}

/* 彻底隐藏展开按钮内部的原始文字/material 图标 */
[data-testid="stExpandSidebarButton"] span,
[data-testid="stExpandSidebarButton"] div,
[data-testid="stExpandSidebarButton"] svg,
button[aria-label="Expand sidebar"] span,
button[aria-label="Expand sidebar"] div,
button[aria-label="Expand sidebar"] svg {
    display: none !important;
}

/* 展开按钮图标：Feather 风格侧边栏展开图标 (显式 stroke='black' 蒙版) */
[data-testid="stExpandSidebarButton"]::after,
[data-testid="stExpandSidebarButton"] button::after,
button[aria-label="Expand sidebar"]::after,
[data-testid="collapsedControl"]::after {
    content: "" !important;
    display: block !important;
    width: 20px !important;
    height: 20px !important;
    min-width: 20px !important;
    min-height: 20px !important;
    background-color: var(--apple-text-primary) !important;
    -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect width='18' height='18' x='3' y='3' rx='4' ry='4'/%3E%3Cpath d='M9 3v18'/%3E%3Cpath d='m14 9 3 3-3 3'/%3E%3C/svg%3E") no-repeat center / contain !important;
    mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect width='18' height='18' x='3' y='3' rx='4' ry='4'/%3E%3Cpath d='M9 3v18'/%3E%3Cpath d='m14 9 3 3-3 3'/%3E%3C/svg%3E") no-repeat center / contain !important;
}

/* =========================================================================
   3. 统一全局卡片规范 (.card) 与数据呼吸感留白 (Padding >= 24px)
   ========================================================================= */
.card, .apple-panel, .apple-kpi-card {
    background-color: var(--apple-surface) !important;
    border-radius: var(--apple-radius-card) !important;
    padding: var(--apple-padding-card) !important;
    box-shadow: var(--apple-shadow-card) !important;
    border: var(--apple-border) !important;
    margin-bottom: 20px !important;
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease !important;
}

.card:hover, .apple-panel:hover, .apple-kpi-card:hover {
    box-shadow: var(--apple-shadow-hover) !important;
}

.card-title {
    font-size: 16px !important;
    font-weight: 600 !important;
    color: var(--apple-text-primary) !important;
    letter-spacing: -0.01em !important;
    margin-bottom: 16px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
}

.card-subtitle {
    font-size: 12.5px !important;
    color: var(--apple-text-secondary) !important;
    font-weight: 400 !important;
}

/* KPI 指标排版 */
.kpi-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.kpi-label {
    font-size: 13.5px;
    font-weight: 500;
    color: var(--apple-text-secondary);
}

.kpi-value {
    font-size: 32px;
    font-weight: 700;
    color: var(--apple-text-primary);
    letter-spacing: -0.03em;
    line-height: 1.15;
}

/* 统一轻质感药丸微徽章 */
.apple-badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 9px;
    border-radius: var(--apple-radius-pill);
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: -0.01em;
}

.badge-apple-green {
    background-color: var(--apple-green-subtle);
    color: #059669;
}

.badge-apple-red {
    background-color: var(--apple-red-subtle);
    color: #DC2626;
}

.badge-apple-blue {
    background-color: var(--apple-blue-subtle);
    color: var(--apple-blue);
}

.badge-apple-gray {
    background-color: #F3F4F6;
    color: var(--apple-text-secondary);
}

/* =========================================================================
   4. 侧边栏统一单色矢量图标库 (Monochrome Lucide Icons)
   ========================================================================= */
[data-testid="stSidebar"] {
    background-color: var(--apple-sidebar-bg) !important;
    border-right: 1px solid rgba(0, 0, 0, 0.05) !important;
}

/* 侧边栏导航按钮胶囊化 */
[data-testid="stSidebar"] .stButton > button {
    position: relative !important;
    border-radius: var(--apple-radius-button) !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 10px 14px 10px 44px !important;
    height: 42px !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    border: none !important;
}

/* 基础图标槽：单色矢量蒙版 */
[data-testid="stSidebar"] .stButton > button::before {
    content: "" !important;
    position: absolute !important;
    left: 14px !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    width: 18px !important;
    height: 18px !important;
    background-color: var(--apple-text-secondary) !important;
    -webkit-mask-size: contain !important;
    mask-size: contain !important;
    -webkit-mask-repeat: no-repeat !important;
    mask-repeat: no-repeat !important;
    -webkit-mask-position: center !important;
    mask-position: center !important;
    transition: all 0.2s ease !important;
}

/* 非激活状态项 */
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    background: transparent !important;
    color: #4B5563 !important;
}

[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
    background: rgba(0, 0, 0, 0.04) !important;
    color: var(--apple-text-primary) !important;
}

[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover::before {
    background-color: var(--apple-text-primary) !important;
}

/* 激活选中状态：统一主题色高亮背景 (Apple Blue Capsule) */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: var(--apple-blue-subtle) !important;
    color: var(--apple-blue) !important;
    font-weight: 600 !important;
    box-shadow: none !important;
}

[data-testid="stSidebar"] .stButton > button[kind="primary"]::before {
    background-color: var(--apple-blue) !important;
}

/* 注入 9 大核心业务模块单色矢量图标 (Lucide SVG Icons, 显式 stroke='black' 蒙版) */
div[class*="st-key-nav_btn_dashboard"] button::before,
div[class*="nav_btn_dashboard"] button::before,
button[key*="nav_btn_dashboard"]::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='3' width='7' height='9'/%3E%3Crect x='14' y='3' width='7' height='5'/%3E%3Crect x='14' y='12' width='7' height='9'/%3E%3Crect x='3' y='16' width='7' height='5'/%3E%3C/svg%3E") !important;
}
div[class*="st-key-nav_btn_ads_analytics"] button::before,
div[class*="nav_btn_ads_analytics"] button::before,
button[key*="nav_btn_ads_analytics"]::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m3 11 18-5v12L3 14v-3z'/%3E%3Cpath d='M11.6 16.8a3 3 0 1 1-5.8-1.6'/%3E%3C/svg%3E") !important;
}
div[class*="st-key-nav_btn_sales_analytics"] button::before,
div[class*="nav_btn_sales_analytics"] button::before,
button[key*="nav_btn_sales_analytics"]::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='8' cy='21' r='1'/%3E%3Ccircle cx='19' cy='21' r='1'/%3E%3Cpath d='M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12'/%3E%3C/svg%3E") !important;
}
div[class*="st-key-nav_btn_inventory"] button::before,
div[class*="nav_btn_inventory"] button::before,
button[key*="nav_btn_inventory"]::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m7.5 4.27 9 5.15'/%3E%3Cpath d='M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z'/%3E%3Cpath d='m3.3 7 8.7 5 8.7-5'/%3E%3Cpath d='M12 22V12'/%3E%3C/svg%3E") !important;
}
div[class*="st-key-nav_btn_products"] button::before,
div[class*="nav_btn_products"] button::before,
button[key*="nav_btn_products"]::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z'/%3E%3Cpath d='M7 7h.01'/%3E%3C/svg%3E") !important;
}
div[class*="st-key-nav_btn_profitability"] button::before,
div[class*="nav_btn_profitability"] button::before,
button[key*="nav_btn_profitability"]::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpath d='M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8'/%3E%3Cpath d='M12 18V6'/%3E%3C/svg%3E") !important;
}
div[class*="st-key-nav_btn_ai_intelligence"] button::before,
div[class*="nav_btn_ai_intelligence"] button::before,
button[key*="nav_btn_ai_intelligence"]::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z'/%3E%3C/svg%3E") !important;
}
div[class*="st-key-nav_btn_data_hub"] button::before,
div[class*="nav_btn_data_hub"] button::before,
button[key*="nav_btn_data_hub"]::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cellipse cx='12' cy='5' rx='9' ry='3'/%3E%3Cpath d='M3 5V19A9 3 0 0 0 21 19V5'/%3E%3Cpath d='M3 12A9 3 0 0 0 21 12'/%3E%3C/svg%3E") !important;
}
div[class*="st-key-nav_btn_settings"] button::before,
div[class*="nav_btn_settings"] button::before,
button[key*="nav_btn_settings"]::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='4' x2='20' y1='21' y2='21'/%3E%3Cline x1='4' x2='20' y1='14' y2='14'/%3E%3Cline x1='4' x2='20' y1='7' y2='7'/%3E%3Ccircle cx='14' cy='21' r='2'/%3E%3Ccircle cx='8' cy='14' r='2'/%3E%3Ccircle cx='16' cy='7' r='2'/%3E%3C/svg%3E") !important;
}

/* =========================================================================
   5. 图表去噪与统一组件微调
   ========================================================================= */
/* 下拉菜单 Apple 规范微调 */
div[data-baseweb="select"] {
    border-radius: var(--apple-radius-button) !important;
    background: #FFFFFF !important;
    border: var(--apple-border) !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
}

div[data-baseweb="select"] > div {
    border-radius: var(--apple-radius-button) !important;
    border: none !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}

/* 统一选项卡 Tab 设计 */
.stTabs [data-baseweb="tab-list"] {
    background: #EAEAEF !important;
    border-radius: 12px !important;
    padding: 3px !important;
    gap: 3px !important;
    border-bottom: none !important;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 9px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 7px 16px !important;
    border: none !important;
    color: var(--apple-text-secondary) !important;
}

.stTabs [aria-selected="true"] {
    background: #FFFFFF !important;
    color: var(--apple-text-primary) !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06) !important;
}

/* 主内容区留白 */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3.5rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 100% !important;
}
</style>
"""


def inject_saas_theme():
    import streamlit as st
    st.markdown(SAAS_THEME_CSS, unsafe_allow_html=True)
    
    # 注入客户端自动展开防护与双向联动脚本
    try:
        import streamlit.components.v1 as components
        components.html(
            """
            <script>
            (function() {
                function checkAndExpandSidebar() {
                    try {
                        const pDoc = window.parent.document;
                        if (!pDoc) return;
                        
                        // 若侧边栏当前处于收起状态（存在展开按钮），自动点击展开
                        const expandBtn = pDoc.querySelector(
                            '[data-testid="stExpandSidebarButton"] button, ' +
                            '[data-testid="stExpandSidebarButton"], ' +
                            'button[aria-label="Expand sidebar"], ' +
                            '[data-testid="collapsedControl"]'
                        );
                        if (expandBtn) {
                            expandBtn.click();
                        }
                    } catch(e) {}
                }
                
                checkAndExpandSidebar();
                setTimeout(checkAndExpandSidebar, 80);
                setTimeout(checkAndExpandSidebar, 250);
                setTimeout(checkAndExpandSidebar, 600);
                setTimeout(checkAndExpandSidebar, 1200);
            })();
            </script>
            """,
            height=0,
            width=0,
        )
    except Exception:
        pass
