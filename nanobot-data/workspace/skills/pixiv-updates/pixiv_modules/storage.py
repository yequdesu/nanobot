"""
数据存储模块
负责持久化数据的管理，包括持久化、快速查询、更新和删除
"""

import json
import os
from typing import Optional, Dict, Any, List
from pathlib import Path


class StorageManager:
    """存储管理器，负责数据的持久化、查询、更新和删除"""
    
    def __init__(self, assets_dir: str):
        """初始化存储管理器，参数: assets_dir (资产目录路径)"""
        self.assets_dir = Path(assets_dir)
        self.assets_dir.mkdir(exist_ok=True)
        self.data_file = self.assets_dir / "storage.json"
        self._data: Dict[str, Any] = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """加载数据，返回: Dict[str, Any] (存储的数据)"""
        if not self.data_file.exists():
            return {
                "following_lists": {},  # 用户关注列表
                "user_data": {},       # 用户相关数据
                "cache": {}            # 缓存数据
            }
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 确保数据结构完整
                if "following_lists" not in data:
                    data["following_lists"] = {}
                if "user_data" not in data:
                    data["user_data"] = {}
                if "cache" not in data:
                    data["cache"] = {}
                return data
        except Exception:
            return {
                "following_lists": {},
                "user_data": {},
                "cache": {}
            }
    
    def _save_data(self):
        """保存数据"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    # 用户关注列表管理
    def save_following_list(self, user_id: str, following_list: List[Dict[str, Any]]):
        """保存用户关注列表，参数: user_id (用户ID), following_list (关注列表)"""
        self._data["following_lists"][user_id] = following_list
        self._save_data()
    
    def get_following_list(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户关注列表，参数: user_id (用户ID)，返回: List[Dict[str, Any]] (关注列表)"""
        return self._data["following_lists"].get(user_id, [])
    
    def update_following_list(self, user_id: str, following_list: List[Dict[str, Any]]):
        """更新用户关注列表，参数: user_id (用户ID), following_list (新的关注列表)"""
        self.save_following_list(user_id, following_list)
    
    def delete_following_list(self, user_id: str):
        """删除用户关注列表，参数: user_id (用户ID)"""
        if user_id in self._data["following_lists"]:
            del self._data["following_lists"][user_id]
            self._save_data()
    
    # 用户数据管理
    def save_user_data(self, user_id: str, key: str, value: Any):
        """保存用户数据，参数: user_id (用户ID), key (数据键), value (数据值)"""
        if user_id not in self._data["user_data"]:
            self._data["user_data"][user_id] = {}
        self._data["user_data"][user_id][key] = value
        self._save_data()
    
    def get_user_data(self, user_id: str, key: str) -> Optional[Any]:
        """获取用户数据，参数: user_id (用户ID), key (数据键)，返回: Optional[Any] (数据值)"""
        if user_id in self._data["user_data"]:
            return self._data["user_data"][user_id].get(key)
        return None
    
    def get_all_user_data(self, user_id: str) -> Dict[str, Any]:
        """获取用户所有数据，参数: user_id (用户ID)，返回: Dict[str, Any] (用户所有数据)"""
        return self._data["user_data"].get(user_id, {})
    
    def update_user_data(self, user_id: str, key: str, value: Any):
        """更新用户数据，参数: user_id (用户ID), key (数据键), value (数据值)"""
        self.save_user_data(user_id, key, value)
    
    def delete_user_data(self, user_id: str, key: str):
        """删除用户数据，参数: user_id (用户ID), key (数据键)"""
        if user_id in self._data["user_data"] and key in self._data["user_data"][user_id]:
            del self._data["user_data"][user_id][key]
            self._save_data()
    
    def delete_all_user_data(self, user_id: str):
        """删除用户所有数据，参数: user_id (用户ID)"""
        if user_id in self._data["user_data"]:
            del self._data["user_data"][user_id]
            self._save_data()
    
    # 缓存管理
    def save_cache(self, key: str, value: Any, expiration: Optional[int] = None):
        """保存缓存，参数: key (缓存键), value (缓存值), expiration (过期时间，秒)"""
        cache_data = {
            "value": value
        }
        if expiration:
            import time
            cache_data["expires_at"] = time.time() + expiration
        self._data["cache"][key] = cache_data
        self._save_data()
    
    def get_cache(self, key: str) -> Optional[Any]:
        """获取缓存，参数: key (缓存键)，返回: Optional[Any] (缓存值)"""
        if key not in self._data["cache"]:
            return None
        
        cache_data = self._data["cache"][key]
        
        # 检查是否过期
        if "expires_at" in cache_data:
            import time
            if time.time() > cache_data["expires_at"]:
                del self._data["cache"][key]
                self._save_data()
                return None
        
        return cache_data.get("value")
    
    def delete_cache(self, key: str):
        """删除缓存，参数: key (缓存键)"""
        if key in self._data["cache"]:
            del self._data["cache"][key]
            self._save_data()
    
    def clear_expired_cache(self):
        """清理过期缓存"""
        import time
        current_time = time.time()
        expired_keys = []
        
        for key, cache_data in self._data["cache"].items():
            if "expires_at" in cache_data and current_time > cache_data["expires_at"]:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._data["cache"][key]
        
        if expired_keys:
            self._save_data()
    
    # 通用数据操作
    def save_data(self, category: str, key: str, value: Any):
        """保存通用数据，参数: category (数据类别), key (数据键), value (数据值)"""
        if category not in self._data:
            self._data[category] = {}
        self._data[category][key] = value
        self._save_data()
    
    def get_data(self, category: str, key: str) -> Optional[Any]:
        """获取通用数据，参数: category (数据类别), key (数据键)，返回: Optional[Any] (数据值)"""
        if category in self._data:
            return self._data[category].get(key)
        return None
    
    def update_data(self, category: str, key: str, value: Any):
        """更新通用数据，参数: category (数据类别), key (数据键), value (数据值)"""
        self.save_data(category, key, value)
    
    def delete_data(self, category: str, key: str):
        """删除通用数据，参数: category (数据类别), key (数据键)"""
        if category in self._data and key in self._data[category]:
            del self._data[category][key]
            self._save_data()
    
    def list_categories(self) -> List[str]:
        """列出所有数据类别，返回: List[str] (数据类别列表)"""
        return list(self._data.keys())
    
    def list_keys(self, category: str) -> List[str]:
        """列出指定类别的所有键，参数: category (数据类别)，返回: List[str] (键列表)"""
        if category in self._data:
            return list(self._data[category].keys())
        return []
