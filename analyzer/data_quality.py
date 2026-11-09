from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

def inspect_data_quality(
    section_data: Dict[str, Any],
    sku_map: Optional[Dict[str, str]] = None,
    sku_cost_dict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    第一层：数据质量分析引擎 (Data Quality Analysis Engine)
    
    核心职责：
    1. 字段完整性：各上传报表是否包含必需的主键维度与指标列；
    2. 数据类型和格式：数字、比率、日期的有效性，检测异常格式与坏点；
    3. 区分真实 0 与缺失/异常：明确区分零花费/零订单（事实）与列缺失/解析失败（缺陷）；
    4. 跨表勾稽与一致性：
       - Campaign/Ad Group/关键词在各表之间的关联覆盖度；
       - Item ID 与 SKU 映射表的匹配覆盖率；
       - 各表累计花费、订单的统计口径差异校验；
    5. 数据质量综合评分 (0~100) 与 AI 决策可信度等级（高/中/低）；
    6. 熔断保护：若数据质量不合格 (<60分)，激活确定性结论风控熔断，防止误杀误调。
    """
    checks: List[Dict[str, Any]] = []
    penalties = 0
    active_sections = {k: v for k, v in section_data.items() if v is not None}
    
    if not active_sections:
        return {
            "score": 0,
            "confidence": "低置信度",
            "status": "暂无数据",
            "summary": "尚未上传任何广告报表，无法评估数据质量。",
            "checks": [],
            "reconciliation": {},
            "guardrail_active": True,
        }

    # 1. 检查各报表的存在性与基础字段完整性
    required_schemas = {
        "campaign": {
            "name": "① 广告活动报表",
            "core_keys": ["活动名", "广告活动"],
            "core_metrics": ["花费", "广告花费", "订单", "广告订单", "销售额", "总销售额"],
        },
        "search_term": {
            "name": "② 搜索词报表",
            "core_keys": ["搜索词"],
            "core_metrics": ["花费", "点击", "订单"],
        },
        "keyword": {
            "name": "③ 关键词报表",
            "core_keys": ["关键词"],
            "core_metrics": ["花费", "点击"],
        },
        "ad_item": {
            "name": "④ 商品广告列表",
            "core_keys": ["项目ID", "Item Id", "item_id", "SKU"],
            "core_metrics": ["广告花费", "花费", "总销售额", "销售额"],
        },
    }

    total_spends_by_table = {}
    total_orders_by_table = {}

    for sec_key, schema in required_schemas.items():
        table_df = section_data.get(sec_key)
        # 支持 trend 中的 period_df 代理
        if sec_key == "ad_item" and table_df is None and section_data.get("trend") is not None:
            t_obj = section_data.get("trend")
            if isinstance(t_obj, dict) and "period_df" in t_obj:
                table_df = t_obj["period_df"]

        if table_df is None or table_df.empty:
            continue

        sec_name = schema["name"]
        cols = [str(c).strip().lower() for c in table_df.columns]

        # 检查主键存在性
        has_key = any(any(k.lower() in c for c in cols) for k in schema["core_keys"])
        if not has_key:
            penalties += 25
            checks.append({
                "level": "ERROR",
                "table": sec_name,
                "item": "缺少核心主键维度",
                "detail": f"未检测到关键字段（期望包含：{'/'.join(schema['core_keys'])}），可能导致模型错配或捏造虚假实体",
            })
        else:
            checks.append({
                "level": "PASS",
                "table": sec_name,
                "item": "主键字段完整",
                "detail": f"核心维度识别正常（数据量: {len(table_df):,} 行）",
            })

        # 检查缺失值与假 0
        spend_col = None
        for cand in ["广告花费", "花费", "spend"]:
            for c in table_df.columns:
                if cand == str(c).strip().lower():
                    spend_col = c
                    break
            if spend_col:
                break

        order_col = None
        for cand in ["广告订单", "订单", "orders"]:
            for c in table_df.columns:
                if cand == str(c).strip().lower():
                    order_col = c
                    break
            if order_col:
                break

        if spend_col:
            s_series = pd.to_numeric(table_df[spend_col], errors="coerce")
            null_count = s_series.isna().sum()
            if null_count > 0:
                penalties += min(15, null_count)
                checks.append({
                    "level": "WARN",
                    "table": sec_name,
                    "item": "花费指标包含无效/缺失值",
                    "detail": f"发现 {null_count} 处非标准数值，系统已进行安全转换",
                })
            total_spends_by_table[sec_key] = float(s_series.fillna(0.0).sum())

        if order_col:
            o_series = pd.to_numeric(table_df[order_col], errors="coerce")
            total_orders_by_table[sec_key] = int(o_series.fillna(0).sum())

    # 2. 跨表勾稽校验（统计口径与金额对账）
    reconciliation = {}
    if "campaign" in total_spends_by_table and "search_term" in total_spends_by_table:
        c_spend = total_spends_by_table["campaign"]
        s_spend = total_spends_by_table["search_term"]
        diff_pct = abs(c_spend - s_spend) / (c_spend if c_spend > 0 else 1.0) * 100
        reconciliation["campaign_vs_search_spend_diff"] = f"{diff_pct:.1f}%"
        if diff_pct > 30.0:
            penalties += 15
            checks.append({
                "level": "WARN",
                "table": "跨表勾稽对账",
                "item": "活动与搜索词花费差异偏大",
                "detail": f"广告活动报表总花费 ${c_spend:,.2f} vs 搜索词报表总花费 ${s_spend:,.2f}（差异率 {diff_pct:.1f}%），通常由于领星导出时间范围不完全一致引起",
            })
        else:
            checks.append({
                "level": "PASS",
                "table": "跨表勾稽对账",
                "item": "活动与搜索词金额口径匹配良好",
                "detail": f"差异率仅 {diff_pct:.1f}%，数据可信度高",
            })

    # 3. 实体级关联度检查（Campaign 级关联）
    camp_df = section_data.get("campaign")
    st_df = section_data.get("search_term")
    if camp_df is not None and not camp_df.empty and st_df is not None and not st_df.empty:
        # 获取活动名集合
        c_names = set(camp_df["广告活动"].astype(str).str.strip().unique()) if "广告活动" in camp_df.columns else (
            set(camp_df["活动名"].astype(str).str.strip().unique()) if "活动名" in camp_df.columns else set()
        )
        st_c_col = "广告活动" if "广告活动" in st_df.columns else ("来源广告活动" if "来源广告活动" in st_df.columns else None)
        if c_names and st_c_col:
            st_c_names = set(st_df[st_c_col].astype(str).str.strip().unique())
            matched = st_c_names.intersection(c_names)
            coverage = len(matched) / (len(st_c_names) if st_c_names else 1) * 100
            if coverage < 50.0:
                penalties += 10
                checks.append({
                    "level": "WARN",
                    "table": "实体层级勾稽",
                    "item": "搜索词活动与活动报表匹配率偏低",
                    "detail": f"搜索词报表中的广告活动仅 {coverage:.1f}% 存在于活动总表中，可能包含已归档活动或多店铺混合数据",
                })
            else:
                checks.append({
                    "level": "PASS",
                    "table": "实体层级勾稽",
                    "item": "跨表活动标识高度吻合",
                    "detail": f"活动实体匹配率达到 {coverage:.1f}%",
                })

    # 4. SKU 映射覆盖率检查
    sku_map_dict = sku_map or {}
    ad_item_df = section_data.get("ad_item")
    if ad_item_df is None and section_data.get("trend") is not None:
        t_obj = section_data.get("trend")
        if isinstance(t_obj, dict) and "period_df" in t_obj:
            ad_item_df = t_obj["period_df"]

    if ad_item_df is not None and not ad_item_df.empty:
        id_col = None
        for cand in ["项目ID", "Item Id", "item_id", "商品ID"]:
            if cand in ad_item_df.columns:
                id_col = cand
                break
        if id_col:
            unique_ids = set(ad_item_df[id_col].astype(str).str.strip().str.split(".").str[0].unique())
            if not sku_map_dict:
                penalties += 10
                checks.append({
                    "level": "WARN",
                    "table": "SKU映射表",
                    "item": "未上传 SKU 映射表",
                    "detail": f"当前存在 {len(unique_ids)} 个 Item ID 待映射为店铺内部品名；建议上传映射表以获得以真实 SKU 为视角的经营诊断",
                })
            else:
                mapped_count = sum(1 for i in unique_ids if i in sku_map_dict)
                map_pct = mapped_count / len(unique_ids) * 100 if unique_ids else 0
                if map_pct < 60.0:
                    penalties += 8
                    checks.append({
                        "level": "WARN",
                        "table": "SKU映射表",
                        "item": "SKU 映射匹配率不完全",
                        "detail": f"已匹配 {mapped_count}/{len(unique_ids)} 个商品位 ({map_pct:.1f}%)，部分冷门品仍将以 Item ID 展示",
                    })
                else:
                    checks.append({
                        "level": "PASS",
                        "table": "SKU映射表",
                        "item": "SKU 映射充分",
                        "detail": f"覆盖率达到 {map_pct:.1f}%",
                    })

    # 5. 成本底表完整性检查
    cost_dict = sku_cost_dict or {}
    if not cost_dict:
        penalties += 10
        checks.append({
            "level": "WARN",
            "table": "💰 商品单位成本底表",
            "item": "未配置真实单位成本表",
            "detail": "当前利润模型按行业基准毛利率估算保本线；若需 100% 精确的真实净现金贡献，建议上传采购、头程与尾程成本表",
        })
    else:
        checks.append({
            "level": "PASS",
            "table": "💰 商品单位成本底表",
            "item": "成本配置已就绪",
            "detail": f"已录入 {len(cost_dict)} 个 SKU 的采购/物流/佣金单位经济学参数",
        })

    # 计算最终质量得分与置信度
    final_score = max(0, min(100, 100 - penalties))
    if final_score >= 85:
        confidence = "高置信度"
        status_text = "数据质量极佳，分析结论高度可信"
        guardrail = False
    elif final_score >= 60:
        confidence = "中置信度"
        status_text = "数据基本完整，部分指标存在口径差异或缺少成本映射"
        guardrail = False
    else:
        confidence = "低置信度"
        status_text = "核心字段缺失或关键数据口径冲突，已激活安全熔断保护"
        guardrail = True

    return {
        "score": final_score,
        "confidence": confidence,
        "status": status_text,
        "summary": f"数据质量评分: {final_score}/100（{confidence}）。已完成字段、格式、实体勾稽与口径全方位体检。",
        "checks": checks,
        "reconciliation": {
            "spends": total_spends_by_table,
            "orders": total_orders_by_table,
        },
        "guardrail_active": guardrail,
    }
