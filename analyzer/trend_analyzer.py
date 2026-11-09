import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from .metrics import safe_divide
from data_loader.sku_mapper import apply_sku_mapping

def extract_period_label(filename: str, fallback_index: int = 1) -> str:
    """
    从文件名中提取日期或周期标签
    """
    if not filename:
        return f"周期 {fallback_index}"

    base = filename.split(".")[0]

    # 1. 匹配 YYYY-MM-DD 或 YYYY.MM.DD 或 YYYY_MM_DD
    m1 = re.search(r"(202\d[-._][0-1]?\d[-._][0-3]?\d)", base)
    if m1:
        s = m1.group(1).replace(".", "-").replace("_", "-")
        return s

    # 2. 匹配 YYYYMMDD (8位连续数字)
    m2 = re.search(r"(202\d[0-1]\d[0-3]\d)", base)
    if m2:
        s = m2.group(1)
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"

    # 3. 匹配中文 'X月X日' 或 '第X周' 或 'X月份'
    m3 = re.search(r"(\d{1,2}月\d{1,2}日|\d{1,2}月份|第\d{1,2}周|Week\s*\d+)", base, re.I)
    if m3:
        return m3.group(1)

    # 4. 匹配 YYYY-MM
    m4 = re.search(r"(202\d[-._][0-1]?\d)", base)
    if m4:
        return m4.group(1).replace(".", "-").replace("_", "-")

    # 5. 若含有领星导出的长数字 ID，截取后4位作为批次标识
    m5 = re.search(r"-(\d{4,})", base)
    if m5:
        return f"批次 {m5.group(1)[-4:]}"

    return f"周期 {fallback_index}"

HEADER_MAPPING = {
    # 日期 / 周期
    "date": "日期", "day": "日期", "时间": "日期", "统计时间": "日期", "数据日期": "日期",
    # SKU
    "skuid": "SKU", "sku_id": "SKU", "sku": "SKU", "sellersku": "SKU", "seller_sku": "SKU", "对应sku": "SKU",
    # 项目ID
    "itemid": "项目ID", "item_id": "项目ID", "商品id": "项目ID", "沃尔玛id": "项目ID",
    # 商品名称
    "itemname": "商品名称", "item_name": "商品名称", "广告": "商品名称",
    # 花费
    "adspend": "广告花费", "spend": "广告花费", "cost": "广告花费",
    # 曝光
    "impressions": "曝光量", "impression": "曝光量",
    # 点击
    "clicks": "点击", "click": "点击",
    # 订单
    "orders": "广告订单", "order": "广告订单", "conversions": "广告订单",
    # 销售额
    "totalattributedsales": "总销售额", "attributedsales": "总销售额", "sales": "总销售额",
    # 广告活动
    "campaignname": "广告活动", "campaign": "广告活动",
    # 竞价与比率
    "bid": "广告竞价", "cpc": "CPC", "averagecpc": "CPC", "ctr": "CTR", "roas": "ROAS"
}

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """// FIX: 自动将中英文列名标准化为系统统一列名，并自动消除重复列名以防止 DataFrame.str 报错"""
    col_map = {}
    seen_targets = set()
    for col in df.columns:
        norm_key = str(col).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
        if norm_key in HEADER_MAPPING:
            target = HEADER_MAPPING[norm_key]
            if target not in seen_targets and target not in df.columns:
                col_map[col] = target
                seen_targets.add(target)
    out = df.rename(columns=col_map)
    if out.columns.duplicated().any():
        out = out.loc[:, ~out.columns.duplicated()]
    return out

def parse_date_series(series: pd.Series) -> pd.Series:
    """
    智能解析日期序列：
    - 兼容 Excel 连续数值序号（如 46326 -> 2026-10-31）
    - 兼容标准日期字符串（YYYY-MM-DD / YYYY/MM/DD 等）
    """
    # 优先检测 Excel 序列号 (通常位于 20000 到 80000 之间)
    num_s = pd.to_numeric(series, errors="coerce")
    if num_s.notna().mean() >= 0.7:
        valid_nums = num_s.dropna()
        if len(valid_nums) > 0 and 20000 <= valid_nums.iloc[0] <= 80000:
            parsed = pd.to_datetime(valid_nums, unit="D", origin="1899-12-30", errors="coerce")
            res = series.copy().astype(str)
            res.loc[parsed.index] = parsed.dt.strftime("%Y-%m-%d")
            return res

    # 尝试标准日期字符串解析
    dt = pd.to_datetime(series, errors="coerce")
    if dt.notna().mean() >= 0.5:
        res = dt.dt.strftime("%Y-%m-%d")
        return res.fillna(series.astype(str))

    return series.astype(str)

def build_sku_trend_data(
    ad_item_records: Any,
    sku_map: Optional[Dict[str, str]] = None,
    target_acos: float = 0.20,
    breakeven_acos: float = 0.35,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[Dict[str, Any]], pd.DataFrame]:
    """
    处理多周期/每日广告列表数据：
    输入:
        ad_item_records: [{"period": "2026-10-01", "df": df, "filename": "..."}, ...] 或单张 DataFrame
    输出:
        (period_df, sku_summary_df, anomalies, daily_macro_df)
    """
    if isinstance(ad_item_records, pd.DataFrame):
        if ad_item_records.empty:
            return pd.DataFrame(), pd.DataFrame(), [], pd.DataFrame()
        ad_item_records = [{"df": ad_item_records, "period": "全部周期", "filename": "报表"}]
    elif not ad_item_records:
        return pd.DataFrame(), pd.DataFrame(), [], pd.DataFrame()

    all_dfs = []
    for idx, rec in enumerate(ad_item_records):
        df_item = rec.get("df")
        if df_item is None or df_item.empty:
            continue
        
        # 统一标准化中英文列名
        df_norm = normalize_columns(df_item.copy())

        period_lbl = rec.get("period") or extract_period_label(rec.get("filename", ""), idx + 1)

        # 检查是否已有内部日期列
        date_col = None
        for cand in ["日期", "统计时间", "时间", "Date", "date", "数据日期", "天"]:
            if cand in df_norm.columns:
                target_col = df_norm[cand].iloc[:, 0] if isinstance(df_norm[cand], pd.DataFrame) else df_norm[cand]
                valid_vals = target_col.dropna().astype(str).str.strip()
                valid_vals = valid_vals[~valid_vals.isin(["-", ""])]
                if len(valid_vals) > 0:
                    date_col = cand
                    break

        df_copy = df_norm.copy()
        if date_col:
            d_col_data = df_copy[date_col].iloc[:, 0] if isinstance(df_copy[date_col], pd.DataFrame) else df_copy[date_col]
            df_copy["周期"] = parse_date_series(d_col_data)
        else:
            df_copy["周期"] = period_lbl

        all_dfs.append(df_copy)

    if not all_dfs:
        return pd.DataFrame(), pd.DataFrame(), [], pd.DataFrame()

    combined_df = pd.concat(all_dfs, ignore_index=True)

    # 规范已有的 SKU 列
    if "对应SKU" in combined_df.columns and "SKU" not in combined_df.columns:
        combined_df["SKU"] = combined_df["对应SKU"].astype(str).str.strip()

    # 应用 SKU 映射
    if sku_map:
        combined_df = apply_sku_mapping(combined_df, sku_map)
    else:
        if "SKU" in combined_df.columns:
            combined_df["SKU"] = combined_df["SKU"].astype(str).str.strip()
            if "项目ID" in combined_df.columns:
                id_s = combined_df["项目ID"].astype(str).str.split(".").str[0]
                combined_df["SKU_Display"] = combined_df.apply(
                    lambda r: f"{r['SKU']} ({id_s[r.name]})" if str(r['SKU']) != str(id_s[r.name]) and str(r['SKU']) not in ["未知", "-", "nan", ""] else str(r['SKU']),
                    axis=1
                )
            else:
                combined_df["SKU_Display"] = combined_df["SKU"]
        elif "项目ID" in combined_df.columns:
            combined_df["SKU"] = combined_df["项目ID"].astype(str).str.split(".").str[0]
            combined_df["SKU_Display"] = combined_df["项目ID"].astype(str).str.split(".").str[0]
        else:
            combined_df["SKU"] = "未知"
            combined_df["SKU_Display"] = "未知"

    # 维护 SKU 与商品名称的映射
    title_mapping = {}
    if "商品名称" in combined_df.columns:
        valid_titles = combined_df.dropna(subset=["商品名称"])
        valid_titles = valid_titles[valid_titles["商品名称"].astype(str).str.strip() != "-"]
        if not valid_titles.empty:
            title_mapping = valid_titles.groupby("SKU")["商品名称"].last().to_dict()

    # 数值列清洗
    metric_cols = ["广告花费", "曝光量", "点击", "广告订单", "总销售额"]
    for c in metric_cols:
        if c not in combined_df.columns:
            combined_df[c] = 0.0
        else:
            combined_df[c] = pd.to_numeric(combined_df[c], errors="coerce").fillna(0.0)

    # 按照 [SKU, SKU_Display, 周期] 分组聚合指标
    group_keys = ["SKU", "SKU_Display", "周期"]
    agg_df = combined_df.groupby(group_keys, as_index=False)[metric_cols].sum()

    # 映射商品名称
    agg_df["商品名称"] = agg_df["SKU"].map(title_mapping).fillna("未命名商品")

    # 计算比率
    agg_df["CTR"] = safe_divide(agg_df["点击"], agg_df["曝光量"])
    agg_df["CPC"] = safe_divide(agg_df["广告花费"], agg_df["点击"])
    agg_df["CVR"] = safe_divide(agg_df["广告订单"], agg_df["点击"])
    agg_df["CPA"] = safe_divide(agg_df["广告花费"], agg_df["广告订单"])
    agg_df["ROAS"] = safe_divide(agg_df["总销售额"], agg_df["广告花费"])
    agg_df["ACOS"] = safe_divide(agg_df["广告花费"], agg_df["总销售额"])

    # 周期严格按时间排序
    try:
        agg_df["_sort_key"] = pd.to_datetime(agg_df["周期"], errors="coerce")
        agg_df = agg_df.sort_values(by=["SKU", "_sort_key", "周期"]).reset_index(drop=True)
        agg_df = agg_df.drop(columns=["_sort_key"])
    except Exception:
        agg_df = agg_df.sort_values(by=["SKU", "周期"]).reset_index(drop=True)

    # 全店大盘每日走势聚合
    daily_macro = agg_df.groupby("周期", as_index=False)[metric_cols].sum()
    try:
        daily_macro["_sort_key"] = pd.to_datetime(daily_macro["周期"], errors="coerce")
        daily_macro = daily_macro.sort_values(by="_sort_key").reset_index(drop=True).drop(columns=["_sort_key"])
    except Exception:
        daily_macro = daily_macro.sort_values(by="周期").reset_index(drop=True)

    daily_macro["ROAS"] = safe_divide(daily_macro["总销售额"], daily_macro["广告花费"])
    daily_macro["CPC"] = safe_divide(daily_macro["广告花费"], daily_macro["点击"])
    daily_macro["CVR"] = safe_divide(daily_macro["广告订单"], daily_macro["点击"])

    # 深度评估 SKU 趋势与生成预警建议
    sku_summary, anomalies = _evaluate_sku_trends_advanced(
        agg_df, target_acos=target_acos, breakeven_acos=breakeven_acos
    )

    return agg_df, sku_summary, anomalies, daily_macro

def _evaluate_sku_trends_advanced(
    period_df: pd.DataFrame,
    target_acos: float = 0.20,
    breakeven_acos: float = 0.35,
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    高级多期趋势评估引擎：
    - 支持多日（如30天）时间序列分段窗口分析（最新 7 天 vs 前 7 天）
    - 结合保本线与目标线双线解耦，多维输出预警与落地建议
    """
    if period_df.empty:
        return pd.DataFrame(), []

    summary_rows = []
    anomalies = []

    target_roas = round(1.0 / target_acos, 2) if target_acos > 0 else 5.0
    breakeven_roas = round(1.0 / breakeven_acos, 2) if breakeven_acos > 0 else 2.86
    ref_roas = target_roas

    for sku, grp in period_df.groupby("SKU"):
        grp = grp.sort_values(by="周期").reset_index(drop=True)
        sku_display = grp["SKU_Display"].iloc[0]
        item_title = grp["商品名称"].iloc[0] if "商品名称" in grp.columns else "未命名商品"

        n_periods = len(grp)
        total_spend = float(grp["广告花费"].sum())
        total_sales = float(grp["总销售额"].sum())
        total_orders = int(grp["广告订单"].sum())
        total_clicks = int(grp["点击"].sum())
        overall_roas = safe_divide(total_sales, total_spend)

        # 最新单期数据
        latest_row = grp.iloc[-1]
        latest_period = latest_row["周期"]
        latest_spend = float(latest_row["广告花费"])
        latest_sales = float(latest_row["总销售额"])
        latest_orders = int(latest_row["广告订单"])
        latest_roas = float(latest_row["ROAS"]) if pd.notna(latest_row["ROAS"]) else 0.0

        # 核心修正：严格基于【自然日】时间窗口计算环比（修正按行数 iloc[-7:] 切片的错误）
        grp_dt = pd.to_datetime(grp["周期"], errors="coerce")
        has_real_dates = grp_dt.notna().sum() >= max(2, int(len(grp) * 0.5))

        if has_real_dates:
            max_d = grp_dt.dropna().max()
            # 近 7 个自然日与前 7 个自然日
            recent_mask = (grp_dt >= max_d - pd.Timedelta(days=6)) & (grp_dt <= max_d)
            prev_mask = (grp_dt >= max_d - pd.Timedelta(days=13)) & (grp_dt < max_d - pd.Timedelta(days=6))

            recent_grp = grp[recent_mask]
            prev_grp = grp[prev_mask]

            # 边界容错：若近自然日无记录（如断层），平滑回退
            if recent_grp.empty:
                recent_grp = grp.iloc[-1:]
            if prev_grp.empty:
                prev_sub = grp[~recent_mask]
                prev_grp = prev_sub if not prev_sub.empty else recent_grp
        else:
            # 非标准自然日格式（如批次名称），退化为序列分块保底
            if n_periods >= 14:
                recent_grp = grp.iloc[-7:]
                prev_grp = grp.iloc[-14:-7]
            elif n_periods >= 4:
                half = n_periods // 2
                recent_grp = grp.iloc[-half:]
                prev_grp = grp.iloc[:half]
            else:
                recent_grp = grp.iloc[-1:]
                prev_grp = grp.iloc[:-1] if n_periods > 1 else grp.iloc[-1:]

        recent_spend = float(recent_grp["广告花费"].sum())
        recent_sales = float(recent_grp["总销售额"].sum())
        recent_orders = int(recent_grp["广告订单"].sum())
        recent_roas = safe_divide(recent_sales, recent_spend) or 0.0

        prev_spend = float(prev_grp["广告花费"].sum())
        prev_sales = float(prev_grp["总销售额"].sum())
        prev_orders = int(prev_grp["广告订单"].sum())
        prev_roas = safe_divide(prev_sales, prev_spend) or 0.0

        # 环比变动率计算
        diff_spend = recent_spend - prev_spend
        spend_change_pct = (diff_spend / prev_spend * 100.0) if prev_spend > 0 else (100.0 if recent_spend > 0 else 0.0)
        diff_orders = recent_orders - prev_orders
        orders_change_pct = (diff_orders / prev_orders * 100.0) if prev_orders > 0 else (100.0 if recent_orders > 0 else 0.0)
        diff_roas = recent_roas - prev_roas

        # 核心趋势研判与行动预警建议
        trend_status = "平稳运行"
        trend_category = "平稳"
        action_advice = ""
        core_issue = ""

        # 1. 紧急失血恶化判断
        if recent_spend >= 20.0 and recent_orders == 0:
            trend_status = "🚨 严重失血零转化"
            trend_category = "异常变差"
            core_issue = f"近期消耗 ${recent_spend:.2f} 且 0 出单，高额沉没"
            action_advice = "【紧急止血】建议立即下调竞价 30%~50% 或暂停广告活动，排查搜索词无效点击与商品评价/价格断崖。"
        elif recent_roas < (ref_roas * 0.6) and recent_spend >= 15.0 and diff_roas <= -1.0:
            trend_status = "🚨 ROAS断崖式下滑"
            trend_category = "异常变差"
            core_issue = f"近期ROAS由 {prev_roas:.2f} 暴跌至 {recent_roas:.2f}，且花费仍在持续消耗"
            action_advice = "【控本降权】投产跌破警戒线，建议下调出价 20%，清理高 CPC 词组，核查 Listing 首图与核心买家关注点。"
        elif recent_spend > prev_spend * 1.4 and recent_orders < prev_orders:
            trend_status = "⚠️ 花费激增转化萎缩"
            trend_category = "异常变差"
            core_issue = f"花费环比激增 {spend_change_pct:.0f}% 但订单萎缩 {abs(diff_orders)} 单"
            action_advice = "【防失控】流量放量未转化为订单，建议严格锁定广告活动日预算，排查是否被低意图大词抢占预算。"
        
        # 2. 流量萎缩判断
        elif recent_spend < prev_spend * 0.5 and prev_orders >= 2 and recent_orders == 0:
            trend_status = "⚠️ 流量大幅萎缩"
            trend_category = "异常变差"
            core_issue = f"近期花费缩减超过 50%，订单骤减"
            action_advice = "【唤醒流量】可能因竞品提价导致曝光位被抢占，建议适当调高核心出价 15% 或拓充精准关键词。"

        # 3. 强势放量爆款
        elif recent_roas >= ref_roas and (diff_orders >= 2 or orders_change_pct >= 20) and recent_orders >= 3:
            trend_status = "🚀 强势放量增长"
            trend_category = "变好向好"
            core_issue = f"近期订单增长 +{diff_orders} 单 (环比+{orders_change_pct:.0f}%)，近期ROAS达 {recent_roas:.2f}"
            action_advice = "【主动扩量】核心盈利主力，建议上调日预算 20%~30%，核心出价上浮 10% 锁定搜索首位 (Top of Search)。"
        elif recent_roas >= (ref_roas * 1.25) and recent_spend >= 10.0:
            trend_status = "🌟 高投产稳健款"
            trend_category = "变好向好"
            core_issue = f"近期 ROAS 达到 {recent_roas:.2f}，显著高于保本线 ({ref_roas:.2f}x)"
            action_advice = "【保持优势】产出高效稳健，建议维持充沛预算供给，拓展同类关联品广告位以扩大战果。"

        # 4. 低效消耗款（解耦保本线与目标线）
        elif total_spend >= 20.0 and (overall_roas or 0) < breakeven_roas:
            trend_status = "📉 击穿保本线亏损"
            trend_category = "异常变差"
            core_issue = f"整体 ROAS 仅 {overall_roas:.2f} (低于保本线 {breakeven_roas:.2f}x)，净亏损侵蚀毛利"
            action_advice = f"【保本止损】实际投产低于保本线 (保本 ACoS {breakeven_acos*100:.0f}%)，建议在关键词层级下调竞价 20% 并排查高损大词。"
        elif total_spend >= 20.0 and (overall_roas or 0) < target_roas:
            trend_status = "📉 保本微利未达标"
            trend_category = "观察优化"
            core_issue = f"整体 ROAS {overall_roas:.2f} 高于保本线，但未达到预期盈利目标 ({target_roas:.2f}x)"
            action_advice = "【精细提效】虽未亏损但利润垫较薄，建议通过精准否词与竞价微调 10% 提升纯利空间。"

        # 5. 长尾款
        elif total_spend < 10.0:
            trend_status = "💤 低消耗长尾款"
            trend_category = "平稳"
            core_issue = f"累计消耗不足 $10，曝光基数较小"
            action_advice = "【低价观察】维持低出价持续捡漏，定期观察出单潜力。"
        else:
            trend_status = "平稳运行"
            trend_category = "平稳"
            core_issue = f"各项指标平稳，近期ROAS {recent_roas:.2f}"
            action_advice = "【平稳监控】继续保持当前投放策略，持续跟踪转化动向。"

        summary_rows.append({
            "SKU": sku,
            "SKU展示": sku_display,
            "商品名称": item_title,
            "周期数": n_periods,
            "总花费": round(total_spend, 2),
            "总销售额": round(total_sales, 2),
            "总订单": total_orders,
            "整体ROAS": round(overall_roas, 2) if overall_roas is not None else None,
            "最新单日花费": round(latest_spend, 2),
            "最新单日订单": latest_orders,
            "最新单日ROAS": round(latest_roas, 2),
            "近期花费": round(recent_spend, 2),
            "近期订单": recent_orders,
            "近期ROAS": round(recent_roas, 2),
            "花费环比%": round(spend_change_pct, 1),
            "订单环比%": round(orders_change_pct, 1),
            "趋势状态": trend_status,
            "趋势分类": trend_category,
            "数据特征剖析": core_issue,
            "建议预警动作": action_advice,
        })

        if trend_category in ["异常变差", "变好向好"]:
            anomalies.append({
                "SKU": sku,
                "SKU展示": sku_display,
                "商品名称": item_title,
                "类别": trend_category,
                "状态表现": trend_status,
                "近期花费": round(recent_spend, 2),
                "近期订单": recent_orders,
                "近期ROAS": round(recent_roas, 2),
                "核心诊断": core_issue,
                "优化建议": action_advice,
            })

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(by="总花费", ascending=False).reset_index(drop=True)

    return summary_df, anomalies
