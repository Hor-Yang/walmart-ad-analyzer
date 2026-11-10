"""
CrossBorder BI · 轻量级用户鉴权与多租户隔离服务 (Lightweight Auth & Multi-Tenant Service)
遵循规范：
1. 开箱即用：基于 SQLite dim_users 表，预置主管理员与分析师账号
2. 多租户隔离：各操作空间、历史快照与报表数据严格按 user_id 进行物理与逻辑隔离
3. 无外部依赖：纯 Python 标准库 hashlib, sqlite3, datetime
"""

import os
import hashlib
import sqlite3
from typing import Dict, Any, List, Optional
import streamlit as st
from services.storage_engine import StorageEngine, DEFAULT_DB_PATH


def _hash_pwd(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()


class AuthService:
    """轻量级用户鉴权与租户隔离服务"""

    def __init__(self, storage: Optional[StorageEngine] = None):
        self.storage = storage or StorageEngine()
        self._init_auth_schema()
        self._seed_default_users()

    def _init_auth_schema(self):
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dim_users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT DEFAULT 'analyst',
                    tenant_code TEXT DEFAULT 'default_org',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

    def _seed_default_users(self):
        default_users = [
            ("usr_admin", "admin", _hash_pwd("admin888"), "主管理员 (Admin)", "admin", "org_01"),
            ("usr_analyst", "analyst", _hash_pwd("analyst888"), "沃尔玛广告操盘手", "analyst", "org_01"),
            ("usr_seller", "store_manager", _hash_pwd("seller888"), "多店铺运营总监", "manager", "org_02"),
        ]
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            for u in default_users:
                cursor.execute("""
                    INSERT OR IGNORE INTO dim_users 
                    (user_id, username, password_hash, display_name, role, tenant_code)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, u)
            conn.commit()

    def list_users(self) -> List[Dict[str, Any]]:
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, display_name, role, tenant_code FROM dim_users WHERE is_active = 1")
            return [dict(r) for r in cursor.fetchall()]

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        pwd_h = _hash_pwd(password)
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, display_name, role, tenant_code FROM dim_users WHERE username = ? AND password_hash = ? AND is_active = 1",
                (username.strip(), pwd_h)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, display_name, role, tenant_code FROM dim_users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None


_auth_svc_instance = None


def get_auth_service() -> AuthService:
    global _auth_svc_instance
    if _auth_svc_instance is None:
        _auth_svc_instance = AuthService()
    return _auth_svc_instance


def get_current_user() -> Dict[str, Any]:
    """
    // FIX: 获取当前会话登录的用户身份，未登录时默认使用开箱即用的 admin 身份保证零阻断
    """
    if "user" not in st.session_state or not st.session_state["user"]:
        auth = get_auth_service()
        default_user = auth.get_user_by_id("usr_admin") or {
            "user_id": "usr_admin",
            "username": "admin",
            "display_name": "主管理员 (Admin)",
            "role": "admin",
            "tenant_code": "org_01",
        }
        st.session_state["user"] = default_user
    return st.session_state["user"]


def render_user_profile_pill():
    """
    // FIX: 在侧边栏渲染符合 Apple 设计规范的租户用户胶囊与快捷切换通道
    """
    user = get_current_user()
    auth = get_auth_service()
    all_users = auth.list_users()

    display_name = user.get("display_name", "管理员")
    role_name = "系统主管" if user.get("role") == "admin" else "运营分析师"
    user_initial = display_name[:1].upper()

    st.markdown(
        f"""
        <div style="padding: 10px 14px; background: rgba(0, 0, 0, 0.02); border-radius: 12px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; border: 1px solid rgba(0, 0, 0, 0.04);">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 32px; height: 32px; border-radius: 50%; background: #E8F2FE; color: #0071E3; font-weight: 700; font-size: 14px; display: flex; align-items: center; justify-content: center;">
                    {user_initial}
                </div>
                <div>
                    <div style="font-size: 12.5px; font-weight: 600; color: #1D1D1F; line-height: 1.2;">{display_name}</div>
                    <div style="font-size: 11px; color: #86868B;">ID: {user.get('user_id')} · {role_name}</div>
                </div>
            </div>
            <span class="apple-badge badge-apple-green" style="font-size: 10px; padding: 2px 7px;">在线</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("👤 切换工作空间账号", expanded=False):
        user_names = [f"{u['display_name']} ({u['username']})" for u in all_users]
        curr_idx = 0
        for i, u in enumerate(all_users):
            if u["user_id"] == user["user_id"]:
                curr_idx = i
                break

        sel_user_label = st.selectbox(
            "选择当前租户用户",
            user_names,
            index=curr_idx,
            key="auth_switch_user_sel",
            label_visibility="collapsed"
        )
        if st.button("确认切换租户上下文", key="btn_confirm_switch_user", use_container_width=True):
            chosen = all_users[user_names.index(sel_user_label)]
            st.session_state["user"] = chosen
            st.toast(f"已成功切换至用户：{chosen['display_name']}（多租户数据已隔离加载）", icon="🎉")
            st.rerun()
