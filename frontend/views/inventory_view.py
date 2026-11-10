"""
库存管理模块视图 (Inventory Management View)
多仓库存全景监控：可售库存、在途海运、锁定仓储、日均销量、周转天数与缺货断货智能预警
"""

import streamlit as st
import pandas as pd
from frontend.components.kpi_card import render_kpi_card, render_empty_state, render_page_header
from frontend.utils.formatters import safe_num_divide
from frontend.utils.error_handler import safe_view_render


# // FIX: 全局与模块级异常兜底装饰器，阻断 Traceback 裸露，提供生产级友好提示
@safe_view_render("库存管理")
def render_inventory_view():
    render_page_header("库存管理", "全链路仓储供应链监控：平台仓、第三方海外仓、国内在途海运与断货风险联动")

    # // FIX: 【任务 3】业务板块逻辑释义 Expander（降低运营人员认知门槛，严格使用纯净文字，无彩色 Emoji）
    with st.expander("[运营逻辑解读] DOS 安全周转天数与断货断权保护联动", expanded=False):
        st.markdown(
            """
            - **可售天数 (DOS, Days of Supply) 安全警戒线**：
              DOS = 当前可用在库库存 ÷ 近 30 天日均销量。
              - DOS < 15 天：**极度濒危**，AI 决策中枢强制拦截加价与拓词，启动提价控速与断货保护；
              - 15 ≤ DOS < 25 天：**补货预警**，需立即向供应链下达生产或海运补货指令；
              - 25 ≤ DOS ≤ 90 天：**健康周转区间**；
              - DOS > 90 天：**呆滞积压**，需启动冗余促销或站外清仓，降低仓储费。
            - **广告 × 库存 联动断货保护**：
              Listing 一旦断货，沃尔玛搜索算法会迅速扣减商品权重。与其断货后重新花数倍广告费激活冷启动，必须在濒危期主动通过出价调降与控速保持在线连续性。
            """
        )

    sec_data = st.session_state.get("section_data", {})
    item_df = sec_data.get("ad_item")
    inventory_df = sec_data.get("inventory") or st.session_state.get("inventory_df")

    # // FIX: 彻底移除模拟库存生成逻辑！没有真实库存数据时，必须展示空状态
    if inventory_df is None or not isinstance(inventory_df, pd.DataFrame) or inventory_df.empty:
        render_empty_state(
            title="暂无真实库存快照数据",
            description="系统尚未导入商品在库或在途真实报表。为确保经营决策严肃性，系统已彻底禁用基于公式的模拟虚假库存推演。请在「数据中心」上传真实的「库存快照表」以开启周转监控与断货预警。",
            icon_type="inventory",
            action_label="前往数据中心上传库存表",
            action_key="inv_to_dh_btn",
        )
        if st.session_state.get("inv_to_dh_btn"):
            st.session_state["active_page"] = "data_hub"
            st.rerun()
        return

    # 基于真实导入的库存数据解析各仓与周转
    sku_col = next((c for c in ["SKU", "sku", "商品SKU", "Item ID", "项目ID"] if c in inventory_df.columns), inventory_df.columns[0])
    avail_col = next((c for c in ["可用库存", "总可用在库", "平台仓可用", "available_stock", "现货", "在库"] if c in inventory_df.columns), None)
    transit_col = next((c for c in ["在途", "在途海运", "在途库存", "in_transit", "海快在途"] if c in inventory_df.columns), None)

    # 结合广告出单量计算日均出单速度
    velocity_map = {}
    if item_df is not None and not item_df.empty:
        item_sku_c = next((c for c in ["SKU", "sku", "项目ID", "item_id"] if c in item_df.columns), None)
        item_ord_c = next((c for c in ["广告订单", "订单量", "订单", "orders"] if c in item_df.columns), None)
        if item_sku_c and item_ord_c:
            v_agg = item_df.groupby(item_sku_c)[item_ord_c].sum().to_dict()
            velocity_map = {str(k).split('.')[0].strip(): float(v)/30.0 for k, v in v_agg.items()}

    inv_records = []
    for _, row in inventory_df.iterrows():
        s = str(row[sku_col]).split('.')[0].strip()
        avail_stock = int(pd.to_numeric(row[avail_col], errors="coerce")) if avail_col else 0
        in_transit = int(pd.to_numeric(row[transit_col], errors="coerce")) if transit_col else 0
        daily_velocity = round(velocity_map.get(s, 0.0), 2)
        days_of_supply = round(avail_stock / daily_velocity, 0) if daily_velocity > 0 else 999

        status = "健康充足"
        if days_of_supply < 15:
            status = "极度濒危"
        elif days_of_supply < 25:
            status = "补货预警"
        elif days_of_supply > 90:
            status = "呆滞积压"

        inv_records.append({
            "SKU": s,
            "总可用在库": avail_stock,
            "在途海运": in_transit,
            "日均销量 (件/天)": daily_velocity,
            "预估可售天数 (DOS)": int(days_of_supply),
            "库存健康状态": status,
            "建议采购补货量": int(daily_velocity * 60 - avail_stock - in_transit) if (avail_stock + in_transit) < (daily_velocity * 60) else 0,
        })

    inv_df = pd.DataFrame(inv_records)

    # 1. 核心库存看板指标
    tot_avail = inv_df["总可用在库"].sum()
    tot_transit = inv_df["在途海运"].sum()
    risk_skus = len(inv_df[inv_df["预估可售天数 (DOS)"] < 25])
    avg_dos = int(inv_df["预估可售天数 (DOS)"].median())

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("全仓总可售在库", f"{tot_avail:,} 件", sub_title="平台仓 + 海外仓现货", badge="现货", badge_color="green")
    with k2:
        render_kpi_card("在途海运海快", f"{tot_transit:,} 件", sub_title="已出运/港口清关中", badge="在途", badge_color="blue")
    with k3:
        render_kpi_card("中位周转天数 (DOS)", f"{avg_dos} 天", sub_title="大盘平均安全周转线: 45天")
    with k4:
        r_badge = "green" if risk_skus == 0 else "red"
        render_kpi_card("断货风险 SKU 数", f"{risk_skus} 款", sub_title="预估周转低于 25 天", badge=f"{risk_skus}款预警", badge_color=r_badge)

    st.markdown("---")

    # 2. 详细库存台账与联动保护
    st.markdown("#### 各 SKU 实时库存快照与智能补货建议")
    # // FIX: 【任务 1】改用 Streamlit 原生容器与排版，彻底杜绝 HTML 标签外泄
    with st.container(border=True):
        st.markdown("**跨模块联动保护：广告 × 库存**")
        st.caption("当某款 SKU 的可售天数低于 15 天时，AI 决策中枢将自动发出拦截指令：「禁止加大广告出价或拓词放量」，防止断货导致 Listing 权重断崖式下跌。")
    st.dataframe(
        inv_df,
        column_config={
            "SKU": st.column_config.TextColumn("统一商品编码 (Master SKU)", width="large"),
            "总可用在库": st.column_config.NumberColumn("总现货库存", format="%d 件"),
            "日均销量 (件/天)": st.column_config.NumberColumn("日销速度", format="%.1f 件/天"),
            "预估可售天数 (DOS)": st.column_config.NumberColumn("可售天数", format="%d 天"),
            "在途海运": st.column_config.NumberColumn("在途库存", format="%d 件"),
            "建议采购补货量": st.column_config.NumberColumn("建议补货下单", format="%d 件"),
            "库存健康状态": st.column_config.TextColumn("健康评估"),
        },
        use_container_width=True,
        hide_index=True,
    )
