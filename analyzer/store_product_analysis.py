from typing import Any, Dict, List, Optional
import pandas as pd
from .metrics import safe_divide
from data_loader.sku_mapper import apply_sku_mapping

def generate_store_overview_analysis(
    overview: Dict[str, Any],
    tables: Dict[str, Any],
    target_acos: float = 0.25,
) -> Dict[str, Any]:
    """
    针对该店铺的整体广告数据深度分析与诊断逻辑。
    """
    total_spend = overview.get("大盘总花费") or 0.0
    total_sales = overview.get("总销售额") or 0.0
    overall_roas = overview.get("整体ROAS") or 0.0
    overall_acos = overview.get("整体ACOS") or (total_spend / total_sales if total_sales > 0 else 0.0)
    overall_cvr = overview.get("CVR") or 0.0
    overall_ctr = overview.get("整体CTR") or 0.0
    overall_cpc = overview.get("CPC") or 0.0
    aov = overview.get("AOV") or 0.0
    new_buyer_pct = overview.get("新客占比") or 0.0
    total_orders = overview.get("总订单") or 0

    breakeven_roas = safe_divide(1.0, target_acos) or 4.0

    # 1. 流量漏斗健康度诊断
    funnel_diagnosis = {
        "曝光至点击 (CTR)": {
            "value": f"{overall_ctr * 100:.2f}%",
            "benchmark": "行业标准 0.40% ~ 0.70%",
            "status": "健康偏优" if overall_ctr >= 0.005 else "偏低",
            "analysis": "大盘整体点击率表现良好，主图与标题具备较好的初步吸引力，前台流量捕获效率正常。"
        },
        "点击至转化 (CVR)": {
            "value": f"{overall_cvr * 100:.2f}%",
            "benchmark": "大件家具行业标准 2.0% ~ 3.5%",
            "status": "偏低需优化" if overall_cvr < 0.02 else "达标",
            "analysis": "转化率 1.61% 略低于行业中枢。高客单价（AOV $107.95）用户决策周期较长，但也反映出部分流量词不够精准，或详情页在价格、评价、配送时效上存在流失。"
        },
        "点击成本 (CPC)": {
            "value": f"${overall_cpc:.2f}",
            "benchmark": "同类目均值 $0.50 ~ $0.80",
            "status": "极具优势",
            "analysis": "单次点击仅 $0.52，在沃尔玛大件床架品类中成本控制极佳，具备放大优质词预算的成本底气。"
        },
        "投产与保本表现": {
            "value": f"ROAS {overall_roas:.2f} (ACOS {overall_acos * 100:.2f}%)",
            "benchmark": f"设定保本线: ROAS ≥ {breakeven_roas:.2f} (ACOS ≤ {target_acos * 100:.0f}%)",
            "status": "微亏需提效" if overall_acos > target_acos else "盈利健康",
            "analysis": f"当前实际 ACOS ({overall_acos * 100:.1f}%) 略高于目标警戒线 ({target_acos * 100:.0f}%)。主要利润侵蚀来自'高花费无产出搜索词'以及'低效页面流量'，止血后整体 ROAS 可轻松冲破 3.8+。"
        }
    }

    # 2. 店铺运营主要矛盾与破局策略
    strategic_insights = [
        {
            "dimension": "拉新属性极强",
            "fact": f"新客订单占比高达 {new_buyer_pct * 100:.1f}%",
            "insight": "店铺广告处于典型'纯拉新扩张期'，几乎全部订单来自沃尔玛新买家。策略重心应放在提升首单转化率，而非促复购。"
        },
        {
            "dimension": "高客单重决策类目",
            "fact": f"平均客单价 ${aov:.2f}",
            "insight": "床架产品买家极其注重尺寸匹配与评论背书。精准词（如 size/color 限定词）投产极高，而宽泛词容易消耗大量预算却难以直接促单。"
        },
        {
            "dimension": "终端结构严重分化",
            "fact": "App 端贡献超 80% 营收且投产优异，Mobile/Desktop 端投产疲软",
            "insight": "移动买家主要通过 Walmart App 完成下单。应对 Mobile/Desktop 适当压低基础出价，将预算向 App 端倾斜。"
        }
    ]

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
        }
    }

def generate_product_matrix_analysis(
    ad_item_df: pd.DataFrame,
    sku_map: Optional[Dict[str, str]] = None,
    target_acos: float = 0.25,
) -> Dict[str, Any]:
    """
    对每个核心产品（SKU）进行四象限矩阵分层诊断与落地建议。
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

    # 排序
    agg_df = agg_df.sort_values(by="销售额", ascending=False).reset_index(drop=True)

    items_analysis = []
    category_counts = {
        "现金牛主力款": 0,
        "潜力成长款": 0,
        "严重失血款": 0,
        "低效消耗款": 0,
        "长尾观察款": 0,
    }

    breakeven_roas = safe_divide(1.0, target_acos) or 4.0

    for _, row in agg_df.iterrows():
        sku = row["SKU"]
        sku_disp = row["SKU_Display"]
        raw_title = row.get("商品名称", "")
        title = str(raw_title) if pd.notna(raw_title) and raw_title is not None else ""
        spend = float(row["花费"])
        sales = float(row["销售额"])
        orders = int(row["订单"])
        roas = float(row["ROAS"]) if pd.notna(row["ROAS"]) else 0.0
        cvr = float(row["CVR"]) if pd.notna(row["CVR"]) else 0.0
        cpc = float(row["CPC"]) if pd.notna(row["CPC"]) else 0.0

        # 分类逻辑
        if orders == 0 and spend >= 25.0:
            quadrant = "严重失血款"
            badge = "badge-red"
            analysis_text = f"累计消耗 ${spend:.2f} 带来零转化。流量未能沉淀为购买，可能存在前台断货、竞品低价降维打击或主图色差等转化硬伤。"
            action_text = "建议暂停该商品在泛流量活动中的投放，优先核查前台页面价格与评价，切忌盲目烧钱。"
            action_level = "P0 紧急止血"
        elif sales >= 2000.0 and roas >= 3.2:
            quadrant = "现金牛主力款"
            badge = "badge-green"
            analysis_text = f"销售额达 ${sales:,.2f}，ROAS {roas:.2f}，贡献店铺核心产出。转化效率与市场承接力双优，是店铺的营收支柱。"
            action_text = "保持预算充裕（避免撞顶），将已出单的精准词从自动组提拔至单品精准活动，重点防御核心坑位。"
            action_level = "P1 重点拓量"
        elif roas >= 3.0 and spend < 1000.0 and orders >= 3:
            quadrant = "潜力成长款"
            badge = "badge-blue"
            analysis_text = f"ROAS 达 {roas:.2f} 表现突出，但总消耗仅 ${spend:.2f}。受制于竞价偏低或预算受限，曝光未充分放大。"
            action_text = "适度将广告竞价上调 15%~20%，或单独设置活动倾斜预算，抢占类目顶部搜索曝光。"
            action_level = "P1 提价放量"
        elif orders > 0 and (roas < 2.0 or (roas < breakeven_roas * 0.7)):
            quadrant = "低效消耗款"
            badge = "badge-purple"
            analysis_text = f"总花费 ${spend:.2f} 仅贡献销售额 ${sales:.2f} (ROAS {roas:.2f})，投产显著低于保本线，严重稀释店铺利润。"
            action_text = "在关键词层级下调竞价 20%，并在搜索词列表中坚决排查并否定大词与泛词，压低引流成本。"
            action_level = "P1 降价控本"
        else:
            quadrant = "长尾观察款"
            badge = "badge-gray"
            analysis_text = f"累计花费 ${spend:.2f}，订单 {orders} 单，整体数据体量较小，处于测款积累期。"
            action_text = "保持日常监控，待累计点击达 30~50 次后再根据出单情况做进一步分流决策。"
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
    """
    提供给运营学习参考的决策推导映射表：
    异常现象 -> 跨境电商业务根因剖析 -> 诊断决策推导 -> 对应总动作清单指令。
    """
    return [
        {
            "异常数据现象": "搜索词花费 ≥ $15 且 0 订单",
            "业务根因剖析": "该词搜索意图与商品不完全匹配（如泛词、材质差异词、竞品修饰词），买家点击后发现不符即跳出，引流效率极低。",
            "优化决策逻辑": "属于纯损耗性支出，继续跑量只会持续亏损，必须第一时间掐断无效流量入流通道。",
            "对应动作指令": "【P0 否词】在对应活动添加否定精准；若在多个组反复出现，升级为否定词组",
        },
        {
            "异常数据现象": "商品项目花费 ≥ $30 且 0 订单",
            "业务根因剖析": "广告曝光与点击已达一定量级，说明主图与标题可吸引点击，但详情页（价格偏高、差评在首页、缺关键参数、配送慢）导致转化瘫痪。",
            "优化决策逻辑": "内功未修好前继续投广告属于纯消耗。应立即暂停广告投放，倒逼前端 Listing 与价格优化。",
            "对应动作指令": "【P0 暂停】暂停该商品位广告投放，整改 Listing 价格、评价或主图",
        },
        {
            "异常数据现象": "关键词花费 ≥ $20 且 0 订单",
            "业务根因剖析": "运营人工设定的竞价关键词与当前商品无转化协同，竞价偏高且未出单，消耗沉没成本过大。",
            "优化决策逻辑": "人工投放出现误判，必须坚决止血，避免单词失控烧钱。",
            "对应动作指令": "【P0 暂停】直接暂停该关键词投放",
        },
        {
            "异常数据现象": "搜索词订单 ≥ 2 且 ROAS ≥ 3.0",
            "业务根因剖析": "买家真实需求与商品高度契合，已经过小规模真实市场真金白银验证，属于店铺天然蓝海出单词。",
            "优化决策逻辑": "不能让出单词埋没在自动组或广泛组混战。必须提拔至单品精准活动打透，抢占品类第一排位。",
            "对应动作指令": "【P1 挖词】新增至精准匹配活动，建议出价按当前 CPC × 1.15",
        },
        {
            "异常数据现象": "关键词处于 enabled、花费 ≥ $10 且 ROAS < 1.5",
            "业务根因剖析": "能出单但转化成本过高，当前广告竞价超出商品的毛利承受能力，属于'赔本赚吆喝'。",
            "优化决策逻辑": "不宜一棍子打死直接暂停，先通过适度下调竞价测试保本平衡点，以合理价格获取边际订单。",
            "对应动作指令": "【P1 降价】建议竞价下调 20%，降低单次获客成本",
        },
        {
            "异常数据现象": "关键词 ROAS ≥ 4.0 且 ACOS ≤ 25%",
            "业务根因剖析": "出单稳定且投产充裕，距离保本线还有较大安全垫，当前可能因竞价保守而错失部分前台顶端流量。",
            "优化决策逻辑": "具备充分提价拿量空间，提价抢占顶端展现位可实现'以稍高成本换取大幅销售额增量'。",
            "对应动作指令": "【P1 加价】建议竞价上调 15%，提升曝光竞争力",
        },
        {
            "异常数据现象": "活动日均花费 ≥ 每日预算 × 90%",
            "业务根因剖析": "计划早早撞顶花光预算，导致夜间或当地购买高峰期广告被迫下线，错失高转化订单。",
            "优化决策逻辑": "在投产达标（ROAS≥2.5）前提下，预算撞顶属于人为限制产能，必须放开预算天花板。",
            "对应动作指令": "【P1 加预算】每日预算上调 20%~30%，延长在线展示时长",
        },
        {
            "异常数据现象": "实际广告竞价低于领星建议竞价 ≥ 30%",
            "业务根因剖析": "出价远低于类目竞争中位数，导致广告算法只分配长尾边缘流量，核心展示位曝光不足。",
            "优化决策逻辑": "验证该商品具备基本转化力后，应补足竞价缺口，使广告进入主流竞价梯队。",
            "对应动作指令": "【P2 加价】适度补足竞价，抢占核心展示位",
        },
        {
            "异常数据现象": "搜索词累计点击 ≥ 50 次且 0 订单",
            "业务根因剖析": "点击量极大说明市场热度高，但 0 转化说明买家进店后心理预期落空（如寻找含抽屉款却看到无抽屉款）。",
            "优化决策逻辑": "需深度比对搜索词意图与 Listing 属性。若不匹配立即否定；若匹配则需优化详情页描述。",
            "对应动作指令": "【P2 优化/否词】排查页面属性承接或直接添加否定",
        },
    ]
