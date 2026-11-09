"""
CrossBorder BI · 嵌入式分析存储引擎 (Embedded SQLite Storage Engine)
基于 Python 标准库 sqlite3，零外部依赖，提供事务安全、高性能 SQL 聚合与持久化能力。
作为 CDM (Canonical Data Model) 的底层存储载体。
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional
import pandas as pd

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".session_cache",
    "crossborder_bi.db"
)


class StorageEngine:
    """CDM 标准模型数据库存储管理类"""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._ensure_dir()
        self._init_schema()

    def _ensure_dir(self):
        if self.db_path == ":memory:":
            return
        d = os.path.dirname(self.db_path)
        if not os.path.exists(d):
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                pass

    def get_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """初始化 CDM 标准事实表与维度表架构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. 主商品维度表 (Dim_Master_Product)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dim_master_product (
                    master_sku TEXT PRIMARY KEY,
                    spu TEXT,
                    product_name TEXT,
                    category_l1 TEXT,
                    category_l2 TEXT,
                    brand TEXT,
                    lifecycle_stage TEXT DEFAULT '成熟期',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. 多平台商品 ID 映射表 (Dim_Platform_Item_Mapping)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dim_platform_item_mapping (
                    mapping_id TEXT PRIMARY KEY,
                    master_sku TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    store_id TEXT NOT NULL,
                    platform_item_id TEXT NOT NULL,
                    platform_seller_sku TEXT,
                    mapping_status TEXT DEFAULT '已生效',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(platform, store_id, platform_item_id)
                );
            """)

            # 3. SKU 供应链成本维度表 (Dim_SKU_Cost)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dim_sku_cost (
                    master_sku TEXT PRIMARY KEY,
                    cogs REAL DEFAULT 0.0,
                    first_leg REAL DEFAULT 0.0,
                    last_leg REAL DEFAULT 0.0,
                    commission_rate REAL DEFAULT 0.15,
                    other_cost REAL DEFAULT 0.0,
                    unit_product_cost REAL DEFAULT 0.0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. 统一广告表现事实表 (Fact_Ad_Performance)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fact_ad_performance (
                    id TEXT PRIMARY KEY,
                    event_date TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    store_id TEXT NOT NULL,
                    master_sku TEXT NOT NULL,
                    platform_item_id TEXT,
                    campaign_name TEXT,
                    entity_type TEXT DEFAULT 'ad_item',
                    spend REAL DEFAULT 0.0,
                    attributed_sales REAL DEFAULT 0.0,
                    orders INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    impressions INTEGER DEFAULT 0,
                    source_file TEXT,
                    granularity TEXT DEFAULT 'daily',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 5. 店铺全渠道销售事实表 (Fact_Sales_Order)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fact_sales_order (
                    id TEXT PRIMARY KEY,
                    order_date TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    store_id TEXT NOT NULL,
                    master_sku TEXT,
                    gross_sales REAL DEFAULT 0.0,
                    orders INTEGER DEFAULT 0,
                    units_sold INTEGER DEFAULT 0,
                    source_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 6. 库存快照事实表 (Fact_Inventory_Snapshot)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fact_inventory_snapshot (
                    id TEXT PRIMARY KEY,
                    snapshot_date TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    store_id TEXT NOT NULL,
                    master_sku TEXT NOT NULL,
                    available_stock INTEGER DEFAULT 0,
                    in_transit_stock INTEGER DEFAULT 0,
                    source_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 索引建立
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ad_sku_date ON fact_ad_performance(master_sku, event_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ad_platform_store ON fact_ad_performance(platform, store_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_map_item ON dim_platform_item_mapping(platform_item_id);")
            conn.commit()

    def upsert_dataframe(self, table_name: str, df: pd.DataFrame, pks: List[str]) -> int:
        """安全高效将 DataFrame 批量 Upsert 入库"""
        if df.empty:
            return 0
        cols = list(df.columns)
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        
        # ON CONFLICT UPDATE
        update_set = ", ".join([f"{c}=excluded.{c}" for c in cols if c not in pks])
        pk_conflict = ", ".join(pks)
        
        sql = f"""
            INSERT INTO {table_name} ({col_names})
            VALUES ({placeholders})
            ON CONFLICT({pk_conflict}) DO UPDATE SET
            {update_set}
        """

        records = [tuple(x) for x in df.to_numpy()]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, records)
            conn.commit()
            return cursor.rowcount

    def query_df(self, query: str, params: Optional[List[Any]] = None) -> pd.DataFrame:
        """执行 SQL 并返回 Pandas DataFrame"""
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params or [])

    def execute_non_query(self, sql: str, params: Optional[List[Any]] = None) -> int:
        """执行更新或删除语句"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params or [])
            conn.commit()
            return cursor.rowcount


# 全局单例引擎
_storage_instance: Optional[StorageEngine] = None

def get_storage_engine() -> StorageEngine:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageEngine()
    return _storage_instance
