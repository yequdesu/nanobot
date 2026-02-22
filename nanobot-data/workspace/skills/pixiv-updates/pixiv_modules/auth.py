"""
认证管理模块
基于 pixivpy 实现认证功能
"""

from pixivpy3 import AppPixivAPI
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class AuthResult:
    """认证结果"""
    success: bool
    access_token: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    error_message: Optional[str] = None


class PixivAuth:
    """认证管理器"""
    
    def __init__(self, refresh_token: Optional[str] = None):
        """初始化认证管理器，参数: refresh_token (刷新令牌)"""
        self.refresh_token = refresh_token
        # 初始化API，添加网络配置
        self.api = AppPixivAPI()
        self._access_token: Optional[str] = None
        self._user_id: Optional[str] = None
        self._user_name: Optional[str] = None
    
    @property
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return self._access_token is not None
    
    @property
    def access_token(self) -> Optional[str]:
        """获取访问令牌"""
        return self._access_token
    
    @property
    def user_id(self) -> Optional[str]:
        """获取用户ID"""
        return self._user_id
    
    @property
    def user_name(self) -> Optional[str]:
        """获取用户名"""
        return self._user_name
    
    def authenticate(self) -> AuthResult:
        """认证方法，返回: AuthResult (认证结果)"""
        if not self.refresh_token:
            return AuthResult(
                success=False,
                error_message="未提供刷新令牌"
            )
        
        try:
            # 使用 pixivpy 认证
            result = self.api.auth(refresh_token=self.refresh_token)
            
            if hasattr(result, 'error') and result.error:
                return AuthResult(
                    success=False,
                    error_message=f"认证失败: {result.error}"
                )
            
            # 获取认证信息
            if hasattr(result, 'response'):
                response = result.response
                self._access_token = response.access_token
                self._user_id = str(response.user.id)
                self._user_name = response.user.name
            elif 'access_token' in result:
                self._access_token = result['access_token']
                self._user_id = str(result['user']['id'])
                self._user_name = result['user']['name']
            else:
                return AuthResult(
                    success=False,
                    error_message="认证信息不完整"
                )
            
            return AuthResult(
                success=True,
                access_token=self._access_token,
                user_id=self._user_id,
                user_name=self._user_name
            )
            
        except Exception as e:
            return AuthResult(
                success=False,
                error_message=f"认证失败: {str(e)}"
            )
    
    def login(self) -> AuthResult:
        """登录方法，返回: AuthResult (登录结果)"""
        return self.authenticate()
    
    def get_auth_headers(self) -> Dict[str, str]:
        """获取认证头，返回: Dict[str, str] (认证头)"""
        if not self._access_token:
            raise RuntimeError("未认证")
        return self.api.headers
