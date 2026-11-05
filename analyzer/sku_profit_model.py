import io
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from .metrics import safe_divide

def generate_sku_cost_template() -> bytes:
    """生成 SKU 商品单位成本配置 Excel 模板"""
    df = pd.DataFrame({
        "SKU": ["SKU-BED-001", "SKU-BED-002", "SKU-CHAIR-003"],
        "采购成本($)": [25.0, 32.0, 15.0],
        "头程物流($)": [12.0, 15.0, 6.0],
        "尾程运费($)": [18.0, 22.0, 9.0],
        "平台佣金率(%)": [15.0, 15.0, 15.0],
        "其他包装损耗($)": [2.0, 2.5, 1.0],
        "参考售价($)": [99.0, 129.0, 59.0],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="成本配置表")
    buf.seek(0)
    return buf.getvalue()

def load_sku_cost_table(file_obj: Any) -> Tuple[Dict[str, Dict[str, float]], Optional[str]]:
    """
    读取并解析 SKU 成本表：
    支持字段：SKU、采购成本、头程物流、尾程运费、平台佣金率、其他成本。
    返回: (cost_dict, error_msg)
    """
    if file_obj is None:
        return {}, None
    try:
        if hasattr(file_obj, "name") and str(file_obj.name).lower().endswith(".csv"):
            df = pd.read_csv(file_obj)
        elif hasattr(file_obj, "getvalue"):
            df = pd.read_excel(io.BytesIO(file_obj.getvalue()))
        else:
            df = pd.read_excel(file_obj)
    except Exception as e:
        return {}, f"成本表格读取失败: {e}"

    if df.empty:
        return {}, "成本表格为空"

    # 规范化列名
    sku_col = None
    for cand in ["sku", "商品sku", "item_sku", "平台sku", "项目id", "item id"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                sku_col = col
                break
        if sku_col:
            break
    if not sku_col:
        return {}, "未找到 SKU 标识列（请提供包含'SKU'的列名）"

    cost_dict = {}
    for _, row in df.iterrows():
        sku_val = str(row[sku_col]).strip().split(".")[0]
        if not sku_val or sku_val.lower() in ("nan", "none", "-"):
            continue

        cogs = 0.0
        first_leg = 0.0
        last_leg = 0.0
        commission_rate = 0.15 # 默认类目佣金 15%
        other_cost = 0.0

        for col in df.columns:
            c_name = str(col).strip().lower()
            val = row[col]
            if pd.isna(val):
                continue
            v_num = pd.to_numeric(str(val).replace("$", "").replace("%", "").strip(), errors="coerce")
            if pd.isna(v_num):
                continue
            num_f = float(v_num)

            if any(k in c_name for k in ["采购", "cogs", "供货价", "出厂价"]):
                cogs = num_f
            elif any(k in c_name for k in ["头程", "海运", "空运", "first leg", "first_leg"]):
                first_leg = num_f
            elif any(k in c_name for k in ["尾程", "配送", "wfs", "fba", "last leg", "last_leg"]):
                last_leg = num_f
            elif any(k in c_name for k in ["佣金", "commission", "referral"]):
                commission_rate = num_f / 100.0 if num_f > 1.0 else num_f
            elif any(k in c_name for k in ["其他", "包装", "损耗", "other"]):
                other_cost = num_f

        unit_product_cost = cogs + first_leg + last_leg + other_cost
        cost_dict[sku_val] = {
            "cogs": cogs,
            "first_leg": first_leg,
            "last_leg": last_leg,
            "commission_rate": commission_rate,
            "other_cost": other_cost,
            "unit_product_cost": unit_product_cost,
        }

    return cost_dict, None

def calculate_sku_profit_analytics(
    sku_ad_df: pd.DataFrame,
    cost_dict: Dict[str, Dict[str, float]],
    default_margin: float = 0.35,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    打通广告数据与商品成本底表：
    计算每个 SKU 的真实广告前利润、广告花费与广告后真实净贡献。
    """
    if sku_ad_df is None or sku_ad_df.empty:
        return pd.DataFrame(), {}

    df = sku_ad_df.copy()
    results = []

    total_sales_all = 0.0
    total_spend_all = 0.0
    total_pre_profit_all = 0.0
    total_post_profit_all = 0.0

    for _, r in df.iterrows():
        sku = str(r.get("SKU", r.get("SKU展示", "未知"))).strip()
        spend = float(r.get("花费", r.get("广告花费", 0.0)) or 0.0)
        sales = float(r.get("销售额", r.get("总销售额", 0.0)) or 0.0)
        orders = int(r.get("订单", r.get("广告订单", 0)) or 0)
        aov = sales / orders if orders > 0 else (sales if sales > 0 else 0.0)

        cost_info = cost_dict.get(sku)
        if cost_info and aov > 0:
            unit_cost = cost_info["unit_product_cost"]
            comm_rate = cost_info["commission_rate"]
            unit_commission = aov * comm_rate
            unit_pre_ad_profit = aov - unit_cost - unit_commission
            pre_ad_margin = unit_pre_ad_profit / aov if aov > 0 else default_margin
            total_pre_ad_profit = orders * unit_pre_ad_profit
            has_cost = True
        else:
            # 未配置成本底表时使用保本默认毛利率估算
            pre_ad_margin = default_margin
            total_pre_ad_profit = sales * pre_ad_margin
            unit_pre_ad_profit = (total_pre_ad_profit / orders) if orders > 0 else 0.0
            unit_cost = aov * (1.0 - pre_ad_margin - 0.15)
            has_cost = False

        # 广告后真实净利润 = 广告前毛利总额 - 广告花费
        post_ad_net_profit = total_pre_ad_profit - spend
        net_profit_margin = post_ad_net_profit / sales if sales > 0 else 0.0
        actual_acos = spend / sales if sales > 0 else (1.0 if spend > 0 else 0.0)
        breakeven_acos = max(0.05, min(0.90, pre_ad_margin))
        breakeven_roas = 1.0 / breakeven_acos if breakeven_acos > 0 else 2.86

        if post_ad_net_profit > 0 and actual_acos <= breakeven_acos * 0.7:
            profit_tier = "🚀 强力净盈利"
            badge = "badge-green"
            advice = "真实净贡献极高，该品具备充分的安全垫，可果断加大广告预算拓量"
        elif post_ad_net_profit >= 0:
            profit_tier = "⚖️ 保本正贡献"
            badge = "badge-blue"
            advice = "广告费未击穿商品毛利，贡献正向净现金流，建议精细化否词控本"
        else:
            profit_tier = "🚨 真实净亏损"
            badge = "badge-red"
            advice = f"广告费吞噬了全部毛利，净亏损 ${abs(post_ad_net_profit):,.2f}，必须立刻降权或暂停止血"

        total_sales_all += sales
        total_spend_all += spend
        total_pre_profit_all += total_pre_ad_profit
        total_post_profit_all += post_ad_net_profit

        results.append({
            "SKU": sku,
            "成本来源": "已匹配成本表" if has_cost else "按行业基准估算",
            "广告销售额": sales,
            "广告订单": orders,
            "平均客单价": aov,
            "广告花费": spend,
            "实际ACoS": actual_acos,
            "动态保本ACoS": breakeven_acos,
            "保本ROAS": breakeven_roas,
            "广告前毛利": total_pre_ad_profit,
            "广告前毛利率": pre_ad_margin,
            "广告后真实净利": post_ad_net_profit,
            "广告后净利率": net_profit_margin,
            "盈利状态": profit_tier,
            "状态徽章": badge,
            "经营决策指令": advice,
        })

    res_df = pd.DataFrame(results).sort_values("广告后真实净利", ascending=False).reset_index(drop=True)

    summary_stats = {
        "total_sales": total_sales_all,
        "total_spend": total_spend_all,
        "total_pre_ad_profit": total_pre_profit_all,
        "total_post_ad_net_profit": total_post_profit_all,
        "overall_net_margin": total_post_profit_all / total_sales_all if total_sales_all > 0 else 0.0,
        "configured_sku_count": len([r for r in results if r["成本来源"] == "已匹配成本表"]),
        "profitable_sku_count": len([r for r in results if r["广告后真实净利"] > 0]),
        "loss_sku_count": len([r for r in results if r["广告后真实净利"] < 0]),
    }

    return res_df, summary_stats
