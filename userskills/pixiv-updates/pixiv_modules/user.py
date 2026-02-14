"""
用户管理模块
支持多用户管理和refresh_token的加密存储
"""

import json
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Optional, Dict, Any
from pathlib import Path


class UserManager:
    """用户管理器，负责用户的登入登出和数据存储"""
    
    def __init__(self, assets_dir: str):
        """初始化用户管理器，参数: assets_dir (资产目录路径)"""
        self.assets_dir = Path(assets_dir)
        self.assets_dir.mkdir(exist_ok=True)
        self.users_file = self.assets_dir / "users.json"
        self.key_file = self.assets_dir / "encryption.key"
        self._encryption_key = self._load_or_generate_key()
        self._current_user: Optional[str] = None
    
    def _load_or_generate_key(self) -> bytes:
        """加载或生成加密密钥，返回: bytes (加密密钥)"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            return key
    
    def _encrypt(self, data: str) -> str:
        """加密数据，参数: data (原始数据)，返回: str (加密后的数据)"""
        f = Fernet(self._encryption_key)
        encrypted = f.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()
    
    def _decrypt(self, encrypted_data: str) -> str:
        """解密数据，参数: encrypted_data (加密数据)，返回: str (解密后的数据)"""
        f = Fernet(self._encryption_key)
        encrypted = base64.b64decode(encrypted_data.encode())
        decrypted = f.decrypt(encrypted)
        return decrypted.decode()
    
    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        """加载用户数据，返回: Dict[str, Dict[str, Any]] (用户数据)"""
        if not self.users_file.exists():
            return {}
        
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_users(self, users: Dict[str, Dict[str, Any]]):
        """保存用户数据，参数: users (用户数据)"""
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    
    def login(self, user_id: str, refresh_token: str) -> bool:
        """用户登入，参数: user_id (用户ID), refresh_token (刷新令牌)，返回: bool (是否成功)"""
        try:
            users = self._load_users()
            
            # 加密存储refresh_token
            encrypted_token = self._encrypt(refresh_token)
            
            # 更新或创建用户数据
            users[user_id] = {
                "refresh_token": encrypted_token,
                "last_login": "now"
            }
            
            self._save_users(users)
            self._current_user = user_id
            return True
            
        except Exception:
            return False
    
    def logout(self, user_id: str) -> bool:
        """用户登出，参数: user_id (用户ID)，返回: bool (是否成功)"""
        try:
            users = self._load_users()
            
            if user_id in users:
                # 删除用户的refresh_token
                del users[user_id]
                self._save_users(users)
                
                if self._current_user == user_id:
                    self._current_user = None
                
                return True
            
            return False
            
        except Exception:
            return False
    
    def get_refresh_token(self, user_id: str) -> Optional[str]:
        """获取用户的refresh_token，参数: user_id (用户ID)，返回: Optional[str] (刷新令牌)"""
        try:
            users = self._load_users()
            
            if user_id in users and "refresh_token" in users[user_id]:
                encrypted_token = users[user_id]["refresh_token"]
                return self._decrypt(encrypted_token)
            
            return None
            
        except Exception:
            return None
    
    def get_current_user(self) -> Optional[str]:
        """获取当前用户，返回: Optional[str] (当前用户ID)"""
        return self._current_user
    
    def set_current_user(self, user_id: Optional[str]):
        """设置当前用户，参数: user_id (用户ID)"""
        self._current_user = user_id
    
    def list_users(self) -> list:
        """列出所有用户，返回: list (用户ID列表)"""
        users = self._load_users()
        return list(users.keys())
