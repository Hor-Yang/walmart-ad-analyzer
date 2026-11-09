from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from .metrics import safe_divide
from data_loader.sku_mapper import apply_sku_mapping

def diagnose_ad_items(
    ad_item_df: pd.DataFrame,
    sku_map: Optional[Dict[str, str]] = None,
    **kwargs,  # // FIX: 增加 **kwargs 容错吸收任何额外关键字参数 (如 target_acos 等)，防止 TypeError
) -> Dict[str, Any]:
    """
    广告商品（商品位）诊断分析模块：
    1. 跑量商品 TOP10（按总销售额排序）
    2. 烧钱商品：花费 ≥ $30 且 订单 = 0
    3. 竞价对比：实际"广告竞价"明显低于领星"建议竞价"（低于 30% 以上）的商品位，提示提价抢曝光
    4. 异常状态商品位：审核状态 ≠ 'approved' 或 广告状态 ≠ 'enabled'
    """
    empty_res = {
        "top10_items": pd.DataFrame(),
        "burning_items": pd.DataFrame(),
        "low_bid_items": pd.DataFrame(),
        "abnormal_items": pd.DataFrame(),
        "stats": {
            "top10_sales": 0.0,
            "burning_count": 0,
            "burning_spend": 0.0,
            "low_bid_count": 0,
            "abnormal_count": 0,
            "abnormal_spend": 0.0,
        },
    }

    if ad_item_df is None or ad_item_df.empty:
        return empty_res

    df = ad_item_df.copy()

    # 标准化数值
    for col in ["广告花费", "曝光量", "点击", "广告订单", "总销售额", "建议竞价", "广告竞价"]:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # 商品名称容错映射
    if "商品名称" in df.columns:
        df["商品名称"] = df["商品名称"].astype(str).str.strip()
    elif "广告" in df.columns:
        df["商品名称"] = df["广告"].astype(str).str.strip()
    elif "Item Name" in df.columns:
        df["商品名称"] = df["Item Name"].astype(str).str.strip()
    elif "item_name" in df.columns:
        df["商品名称"] = df["item_name"].astype(str).str.strip()
    elif "SKU" in df.columns:
        df["商品名称"] = df["SKU"].astype(str).str.strip()
    else:
        df["商品名称"] = "未命名商品"

    # 项目ID容错映射
    if "项目ID" in df.columns:
        df["项目ID"] = df["项目ID"].astype(str).str.strip()
    elif "Item Id" in df.columns:
        df["项目ID"] = df["Item Id"].astype(str).str.strip()
    elif "item_id" in df.columns:
        df["项目ID"] = df["item_id"].astype(str).str.strip()
    elif "SKU" in df.columns:
        df["项目ID"] = df["SKU"].astype(str).str.strip()
    else:
        df["项目ID"] = "未知ID"

    # 广告活动容错映射
    if "广告活动" in df.columns:
        df["广告活动"] = df["广告活动"].astype(str).str.strip()
    elif "Campaign Name" in df.columns:
        df["广告活动"] = df["Campaign Name"].astype(str).str.strip()
    else:
        df["广告活动"] = "-"

    # 审核状态与广告状态容错映射
    if "审核状态" in df.columns:
        df["审核状态"] = df["审核状态"].astype(str).str.lower().str.strip()
    else:
        df["审核状态"] = "approved"

    if "广告状态" in df.columns:
        df["广告状态"] = df["广告状态"].astype(str).str.lower().str.strip()
    else:
        df["广告状态"] = "enabled"
    if sku_map:
        df = apply_sku_mapping(df, sku_map)

    has_sku = "SKU" in df.columns
    if has_sku:
        df["SKU"] = df["SKU"].astype(str).str.strip()
        sku_map_by_id = df.groupby("项目ID")["SKU"].first()
    else:
        sku_map_by_id = df.groupby("项目ID")["项目ID"].first()

    # 商品标题映射（取同项目ID中最完整的标题）
    title_map = df.sort_values("商品名称", key=lambda s: s.str.len()).groupby("项目ID")["商品名称"].last()

    # =========================================================================
    # 1. 跑量商品 TOP10（按商品维度聚合并按销售额排序）
    # =========================================================================
    item_agg = df.groupby("项目ID").agg(
        花费=("广告花费", "sum"),
        订单=("广告订单", "sum"),
        销售额=("总销售额", "sum"),
        点击=("点击", "sum"),
        曝光=("曝光量", "sum"),
        投放活动数=("广告活动", "nunique"),
    ).reset_index()

    item_agg["商品名称"] = item_agg["项目ID"].map(title_map)
    item_agg["SKU"] = item_agg["项目ID"].map(sku_map_by_id).fillna(item_agg["项目ID"])
    item_agg["ROAS"] = safe_divide(item_agg["销售额"], item_agg["花费"])
    item_agg["CVR"] = safe_divide(item_agg["订单"], item_agg["点击"])
    item_agg["CPC"] = safe_divide(item_agg["花费"], item_agg["点击"])

    top10_items = item_agg.sort_values("销售额", ascending=False).head(10).reset_index(drop=True)
    top10_cols = ["SKU", "项目ID", "商品名称", "销售额", "花费", "订单", "ROAS", "CVR", "CPC", "投放活动数"]
    top10_items = top10_items[top10_cols]

    # =========================================================================
    # 2. 烧钱商品：商品维度花费 ≥ $30 且 订单 = 0
    # =========================================================================
    burning_raw = item_agg[(item_agg["花费"] >= 30.0) & (item_agg["订单"] == 0)].copy()
    if not burning_raw.empty:
        burning_raw = burning_raw.sort_values("花费", ascending=False).reset_index(drop=True)
        burning_raw["建议动作"] = burning_raw.apply(
            lambda r: f"已累计消耗 ${r['花费']:.2f} 且 0 转化，建议检查商品 Listing 价格、评价或在各活动暂停该商品投放",
            axis=1,
        )
        burn_cols = ["SKU", "项目ID", "商品名称", "花费", "点击", "曝光", "投放活动数", "建议动作"]
        burning_items = burning_raw[burn_cols]
    else:
        burn_cols = ["SKU", "项目ID", "商品名称", "花费", "点击", "曝光", "投放活动数", "建议动作"]
        burning_items = pd.DataFrame(columns=burn_cols)

    # =========================================================================
    # 3. 竞价对比：实际"广告竞价"明显低于领星"建议竞价"（低于 30% 以上）
    # =========================================================================
    bid_eval = df[(df["建议竞价"] > 0) & (df["广告竞价"] > 0)].copy()
    if not bid_eval.empty:
        if "SKU" not in bid_eval.columns:
            bid_eval["SKU"] = bid_eval["项目ID"].map(sku_map_by_id).fillna(bid_eval["项目ID"])
        bid_eval["低于比例"] = (bid_eval["广告竞价"] - bid_eval["建议竞价"]) / bid_eval["建议竞价"]
        low_bid_raw = bid_eval[bid_eval["低于比例"] <= -0.30].copy()
        low_bid_raw = low_bid_raw.sort_values("广告花费", ascending=False).reset_index(drop=True)
        low_bid_raw["低于幅度"] = low_bid_raw["低于比例"].apply(lambda p: f"{abs(p)*100:.1f}%")
        low_bid_raw["建议动作"] = low_bid_raw.apply(
            lambda r: f"当前竞价 ${r['广告竞价']:.2f} 明显低于建议竞价 ${r['建议竞价']:.2f}（低 {r['低于幅度']}），建议适度提价抢占核心展现位",
            axis=1,
        )
        low_cols = [
            "SKU", "项目ID", "商品名称", "广告活动", "广告竞价", "建议竞价", "低于幅度", "花费", "曝光量", "点击", "建议动作"
        ]
        low_bid_items = low_bid_raw.rename(columns={"广告花费": "花费"})[low_cols]
    else:
        low_cols = [
            "SKU", "项目ID", "商品名称", "广告活动", "广告竞价", "建议竞价", "低于幅度", "花费", "曝光量", "点击", "建议动作"
        ]
        low_bid_items = pd.DataFrame(columns=low_cols)

    # =========================================================================
    # 4. 检查并列出 审核状态 ≠ 'approved' 或 广告状态 ≠ 'enabled' 的商品位
    # =========================================================================
    abnormal_mask = (df["审核状态"] != "approved") | (df["广告状态"] != "enabled")
    abnormal_raw = df[abnormal_mask].copy()

    if not abnormal_raw.empty:
        abnormal_raw = abnormal_raw.sort_values("广告花费", ascending=False).reset_index(drop=True)

        def diagnose_abnormal(r: pd.Series) -> str:
            notes = []
            if r["审核状态"] != "approved":
                notes.append(f"审核状态异常: {r['审核状态']}")
            if r["广告状态"] != "enabled":
                notes.append(f"广告处于 {r['广告状态']} 状态")
            if r["广告花费"] > 0:
                notes.append(f"历史消耗 ${r['广告花费']:.2f}")
            return "；".join(notes)

        abnormal_raw["诊断说明"] = abnormal_raw.apply(diagnose_abnormal, axis=1)
        ab_cols = ["SKU", "项目ID", "商品名称", "广告活动", "广告状态", "审核状态", "花费", "订单", "销售额", "诊断说明"] if has_sku else ["项目ID", "商品名称", "广告活动", "广告状态", "审核状态", "花费", "订单", "销售额", "诊断说明"]
        abnormal_items = abnormal_raw.rename(columns={"广告花费": "花费", "广告订单": "订单", "总销售额": "销售额"})[ab_cols]
    else:
        ab_cols = ["SKU", "项目ID", "商品名称", "广告活动", "广告状态", "审核状态", "花费", "订单", "销售额", "诊断说明"] if has_sku else ["项目ID", "商品名称", "广告活动", "广告状态", "审核状态", "花费", "订单", "销售额", "诊断说明"]
        abnormal_items = pd.DataFrame(columns=ab_cols)

    stats = {
        "top10_sales": float(top10_items["销售额"].sum()) if not top10_items.empty else 0.0,
        "burning_count": len(burning_items),
        "burning_spend": float(burning_raw["花费"].sum()) if not burning_raw.empty else 0.0,
        "low_bid_count": len(low_bid_items),
        "abnormal_count": len(abnormal_items),
        "abnormal_spend": float(abnormal_raw["广告花费"].sum()) if not abnormal_raw.empty else 0.0,
    }

    return {
        "top10_items": top10_items,
        "burning_items": burning_items,
        "low_bid_items": low_bid_items,
        "abnormal_items": abnormal_items,
        "stats": stats,
    }
