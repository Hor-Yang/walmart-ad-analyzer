from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from .metrics import safe_divide

def analyze_traffic_structure(
    campaign_df: Optional[pd.DataFrame] = None,
    keyword_df: Optional[pd.DataFrame] = None,
    search_term_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    第二层：广告表现与流量结构深度分析引擎 (Ad Performance & Traffic Structure Engine)
    
    核心职责：
    1. Auto (自动) 与 Manual (手动) 流量贡献与预算失衡诊断；
    2. Exact (精准), Phrase (词组), Broad (广泛) 匹配方式的投产对比；
    3. 流量内耗与同词互搏识别 (Traffic Overlap / Cannibalization)；
    4. 全链路转化漏斗健康度透视。
    """
    res: Dict[str, Any] = {
        "auto_vs_manual_df": pd.DataFrame(),
        "match_type_df": pd.DataFrame(),
        "overlap_terms_df": pd.DataFrame(),
        "structure_insights": [],
        "summary": {},
    }

    # =========================================================================
    # 1. Auto vs Manual 广告活动结构分析
    # =========================================================================
    if campaign_df is not None and not campaign_df.empty:
        c_df = campaign_df.copy()
        camp_col = "广告活动" if "广告活动" in c_df.columns else ("活动名" if "活动名" in c_df.columns else None)
        if camp_col:
            # 智能判定 Auto 与 Manual
            def classify_targeting(name: Any) -> str:
                s = str(name).lower()
                if "auto" in s or "自动" in s:
                    return "🤖 Auto (自动投放)"
                elif any(k in s for k in ["manual", "手动", "精准", "exact", "广泛", "broad", "词组", "phrase", "长尾"]):
                    return "🎯 Manual (手动投放)"
                return "📦 其他/混合投放"

            c_df["投放模式"] = c_df[camp_col].apply(classify_targeting)
            
            # 数值列清洗
            for col in ["花费", "广告花费", "销售额", "总销售额", "订单", "广告订单", "曝光量", "点击"]:
                if col in c_df.columns:
                    c_df[col] = pd.to_numeric(c_df[col], errors="coerce").fillna(0.0)

            spend_c = "花费" if "花费" in c_df.columns else ("广告花费" if "广告花费" in c_df.columns else None)
            sales_c = "销售额" if "销售额" in c_df.columns else ("总销售额" if "总销售额" in c_df.columns else None)
            orders_c = "订单" if "订单" in c_df.columns else ("广告订单" if "广告订单" in c_df.columns else None)
            clicks_c = "点击" if "点击" in c_df.columns else None
            impr_c = "曝光量" if "曝光量" in c_df.columns else None

            if spend_c and sales_c and orders_c:
                agg_dict = {spend_c: "sum", sales_c: "sum", orders_c: "sum"}
                if clicks_c:
                    agg_dict[clicks_c] = "sum"
                if impr_c:
                    agg_dict[impr_c] = "sum"

                t_mode = c_df.groupby("投放模式", as_index=False).agg(agg_dict)
                t_mode = t_mode.rename(columns={
                    spend_c: "广告花费", sales_c: "总销售额", orders_c: "广告订单"
                })
                tot_spend = float(t_mode["广告花费"].sum())
                t_mode["花费占比"] = (t_mode["广告花费"] / (tot_spend if tot_spend > 0 else 1.0)) * 100.0
                t_mode["ROAS"] = safe_divide(t_mode["总销售额"], t_mode["广告花费"])
                t_mode["ACoS"] = safe_divide(t_mode["广告花费"], t_mode["总销售额"])
                if clicks_c and clicks_c in t_mode.columns:
                    t_mode["CPC"] = safe_divide(t_mode["广告花费"], t_mode[clicks_c])
                    t_mode["CVR"] = safe_divide(t_mode["广告订单"], t_mode[clicks_c])
                if impr_c and impr_c in t_mode.columns and clicks_c:
                    t_mode["CTR"] = safe_divide(t_mode[clicks_c], t_mode[impr_c])

                res["auto_vs_manual_df"] = t_mode

                # 诊断 Insights
                auto_row = t_mode[t_mode["投放模式"].str.contains("Auto")]
                manual_row = t_mode[t_mode["投放模式"].str.contains("Manual")]
                if not auto_row.empty:
                    auto_spend_pct = float(auto_row["花费占比"].iloc[0])
                    auto_roas = float(auto_row["ROAS"].iloc[0]) if auto_row["ROAS"].iloc[0] is not None else 0.0
                    manual_roas = float(manual_row["ROAS"].iloc[0]) if (not manual_row.empty and manual_row["ROAS"].iloc[0] is not None) else 0.0
                    
                    if auto_spend_pct >= 60.0:
                        res["structure_insights"].append({
                            "type": "⚠️ 流量结构倾斜",
                            "severity": "HIGH",
                            "finding": f"Auto 自动广告消耗占比高达 {auto_spend_pct:.1f}%，严重挤压手动精准预算",
                            "action": "建议将 Auto 预算控制在 25%~35% 区间，将已验证出单词提拔迁移至 Manual Exact（单品精准组）专属承接",
                        })
                    if manual_roas > auto_roas * 1.25 and auto_spend_pct >= 40.0:
                        res["structure_insights"].append({
                            "type": "💡 投产优化机会",
                            "severity": "MEDIUM",
                            "finding": f"Manual 手动投产 ({manual_roas:.2f}) 显著高于 Auto 自动 ({auto_roas:.2f})，存在明显预算错配",
                            "action": "应将 15%~25% 的低效自动广告预算再分配倾斜至表现优异的手动广告组中",
                        })

    # =========================================================================
    # 2. Match Type 匹配方式结构剖析
    # =========================================================================
    if keyword_df is not None and not keyword_df.empty:
        k_df = keyword_df.copy()
        m_col = "匹配方式" if "匹配方式" in k_df.columns else None
        if m_col:
            k_df["规范匹配方式"] = k_df[m_col].astype(str).str.lower().str.strip().map({
                "exact": "🎯 精准匹配 (Exact)",
                "phrase": "🔗 词组匹配 (Phrase)",
                "broad": "🌐 广泛匹配 (Broad)",
            }).fillna("🌐 广泛匹配 (Broad)")

            for c in ["广告花费", "总销售额", "广告订单", "点击", "曝光量"]:
                if c in k_df.columns:
                    k_df[c] = pd.to_numeric(k_df[c], errors="coerce").fillna(0.0)

            m_agg = k_df.groupby("规范匹配方式", as_index=False).agg({
                "广告花费": "sum",
                "总销售额": "sum",
                "广告订单": "sum",
                "点击": "sum",
                "曝光量": "sum",
            })
            tot_k_spend = float(m_agg["广告花费"].sum())
            m_agg["花费占比"] = (m_agg["广告花费"] / (tot_k_spend if tot_k_spend > 0 else 1.0)) * 100.0
            m_agg["ROAS"] = safe_divide(m_agg["总销售额"], m_agg["广告花费"])
            m_agg["ACoS"] = safe_divide(m_agg["广告花费"], m_agg["总销售额"])
            m_agg["CPC"] = safe_divide(m_agg["广告花费"], m_agg["点击"])
            m_agg["CVR"] = safe_divide(m_agg["广告订单"], m_agg["点击"])
            m_agg["CTR"] = safe_divide(m_agg["点击"], m_agg["曝光量"])
            res["match_type_df"] = m_agg.sort_values("广告花费", ascending=False).reset_index(drop=True)

    # =========================================================================
    # 3. 跨活动流量重叠与内耗检查 (Traffic Cannibalization)
    # =========================================================================
    if search_term_df is not None and not search_term_df.empty and "搜索词" in search_term_df.columns:
        s_df = search_term_df.copy()
        camp_col = "广告活动" if "广告活动" in s_df.columns else ("来源广告活动" if "来源广告活动" in s_df.columns else None)
        if camp_col:
            # 按搜索词统计跨活动出现频次
            term_camps = s_df.groupby("搜索词")[camp_col].nunique()
            overlap_terms = term_camps[term_camps > 1].index.tolist()
            if overlap_terms:
                ov_sub = s_df[s_df["搜索词"].isin(overlap_terms)]
                ov_agg = ov_sub.groupby("搜索词").agg(
                    跨活动数=(camp_col, "nunique"),
                    活动清单=(camp_col, lambda x: " | ".join(sorted(set(str(v) for v in x))[:3])),
                    总花费=("广告花费", "sum"),
                    总订单=("广告订单", "sum"),
                    总销售额=("总销售额", "sum"),
                ).reset_index()
                ov_agg["综合ROAS"] = safe_divide(ov_agg["总销售额"], ov_agg["总花费"])
                ov_agg = ov_agg.sort_values("总花费", ascending=False).head(15).reset_index(drop=True)
                res["overlap_terms_df"] = ov_agg

                if len(overlap_terms) > 5:
                    top_waste_term = ov_agg.iloc[0]["搜索词"]
                    n_camps = ov_agg.iloc[0]["跨活动数"]
                    res["structure_insights"].append({
                        "type": "⚔️ 同词跨活动内耗竞价",
                        "severity": "HIGH",
                        "finding": f"检测到 {len(overlap_terms)} 个搜索词在多个活动中同时被触发；例如【{top_waste_term}】同时在 {n_camps} 个活动中争抢流量",
                        "action": "建议实施否定关键词隔离：在 Auto 组和 Broad 组中精确否定该词，指定单一的 Exact 组独家竞价承接，杜绝自家抬高 CPC 内耗",
                    })

    return res
