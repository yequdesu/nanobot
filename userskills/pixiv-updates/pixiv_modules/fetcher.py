"""
数据获取模块
"""

from pixivpy3 import AppPixivAPI
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from .auth import PixivAuth


@dataclass
class PixivImage:
    """图片信息"""
    id: str
    title: str
    author_name: str
    author_id: str
    image_urls: List[str]
    tags: List[str]
    bookmark_count: int
    view_count: int
    created_date: str
    page_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "author_name": self.author_name,
            "author_id": self.author_id,
            "image_urls": self.image_urls,
            "tags": self.tags,
            "bookmark_count": self.bookmark_count,
            "view_count": self.view_count,
            "created_date": self.created_date,
            "page_count": self.page_count
        }


@dataclass
class FetchResult:
    """获取结果"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class PixivFetcher:
    """数据获取器"""
    
    def __init__(self, auth: PixivAuth):
        """初始化获取器，参数: auth (认证实例)"""
        self.auth = auth
        self.api = auth.api
    
    def get_user_following(self, user_id: Optional[str] = None, 
                          restrict: str = "public") -> FetchResult:
        """获取用户关注列表，参数: user_id (用户ID，默认当前用户), restrict (权限，public 或 private)，返回: FetchResult (获取结果)"""
        target_user_id = user_id or self.auth.user_id
        
        try:
            result = self.api.user_following(target_user_id, restrict=restrict)
            
            if hasattr(result, 'error') and result.error:
                return FetchResult(
                    success=False,
                    error=f"获取关注列表失败: {result.error}"
                )
            
            following = []
            if hasattr(result, 'user_previews'):
                for preview in result.user_previews:
                    user = preview.user
                    following.append({
                        "id": str(user.id),
                        "name": user.name,
                        "account": user.account
                    })
            
            return FetchResult(
                success=True,
                data=following
            )
            
        except Exception as e:
            return FetchResult(
                success=False,
                error=f"获取关注列表失败: {str(e)}"
            )
    
    def get_all_following(self, restrict: str = "public") -> List[Dict[str, Any]]:
        """获取所有关注，参数: restrict (权限，public 或 private)，返回: List[Dict[str, Any]] (关注列表)"""
        all_following = []
        max_retries = 3
        retry_count = 0
        next_url = None
        page = 1
        
        print(f"获取 {restrict} 关注列表...")
        
        while True:
            try:
                print(f"第 {page} 页")
                
                if next_url:
                    # 使用next_url获取下一页
                    result = self.api.user_following(**self.api.parse_qs(next_url))
                else:
                    # 获取第一页
                    result = self.api.user_following(self.auth.user_id, restrict=restrict)
                
                if hasattr(result, 'error') and result.error:
                    error_msg = str(result.error)
                    if "Rate Limit" in error_msg:
                        import time
                        print("遇到速率限制，暂停 5 秒...")
                        time.sleep(5)
                        retry_count += 1
                        if retry_count < max_retries:
                            continue
                        else:
                            print("重试次数达到上限")
                            break
                    else:
                        break
                
                if not hasattr(result, 'user_previews'):
                    break
                
                previews = result.user_previews
                if not previews:
                    break
                
                for preview in previews:
                    user = preview.user
                    all_following.append({
                        "id": str(user.id),
                        "name": user.name,
                        "account": user.account
                    })
                
                # 检查是否有下一页
                if hasattr(result, 'next_url') and result.next_url:
                    next_url = result.next_url
                    page += 1
                    retry_count = 0
                    
                    import time
                    time.sleep(1)
                else:
                    break
                
            except Exception as e:
                import time
                print(f"错误: {str(e)}，暂停 3 秒...")
                time.sleep(3)
                retry_count += 1
                if retry_count >= max_retries:
                    break
                continue
        
        print(f"获取完成，共 {len(all_following)} 个 {restrict} 关注")
        return all_following
    
    def get_user_works(self, user_id: str, work_type: str = "illust", max_pages: int = 10) -> List[PixivImage]:
        """获取用户作品，参数: user_id (用户ID), work_type (作品类型，illust 或 manga), max_pages (最大页数)，返回: List[PixivImage] (作品列表)"""
        works = []
        next_url = None
        page_count = 0
        
        while page_count < max_pages:
            try:
                if next_url:
                    # 使用next_url获取下一页
                    result = self.api.user_illusts(**self.api.parse_qs(next_url))
                else:
                    # 获取第一页
                    result = self.api.user_illusts(user_id, type=work_type)
                
                if hasattr(result, 'error') and result.error:
                    break
                
                if not hasattr(result, 'illusts'):
                    break
                
                illusts = result.illusts
                if not illusts:
                    break
                
                for illust in illusts:
                    # 获取图片URL
                    image_urls = []
                    if hasattr(illust, 'image_urls'):
                        urls = illust.image_urls
                        if hasattr(urls, 'large'):
                            image_urls.append(urls.large)
                    
                    # 获取标签
                    tags = []
                    if hasattr(illust, 'tags'):
                        for tag in illust.tags:
                            if hasattr(tag, 'name'):
                                tags.append(tag.name)
                    
                    image = PixivImage(
                        id=str(illust.id),
                        title=illust.title,
                        author_name=illust.user.name,
                        author_id=str(illust.user.id),
                        image_urls=image_urls,
                        tags=tags,
                        bookmark_count=illust.total_bookmarks or 0,
                        view_count=illust.total_view or 0,
                        created_date=illust.create_date,
                        page_count=illust.page_count or 1
                    )
                    works.append(image)
                
                # 检查是否有下一页
                if hasattr(result, 'next_url') and result.next_url:
                    next_url = result.next_url
                    page_count += 1
                    # 添加延迟，避免速率限制
                    import time
                    time.sleep(0.5)
                else:
                    break
                    
            except Exception as e:
                print(f"获取作品错误: {str(e)}")
                break
        
        return works
    
    def get_user_bookmarks(self, restrict: str = "public", page: int = 1) -> List[PixivImage]:
        """获取用户收藏列表，参数: restrict (权限，public 或 private), page (页码)，返回: List[PixivImage] (收藏作品列表)"""
        bookmarks = []
        
        try:
            result = self.api.user_bookmarks_illust(self.auth.user_id, restrict=restrict)
            
            if hasattr(result, 'error') and result.error:
                return bookmarks
            
            if not hasattr(result, 'illusts'):
                return bookmarks
            
            illusts = result.illusts
            if not illusts:
                return bookmarks
            
            for illust in illusts:
                # 获取图片URL
                image_urls = []
                if hasattr(illust, 'image_urls'):
                    urls = illust.image_urls
                    if hasattr(urls, 'large'):
                        image_urls.append(urls.large)
                
                # 获取标签
                tags = []
                if hasattr(illust, 'tags'):
                    for tag in illust.tags:
                        if hasattr(tag, 'name'):
                            tags.append(tag.name)
                
                image = PixivImage(
                    id=str(illust.id),
                    title=illust.title,
                    author_name=illust.user.name,
                    author_id=str(illust.user.id),
                    image_urls=image_urls,
                    tags=tags,
                    bookmark_count=illust.total_bookmarks or 0,
                    view_count=illust.total_view or 0,
                    created_date=illust.create_date,
                    page_count=illust.page_count or 1
                )
                bookmarks.append(image)
            
        except Exception:
            pass
        
        return bookmarks
    
    def get_user_detail(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户详情，参数: user_id (用户ID)，返回: Optional[Dict[str, Any]] (用户详情)"""
        try:
            result = self.api.user_detail(user_id)
            
            if hasattr(result, 'error') and result.error:
                return None
            
            if hasattr(result, 'user'):
                user = result.user
                return {
                    "id": str(user.id),
                    "name": user.name,
                    "account": user.account,
                    "profile_image_urls": user.profile_image_urls,
                    "is_premium": user.is_premium,
                    "x_restrict": user.x_restrict
                }
            
        except Exception:
            pass
        
        return None
    
    def get_illust_detail(self, illust_id: str) -> Optional[Dict[str, Any]]:
        """获取作品详情，参数: illust_id (作品ID)，返回: Optional[Dict[str, Any]] (作品详情)"""
        try:
            result = self.api.illust_detail(illust_id)
            
            if hasattr(result, 'error') and result.error:
                return None
            
            if hasattr(result, 'illust'):
                illust = result.illust
                return {
                    "id": str(illust.id),
                    "title": illust.title,
                    "author_name": illust.user.name,
                    "author_id": str(illust.user.id),
                    "image_urls": illust.image_urls,
                    "tags": [tag.name for tag in illust.tags] if hasattr(illust, 'tags') else [],
                    "bookmark_count": illust.total_bookmarks or 0,
                    "view_count": illust.total_view or 0,
                    "created_date": illust.create_date,
                    "page_count": illust.page_count or 1,
                    "type": illust.type
                }
            
        except Exception:
            pass
        
        return None
