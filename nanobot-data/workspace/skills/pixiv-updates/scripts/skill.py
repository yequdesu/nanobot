# -*- coding: utf-8 -*-
"""
Pixiv Skill
供agent使用的核心功能
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pixiv_modules import PixivAuth, PixivFetcher
from pixiv_modules.user import UserManager
from pixiv_modules.storage import StorageManager


class PixivSkill:
    """Pixiv Skill类，供agent使用"""
    
    def __init__(self):
        """初始化Skill"""
        # 创建assets目录路径
        assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets'))
        # 初始化用户管理器
        self.user_manager = UserManager(assets_dir)
        # 初始化存储管理器
        self.storage_manager = StorageManager(assets_dir)
        self.auth = None
        self.fetcher = None
        self.initialized = False
    
    def initialize(self):
        """初始化认证，返回: bool (是否成功)"""

        if self.initialized:
            return True
        
        # 获取当前用户
        current_user = self.user_manager.get_current_user()
        if not current_user:
            print("未登录用户，请先调用login方法")
            return False
        
        # 获取用户的refresh_token
        refresh_token = self.user_manager.get_refresh_token(current_user)
        if not refresh_token:
            print("未找到用户的refresh_token")
            return False
        
        try:
            self.auth = PixivAuth(refresh_token=refresh_token)
            result = self.auth.login()
            
            if not result.success:
                print(f"初始化失败: {result.error_message}")
                return False
            
            self.fetcher = PixivFetcher(self.auth)
            self.initialized = True
            print(f"初始化成功，用户: {result.user_name}")
            return True
            
        except Exception as e:
            print(f"初始化异常: {str(e)}")
            return False
    
    def login(self, user_id: str, refresh_token: str) -> bool:
        """用户登录，参数: user_id (用户ID), refresh_token (刷新令牌)，返回: bool (是否成功)"""

        print(f"用户 {user_id} 登录中...")
        success = self.user_manager.login(user_id, refresh_token)
        
        if success:
            print(f"用户 {user_id} 登录成功")
            # 重置初始化状态
            self.initialized = False
            self.auth = None
            self.fetcher = None
        else:
            print(f"用户 {user_id} 登录失败")
        
        return success
    
    def logout(self, user_id: str) -> bool:
        """用户登出，参数: user_id (用户ID)，返回: bool (是否成功)"""

        print(f"用户 {user_id} 登出中...")
        success = self.user_manager.logout(user_id)
        
        if success:
            # 删除用户的关注列表和其他数据
            self.storage_manager.delete_following_list(user_id)
            self.storage_manager.delete_all_user_data(user_id)
            
            print(f"用户 {user_id} 登出成功")
            # 如果登出的是当前用户，重置状态
            if self.user_manager.get_current_user() is None:
                self.initialized = False
                self.auth = None
                self.fetcher = None
        else:
            print(f"用户 {user_id} 登出失败")
        
        return success
    
    def switch_user(self, user_id: str) -> bool:
        """切换用户，参数: user_id (用户ID)，返回: bool (是否成功)"""

        # 检查用户是否存在
        if user_id not in self.user_manager.list_users():
            print(f"用户 {user_id} 不存在")
            return False
        
        print(f"切换到用户 {user_id}...")
        self.user_manager.set_current_user(user_id)
        # 重置初始化状态
        self.initialized = False
        self.auth = None
        self.fetcher = None
        print(f"切换到用户 {user_id} 成功")
        return True
    
    def get_current_user(self) -> str:
        """获取当前用户，返回: str (当前用户ID)"""
        return self.user_manager.get_current_user()
    
    def list_users(self) -> list:
        """列出所有用户，返回: list (用户ID列表)"""
        return self.user_manager.list_users()
    
    def parse_date(self, date_str):
        """解析日期，参数: date_str (日期字符串)，返回: datetime (日期对象)"""
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            return datetime.min
    
    def is_date_in_range(self, date_str, start_date, end_date):
        """检查日期是否在范围内，参数: date_str (日期字符串), start_date (开始日期), end_date (结束日期)，返回: bool (是否在范围内)"""

        try:
            date = self.parse_date(date_str)
            return start_date <= date <= end_date
        except Exception:
            return False
    
    def load_following(self):
        """加载关注列表，返回: List[Dict[str, Any]] (关注列表)"""

        # 获取当前用户
        current_user = self.user_manager.get_current_user()
        if not current_user:
            print("未登录用户，无法加载关注列表")
            return []
        
        # 先尝试从StorageManager中获取
        following = self.storage_manager.get_following_list(current_user)
        if following:
            print(f"从存储加载关注列表: {len(following)} 个画师")
            return following
        
        # 从API获取
        print("从API获取关注列表...")
        following_public = self.fetcher.get_all_following('public')
        following_private = self.fetcher.get_all_following('private')
        following = following_public + following_private
        
        # 去重
        seen_ids = set()
        unique_following = []
        for user in following:
            if user['id'] not in seen_ids:
                seen_ids.add(user['id'])
                unique_following.append(user)
        
        # 保存到StorageManager
        self.storage_manager.save_following_list(current_user, unique_following)
        print(f"获取并保存关注列表: {len(unique_following)} 个画师")
        return unique_following
    
    def get_updates_by_date(self, target_date):
        """获取指定日期的更新，参数: target_date (目标日期, YYYY-MM-DD)，返回: Dict (更新结果)"""

        if not self.initialize():
            return {
                "success": False,
                "message": "初始化失败"
            }
        
        print(f"获取 {target_date} 的更新...")
        
        # 解析目标日期
        try:
            target = datetime.strptime(target_date, '%Y-%m-%d')
        except Exception as e:
            return {
                "success": False,
                "message": f"日期格式错误: {str(e)}"
            }
        
        # 计算日期范围（UTC时区）
        start_date = datetime(target.year, target.month, target.day, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(target.year, target.month, target.day, 23, 59, 59, tzinfo=timezone.utc)
        
        # 加载关注列表
        following = self.load_following()
        if not following:
            return {
                "success": False,
                "message": "未获取到关注列表"
            }
        
        # 收集更新
        updates = []
        all_tags = []
        processed = 0
        
        for user in following:
            processed += 1
            print(f"处理 {processed}/{len(following)}: {user['name']}")
            
            try:
                # 获取作品
                works = self.fetcher.get_user_works(user['id'], max_pages=3)
                
                user_updates = []
                for work in works:
                    # 检查日期
                    if self.is_date_in_range(work.created_date, start_date, end_date):
                        user_updates.append({
                            "id": work.id,
                            "title": work.title,
                            "tags": work.tags,
                            "bookmark_count": work.bookmark_count,
                            "view_count": work.view_count,
                            "created_date": work.created_date
                        })
                        all_tags.extend(work.tags)
                    else:
                        # 作品早于目标日期，停止检查
                        if self.parse_date(work.created_date) < start_date:
                            break
                
                if user_updates:
                    updates.append({
                        "author": user['name'],
                        "author_id": user['id'],
                        "works": user_updates
                    })
                
                # 添加延迟，避免速率限制
                time.sleep(1)
                
            except Exception as e:
                print(f"错误: {str(e)}")
                time.sleep(3)
                continue
        
        # 统计
        total_works = sum(len(u['works']) for u in updates)
        total_tags = len(set(all_tags))
        
        # 保存结果
        output_file = Path('./pixiv_data') / f"{target_date}_updates.json"
        output_file.parent.mkdir(exist_ok=True)
        
        result = {
            "success": True,
            "data": {
                "date": target_date,
                "total_artists": len(updates),
                "total_works": total_works,
                "total_tags": total_tags,
                "updates": updates
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result['data'], f, ensure_ascii=False, indent=2)
        
        print(f"完成，更新画师: {len(updates)}，更新作品: {total_works}")
        return result
    
    def get_today_updates(self):
        """获取今天的更新，优先使用illust_follow API，失败时回退到遍历逻辑，返回: Dict (更新结果)"""
        if not self.initialize():
            return {
                "success": False,
                "message": "初始化失败"
            }
        
        print("优先使用illust_follow API获取今日新作...")
        
        try:
            # 尝试使用illust_follow API
            result = self.fetcher.api.illust_follow(restrict="public", req_auth=True)
            
            if hasattr(result, 'error') and result.error:
                print(f"illust_follow API失败: {result.error}，回退到遍历逻辑")
            elif hasattr(result, 'illusts'):
                illusts = result.illusts
                
                # 转换为字典
                updates = []
                for illust in illusts:
                    updates.append({
                        "id": illust.id,
                        "title": illust.title,
                        "author": illust.user.name,
                        "author_id": illust.user.id,
                        "tags": [tag.name for tag in illust.tags] if hasattr(illust, 'tags') else [],
                        "bookmark_count": illust.total_bookmarks or 0,
                        "view_count": illust.total_view or 0,
                        "created_date": illust.create_date
                    })
                
                result_dict = {
                    "success": True,
                    "data": {
                        "date": datetime.now().strftime('%Y-%m-%d'),
                        "total_artists": len(set([update['author_id'] for update in updates])),
                        "total_works": len(updates),
                        "total_tags": len(set([tag for update in updates for tag in update['tags']])),
                        "updates": updates
                    }
                }
                
                print(f"illust_follow API成功获取到 {len(updates)} 个新作")
                return result_dict
            else:
                print("illust_follow API响应中没有illusts字段，回退到遍历逻辑")
                
        except Exception as e:
            print(f"illust_follow API异常: {str(e)}，回退到遍历逻辑")
        
        # 回退到原有的遍历逻辑
        today = datetime.now().strftime('%Y-%m-%d')
        return self.get_updates_by_date(today)
    
    def get_yesterday_updates(self):
        """获取昨天的更新，返回: Dict (更新结果)"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        return self.get_updates_by_date(yesterday)
    
    def get_bookmarks(self, page=1, restrict='public'):
        """获取收藏列表，参数: page (页码), restrict (权限)，返回: Dict (收藏结果)"""
        if not self.initialize():
            return {
                "success": False,
                "message": "初始化失败"
            }
        
        print(f"获取收藏列表，页码: {page}")
        
        try:
            # 获取收藏
            bookmarks = self.fetcher.get_user_bookmarks(restrict, page)
            
            # 转换为字典
            bookmarks_dict = []
            for bookmark in bookmarks:
                bookmarks_dict.append({
                    "id": bookmark.id,
                    "title": bookmark.title,
                    "author": bookmark.author_name,
                    "author_id": bookmark.author_id,
                    "tags": bookmark.tags,
                    "bookmark_count": bookmark.bookmark_count,
                    "view_count": bookmark.view_count,
                    "created_date": bookmark.created_date
                })
            
            result = {
                "success": True,
                "data": {
                    "page": page,
                    "restrict": restrict,
                    "count": len(bookmarks_dict),
                    "bookmarks": bookmarks_dict
                }
            }
            
            print(f"获取到 {len(bookmarks_dict)} 个收藏作品")
            return result
            
        except Exception as e:
            print(f"错误: {str(e)}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def get_follow_updates(self):
        """获取关注用户的新作，返回: Dict (新作结果)"""

        if not self.initialize():
            return {
                "success": False,
                "message": "初始化失败"
            }
        
        print("获取关注用户的新作...")
        
        try:
            # 使用 illust_follow API
            result = self.fetcher.api.illust_follow(restrict="public", req_auth=True)
            
            if hasattr(result, 'error') and result.error:
                return {
                    "success": False,
                    "message": str(result.error)
                }
            elif hasattr(result, 'illusts'):
                illusts = result.illusts
                
                # 转换为字典
                updates = []
                for illust in illusts:
                    updates.append({
                        "id": illust.id,
                        "title": illust.title,
                        "author": illust.user.name,
                        "author_id": illust.user.id,
                        "tags": [tag.name for tag in illust.tags] if hasattr(illust, 'tags') else [],
                        "bookmark_count": illust.total_bookmarks or 0,
                        "view_count": illust.total_view or 0,
                        "created_date": illust.create_date
                    })
                
                result_dict = {
                    "success": True,
                    "data": {
                        "count": len(updates),
                        "updates": updates
                    }
                }
                
                print(f"获取到 {len(updates)} 个新作")
                return result_dict
            else:
                return {
                    "success": False,
                    "message": "API 响应中没有 illusts 字段"
                }
                
        except Exception as e:
            print(f"错误: {str(e)}")
            return {
                "success": False,
                "message": str(e)
            }


# 全局实例
pixiv_skill = PixivSkill()


def login(user_id, refresh_token):
    """用户登录，参数: user_id (用户ID), refresh_token (刷新令牌)，返回: bool (是否成功)"""
    return pixiv_skill.login(user_id, refresh_token)


def logout(user_id):
    """用户登出，参数: user_id (用户ID)，返回: bool (是否成功)"""
    return pixiv_skill.logout(user_id)


def switch_user(user_id):
    """切换用户，参数: user_id (用户ID)，返回: bool (是否成功)"""
    return pixiv_skill.switch_user(user_id)


def get_current_user():
    """获取当前用户，返回: str (当前用户ID)"""
    return pixiv_skill.get_current_user()


def list_users():
    """列出所有用户，返回: list (用户ID列表)"""
    return pixiv_skill.list_users()


def get_updates_by_date(date):
    """获取指定日期的更新，参数: date (目标日期, YYYY-MM-DD)，返回: Dict (更新结果)"""
    return pixiv_skill.get_updates_by_date(date)


def get_today_updates():
    """获取今天的更新，返回: Dict (更新结果)"""
    return pixiv_skill.get_today_updates()


def get_yesterday_updates():
    """获取昨天的更新，返回: Dict (更新结果)"""
    return pixiv_skill.get_yesterday_updates()


def get_bookmarks(page=1, restrict='public'):
    """获取收藏列表，参数: page (页码), restrict (权限)，返回: Dict (收藏结果)"""
    return pixiv_skill.get_bookmarks(page, restrict)


def get_follow_updates():
    """获取关注用户的新作，返回: Dict (新作结果)"""
    return pixiv_skill.get_follow_updates()


if __name__ == '__main__':
    # 测试
    # 1. 先登录用户
    # 注意：在实际使用时，请替换为你的有效用户ID和refresh_token
    # test_user_id = "your_user_id"
    # test_refresh_token = "YOUR_REFRESH_TOKEN_HERE"
    
    # 示例：从环境变量获取（推荐）
    import os
    test_user_id = os.getenv('PIXIV_TEST_USER_ID', 'test_user')
    test_refresh_token = os.getenv('PIXIV_TEST_REFRESH_TOKEN')
    
    if not test_refresh_token:
        print("错误：未设置PIXIV_TEST_REFRESH_TOKEN环境变量")
        print("请设置环境变量或取消注释上面的硬编码token进行测试")
        exit(1)
    
    print("测试登录...")
    login_success = login(test_user_id, test_refresh_token)
    print(f"登录结果: {login_success}")
    
    if login_success:
        # 2. 获取当前用户
        current_user = get_current_user()
        print(f"当前用户: {current_user}")
        
        # 3. 列出所有用户
        users = list_users()
        print(f"所有用户: {users}")
        
        # 4. 获取今天的更新
        print("\n测试获取今天的更新...")
        result = get_today_updates()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 5. 测试登出
        print("\n测试登出...")
        logout_success = logout(test_user_id)
        print(f"登出结果: {logout_success}")
    else:
        print("登录失败，无法进行后续测试")
