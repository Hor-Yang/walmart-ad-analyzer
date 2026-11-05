from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from .metrics import safe_divide

def analyze_placements(
    platform_df: Optional[pd.DataFrame],
    page_type_df: Optional[pd.DataFrame],
    macro_roas: Optional[float] = None,
) -> Dict[str, Any]:
    """
    平台与页面投放位置分析模块：
    1. 平台维度（app/mobile/desktop）：各自花费占比、ROAS、CPC、CVR；找出 ROAS 显著低于大盘（低于大盘60%）的端，提示下调出价
    2. 页面类型维度（search/browse/item/category/topic/homepage/others）：各自表现；标出花费占比高但 ROAS 低于大盘一半的位置，提示裁剪流量
    """
    res = {
        "platform_df": pd.DataFrame(),
        "page_type_df": pd.DataFrame(),
        "platform_insights": [],
        "page_type_insights": [],
        "macro_roas": macro_roas or 3.36,
    }

    # =========================================================================
    # 1. 平台维度分析
    # =========================================================================
    if platform_df is not None and not platform_df.empty:
        pdf = platform_df.copy()
        
        # 兼容平台列名
        plat_col = None
        for cand in ["平台", "platform", "设备", "device"]:
            for col in pdf.columns:
                if cand == str(col).strip().lower():
                    plat_col = col
                    break
            if plat_col:
                break
        if plat_col and plat_col != "平台":
            pdf = pdf.rename(columns={plat_col: "平台"})
        elif "平台" not in pdf.columns:
            pdf["平台"] = "默认平台"

        for col in ["广告花费", "曝光量", "点击", "广告订单", "总销售额"]:
            if col in pdf.columns:
                pdf[col] = pd.to_numeric(pdf[col], errors="coerce").fillna(0.0)
            else:
                pdf[col] = 0.0

        pdf["平台"] = pdf["平台"].astype(str).str.lower().str.strip()

        # 分子分母先加总再相除重算
        plat_agg = pdf.groupby("平台").agg(
            花费=("广告花费", "sum"),
            点击=("点击", "sum"),
            曝光=("曝光量", "sum"),
            订单=("广告订单", "sum"),
            销售额=("总销售额", "sum"),
        ).reset_index()

        total_plat_spend = plat_agg["花费"].sum()
        total_plat_sales = plat_agg["销售额"].sum()
        calc_macro_roas = safe_divide(total_plat_sales, total_plat_spend)
        if calc_macro_roas is not None and calc_macro_roas > 0:
            res["macro_roas"] = calc_macro_roas

        m_roas = res["macro_roas"]

        plat_agg["花费占比"] = plat_agg["花费"] / (total_plat_spend if total_plat_spend > 0 else 1.0)
        plat_agg["ROAS"] = safe_divide(plat_agg["销售额"], plat_agg["花费"])
        plat_agg["CPC"] = safe_divide(plat_agg["花费"], plat_agg["点击"])
        plat_agg["CVR"] = safe_divide(plat_agg["订单"], plat_agg["点击"])
        plat_agg["CTR"] = safe_divide(plat_agg["点击"], plat_agg["曝光"])

        # 诊断与建议
        plat_actions = []
        plat_insights = []
        for _, r in plat_agg.iterrows():
            p_name = r["平台"]
            r_val = r["ROAS"]
            spend_pct = r["花费占比"] * 100

            if r_val is not None and not pd.isna(r_val):
                if r_val < m_roas * 0.60:
                    action = f"ROAS ({r_val:.2f}) 显著低于大盘60%（基准 {m_roas*0.60:.2f}），建议对该端下调出价 15%~25%"
                    plat_insights.append(f"🔴 **{p_name.upper()} 端表现欠佳**：花费占比 {spend_pct:.1f}%，ROAS 仅为 {r_val:.2f}，建议下调出价。")
                elif r_val >= m_roas * 1.15:
                    action = f"ROAS ({r_val:.2f}) 高于大盘，表现优质，可维持高位竞价"
                    plat_insights.append(f"🟢 **{p_name.upper()} 端产出强劲**：ROAS 达 {r_val:.2f}，表现优于大盘。")
                else:
                    action = "表现达标，建议保持当前出价"
            else:
                action = "无消耗或产出数据"

            plat_actions.append(action)

        plat_agg["诊断建议"] = plat_actions
        plat_agg = plat_agg.sort_values("花费", ascending=False).reset_index(drop=True)
        res["platform_df"] = plat_agg
        res["platform_insights"] = plat_insights

    # =========================================================================
    # 2. 页面类型维度分析
    # =========================================================================
    if page_type_df is not None and not page_type_df.empty:
        pg_df = page_type_df.copy()

        # 兼容页面类型列名
        page_col = None
        for cand in ["页面类型", "page_type", "page type", "pagetype", "页面", "placement", "位置"]:
            for col in pg_df.columns:
                if cand == str(col).strip().lower():
                    page_col = col
                    break
            if page_col:
                break
        if page_col and page_col != "页面类型":
            pg_df = pg_df.rename(columns={page_col: "页面类型"})
        elif "页面类型" not in pg_df.columns:
            pg_df["页面类型"] = "默认位置"

        for col in ["广告花费", "曝光量", "点击", "广告订单", "总销售额"]:
            if col in pg_df.columns:
                pg_df[col] = pd.to_numeric(pg_df[col], errors="coerce").fillna(0.0)
            else:
                pg_df[col] = 0.0

        pg_df["页面类型"] = pg_df["页面类型"].astype(str).str.lower().str.strip()

        page_agg = pg_df.groupby("页面类型").agg(
            花费=("广告花费", "sum"),
            点击=("点击", "sum"),
            曝光=("曝光量", "sum"),
            订单=("广告订单", "sum"),
            销售额=("总销售额", "sum"),
        ).reset_index()

        total_pg_spend = page_agg["花费"].sum()
        m_roas = res["macro_roas"]

        page_agg["花费占比"] = page_agg["花费"] / (total_pg_spend if total_pg_spend > 0 else 1.0)
        page_agg["ROAS"] = safe_divide(page_agg["销售额"], page_agg["花费"])
        page_agg["CPC"] = safe_divide(page_agg["花费"], page_agg["点击"])
        page_agg["CVR"] = safe_divide(page_agg["订单"], page_agg["点击"])
        page_agg["CTR"] = safe_divide(page_agg["点击"], page_agg["曝光"])

        # 诊断与建议：标出"花费占比高但 ROAS 低于大盘一半"的位置，提示裁剪该位置流量
        page_actions = []
        page_insights = []

        for _, r in page_agg.iterrows():
            name = r["页面类型"]
            spend_pct = r["花费占比"]
            r_val = r["ROAS"]
            orders = r["订单"]

            # 花费占比高 (>= 5%) 且 ROAS 低于大盘一半
            if spend_pct >= 0.05 and (r_val is None or r_val < m_roas * 0.50):
                action = f"⚠️ 花费占比高（{spend_pct*100:.1f}%）但 ROAS 低于大盘一半（{m_roas*0.50:.2f}），建议下调溢价或裁剪该位置流量"
                page_insights.append(f"⚠️ **{name} 位置产出偏低**：花费占比 {spend_pct*100:.1f}%，ROAS 仅为 {r_val if r_val else 0:.2f}，低于大盘一半，需注意控成本。")
            elif orders == 0 and r["花费"] >= 20.0:
                action = f"🚨 零转化低效位（累计花费 ${r['花费']:.2f}），建议大幅降低竞价或排除该位置"
                page_insights.append(f"🚨 **{name} 位置零转化**：花费 ${r['花费']:.2f} 且 0 订单，建议下调出价。")
            elif r_val is not None and r_val >= m_roas:
                action = f"优质展示位（ROAS {r_val:.2f}），建议保持或加大出价倾斜"
            else:
                action = "表现正常，维持当前策略"

            page_actions.append(action)

        page_agg["诊断建议"] = page_actions
        page_agg = page_agg.sort_values("花费", ascending=False).reset_index(drop=True)
        res["page_type_df"] = page_agg
        res["page_type_insights"] = page_insights

    return res
