"""
企业级 SaaS 统一视觉设计系统 (Design System)
规范：现代、简洁、低饱和度、以数据为中心、卡片化布局
"""

SAAS_THEME_CSS = """
<style>
/* 引入现代系统字体族 */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #1e293b;
}

/* 隐藏 Streamlit 原生装饰性元素 */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.stDeployButton {display: none;}

/* 主工作区背景与边距优化 */
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2.5rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100% !important;
}

/* 顶部全局筛选条卡片 */
.global-filter-bar {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 18px 4px 18px;
    margin-bottom: 18px;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
}

.filter-bar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 13px;
    font-weight: 600;
    color: #475569;
}

/* KPI 指标卡 */
.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 12px;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.kpi-card:hover {
    box-shadow: 0 4px 12px 0 rgba(0, 0, 0, 0.05);
}
.kpi-title {
    font-size: 13px;
    font-weight: 500;
    color: #64748b;
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.kpi-value {
    font-size: 26px;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.2;
    letter-spacing: -0.02em;
}
.kpi-sub {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.kpi-delta-up {
    color: #059669;
    font-weight: 600;
}
.kpi-delta-down {
    color: #dc2626;
    font-weight: 600;
}

/* 模块容器卡片 */
.saas-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 20px 22px;
    margin-bottom: 18px;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.03);
}

.saas-card-header {
    font-size: 16px;
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

/* 状态徽章 */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 600;
}
.badge-blue { background-color: #eff6ff; color: #1d4ed8; }
.badge-green { background-color: #ecfdf5; color: #047857; }
.badge-amber { background-color: #fffbeb; color: #b45309; }
.badge-red { background-color: #fef2f2; color: #b91c1c; }
.badge-slate { background-color: #f1f5f9; color: #475569; }

/* 侧边导航栏样式优化 */
[data-testid="stSidebar"] {
    background-color: #0f172a !important;
    color: #f8fafc !important;
    border-right: 1px solid #1e293b;
}

[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
    color: #e2e8f0 !important;
}

[data-testid="stSidebar"] hr {
    border-color: #1e293b !important;
}

/* 空状态卡片 */
.empty-state-box {
    text-align: center;
    padding: 48px 24px;
    background: #f8fafc;
    border: 1px dashed #cbd5e1;
    border-radius: 12px;
    margin: 20px 0;
}
.empty-state-icon {
    font-size: 40px;
    color: #94a3b8;
    margin-bottom: 12px;
}
.empty-state-title {
    font-size: 16px;
    font-weight: 600;
    color: #334155;
    margin-bottom: 6px;
}
.empty-state-desc {
    font-size: 13px;
    color: #64748b;
    max-width: 480px;
    margin: 0 auto 16px auto;
    line-height: 1.5;
}
</style>
"""


def inject_saas_theme():
    import streamlit as st
    st.markdown(SAAS_THEME_CSS, unsafe_allow_html=True)
