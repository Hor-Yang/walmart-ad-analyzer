"""
产品管理模块视图 (Product Management View)
统一 Master SKU 产品档案中心：SPU、平台商品 ID 映射 (Walmart/Wayfair/eBay)、类目、成本要素与生命周期管理
"""

import streamlit as st
import pandas as pd
from frontend.components.kpi_card import render_kpi_card, render_empty_state
from analyzer.sku_profit_model import generate_sku_cost_template


def render_products_view():
    st.markdown("## 🏷️ 产品管理 (Product Management)")
    st.caption("统一主商品档案库：一个 Master SKU 关联多个平台商品 ID，全生命周期与成本属性穿透")

    sku_mapping = st.session_state.get("sku_mapping", {})
    sku_cost_df = st.session_state.get("sku_cost_df")
    sec_data = st.session_state.get("section_data", {})
    item_df = sec_data.get("ad_item")

    # 构建统一商品档案表
    master_records = []
    
    # 1. 优先从映射表构建
    if sku_mapping:
        for item_id, sku in sku_mapping.items():
            master_records.append({
                "Master SKU": sku,
                "SPU 款号": sku.split("-")[0] if "-" in sku else sku,
                "Walmart Item ID": str(item_id),
                "Wayfair SKU": "待映射",
                "eBay Item ID": "待映射",
                "类目": "家具/床架 (主营)",
                "品牌": "自营主品牌",
                "生命周期": "成熟放量期",
                "映射状态": "已生效",
            })
    elif item_df is not None and not item_df.empty:
        sku_col = "sku" if "sku" in item_df.columns else "item_id"
        for s in item_df[sku_col].dropna().unique():
            master_records.append({
                "Master SKU": str(s),
                "SPU 款号": str(s).split("-")[0] if "-" in str(s) else str(s),
                "Walmart Item ID": str(s),
                "Wayfair SKU": "待映射",
                "eBay Item ID": "待映射",
                "类目": "跨境通用",
                "品牌": "主品牌",
                "生命周期": "成长期",
                "映射状态": "自动推导",
            })

    if not master_records:
        render_empty_state(
            title="暂无统一商品档案",
            description="系统尚未绑定 Master SKU 映射关系或商品广告数据。请在「数据中心」上传「SKU 映射表」以激活多平台统一商品档案库。",
            icon="🏷️",
            action_label="👉 前往数据中心上传 SKU 映射表",
            action_key="prod_to_dh_btn",
        )
        if st.session_state.get("prod_to_dh_btn"):
            st.session_state["active_page"] = "data_hub"
            st.rerun()
        return

    prod_df = pd.DataFrame(master_records).drop_duplicates(subset=["Master SKU"])

    # 1. 产品档案 KPI
    tot_master = len(prod_df)
    active_mapped = len(prod_df[prod_df["Walmart Item ID"] != "待映射"])
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("Master SKU 总数", f"{tot_master} 款", sub_title="企业唯一主编码", badge="核心资产", badge_color="blue")
    with k2:
        render_kpi_card("Walmart 已映射商品", f"{active_mapped} 款", sub_title="自动对齐广告与出单", badge="已对齐", badge_color="green")
    with k3:
        render_kpi_card("Wayfair 待对齐渠道", "0 款", sub_title="预留接口字段准备就绪")
    with k4:
        render_kpi_card("成本档案完善度", f"{len(sku_cost_df) if sku_cost_df is not None else 0} / {tot_master}", sub_title="已配置采购与头尾程", badge="全成本", badge_color="slate")

    st.markdown("---")

    # 2. 档案明细与成本模板下载
    d_col1, d_col2 = st.columns([1.5, 0.5])
    with d_col1:
        st.markdown("#### 📑 统一 Master SKU 与渠道 ID 映射档案库")
    with d_col2:
        cost_tmpl_bytes = generate_sku_cost_template()
        st.download_button(
            "📥 下载 SKU 成本与属性模板",
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
