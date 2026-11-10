"""
产品管理模块视图 (Product Management View)
统一 Master SKU 产品档案中心：SPU、平台商品 ID 映射 (Walmart/Wayfair/eBay)、类目、成本要素与生命周期管理
"""

import streamlit as st
import pandas as pd
from frontend.components.kpi_card import render_kpi_card, render_empty_state, render_page_header
from analyzer.sku_profit_model import generate_sku_cost_template
from frontend.utils.error_handler import safe_view_render


# // FIX: 全局与模块级异常兜底装饰器，阻断 Traceback 裸露，提供生产级友好提示
@safe_view_render("产品管理")
def render_products_view():
    render_page_header("产品管理", "统一主商品档案库：一个 Master SKU 关联多个平台商品 ID，全生命周期与成本属性穿透")

    sku_mapping = st.session_state.get("sku_mapping", {})
    sku_cost_df = st.session_state.get("sku_cost_df")
    sec_data = st.session_state.get("section_data", {})
    item_df = sec_data.get("ad_item")

    # // FIX: 统一连接中央商品目录服务 (Master Catalog Service)
    from services.catalog_service import get_catalog_service
    catalog_svc = get_catalog_service()
    if sku_mapping:
        catalog_svc.bulk_import_mappings(sku_mapping, platform="walmart")

    prod_df = catalog_svc.get_full_catalog_df()

    # 构建统一商品档案表兜底
    if prod_df.empty:
        master_records = []
        if sku_mapping:
            for item_id, sku in sku_mapping.items():
                master_records.append({
                    "Master SKU": sku,
                    "SPU 款号": sku.split("-")[0] if "-" in sku else sku,
                    "Walmart Item ID": str(item_id),
                    "Amazon ASIN": "-",
                    "Wayfair SKU": "待映射",
                    "一级类目": "家具/床架 (主营)",
                    "二级类目": "床架",
                    "生命周期": "成熟放量期",
                    "映射状态": "已生效",
                })
        elif item_df is not None and not item_df.empty:
            # // FIX: 防御性识别 SKU / 项目 ID 列名，防止缺失字段抛出 KeyError
            sku_col = next((c for c in ["SKU", "sku", "对应SKU", "商品SKU", "项目ID", "item_id", "Item ID"] if c in item_df.columns), item_df.columns[0])
            for s in item_df[sku_col].dropna().unique():
                s_str = str(s).strip()
                if not s_str or s_str in ["nan", "None", "-"]:
                    continue
                master_records.append({
                    "Master SKU": s_str,
                    "SPU 款号": s_str.split("-")[0] if "-" in s_str else s_str,
                    "Walmart Item ID": s_str,
                    "Amazon ASIN": "-",
                    "Wayfair SKU": "待映射",
                    "一级类目": "跨境通用",
                    "二级类目": "通用",
                    "生命周期": "成长期",
                    "映射状态": "自动推导",
                })
        if master_records:
            prod_df = pd.DataFrame(master_records).drop_duplicates(subset=["Master SKU"])

    if prod_df.empty:
        render_empty_state(
            title="暂无统一商品档案",
            description="系统尚未绑定 Master SKU 映射关系或商品广告数据。请在「数据中心」上传「SKU 映射表」以激活多平台统一商品档案库。",
            icon_type="products",
            action_label="前往数据中心上传 SKU 映射表",
            action_key="prod_to_dh_btn",
        )
        if st.session_state.get("prod_to_dh_btn"):
            st.session_state["active_page"] = "data_hub"
            st.rerun()
        return

    # 1. 产品档案 KPI
    tot_master = len(prod_df)
    active_mapped = len(prod_df[prod_df["Walmart Item ID"] != "-"]) if "Walmart Item ID" in prod_df.columns else tot_master
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("Master SKU 总数", f"{tot_master} 款", sub_title="企业唯一主编码", badge="核心资产", badge_color="blue")
    with k2:
        render_kpi_card("Walmart 已映射商品", f"{active_mapped} 款", sub_title="自动对齐广告与出单", badge="已对齐", badge_color="green")
    with k3:
        render_kpi_card("Wayfair 待对齐渠道", "0 款", sub_title="预留接口字段准备就绪")
    with k4:
        render_kpi_card("成本档案完善度", f"{len(sku_cost_df) if sku_cost_df is not None else 0} / {tot_master}", sub_title="已配置采购与头尾程", badge="全成本", badge_color="slate")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 2. 档案明细与成本模板下载
    d_col1, d_col2 = st.columns([1.5, 0.5])
    with d_col1:
        st.markdown("#### 统一 Master SKU 与渠道 ID 映射档案库")
    with d_col2:
        cost_tmpl_bytes = generate_sku_cost_template()
        st.download_button(
            "下载 SKU 成本与属性模板",
            data=cost_tmpl_bytes,
            file_name="sku_cost_attributes_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.dataframe(
        prod_df,
        column_config={
            "Master SKU": st.column_config.TextColumn("企业统一主商品编码 (Master SKU)", width="medium"),
            "SPU 款号": st.column_config.TextColumn("SPU", width="small"),
            "Walmart Item ID": st.column_config.TextColumn("Walmart 平台渠道 ID", width="medium"),
            "Wayfair SKU": st.column_config.TextColumn("Wayfair 渠道编码", width="small"),
            "eBay Item ID": st.column_config.TextColumn("eBay 渠道编码", width="small"),
            "类目": st.column_config.TextColumn("商品类目"),
            "生命周期": st.column_config.TextColumn("生命周期阶段"),
            "映射状态": st.column_config.TextColumn("状态"),
        },
        use_container_width=True,
        hide_index=True,
    )
