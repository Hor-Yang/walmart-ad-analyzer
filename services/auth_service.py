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
    // FIX: 【重构目标 1】极简化单层账户读取，统一存取 st.session_state['current_user'] 并做好兼容兜底
    """
    curr = st.session_state.get("current_user") or st.session_state.get("user")
    if not curr or not isinstance(curr, dict):
        curr = {
            "user_id": "usr_default",
            "account": "seller@crossborder.bi",
            "email": "seller@crossborder.bi",
            "display_name": "seller@crossborder.bi",
            "role": "seller",
            "tenant_code": "default",
        }
        st.session_state["current_user"] = curr
        st.session_state["user"] = curr
    return curr


def login_user(account: str) -> Dict[str, Any]:
    """
    // FIX: 【重构目标 1】扁平化登录凭证：仅需邮箱或手机号即可快速完成单层账户校验
    """
    acc = str(account).strip()
    safe_id = "usr_" + hashlib.md5(acc.encode("utf-8")).hexdigest()[:8]
    user_data = {
        "user_id": safe_id,
        "account": acc,
        "email": acc,
        "display_name": acc,
        "role": "seller",
        "tenant_code": "default",
    }
    st.session_state["current_user"] = user_data
    st.session_state["user"] = user_data
    return user_data


def logout_user():
    """
    // FIX: 【重构目标 1】退出当前登录账号
    """
    st.session_state["current_user"] = None
    st.session_state["user"] = None


def render_user_profile_pill():
    """
    // FIX: 【重构目标 1】侧边栏极简展示：
    // 1. 彻底移除“主管理员”、“角色ID”、“切换租户上下文”等复杂的 RBAC 组件与下拉选择框
    // 2. 仅展示清爽的用户首字母 Avatar、当前登录的邮箱/手机号与退出登录按钮
    """
    curr = st.session_state.get("current_user") or st.session_state.get("user")

    if curr and isinstance(curr, dict) and curr.get("account"):
        account_str = str(curr.get("account") or curr.get("email") or "seller@crossborder.bi").strip()
        avatar_char = account_str[:1].upper() if account_str else "S"

        st.markdown(
            f"""
            <div style="padding: 10px 14px; background: rgba(0, 0, 0, 0.02); border-radius: 12px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; border: 1px solid rgba(0, 0, 0, 0.04);">
                <div style="display: flex; align-items: center; gap: 10px; overflow: hidden;">
                    <div style="width: 32px; height: 32px; min-width: 32px; border-radius: 50%; background: #E8F2FE; color: #0071E3; font-weight: 700; font-size: 14px; display: flex; align-items: center; justify-content: center;">
                        {avatar_char}
                    </div>
                    <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        <div style="font-size: 12.5px; font-weight: 600; color: #1D1D1F; line-height: 1.2; overflow: hidden; text-overflow: ellipsis;">{account_str}</div>
                        <div style="font-size: 11px; color: #059669; font-weight: 500;">在线</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("退出登录", key="btn_logout_user", use_container_width=True):
            logout_user()
            st.rerun()
    else:
        # 未登录时展示极简邮箱/手机号输入框
        st.markdown(
            """
            <div style="padding: 8px 4px 6px 4px; font-size: 12px; font-weight: 600; color: #1D1D1F;">
                运营工作台登录
            </div>
            """,
            unsafe_allow_html=True,
        )
        acc_input = st.text_input(
            "账号输入",
            placeholder="输入邮箱或手机号",
            key="input_flat_account",
            label_visibility="collapsed",
        )
        if st.button("一键登录", type="primary", use_container_width=True, key="btn_flat_login"):
            if acc_input.strip():
                login_user(acc_input.strip())
                st.rerun()
            else:
                st.caption("请输入有效的手机号或邮箱")
