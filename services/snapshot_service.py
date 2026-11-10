"""
CrossBorder BI · 分析记录快照与跨周期对比服务 (Analysis Report Snapshot & Diff Service)
遵循规范：
1. 分析快照持久化：双重保存至 SQLite (fact_report_snapshots) 与本地轻量目录 data/users/{user_id}/reports/
2. 历史归档管理：支持一键回溯重载历史某一期诊断面板
3. 双期跨周期对比 (Diff Mode)：自动计算并高亮核心指标环比升降、治愈的亏损 SKU 与问题词优化数量
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from services.storage_engine import StorageEngine


class SnapshotService:
    """分析快照生命周期与跨期对比管理"""

    def __init__(self, storage: Optional[StorageEngine] = None, base_data_dir: Optional[str] = None):
        self.storage = storage or StorageEngine()
        self.base_data_dir = base_data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "users"
        )
        self._init_snapshot_schema()

    def _init_snapshot_schema(self):
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fact_report_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    report_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_spend REAL DEFAULT 0.0,
                    total_sales REAL DEFAULT 0.0,
                    roas REAL DEFAULT 0.0,
                    acos REAL DEFAULT 0.0,
                    total_orders INTEGER DEFAULT 0,
                    pre_ad_profit REAL DEFAULT 0.0,
                    post_ad_profit REAL DEFAULT 0.0,
                    issues_count INTEGER DEFAULT 0,
                    p0_count INTEGER DEFAULT 0,
                    source_files TEXT,
                    snapshot_json TEXT
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snap_user ON fact_report_snapshots(user_id);")
            conn.commit()

    def _get_user_report_dir(self, user_id: str) -> str:
        d = os.path.join(self.base_data_dir, str(user_id).strip(), "reports")
        os.makedirs(d, exist_ok=True)
        return d

    def create_snapshot(
        self,
        user_id: str,
        report_name: str,
        sec_data: Dict[str, Any],
        overview: Optional[Dict[str, Any]] = None,
        action_df: Optional[pd.DataFrame] = None,
        issues: Optional[List[Dict[str, Any]]] = None,
        source_files: Optional[List[str]] = None,
    ) -> str:
        """
        // FIX: 自动将核心指标快照序列化保存至本地数据库与用户隔离目录
        """
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        safe_name = "".join([c for c in report_name if c.isalnum() or c in ("-", "_")]) or "analysis"
        snapshot_id = f"snap_{timestamp_str}_{safe_name}"

        ov = overview or {}
        tot_spend = float(ov.get("大盘总花费") or ov.get("广告花费") or 0.0)
        tot_sales = float(ov.get("总销售额") or 0.0)
        roas = float(ov.get("整体ROAS") or ov.get("ROAS") or 0.0)
        if roas == 0.0 and tot_spend > 0:
            roas = round(tot_sales / tot_spend, 2)
        acos = round(tot_spend / tot_sales, 4) if tot_sales > 0 else 0.0
        tot_orders = int(ov.get("总订单") or ov.get("订单量") or 0)

        p0_c = 0
        if action_df is not None and not action_df.empty:
            p_col = next((c for c in ["优先级", "priority"] if c in action_df.columns), None)
            if p_col:
                p0_c = len(action_df[action_df[p_col].astype(str).str.upper() == "P0"])

        issues_c = len(issues) if issues else 0

        # 提取 SKU 级指标（用于跨期对比）
        sku_metrics = []
        item_df = sec_data.get("ad_item")
        if item_df is not None and isinstance(item_df, pd.DataFrame) and not item_df.empty:
            sku_col = next((c for c in ["SKU", "sku", "对应SKU", "项目ID", "item_id"] if c in item_df.columns), item_df.columns[0])
            sp_col = next((c for c in ["花费", "广告花费", "spend"] if c in item_df.columns), None)
            sl_col = next((c for c in ["总销售额", "广告销售额", "销售额", "sales"] if c in item_df.columns), None)
            od_col = next((c for c in ["广告订单", "订单量", "订单", "orders"] if c in item_df.columns), None)
            
            if sp_col and sl_col:
                agg = item_df.groupby(sku_col).agg({
                    sp_col: "sum",
                    sl_col: "sum",
                    od_col: "sum" if od_col else "count"
                }).reset_index()
                for _, r in agg.head(50).iterrows():
                    s_spend = float(r[sp_col])
                    s_sales = float(r[sl_col])
                    s_roas = round(s_sales / s_spend, 2) if s_spend > 0 else 0.0
                    s_status = "高投产稳健" if s_roas >= 2.5 else ("严重失血" if (s_spend > 30 and (s_sales == 0 or s_roas < 1.0)) else "保本观察")
                    sku_metrics.append({
                        "sku": str(r[sku_col]).strip(),
                        "spend": s_spend,
                        "sales": s_sales,
                        "orders": int(r[od_col]) if od_col else 0,
                        "roas": s_roas,
                        "status": s_status,
                    })

        snapshot_payload = {
            "snapshot_id": snapshot_id,
            "user_id": user_id,
            "report_name": report_name,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "metrics": {
                "total_spend": tot_spend,
                "total_sales": tot_sales,
                "roas": roas,
                "acos": acos,
                "total_orders": tot_orders,
                "issues_count": issues_c,
                "p0_count": p0_c,
            },
            "source_files": source_files or [],
            "sku_metrics": sku_metrics,
            "issues_summary": [
                {"type": iss.get("问题类型"), "level": iss.get("原因置信度"), "action": iss.get("建议采取的措施")}
                for iss in (issues or [])[:5]
            ],
        }

        # 1. 序列化持久化至用户轻量目录 JSON
        user_dir = self._get_user_report_dir(user_id)
        json_path = os.path.join(user_dir, f"{snapshot_id}.json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(snapshot_payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # 2. 写入 SQLite 索引表
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO fact_report_snapshots
                (snapshot_id, user_id, report_name, created_at, total_spend, total_sales, roas, acos, total_orders, issues_count, p0_count, source_files, snapshot_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                snapshot_id,
                user_id,
                report_name,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                tot_spend,
                tot_sales,
                roas,
                acos,
                tot_orders,
                issues_c,
                p0_c,
                json.dumps(source_files or [], ensure_ascii=False),
                json.dumps(snapshot_payload, ensure_ascii=False),
            ))
            conn.commit()

        return snapshot_id

    def list_snapshots(self, user_id: str) -> List[Dict[str, Any]]:
        """列出该用户空间下的所有历史分析快照"""
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT snapshot_id, user_id, report_name, created_at, total_spend, total_sales, roas, acos, total_orders, issues_count, p0_count, source_files
                FROM fact_report_snapshots
                WHERE user_id = ?
                ORDER BY created_at DESC;
            """, (user_id,))
            rows = cursor.fetchall()
            res = []
            for r in rows:
                d = dict(r)
                try:
                    d["source_files"] = json.loads(d["source_files"]) if d.get("source_files") else []
                except Exception:
                    d["source_files"] = []
                res.append(d)
            return res

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """获取单个快照的完整详情"""
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT snapshot_json FROM fact_report_snapshots WHERE snapshot_id = ?", (snapshot_id,))
            row = cursor.fetchone()
            if row and row["snapshot_json"]:
                try:
                    return json.loads(row["snapshot_json"])
                except Exception:
                    pass
        return None

    def delete_snapshot(self, snapshot_id: str, user_id: str) -> bool:
        """安全删除快照"""
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM fact_report_snapshots WHERE snapshot_id = ? AND user_id = ?", (snapshot_id, user_id))
            conn.commit()

        # 同步删除 JSON 文件
        user_dir = self._get_user_report_dir(user_id)
        json_path = os.path.join(user_dir, f"{snapshot_id}.json")
        if os.path.exists(json_path):
            try:
                os.remove(json_path)
            except Exception:
                pass
        return True

    def compare_snapshots(self, snap_id_a: str, snap_id_b: str) -> Dict[str, Any]:
        """
        // FIX: 双期对比核心计算引擎 (Period A 基准期 vs Period B 对比期)
        计算：Spend 变化率、ROAS 差异、问题词减少量、治愈的亏损 SKU 数量
        """
        snap_a = self.get_snapshot(snap_id_a)
        snap_b = self.get_snapshot(snap_id_b)

        if not snap_a or not snap_b:
            return {"error": "快照数据不存在，无法执行双期对比"}

        mA = snap_a.get("metrics", {})
        mB = snap_b.get("metrics", {})

        spA, spB = float(mA.get("total_spend", 0.0)), float(mB.get("total_spend", 0.0))
        slA, slB = float(mA.get("total_sales", 0.0)), float(mB.get("total_sales", 0.0))
        roasA, roasB = float(mA.get("roas", 0.0)), float(mB.get("roas", 0.0))
        acosA, acosB = float(mA.get("acos", 0.0)), float(mB.get("acos", 0.0))
        issA, issB = int(mA.get("issues_count", 0)), int(mB.get("issues_count", 0))
        p0A, p0B = int(mA.get("p0_count", 0)), int(mB.get("p0_count", 0))

        # 宏观环比
        spend_diff = spB - spA
        spend_pct = (spend_diff / spA * 100.0) if spA > 0 else 0.0

        sales_diff = slB - slA
        sales_pct = (sales_diff / slA * 100.0) if slA > 0 else 0.0

        roas_diff = roasB - roasA
        acos_diff_pct = (acosB - acosA) * 100.0
        issues_diff = issB - issA  # 负数表示问题减少（优化有效）
        p0_diff = p0B - p0A

        # SKU 颗粒度对比
        skusA = {item["sku"]: item for item in snap_a.get("sku_metrics", [])}
        skusB = {item["sku"]: item for item in snap_b.get("sku_metrics", [])}

        all_sku_keys = list(set(skusA.keys()).union(set(skusB.keys())))
        cured_skus = []
        deteriorated_skus = []
        sku_diff_rows = []

        for s in all_sku_keys:
            dA = skusA.get(s, {"spend": 0.0, "sales": 0.0, "roas": 0.0, "status": "未投放"})
            dB = skusB.get(s, {"spend": 0.0, "sales": 0.0, "roas": 0.0, "status": "未投放"})

            sp_d = dB["spend"] - dA["spend"]
            sl_d = dB["sales"] - dA["sales"]
            r_d = dB["roas"] - dA["roas"]

            # 治愈判断：A 状态为严重失血，而 B 状态变为高投产或稳健
            is_cured = (dA["status"] == "严重失血" and (dB["roas"] >= 2.5 or (dB["spend"] < 10 and dA["spend"] > 50)))
            is_regressed = (dA["status"] == "高投产稳健" and dB["status"] == "严重失血")

            if is_cured:
                cured_skus.append(s)
            if is_regressed:
                deteriorated_skus.append(s)

            sku_diff_rows.append({
                "SKU": s,
                "基准期花费": f"${dA['spend']:,.2f}",
                "对比期花费": f"${dB['spend']:,.2f}",
                "花费差额": f"${sp_d:+,.2f}",
                "基准期ROAS": f"{dA['roas']:.2f}x",
                "对比期ROAS": f"{dB['roas']:.2f}x",
                "ROAS变化": f"{r_d:+.2f}x",
                "优化评价": "【成功止血治愈】" if is_cured else ("【出现恶化风险】" if is_regressed else "稳健运行"),
            })

        sku_diff_df = pd.DataFrame(sku_diff_rows)

        return {
            "period_a": {
                "name": snap_a.get("report_name"),
                "date": snap_a.get("created_at"),
                "spend": spA, "sales": slA, "roas": roasA, "acos": acosA, "issues": issA, "p0": p0A
            },
            "period_b": {
                "name": snap_b.get("report_name"),
                "date": snap_b.get("created_at"),
                "spend": spB, "sales": slB, "roas": roasB, "acos": acosB, "issues": issB, "p0": p0B
            },
            "deltas": {
                "spend_diff": spend_diff,
                "spend_pct": spend_pct,
                "sales_diff": sales_diff,
                "sales_pct": sales_pct,
                "roas_diff": roas_diff,
                "acos_diff_pct": acos_diff_pct,
                "issues_reduced": max(0, -issues_diff),
                "issues_diff": issues_diff,
                "p0_diff": p0_diff,
                "cured_skus_count": len(cured_skus),
                "cured_skus": cured_skus,
                "deteriorated_count": len(deteriorated_skus),
                "deteriorated_skus": deteriorated_skus,
            },
            "sku_diff_df": sku_diff_df,
        }


_snapshot_svc_instance = None


def get_snapshot_service() -> SnapshotService:
    global _snapshot_svc_instance
    if _snapshot_svc_instance is None:
        _snapshot_svc_instance = SnapshotService()
    return _snapshot_svc_instance
