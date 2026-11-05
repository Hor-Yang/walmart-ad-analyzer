from typing import Any, Dict, List, Optional
import pandas as pd
from .metrics import safe_divide
from data_loader.sku_mapper import apply_sku_mapping

def generate_store_overview_analysis(
    overview: Dict[str, Any],
    tables: Dict[str, Any],
    target_acos: float = 0.20,
    breakeven_acos: float = 0.35,
) -> Dict[str, Any]:
    """
    针对该店铺的整体广告数据深度分析与诊断逻辑：
    彻底消除任何硬编码的静态数值与品类文本，所有诊断分析文本100%基于传入报表动态推导计算生成。
    完全解耦保本 ACoS（毛利率盈亏红线）与目标 ACoS（预期盈利目标线）。
    """
    total_spend = float(overview.get("大盘总花费") or 0.0)
    total_sales = float(overview.get("总销售额") or 0.0)
    overall_roas = float(overview.get("整体ROAS") or (total_sales / total_spend if total_spend > 0 else 0.0))
    overall_acos = float(overview.get("整体ACOS") or (total_spend / total_sales if total_sales > 0 else 0.0))
    overall_cvr = float(overview.get("CVR") or 0.0)
    overall_ctr = float(overview.get("整体CTR") or 0.0)
    overall_cpc = float(overview.get("CPC") or 0.0)
    aov = float(overview.get("AOV") or 0.0)
    new_buyer_pct = float(overview.get("新客占比") or 0.0)
    total_orders = int(overview.get("总订单") or 0)

    # 保本线与目标线解耦
    breakeven_roas = safe_divide(1.0, breakeven_acos) or (1.0 / breakeven_acos if breakeven_acos > 0 else 2.86)
    target_roas = safe_divide(1.0, target_acos) or (1.0 / target_acos if target_acos > 0 else 5.0)

    # 动态盈亏与毛利测算
    margin_gap = breakeven_acos - overall_acos
    ad_net_profit = total_sales * margin_gap
    profit_per_order = aov * margin_gap if aov > 0 else 0.0

    # 1. 动态流量漏斗健康度诊断
    # CTR 诊断
    if overall_ctr >= 0.006:
        ctr_status = "表现优异"
        ctr_desc = f"大盘整体点击率为 {overall_ctr * 100:.2f}%，主图与标题在前台展现中具备极强的吸引力，前台流量捕获效率较高。"
    elif overall_ctr >= 0.0035:
        ctr_status = "健康中枢"
        ctr_desc = f"大盘整体点击率为 {overall_ctr * 100:.2f}%，处于行业正常中枢区间，前台展现与买家初步搜索意图基本吻合。"
    else:
        ctr_status = "偏低需优化"
        ctr_desc = f"大盘整体点击率仅 {overall_ctr * 100:.2f}%，前台点击转化偏弱，建议重点优化主图、价格标牌与核心关键词匹配度。"

    # CVR 诊断
    if overall_cvr >= 0.03:
        cvr_status = "承接优异"
        cvr_desc = f"大盘转化率达 {overall_cvr * 100:.2f}%，页面承接力极强，进店买家购买意向清晰，详情页具备充分转化说服力。"
    elif overall_cvr >= 0.018:
        cvr_status = "正常受控"
        cvr_desc = f"大盘转化率为 {overall_cvr * 100:.2f}%（平均客单价 ${aov:,.2f}），流量能够较为平稳地承接为订单，但仍有通过精细化否词提高流量精准度的空间。"
    else:
        cvr_status = "偏低需提效"
        cvr_desc = f"大盘转化率仅 {overall_cvr * 100:.2f}%，结合客单价 ${aov:,.2f}，存在较多进店后未下单的无效点击流失，建议坚决剔除泛词并检查页面价格与差评承接力。"

    # CPC 诊断
    if overall_cpc <= 0.50:
        cpc_status = "低成本优势"
        cpc_desc = f"单次点击成本仅 ${overall_cpc:.2f}，引流成本控制极佳，具备在优质高投产词上适度提价放量的安全垫空间。"
    elif overall_cpc <= 0.85:
        cpc_status = "行业正常"
        cpc_desc = f"单次点击成本为 ${overall_cpc:.2f}，竞价与市场公允中位数相符，需重点防范无转化词累积高额点击成本。"
    else:
        cpc_status = "成本偏高"
        cpc_desc = f"单次点击成本达 ${overall_cpc:.2f}，单点击获客成本偏高，必须严控宽泛大词竞价，防止高 CPC 词迅速吞噬预算。"

    # 盈亏线与投产诊断
    if overall_acos <= target_acos:
        profit_status = "达到目标盈利"
        profit_desc = (
            f"实际 ACoS ({overall_acos * 100:.1f}%) 优于设定的目标线 ({target_acos * 100:.1f}%)，"
            f"距离保本盈亏红线 ({breakeven_acos * 100:.1f}%) 拥有 {margin_gap * 100:.1f}% 的充足利润垫，"
            f"广告预估贡献正向毛利 ${ad_net_profit:,.2f}（平均每单净盈余约 ${profit_per_order:.2f}），处于健康扩量区间。"
        )
    elif overall_acos <= breakeven_acos:
        profit_status = "保本微利未达标"
        profit_desc = (
            f"实际 ACoS ({overall_acos * 100:.1f}%) 处于目标线 ({target_acos * 100:.1f}%) 与保本线 ({breakeven_acos * 100:.1f}%) 之间。"
            f"广告整体未发生击穿毛利的净亏损（仍产生毛利约 ${ad_net_profit:,.2f}），但未达成预期净利目标，需剔除无效损耗以提升投产。"
        )
    else:
        profit_status = "击穿保本线亏损"
        profit_desc = (
            f"实际 ACoS ({overall_acos * 100:.1f}%) 已击穿保本毛利率红线 ({breakeven_acos * 100:.1f}%)，"
            f"广告投放发生净亏损约 ${abs(ad_net_profit):,.2f}（平均每单亏损约 ${abs(profit_per_order):.2f}），"
            f"主要利润被零转化与低 ROAS 活动侵蚀，必须立即执行 P0 级否词与停关止损！"
        )

    funnel_diagnosis = {
        "曝光至点击 (CTR)": {
            "value": f"{overall_ctr * 100:.2f}%",
            "benchmark": "行业基准 0.40% ~ 0.70%",
            "status": ctr_status,
            "analysis": ctr_desc,
        },
        "点击至转化 (CVR)": {
            "value": f"{overall_cvr * 100:.2f}%",
            "benchmark": "行业基准 1.8% ~ 3.5%",
            "status": cvr_status,
            "analysis": cvr_desc,
        },
        "点击成本 (CPC)": {
            "value": f"${overall_cpc:.2f}",
            "benchmark": "参考区间 $0.50 ~ $0.85",
            "status": cpc_status,
            "analysis": cpc_desc,
        },
        "投产与保本表现": {
            "value": f"ROAS {overall_roas:.2f} (ACoS {overall_acos * 100:.2f}%)",
            "benchmark": f"保本线: ACoS ≤ {breakeven_acos * 100:.0f}% (ROAS ≥ {breakeven_roas:.2f}) | 目标线: ACoS ≤ {target_acos * 100:.0f}% (ROAS ≥ {target_roas:.2f})",
            "status": profit_status,
            "analysis": profit_desc,
        }
    }

    # 2. 动态店铺运营主要矛盾与数据事实推导（彻底移除静态文本）
    strategic_insights = []

    # 维度一：新客拉新特征
    if new_buyer_pct > 0:
        if new_buyer_pct >= 0.70:
            nb_insight = "店铺广告处于高度拉新扩张期，大部分订单由新买家贡献。核心策略应聚焦于前台首单转化承接与拉新投放效率。"
        else:
            nb_insight = "店铺具备一定老客自然回购与品牌粘性，拉新与复购较为均衡，建议兼顾老客复购触达与新客拓词。"
        strategic_insights.append({
            "dimension": "买家结构分布",
            "fact": f"新客订单占比达 {new_buyer_pct * 100:.1f}%",
            "insight": nb_insight,
        })

    # 维度二：客单价与决策模型
    if aov > 0:
        if aov >= 80.0:
            aov_insight = "高客单重决策商品，买家下单前比对周期长，极其注重尺寸参数、评级与配送。宽泛词容易虚耗预算，单品精准词投放效率最高。"
        elif aov >= 35.0:
            aov_insight = "中等客单价商品，价格敏感度适中，广告需注重在核心品类出单词上维持稳健竞价排位。"
        else:
            aov_insight = "轻量快消/低客单商品，买家冲动消费决策快，需严格压低 CPC 以保证单次转化成本不击穿低毛利上限。"
        strategic_insights.append({
            "dimension": "客单价与购买决策",
            "fact": f"全盘平均客单价 ${aov:,.2f} (总订单 {total_orders:,} 笔)",
            "insight": aov_insight,
        })

    # 维度三：跨平台/跨终端动态分布（从真实平台/位置报表中动态分析）
    plat_table = tables.get("platform")
    if plat_table is not None and not plat_table.empty and "平台" in plat_table.columns and "总销售额" in plat_table.columns:
        p_agg = plat_table.groupby("平台", as_index=False)["总销售额"].sum()
        p_total = p_agg["总销售额"].sum()
        if p_total > 0:
            p_agg["占比"] = p_agg["总销售额"] / p_total
            p_top = p_agg.sort_values(by="总销售额", ascending=False).iloc[0]
            top_name = str(p_top["平台"]).strip()
            top_pct = float(p_top["占比"]) * 100.0
            top_sales = float(p_top["总销售额"])
            strategic_insights.append({
                "dimension": "终端渠道集中度",
                "fact": f"【{top_name}】贡献了 {top_pct:.1f}% 的广告销售额 (${top_sales:,.2f})",
                "insight": f"订单高度集中于【{top_name}】端，建议优先将广告预算与竞价向该主力端倾斜，低产出渠道适当调低基础溢价。",
            })
    else:
        # 若无平台报表，则动态提取主力广告活动集中度
        camp_table = tables.get("campaign")
        if camp_table is not None and not camp_table.empty and "总销售额" in camp_table.columns:
            c_agg = camp_table.groupby("广告活动" if "广告活动" in camp_table.columns else camp_table.columns[0], as_index=False)["总销售额"].sum()
            c_total = c_agg["总销售额"].sum()
            if c_total > 0:
                c_agg["占比"] = c_agg["总销售额"] / c_total
                c_top = c_agg.sort_values(by="总销售额", ascending=False).iloc[0]
                c_top_name = str(c_top.iloc[0]).strip()
                c_top_pct = float(c_top["占比"]) * 100.0
                strategic_insights.append({
                    "dimension": "主力活动集中度",
                    "fact": f"核心活动【{c_top_name}】贡献了 {c_top_pct:.1f}% 营收",
                    "insight": "店铺广告产出具备明显的头部活动集聚效应，需重点保证该核心活动的预算不撞顶，同时提防单点波动风险。",
                })

    return {
        "funnel": funnel_diagnosis,
        "strategic_insights": strategic_insights,
        "metrics_summary": {
            "spend": total_spend,
            "sales": total_sales,
            "roas": overall_roas,
            "acos": overall_acos,
            "orders": total_orders,
            "aov": aov,
            "target_acos": target_acos,
            "breakeven_acos": breakeven_acos,
            "margin_gap": margin_gap,
            "ad_net_profit": ad_net_profit,
            "profit_per_order": profit_per_order,
        }
    }

def generate_product_matrix_analysis(
    ad_item_df: pd.DataFrame,
    sku_map: Optional[Dict[str, str]] = None,
    target_acos: float = 0.20,
    breakeven_acos: float = 0.35,
) -> Dict[str, Any]:
    """
    对每个核心产品（SKU）进行基于动态盈亏与保本线的四象限矩阵分层诊断与落地建议。
    解耦 target_acos 与 breakeven_acos。
    """
    if ad_item_df is None or ad_item_df.empty:
        return {"items": [], "matrix_summary": {}}

    df = ad_item_df.copy()
    if sku_map:
        df = apply_sku_mapping(df, sku_map)
    else:
        if "SKU" not in df.columns:
            if "项目ID" in df.columns:
                df["SKU"] = df["项目ID"].astype(str).str.split(".").str[0]
            else:
                df["SKU"] = "未知"
        df["SKU_Display"] = df["SKU"]

    # 数值标准化
    for col in ["广告花费", "曝光量", "点击", "广告订单", "总销售额"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    title_col = None
    for cand in ["商品名称", "广告", "Item Name", "item_name", "Title", "title"]:
        if cand in df.columns:
            title_col = cand
            break
    title_map = df.sort_values(title_col, key=lambda s: s.astype(str).str.len()).groupby("SKU")[title_col].last() if title_col else {}

    # 按 SKU 聚合
    agg_df = df.groupby(["SKU", "SKU_Display"], as_index=False).agg(
        花费=("广告花费", "sum"),
        订单=("广告订单", "sum"),
        销售额=("总销售额", "sum"),
        点击=("点击", "sum"),
        曝光=("曝光量", "sum"),
    )

    agg_df["商品名称"] = agg_df["SKU"].map(title_map).fillna("")
    agg_df["ROAS"] = safe_divide(agg_df["销售额"], agg_df["花费"])
    agg_df["ACOS"] = safe_divide(agg_df["花费"], agg_df["销售额"])
    agg_df["CVR"] = safe_divide(agg_df["订单"], agg_df["点击"])
    agg_df["CPC"] = safe_divide(agg_df["花费"], agg_df["点击"])

    agg_df = agg_df.sort_values(by="销售额", ascending=False).reset_index(drop=True)

    items_analysis = []
    category_counts = {
        "现金牛主力款": 0,
        "潜力成长款": 0,
        "严重失血款": 0,
        "低效消耗款": 0,
        "长尾观察款": 0,
    }

    breakeven_roas = safe_divide(1.0, breakeven_acos) or (1.0 / breakeven_acos if breakeven_acos > 0 else 2.86)
    target_roas = safe_divide(1.0, target_acos) or (1.0 / target_acos if target_acos > 0 else 5.0)

    for _, row in agg_df.iterrows():
        sku = row["SKU"]
        sku_disp = row["SKU_Display"]
        raw_title = row.get("商品名称", "")
        title = str(raw_title) if pd.notna(raw_title) and raw_title is not None else ""
        spend = float(row["花费"])
        sales = float(row["销售额"])
        orders = int(row["订单"])
        roas = float(row["ROAS"]) if pd.notna(row["ROAS"]) else 0.0
        acos = float(row["ACOS"]) if pd.notna(row["ACOS"]) else 1.0
        cvr = float(row["CVR"]) if pd.notna(row["CVR"]) else 0.0
        cpc = float(row["CPC"]) if pd.notna(row["CPC"]) else 0.0

        # 四象限动态分类逻辑（严格以目标线与保本线为标准）
        if orders == 0 and spend >= 20.0:
            quadrant = "严重失血款"
            badge = "badge-red"
            analysis_text = f"累计纯消耗 ${spend:,.2f} 产生 0 笔转化，击穿止损红线，未形成有效购买。"
            action_text = "建议立即暂停该商品在泛流量广告中的投放，优先核查前台页面价格、评价承接力，切忌盲目烧钱。"
            action_level = "P0 紧急止血"
        elif sales >= 1500.0 and roas >= target_roas * 0.8:
            quadrant = "现金牛主力款"
            badge = "badge-green"
            analysis_text = f"销售额达 ${sales:,.2f}，ROAS {roas:.2f} (ACoS {acos*100:.1f}%)，达到优异盈利区间，是店铺营收支柱。"
            action_text = "保持预算充裕（严防预算撞顶），将已出单的精准搜索词提拔至单品专属精准活动，加固核心坑位。"
            action_level = "P1 重点拓量"
        elif roas >= target_roas * 0.75 and spend < 1000.0 and orders >= 2:
            quadrant = "潜力成长款"
            badge = "badge-blue"
            analysis_text = f"ROAS 达 {roas:.2f} 盈利能力良好，但总花费仅 ${spend:.2f}，受制于竞价或预算受限，展现尚未充分释放。"
            action_text = "适度将广告竞价上调 15%~20%，或单独设置活动倾斜预算，抢占类目顶部精准曝光。"
            action_level = "P1 提价放量"
        elif orders > 0 and (acos > breakeven_acos or roas < breakeven_roas):
            quadrant = "低效消耗款"
            badge = "badge-purple"
            analysis_text = f"总花费 ${spend:,.2f}，产出销售额 ${sales:,.2f}，ACoS ({acos*100:.1f}%) 已击穿保本毛利线 ({breakeven_acos*100:.1f}%)，处于净亏损状态。"
            action_text = "在关键词层级下调竞价 20%，并在搜索词列表中坚决排查并否定宽泛大词，压低引流成本争取保本。"
            action_level = "P1 降价控本"
        else:
            quadrant = "长尾观察款"
            badge = "badge-gray"
            analysis_text = f"累计花费 ${spend:.2f}，出单 {orders} 笔，数据体量较小，处于测款积累期。"
            action_text = "保持日常监控，待累计点击达 30~50 次后再根据出单转化情况做进一步调价或分流决策。"
            action_level = "P2 日常观察"

        category_counts[quadrant] = category_counts.get(quadrant, 0) + 1

        items_analysis.append({
            "SKU": sku,
            "SKU展示": sku_disp,
            "商品标题": title[:50] + ("..." if len(title) > 50 else ""),
            "分类矩阵": quadrant,
            "分类徽章": badge,
            "花费": spend,
            "销售额": sales,
            "订单": orders,
            "ROAS": roas,
            "ACOS": acos,
            "CVR": cvr,
            "CPC": cpc,
            "数据诊断逻辑": analysis_text,
            "对应优化建议": action_text,
            "行动级别": action_level,
        })

    return {
        "items": items_analysis,
        "matrix_summary": category_counts,
    }

def get_decision_mapping_guide() -> List[Dict[str, str]]:
    """决策推导映射表（供运营参考）"""
    return [
        {
            "异常数据现象": "搜索词花费 ≥ $15 且 0 订单",
            "业务根因剖析": "该词搜索意图与商品不匹配（泛词、材质差异词、竞品词），买家点击后跳出率极高，引流效率低。",
            "优化决策逻辑": "纯损耗性支出，继续跑量只会持续亏损，必须第一时间掐断无效流量通道。",
            "对应动作指令": "【P0 否词】在对应活动添加否定精准；若在多个组反复出现，升级为否定词组",
        },
        {
            "异常数据现象": "商品项目花费 ≥ $20 且 0 订单",
            "业务根因剖析": "广告曝光与点击已达一定量级，说明主图吸睛，但详情页（价格偏高、差评在首屏、缺关键参数、配送慢）导致转化瘫痪。",
            "优化决策逻辑": "内功未修好前继续投广告属于纯消耗。应立即暂停广告投放，倒逼前端优化。",
            "对应动作指令": "【P0 暂停】暂停该商品位广告投放，整改价格、评价或主图",
        },
        {
            "异常数据现象": "关键词花费 ≥ $20 且 0 订单",
            "业务根因剖析": "人工设定的竞价关键词与当前商品无转化协同，竞价偏高且未出单，沉没成本过大。",
            "优化决策逻辑": "投放出现误判，必须坚决止血，避免单词失控烧钱。",
            "对应动作指令": "【P0 暂停】直接暂停该关键词投放",
        },
        {
            "异常数据现象": "搜索词订单 ≥ 2 且 ROAS ≥ 3.0",
            "业务根因剖析": "买家真实需求与商品高度契合，已经过真实市场验证，属于天然蓝海出单词。",
            "优化决策逻辑": "不能让出单词埋没在自动组或广泛组混战。必须提拔至单品精准活动打透，抢占品类前列排位。",
            "对应动作指令": "【P1 挖词】新增至精准匹配活动，建议出价按当前 CPC × 1.15",
        },
        {
            "异常数据现象": "关键词处于 enabled、花费 ≥ $10 且 ROAS < 1.5",
            "业务根因剖析": "能出单但转化成本过高，当前广告竞价超出商品毛利承受能力，属于'赔本赚吆喝'。",
            "优化决策逻辑": "不宜一棍子打死直接暂停，先通过适度下调竞价测试保本平衡点，以合理价格获取边际订单。",
            "对应动作指令": "【P1 降价】建议实际竞价下调 20%，降低单次获客成本（无实际竞价时先核查）",
        },
        {
            "异常数据现象": "关键词 ROAS ≥ 4.0 且 ACOS ≤ 25%",
            "业务根因剖析": "出单稳定且投产充裕，距离保本线有较大安全垫，当前可能因竞价保守而错失部分顶端流量。",
            "优化决策逻辑": "具备充分提价拿量空间，提价抢占顶端展现位可实现以稍高成本换取大幅销售额增量。",
            "对应动作指令": "【P1 加价】建议实际竞价上调 15%，提升曝光竞争力",
        },
        {
            "异常数据现象": "活动日均花费 ≥ 每日预算 × 90%",
            "业务根因剖析": "计划早早撞顶花光预算，导致夜间或当地购买高峰期广告被迫下线，错失高转化订单。",
            "优化决策逻辑": "在投产达标（ROAS≥2.5）前提下，预算撞顶属于人为限制产能，必须放开预算天花板。",
            "对应动作指令": "【P1 加预算】每日预算上调 20%~30%，延长在线展示时长",
        },
    ]
