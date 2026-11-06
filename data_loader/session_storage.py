import os
import io
import time
import pickle
import datetime
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".session_cache")
SESSION_FILE = os.path.join(CACHE_DIR, "latest_session.pkl")
AUDIT_LOG_FILE = os.path.join(CACHE_DIR, "upload_audit_history.pkl")

def _ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
        except Exception:
            pass

def save_session_cache(
    section_data: Dict[str, Any],
    sku_map: Dict[str, str],
    sku_cost_dict: Dict[str, Any],
    file_names: Dict[str, str],
    settings: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    自动持久化当前会话的核心数据与配置到本地磁盘。
    即使刷新网页或意外关闭标签页，也能一键秒级恢复，免去重复上传 6~7 个 Excel 报表的繁琐。
    """
    try:
        _ensure_cache_dir()
        payload = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "unix_time": time.time(),
            "section_data": section_data,
            "sku_map": sku_map or {},
            "sku_cost_dict": sku_cost_dict or {},
            "file_names": file_names or {},
            "settings": settings or {},
        }
        with open(SESSION_FILE, "wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        return True
    except Exception as e:
        print(f"[session_storage] Error saving session: {e}")
        return False

def load_session_cache() -> Optional[Dict[str, Any]]:
    """读取已保存的会话快照"""
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "rb") as f:
            data = pickle.load(f)
        return data
    except Exception as e:
        print(f"[session_storage] Error loading session: {e}")
        return None

def get_session_cache_metadata() -> Optional[Dict[str, Any]]:
    """获取缓存的简明元数据用于前端提示"""
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        mtime = os.path.getmtime(SESSION_FILE)
        time_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = os.path.getsize(SESSION_FILE) / 1024.0
        
        # 简单探测包含的表
        with open(SESSION_FILE, "rb") as f:
            data = pickle.load(f)
            
        f_names = data.get("file_names", {})
        active_tables = [k for k, v in data.get("section_data", {}).items() if v is not None]
        return {
            "timestamp": data.get("timestamp", time_str),
            "size_kb": size_kb,
            "file_count": len(f_names),
            "file_names": f_names,
            "active_tables": active_tables,
            "sku_count": len(data.get("sku_map", {})),
            "cost_count": len(data.get("sku_cost_dict", {})),
        }
    except Exception as e:
        return None

def clear_session_cache() -> bool:
    """清空本地持久化快照"""
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        return True
    except Exception:
        return False

def record_upload_audit_log(
    file_type: str,
    file_name: str,
    row_count: int,
    file_size_bytes: int = 0,
    metrics_summary: Optional[str] = None,
):
    """
    记录文件上传与处理审计日志，永久保留每次上传的时间、文件、数据条数与关键摘要。
    """
    _ensure_cache_dir()
    log_entry = {
        "时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "板块类别": file_type,
        "文件名": file_name,
        "数据行数": row_count,
        "文件大小(KB)": round(file_size_bytes / 1024.0, 1) if file_size_bytes > 0 else 0,
        "分析指标摘要": metrics_summary or "解析成功并就绪",
    }
    
    logs = []
    if os.path.exists(AUDIT_LOG_FILE):
        try:
            with open(AUDIT_LOG_FILE, "rb") as f:
                logs = pickle.load(f)
        except Exception:
            logs = []
            
    logs.append(log_entry)
    # 最多保留最近 100 条记录
    if len(logs) > 100:
        logs = logs[-100:]
        
    try:
        with open(AUDIT_LOG_FILE, "wb") as f:
            pickle.dump(logs, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass

def get_upload_audit_logs() -> List[Dict[str, Any]]:
    """获取所有历史上传审计日志"""
    if not os.path.exists(AUDIT_LOG_FILE):
        return []
    try:
        with open(AUDIT_LOG_FILE, "rb") as f:
            logs = pickle.load(f)
        return logs
    except Exception:
        return []

def generate_audit_log_markdown() -> str:
    """生成格式化的审计日志 Markdown，便于用户查阅与复制导出"""
    logs = get_upload_audit_logs()
    if not logs:
        return "暂无报表上传与分析日志记录。"
    
    lines = [
        "# 沃尔玛广告分析系统 - 上传与分析审计日志",
        f"*导出生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "| 记录时间 | 业务板块 | 上传文件名 | 数据量 (行) | 文件大小 | 诊断摘要 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for item in reversed(logs):
        lines.append(
            f"| {item['时间']} | {item['板块类别']} | `{item['文件名']}` | {item['数据行数']} | {item['文件大小(KB)']} KB | {item['分析指标摘要']} |"
        )
    return "\n".join(lines)
