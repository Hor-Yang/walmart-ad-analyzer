import os
import time
import pickle
import datetime
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

TRACKER_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".session_cache",
    "optimization_tracking_history.pkl"
)

def _ensure_dir():
    d = os.path.dirname(TRACKER_FILE)
    if not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass

def log_optimization_actions(
    actions: List[Dict[str, Any]],
    batch_name: Optional[str] = None,
) -> int:
    """
    第六层：保存优化决策快照与执行基准数据 (Pre-optimization Baseline)。
    记录：优化前数据、AI原始判断、建议执行动作、执行日期、目标验证周期与成功标准。
    """
    _ensure_dir()
    existing_records = load_tracking_history()
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    count = 0

    for act in actions:
        record_id = f"ACT-{int(time.time())}-{count+1}"
        record = {
            "action_id": record_id,
            "created_at": now_str,
            "execution_date": date_str,
            "batch_name": batch_name or f"优化批次_{date_str}",
            "entity": act.get("对象标识", act.get("entity", "-")),
            "scope": act.get("所属活动/范围", "-"),
            "domain": act.get("决策领域", act.get("issue_type", "广告优化")),
            "priority": act.get("优先级", "P1"),
            "pre_data_evidence": act.get("当前指标依据", act.get("data_evidence", "")),
            "ai_action": act.get("决策执行指令", act.get("action", "")),
            "magnitude": act.get("建议调整幅度", "适度"),
            "risk_warning": act.get("风险提示", "密切监控转化率"),
            "validation_window": act.get("验证周期", "7天"),
            "success_criteria": act.get("成功判断标准", "ROAS改善且出单稳定"),
            "operator_status": "建议执行", # 待执行 / 已执行 / 忽略
            "actual_action": act.get("决策执行指令", ""),
            "post_data": None,
            "outcome_evaluation": "待新周期报表回测验证",
            "calibration_insight": "尚待周期后数据对比",
        }
        existing_records.append(record)
        count += 1

    # 保留最近 200 条
    if len(existing_records) > 200:
        existing_records = existing_records[-200:]

    try:
        with open(TRACKER_FILE, "wb") as f:
            pickle.dump(existing_records, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        print(f"[effect_tracker] Error saving tracking log: {e}")
    
    return count

def load_tracking_history() -> List[Dict[str, Any]]:
    """加载历史优化追踪记录"""
    if not os.path.exists(TRACKER_FILE):
        return []
    try:
        with open(TRACKER_FILE, "rb") as f:
            return pickle.load(f)
    except Exception:
        return []

def clear_tracking_history() -> bool:
    """清空历史追踪记录"""
    try:
        if os.path.exists(TRACKER_FILE):
            os.remove(TRACKER_FILE)
        return True
    except Exception:
        return False

def update_action_status(action_id: str, new_status: str, actual_action: Optional[str] = None) -> bool:
    """// FIX: 更新优化动作的执行状态 (待执行 -> 已执行 / 已忽略)"""
    records = load_tracking_history()
    updated = False
    for r in records:
        if r.get("action_id") == action_id:
            r["operator_status"] = new_status
            if actual_action:
                r["actual_action"] = actual_action
            updated = True
            break
    if updated:
        try:
            with open(TRACKER_FILE, "wb") as f:
                pickle.dump(records, f, protocol=pickle.HIGHEST_PROTOCOL)
            return True
        except Exception:
            return False
    return False


def backfill_post_data(action_id: str, post_data: Dict[str, Any], outcome_evaluation: str, calibration_insight: str = "") -> bool:
    """// FIX: 优化后数据回填与闭环效果评估"""
    records = load_tracking_history()
    updated = False
    for r in records:
        if r.get("action_id") == action_id:
            r["post_data"] = post_data
            r["outcome_evaluation"] = outcome_evaluation
            if calibration_insight:
                r["calibration_insight"] = calibration_insight
            updated = True
            break
    if updated:
        try:
            with open(TRACKER_FILE, "wb") as f:
                pickle.dump(records, f, protocol=pickle.HIGHEST_PROTOCOL)
            return True
        except Exception:
            return False
    return False


# // FIX: 统一兼容历史参数传参 (history)，彻底移除硬编码百分比，动态根据真实记录计算
def generate_tracking_summary(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """生成效果追踪与模型迭代统计数据 (支持传入 history 列表或自动加载)"""
    records = history if history is not None else load_tracking_history()
    if not records:
        return {
            "total_actions": 0,
            "pending_count": 0,
            "pending_actions": 0,
            "validated_count": 0,
            "validated_actions": 0,
            "successful_actions": 0,
            "success_rate_pct": 0.0,
            "success_rate": "0.0%",
            "rule_calibrations": 0,
            "model_rule_stats": [],
            "records_df": pd.DataFrame(),
        }

    df = pd.DataFrame(records)
    total = len(df)
    
    # 动态统计状态
    pending = 0
    successful = 0
    validated = 0
    
    for r in records:
        status = str(r.get("operator_status", ""))
        eval_str = str(r.get("outcome_evaluation", ""))
        if "待" in eval_str or status in ("待执行", "建议执行"):
            pending += 1
        else:
            validated += 1
            if any(k in eval_str for k in ["达标", "成功", "改善", "盈利", "正向", "止血"]):
                successful += 1

    success_rate_pct = (successful / validated * 100.0) if validated > 0 else 0.0

    # 动态规则效果汇总（基于真实记录统计，严禁硬编码虚假数据）
    rule_map: Dict[str, Dict[str, Any]] = {}
    for r in records:
        dom = str(r.get("domain", "常规优化"))
        if dom not in rule_map:
            rule_map[dom] = {"sample_count": 0, "success_count": 0}
        rule_map[dom]["sample_count"] += 1
        eval_str = str(r.get("outcome_evaluation", ""))
        if any(k in eval_str for k in ["达标", "成功", "改善", "盈利", "正向", "止血"]):
            rule_map[dom]["success_count"] += 1

    rule_stats = []
    for r_name, stat in rule_map.items():
        s_count = stat["sample_count"]
        succ = stat["success_count"]
        pct = (succ / s_count * 100.0) if s_count > 0 else 0.0
        rule_stats.append({
            "rule_name": r_name,
            "sample_count": s_count,
            "effectiveness": f"{pct:.1f}% 有效" if s_count > 0 else "待观察",
            "impact": f"已累计追踪 {s_count} 项决策动作，成功验证 {succ} 项",
        })

    return {
        "total_actions": total,
        "pending_count": pending,
        "pending_actions": pending,
        "validated_count": validated,
        "validated_actions": validated,
        "successful_actions": successful,
        "success_rate_pct": round(success_rate_pct, 1),
        "success_rate": f"{success_rate_pct:.1f}%",
        "rule_calibrations": len(rule_map),
        "model_rule_stats": rule_stats,
        "records_df": df,
    }
