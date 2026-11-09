"""
CrossBorder BI · 统一 SKU 产品中心与多平台映射服务 (Master Catalog & ID Mapping Service)
职责：
1. 维护企业唯一统一商品主键 (Master SKU) 及其 SPU、类目、生命周期属性；
2. 维护各电商平台商品 ID (Walmart Item ID / Amazon ASIN / Wayfair SKU) 与 Master SKU 的 1:N 映射关系；
3. 为全系统各报表解析链路提供瞬时 SKU 归一化解析服务。
"""

import time
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from .storage_engine import get_storage_engine


class MasterCatalogService:
    """中央商品目录与跨平台映射服务"""

    def __init__(self):
        self.storage = get_storage_engine()
        self._memory_cache_mapping: Dict[str, str] = {}
        self._load_cache()

    def _load_cache(self):
        """将已有映射预热至内存字典加速实时解析"""
        try:
            df = self.storage.query_df("SELECT platform_item_id, master_sku FROM dim_platform_item_mapping WHERE mapping_status='已生效'")
            if not df.empty:
                for _, r in df.iterrows():
                    self._memory_cache_mapping[str(r["platform_item_id"]).strip()] = str(r["master_sku"]).strip()
        except Exception:
            pass

    def register_product(
        self,
        master_sku: str,
        product_name: str = "",
        spu: str = "",
        category_l1: str = "家具/家居",
        category_l2: str = "床架/卧室",
        brand: str = "自营品牌",
        lifecycle_stage: str = "成熟期",
    ) -> bool:
        """注册或更新主商品档案"""
        sku_clean = str(master_sku).strip()
        if not sku_clean:
            return False
        spu_val = spu or (sku_clean.split("-")[0] if "-" in sku_clean else sku_clean)
        p_name = product_name or f"商品-{sku_clean}"

        df = pd.DataFrame([{
            "master_sku": sku_clean,
            "spu": spu_val,
            "product_name": p_name,
            "category_l1": category_l1,
            "category_l2": category_l2,
            "brand": brand,
            "lifecycle_stage": lifecycle_stage,
            "is_active": 1,
        }])
        self.storage.upsert_dataframe("dim_master_product", df, pks=["master_sku"])
        return True

    def bind_platform_item(
        self,
        platform_item_id: str,
        master_sku: str,
        platform: str = "walmart",
        store_id: str = "default_store",
        platform_seller_sku: Optional[str] = None,
    ) -> bool:
        """绑定平台数字 ID / ASIN 至 Master SKU"""
        item_id_clean = str(platform_item_id).strip().split(".")[0]
        sku_clean = str(master_sku).strip()
        if not item_id_clean or not sku_clean:
            return False

        # 确保主商品已登记
        self.register_product(sku_clean)

        mapping_id = f"{platform}_{store_id}_{item_id_clean}"
        df = pd.DataFrame([{
            "mapping_id": mapping_id,
            "master_sku": sku_clean,
            "platform": platform.lower(),
            "store_id": store_id,
            "platform_item_id": item_id_clean,
            "platform_seller_sku": platform_seller_sku or sku_clean,
            "mapping_status": "已生效",
        }])
        self.storage.upsert_dataframe("dim_platform_item_mapping", df, pks=["mapping_id"])
        self._memory_cache_mapping[item_id_clean] = sku_clean
        return True

    def resolve_master_sku(self, platform_item_id: Any, fallback: Optional[str] = None) -> str:
        """
        核心解析方法：输入平台数字 ID (如 Walmart 10558959663)，秒级返回其唯一 Master SKU
        """
        if platform_item_id is None:
            return fallback or "未知商品"
        id_str = str(platform_item_id).strip().split(".")[0]
        return self._memory_cache_mapping.get(id_str, fallback or id_str)

    def bulk_import_mappings(self, mapping_dict: Dict[str, str], platform: str = "walmart", store_id: str = "default_store") -> int:
        """批量导入映射字典"""
        count = 0
        records = []
        for p_id, m_sku in mapping_dict.items():
            id_clean = str(p_id).strip().split(".")[0]
            sku_clean = str(m_sku).strip()
            if id_clean and sku_clean:
                mapping_id = f"{platform}_{store_id}_{id_clean}"
                records.append({
                    "mapping_id": mapping_id,
                    "master_sku": sku_clean,
                    "platform": platform.lower(),
                    "store_id": store_id,
                    "platform_item_id": id_clean,
                    "platform_seller_sku": sku_clean,
                    "mapping_status": "已生效",
                })
                self._memory_cache_mapping[id_clean] = sku_clean
                count += 1

        if records:
            df = pd.DataFrame(records)
            self.storage.upsert_dataframe("dim_platform_item_mapping", df, pks=["mapping_id"])
            # 同步更新主商品表
            p_records = [{"master_sku": r["master_sku"], "spu": r["master_sku"].split("-")[0], "product_name": r["master_sku"], "category_l1": "跨境品类", "category_l2": "通用", "brand": "自营", "lifecycle_stage": "在售", "is_active": 1} for r in records]
            self.storage.upsert_dataframe("dim_master_product", pd.DataFrame(p_records).drop_duplicates(subset=["master_sku"]), pks=["master_sku"])

        return count

    def get_full_catalog_df(self) -> pd.DataFrame:
        """获取全景商品档案大表（打通主 SKU、各平台 ID、类目与映射状态）"""
        sql = """
            SELECT 
                p.master_sku AS "Master SKU",
                p.spu AS "SPU 款号",
                p.product_name AS "商品名称",
                p.category_l1 AS "一级类目",
                p.category_l2 AS "二级类目",
                COALESCE(wm.platform_item_id, '-') AS "Walmart Item ID",
                COALESCE(amz.platform_item_id, '-') AS "Amazon ASIN",
                COALESCE(way.platform_item_id, '-') AS "Wayfair SKU",
                p.lifecycle_stage AS "生命周期",
                CASE WHEN wm.platform_item_id IS NOT NULL THEN '已生效' ELSE '待映射' END AS "映射状态"
            FROM dim_master_product p
            LEFT JOIN dim_platform_item_mapping wm 
                ON p.master_sku = wm.master_sku AND wm.platform = 'walmart'
            LEFT JOIN dim_platform_item_mapping amz 
                ON p.master_sku = amz.master_sku AND amz.platform = 'amazon'
            LEFT JOIN dim_platform_item_mapping way 
                ON p.master_sku = way.master_sku AND way.platform = 'wayfair'
            ORDER BY p.master_sku ASC
        """
        try:
            df = self.storage.query_df(sql)
            if not df.empty:
                return df
        except Exception:
            pass
        return pd.DataFrame()


# 全局单例
_catalog_instance: Optional[MasterCatalogService] = None

def get_catalog_service() -> MasterCatalogService:
    global _catalog_instance
    if _catalog_instance is None:
        _catalog_instance = MasterCatalogService()
    return _catalog_instance
