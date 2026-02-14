#!/usr/bin/env python3
"""
修复版的Pixiv更新监控工具
修复了原始pixiv.py中的self.api.api错误
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# 修复导入方式
from pixivpy3 import AppPixivAPI, PixivError
import requests


class PixivAuth:
    """Pixiv认证和API调用类 - 修复版"""
    
    def __init__(self, refresh_token: Optional[str] = None, phpsessid: Optional[str] = None):
        """
        初始化Pixiv认证
        
        Args:
            refresh_token: Pixiv refresh token
            phpsessid: Pixiv PHPSESSID cookie (备用)
        """
        self.api = AppPixivAPI()
        self.refresh_token = refresh_token
        self.phpsessid = phpsessid
        self.authenticated = False
        
    def login(self) -> bool:
        """使用refresh_token或PHPSESSID登录"""
        if self.refresh_token:
            try:
                print(f"[INFO] 使用refresh_token登录...")
                auth_result = self.api.auth(refresh_token=self.refresh_token)
                if auth_result and 'access_token' in auth_result:
                    self.authenticated = True
                    print(f"[INFO] 登录成功! 用户: {auth_result.get('user', {}).get('name', '未知')}")
                    return True
                else:
                    print("[ERROR] 认证返回数据异常")
                    return False
            except PixivError as e:
                print(f"[ERROR] Pixiv认证失败: {e}")
                return False
            except Exception as e:
                print(f"[ERROR] 登录过程异常: {e}")
                return False
        elif self.phpsessid:
            try:
                print(f"[INFO] 使用PHPSESSID登录...")
                self.api.set_auth(self.phpsessid)
                # 测试登录状态
                test_result = self.api.user_detail(123)  # 使用测试ID
                if test_result:
                    self.authenticated = True
                    print("[INFO] PHPSESSID登录成功!")
                    return True
            except Exception as e:
                print(f"[ERROR] PHPSESSID登录失败: {e}")
                return False
        else:
            print("[ERROR] 未提供认证信息 (refresh_token或PHPSESSID)")
            return False
        
    def logout(self):
        """登出并清理认证信息"""
        if self.authenticated:
            # pixivpy3没有明确的登出API，我们清理本地状态
            self.api = AppPixivAPI()  # 创建新的API实例
            self.authenticated = False
            self.refresh_token = None
            self.phpsessid = None
            print("[INFO] 已登出并清理认证信息")
    
    def get_followed_illusts(self, limit: int = 10, days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取关注画师的作品 - 修复版
        
        Args:
            limit: 最大返回数量
            days: 仅返回最近N天的作品
            
        Returns:
            作品列表
        """
        if not self.authenticated:
            print("[ERROR] 请先登录")
            return []
        
        try:
            print(f"[INFO] 获取关注画师作品 (limit={limit}, days={days})...")
            
            # 使用正确的API方法：illust_follow()
            json_result = self.api.illust_follow()
            
            if not json_result or 'illusts' not in json_result:
                print("[WARN] 未获取到作品数据")
                return []
            
            illusts = json_result['illusts']
            
            # 按时间筛选
            if days is not None:
                from datetime import date as date_type
                today = date_type.today()
                
                filtered_illusts = []
                for illust in illusts:
                    create_date_str = illust.get('create_date', '')
                    if create_date_str:
                        try:
                            # 解析带时区的日期时间
                            create_date = datetime.strptime(create_date_str, '%Y-%m-%dT%H:%M:%S%z')
                            # 转换为本地日期（忽略时区，只比较日期部分）
                            create_date_local = create_date.astimezone().date()
                            
                            if days == 0:
                                # 今天：只返回今天创建的作品
                                if create_date_local == today:
                                    filtered_illusts.append(illust)
                            else:
                                # N天内：计算截止日期
                                cutoff_date = today - timedelta(days=days)
                                if create_date_local >= cutoff_date:
                                    filtered_illusts.append(illust)
                        except ValueError:
                            # 如果日期解析失败，保留作品（避免丢失数据）
                            filtered_illusts.append(illust)
                    else:
                        # 没有创建日期信息，保留作品
                        filtered_illusts.append(illust)
                illusts = filtered_illusts
            
            # 限制数量
            illusts = illusts[:limit]
            
            # 格式化结果
            formatted_results = []
            for illust in illusts:
                formatted = {
                    'id': illust.get('id'),
                    'title': illust.get('title', '无标题'),
                    'user': illust.get('user', {}).get('name', '未知画师'),
                    'user_id': illust.get('user', {}).get('id'),
                    'create_date': illust.get('create_date', ''),
                    'page_count': illust.get('page_count', 1),
                    'type': illust.get('type', 'illust'),
                    'tags': [tag.get('name', '') for tag in illust.get('tags', [])],
                    'image_urls': illust.get('image_urls', {}),
                    'total_view': illust.get('total_view', 0),
                    'total_bookmarks': illust.get('total_bookmarks', 0),
                }
                formatted_results.append(formatted)
            
            print(f"[INFO] 获取到 {len(formatted_results)} 个作品")
            return formatted_results
            
        except PixivError as e:
            print(f"[ERROR] API调用失败: {e}")
            return []
        except Exception as e:
            print(f"[ERROR] 获取作品时出错: {e}")
            return []
    
    def get_bookmarks(self, limit: int = 10, days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取收藏作品 - 修复版
        """
        if not self.authenticated:
            print("[ERROR] 请先登录")
            return []
        
        try:
            print(f"[INFO] 获取收藏作品 (limit={limit}, days={days})...")
            
            # 使用正确的API方法并传递user_id参数
            json_result = self.api.user_bookmarks_illust(self.api.user_id)
            
            if not json_result or 'illusts' not in json_result:
                print("[WARN] 未获取到收藏数据")
                return []
            
            illusts = json_result['illusts']
            
            # 筛选和限制逻辑（与get_followed_illusts相同）
            if days:
                cutoff_date = datetime.now() - timedelta(days=days)
                filtered_illusts = []
                for illust in illusts:
                    create_date_str = illust.get('create_date', '')
                    if create_date_str:
                        try:
                            create_date = datetime.strptime(create_date_str, '%Y-%m-%dT%H:%M:%S%z')
                            if create_date.replace(tzinfo=None) >= cutoff_date:
                                filtered_illusts.append(illust)
                        except ValueError:
                            filtered_illusts.append(illust)
                illusts = filtered_illusts
            
            illusts = illusts[:limit]
            
            formatted_results = []
            for illust in illusts:
                formatted = {
                    'id': illust.get('id'),
                    'title': illust.get('title', '无标题'),
                    'user': illust.get('user', {}).get('name', '未知画师'),
                    'user_id': illust.get('user', {}).get('id'),
                    'create_date': illust.get('create_date', ''),
                    'page_count': illust.get('page_count', 1),
                    'type': illust.get('type', 'illust'),
                    'tags': [tag.get('name', '') for tag in illust.get('tags', [])],
                    'image_urls': illust.get('image_urls', {}),
                    'total_view': illust.get('total_view', 0),
                    'total_bookmarks': illust.get('total_bookmarks', 0),
                }
                formatted_results.append(formatted)
            
            print(f"[INFO] 获取到 {len(formatted_results)} 个收藏作品")
            return formatted_results
            
        except Exception as e:
            print(f"[ERROR] 获取收藏时出错: {e}")
            return []
    
    def get_following_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取关注的用户 - 修复版
        """
        if not self.authenticated:
            print("[ERROR] 请先登录")
            return []
        
        try:
            print(f"[INFO] 获取关注用户 (limit={limit})...")
            
            # 使用正确的API方法并传递user_id参数
            json_result = self.api.user_following(self.api.user_id)
            
            if not json_result or 'user_previews' not in json_result:
                print("[WARN] 未获取到用户数据")
                return []
            
            users = json_result['user_previews'][:limit]
            
            formatted_results = []
            for user_preview in users:
                user = user_preview.get('user', {})
                formatted = {
                    'id': user.get('id'),
                    'name': user.get('name', '未知用户'),
                    'account': user.get('account', ''),
                    'comment': user.get('comment', ''),
                    'is_followed': user.get('is_followed', False),
                    'total_follow_users': user.get('total_follow_users', 0),
                    'total_illusts': user.get('total_illusts', 0),
                    'total_manga': user.get('total_manga', 0),
                    'total_novels': user.get('total_novels', 0),
                }
                formatted_results.append(formatted)
            
            print(f"[INFO] 获取到 {len(formatted_results)} 个关注用户")
            return formatted_results
            
        except Exception as e:
            print(f"[ERROR] 获取关注用户时出错: {e}")
            return []


def display_illusts(illusts: List[Dict[str, Any]], title: str = "作品列表"):
    """显示作品列表"""
    print(f"\n{'='*60}")
    print(f"{title} (共 {len(illusts)} 个)")
    print(f"{'='*60}")
    
    if not illusts:
        print("没有找到作品")
        return
    
    for i, illust in enumerate(illusts, 1):
        print(f"{i:2d}. [{illust['id']}] {illust['title']}")
        print(f"     画师: {illust['user']} (@{illust.get('user_id', '?')})")
        print(f"     时间: {illust['create_date']}")
        print(f"     标签: {', '.join(illust['tags'][:5])}{'...' if len(illust['tags']) > 5 else ''}")
        print(f"     浏览: {illust['total_view']:,} | 收藏: {illust['total_bookmarks']:,}")
        
        # 图片URL
        if 'medium' in illust['image_urls']:
            img_url = illust['image_urls']['medium']
            print(f"     图片: {img_url[:80]}..." if len(img_url) > 80 else f"     图片: {img_url}")
        
        print()


def display_users(users: List[Dict[str, Any]], title: str = "用户列表"):
    """显示用户列表"""
    print(f"\n{'='*60}")
    print(f"{title} (共 {len(users)} 个)")
    print(f"{'='*60}")
    
    if not users:
        print("没有找到用户")
        return
    
    for i, user in enumerate(users, 1):
        print(f"{i:2d}. [{user['id']}] {user['name']} (@{user.get('account', '?')})")
        print(f"     简介: {user['comment'][:100]}..." if len(user['comment']) > 100 else f"     简介: {user['comment']}")
        print(f"     作品: {user['total_illusts']} | 漫画: {user['total_manga']} | 小说: {user['total_novels']}")
        print(f"     关注: {user['total_follow_users']} | 已关注: {'是' if user['is_followed'] else '否'}")
        print()


def main():
    """命令行入口点"""
    parser = argparse.ArgumentParser(description='Pixiv更新监控工具 - 修复版')
    parser.add_argument('--refresh-token', help='Pixiv refresh token')
    parser.add_argument('--phpsessid', help='Pixiv PHPSESSID cookie')
    parser.add_argument('--followed', action='store_true', help='获取关注画师的作品')
    parser.add_argument('--bookmarks', action='store_true', help='获取收藏作品')
    parser.add_argument('--following', action='store_true', help='获取关注的用户')
    parser.add_argument('--limit', type=int, default=10, help='最大返回数量 (默认: 10)')
    parser.add_argument('--days', type=int, help='仅返回最近N天的内容')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    parser.add_argument('--quiet', action='store_true', help='安静模式，减少输出')
    
    args = parser.parse_args()
    
    # 如果没有指定任何操作，默认获取关注画师作品
    if not (args.followed or args.bookmarks or args.following):
        args.followed = True
    
    # 创建认证实例
    auth = PixivAuth(refresh_token=args.refresh_token, phpsessid=args.phpsessid)
    
    # 登录
    if not auth.login():
        print("[ERROR] 登录失败，请检查认证信息")
        sys.exit(1)
    
    results = {}
    
    try:
        # 获取数据
        if args.followed:
            illusts = auth.get_followed_illusts(limit=args.limit, days=args.days)
            results['followed_illusts'] = illusts
            
            if not args.quiet and not args.json:
                display_illusts(illusts, "关注画师的最新作品")
        
        if args.bookmarks:
            bookmarks = auth.get_bookmarks(limit=args.limit, days=args.days)
            results['bookmarks'] = bookmarks
            
            if not args.quiet and not args.json:
                display_illusts(bookmarks, "收藏作品")
        
        if args.following:
            users = auth.get_following_users(limit=args.limit)
            results['following_users'] = users
            
            if not args.quiet and not args.json:
                display_users(users, "关注的用户")
    
    finally:
        # 登出
        auth.logout()
    
    # JSON输出
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()