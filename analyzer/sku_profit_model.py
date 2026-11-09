"""
SKU 单位经济学与真实贡献利润核算模型 (SKU Profitability & Unit Economics Model)
遵循原则：
1. 先按 SKU 级汇总，再进行单品单位经济学穿透核算；
2. 严格区分广告订单 (Orders) 与销售件数 (Units Sold)；
3. 严格区分真实已核算成本与估算成本；
4. 缺失关键成本时坚决不伪造净利润数字，标记为“成本缺失待补录”；
5. 精准计算广告前贡献利润、广告后贡献利润、SKU 级保本 ACoS 与目标 ACoS。
"""

import io
from typing import Any, Dict, List, Optional, Tuple, Union
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


# // FIX: 统一成本表导入接口，返回 (cost_df, cost_dict, error_msg) 三元组
def load_sku_cost_table(file_obj: Any) -> Tuple[pd.DataFrame, Dict[str, Dict[str, float]], Optional[str]]:
    """
    读取并解析 SKU 成本表：
    支持字段：SKU、采购成本、头程物流、尾程运费、平台佣金率、其他成本。
    返回: (cost_df, cost_dict, error_msg)
    """
    if file_obj is None:
        return pd.DataFrame(), {}, None
    try:
        if hasattr(file_obj, "name") and str(file_obj.name).lower().endswith(".csv"):
            df = pd.read_csv(file_obj)
        elif hasattr(file_obj, "getvalue"):
            df = pd.read_excel(io.BytesIO(file_obj.getvalue()))
        else:
            df = pd.read_excel(file_obj)
    except Exception as e:
        return pd.DataFrame(), {}, f"成本表格读取失败: {e}"

    if df.empty:
        return pd.DataFrame(), {}, "成本表格为空"

    # 规范化列名查找 SKU
    sku_col = None
    for cand in ["sku", "商品sku", "item_sku", "平台sku", "项目id", "item id", "seller sku"]:
        for col in df.columns:
            if cand == str(col).strip().lower():
                sku_col = col
                break
        if sku_col:
            break
    if not sku_col:
        return pd.DataFrame(), {}, "未找到 SKU 标识列（请提供包含'SKU'的列名）"

    cost_dict: Dict[str, Dict[str, float]] = {}
    parsed_rows: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        sku_val = str(row[sku_col]).strip().split(".")[0]
        if not sku_val or sku_val.lower() in ("nan", "none", "-"):
            continue

        cogs = 0.0
        first_leg = 0.0
        last_leg = 0.0
        commission_rate = 0.15
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
        cost_item = {
            "cogs": round(cogs, 2),
            "first_leg": round(first_leg, 2),
            "last_leg": round(last_leg, 2),
            "commission_rate": round(commission_rate, 4),
            "other_cost": round(other_cost, 2),
            "unit_product_cost": round(unit_product_cost, 2),
        }
        cost_dict[sku_val] = cost_item
        parsed_rows.append({
            "SKU": sku_val,
            "采购成本": cogs,
            "头程物流": first_leg,
            "尾程运费": last_leg,
            "平台佣金率": commission_rate,
            "其他损耗": other_cost,
            "单位产品总成本": unit_product_cost,
        })

    cost_df = pd.DataFrame(parsed_rows)
    return cost_df, cost_dict, None


# // FIX: 统一利润模型函数，严格执行 SKU 级预聚合、区分销售件数与订单、缺失成本拒绝捏造净利润
def calculate_sku_profit_analytics(
    sku_ad_df: pd.DataFrame,
    cost_dict: Dict[str, Dict[str, float]],
    default_margin: float = 0.35,
    target_acos_ratio: float = 0.70,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    打通广告数据与商品成本底表：
    1. SKU 级聚合加总后再进行核算；
    2. 严格区分订单量 (Orders) 与销售件数 (Units Sold)；
    3. 区分真实成本与估算成本；
    4. 计算广告前贡献利润、广告后贡献利润、保本 ACoS 与目标 ACoS；
    5. 缺失关键成本时明确标注“成本缺失待补录”，禁止假装生成真实净利。
    """
    if sku_ad_df is None or not isinstance(sku_ad_df, pd.DataFrame) or sku_ad_df.empty:
        return pd.DataFrame(), {
            "total_sales": 0.0,
            "total_spend": 0.0,
            "total_pre_ad_profit": 0.0,
            "total_post_ad_net_profit": 0.0,
            "overall_net_margin": 0.0,
            "configured_sku_count": 0,
            "missing_cost_sku_count": 0,
            "profitable_sku_count": 0,
            "loss_sku_count": 0,
        }

    df = sku_ad_df.copy()

    # 1. 规范识别 SKU 列
    sku_col = None
    for cand in ["SKU", "sku", "SKU展示", "SKU_Display", "对应SKU", "项目ID", "item_id"]:
        if cand in df.columns:
            sku_col = cand
            break
    if not sku_col:
        df["_std_sku"] = "未知"
        sku_col = "_std_sku"

    # 规范指标列
    spend_col = next((c for c in ["广告花费", "花费", "spend", "cost"] if c in df.columns), None)
    sales_col = next((c for c in ["总销售额", "销售额", "sales", "attributed sales"] if c in df.columns), None)
    orders_col = next((c for c in ["广告订单", "订单", "orders", "order"] if c in df.columns), None)
    units_col = next((c for c in ["广告销量", "销售量", "销售件数", "units", "units sold"] if c in df.columns), None)

    df["_spend"] = pd.to_numeric(df[spend_col], errors="coerce").fillna(0.0) if spend_col else 0.0
    df["_sales"] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0.0) if sales_col else 0.0
    df["_orders"] = pd.to_numeric(df[orders_col], errors="coerce").fillna(0.0) if orders_col else 0.0
    df["_units"] = pd.to_numeric(df[units_col], errors="coerce").fillna(0.0) if units_col else df["_orders"]

    # 2. // FIX: 先按 SKU 级预聚合！彻底杜绝同一 SKU 多行重复核算
    agg_df = df.groupby(sku_col, as_index=False).agg(
        广告花费=("_spend", "sum"),
        广告销售额=("_sales", "sum"),
        广告订单=("_orders", "sum"),
        销售件数=("_units", "sum"),
    )

    results = []
    total_sales_all = 0.0
    total_spend_all = 0.0
    total_pre_profit_confirmed = 0.0
    total_post_profit_confirmed = 0.0
    configured_count = 0
    missing_cost_count = 0
    profitable_count = 0
    loss_count = 0

    for _, r in agg_df.iterrows():
        raw_sku = str(r[sku_col]).strip()
        core_sku = raw_sku.split(".")[0].strip()
        spend = float(r["广告花费"])
        sales = float(r["广告销售额"])
        orders = int(r["广告订单"])
        units = int(r["销售件数"])
        aov = (sales / orders) if orders > 0 else (sales if sales > 0 else 0.0)

        # 查找成本配置
        cost_info = None
        if cost_dict:
            cost_info = cost_dict.get(core_sku) or cost_dict.get(raw_sku)

        if cost_info is not None and sales > 0:
            # // FIX: 真实成本核算 (区分销售件数 units 与订单 orders)
            cogs = cost_info["cogs"] * units
            first_leg = cost_info["first_leg"] * units
            last_leg = cost_info["last_leg"] * units
            other = cost_info.get("other_cost", 0.0) * units
            unit_prod_cost = cost_info["unit_product_cost"]
            commission = sales * cost_info["commission_rate"]
            total_cost_goods = cogs + first_leg + last_leg + other + commission

            # 广告前贡献利润 = 销售收入 - 产品采购物流履约及佣金
            pre_ad_profit = sales - total_cost_goods
            pre_ad_margin = (pre_ad_profit / sales) if sales > 0 else 0.0

            # 广告后贡献利润 = 广告前贡献利润 - 广告花费
            post_ad_profit = pre_ad_profit - spend
            post_ad_margin = (post_ad_profit / sales) if sales > 0 else 0.0

            # 保本 ACoS = 广告前贡献利润率
            breakeven_acos = max(0.01, min(0.95, pre_ad_margin))
            target_acos = round(breakeven_acos * target_acos_ratio, 4)
            actual_acos = (spend / sales) if sales > 0 else (1.0 if spend > 0 else 0.0)

            cost_status = "真实已核算"
            has_confirmed_profit = True
            configured_count += 1

            if post_ad_profit > 0 and actual_acos <= breakeven_acos * 0.7:
                profit_tier = "🚀 强力净盈利"
                badge = "badge-green"
                advice = "真实净贡献充沛，ROI 安全垫高，建议加大预算抢占更多流量"
                profitable_count += 1
            elif post_ad_profit >= 0:
                profit_tier = "⚖️ 保本正贡献"
                badge = "badge-blue"
                advice = "广告费在保本线内，贡献正向净现金流，建议精细化否词控本"
                profitable_count += 1
            else:
                profit_tier = "🚨 真实净亏损"
                badge = "badge-red"
                advice = f"广告花费击穿毛利，净亏损 ${abs(post_ad_profit):,.2f}，应立即降权或暂停止血"
                loss_count += 1

            total_pre_profit_confirmed += pre_ad_profit
            total_post_profit_confirmed += post_ad_profit

        else:
            # // FIX: 缺失关键成本时严禁伪造净利数字，明确标记为未确认
            cost_status = "成本缺失待补录"
            has_confirmed_profit = False
            missing_cost_count += 1
            unit_prod_cost = None
            pre_ad_profit = None
            pre_ad_margin = None
            post_ad_profit = None
            post_ad_margin = None
            breakeven_acos = None
            target_acos = None
            actual_acos = (spend / sales) if sales > 0 else 0.0
            profit_tier = "❓ 成本未配置"
            badge = "badge-gray"
            advice = "该 SKU 尚未配置单位成本表，无法计算真实净利润；请在数据中心上传成本底表"

        total_sales_all += sales
        total_spend_all += spend

        results.append({
            "SKU": raw_sku,
            "成本真实性": cost_status,
            "广告销售额": sales,
            "广告订单": orders,
            "销售件数": units,
            "平均客单价": aov,
            "广告花费": spend,
            "实际ACoS": actual_acos,
            "单位商品总成本": unit_prod_cost,
            "广告前贡献利润": pre_ad_profit,
            "广告前贡献利润率": pre_ad_margin,
            "广告后贡献利润": post_ad_profit,
            "广告后贡献利润率": post_ad_margin,
            "保本ACoS": breakeven_acos,
            "目标ACoS": target_acos,
            "盈利健康等级": profit_tier,
            "状态徽章": badge,
            "经营决策建议": advice,
            "_has_confirmed_profit": has_confirmed_profit,
        })

    res_df = pd.DataFrame(results)
    if not res_df.empty:
        # 优先将已核算且利润高排在前面，未配置排在最后
        res_df = res_df.sort_values(by=["_has_confirmed_profit", "广告后贡献利润"], ascending=[False, False]).reset_index(drop=True)

    summary_stats = {
        "total_sales": total_sales_all,
        "total_spend": total_spend_all,
        "total_pre_ad_profit": total_pre_profit_confirmed,
        "total_post_ad_net_profit": total_post_profit_confirmed,
        "overall_net_margin": (total_post_profit_confirmed / total_sales_all) if total_sales_all > 0 else 0.0,
        "configured_sku_count": configured_count,
        "missing_cost_sku_count": missing_cost_count,
        "profitable_sku_count": profitable_count,
        "loss_sku_count": loss_count,
    }

    return res_df, summary_stats
