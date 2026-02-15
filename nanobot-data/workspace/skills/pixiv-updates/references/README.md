# Pixiv Updates Skill 参考文档

## 功能详情

### 1. 用户管理

#### 1.1 登录用户

**函数**: `login(user_id, refresh_token)`

**参数**:
- `user_id`: 用户标识，字符串类型，用于唯一标识用户
- `refresh_token`: Pixiv刷新令牌，字符串类型，用于认证Pixiv账户

**返回值**:
- `bool`: 登录是否成功

**说明**:
- 登录时会加密存储用户的refresh_token
- 登录成功后会自动设置该用户为当前用户
- 如果用户已存在，会更新其refresh_token

#### 1.2 登出用户

**函数**: `logout(user_id)`

**参数**:
- `user_id`: 用户标识，字符串类型

**返回值**:
- `bool`: 登出是否成功

**说明**:
- 登出时会删除用户的refresh_token
- 如果登出的是当前用户，会清除当前用户状态

#### 1.3 切换用户

**函数**: `switch_user(user_id)`

**参数**:
- `user_id`: 用户标识，字符串类型

**返回值**:
- `bool`: 切换是否成功

**说明**:
- 切换用户前需要确保该用户已登录
- 切换成功后会重置认证状态，需要重新初始化

#### 1.4 获取当前用户

**函数**: `get_current_user()`

**参数**: 无

**返回值**:
- `str`: 当前用户标识，未登录时返回 `None`

#### 1.5 列出所有用户

**函数**: `list_users()`

**参数**: 无

**返回值**:
- `list[str]`: 所有已登录用户的标识列表

### 2. 作品获取

#### 2.1 获取指定日期的更新

**函数**: `get_updates_by_date(date)`

**参数**:
- `date`: 目标日期，格式为 `YYYY-MM-DD`

**返回值**:
```python
{
    "success": bool,
    "data": {
        "date": str,
        "total_artists": int,
        "total_works": int,
        "total_tags": int,
        "updates": [
            {
                "author": str,
                "author_id": str,
                "works": [
                    {
                        "id": str,
                        "title": str,
                        "tags": list[str],
                        "bookmark_count": int,
                        "view_count": int,
                        "created_date": str
                    }
                ]
            }
        ]
    },
    "message": str  # 仅在success为False时存在
}
```

#### 2.2 获取今天的更新

**函数**: `get_today_updates()`

**参数**: 无

**返回值**: 与 `get_updates_by_date` 相同

#### 2.3 获取昨天的更新

**函数**: `get_yesterday_updates()`

**参数**: 无

**返回值**: 与 `get_updates_by_date` 相同

#### 2.4 获取收藏列表

**函数**: `get_bookmarks(page=1, restrict='public')`

**参数**:
- `page`: 页码，默认为1
- `restrict`: 权限，可选值为 `'public'` 或 `'private'`，默认为 `'public'`

**返回值**:
```python
{
    "success": bool,
    "data": {
        "page": int,
        "restrict": str,
        "count": int,
        "bookmarks": [
            {
                "id": str,
                "title": str,
                "author": str,
                "author_id": str,
                "tags": list[str],
                "bookmark_count": int,
                "view_count": int,
                "created_date": str
            }
        ]
    },
    "message": str  # 仅在success为False时存在
}
```

#### 2.5 获取关注用户的新作

**函数**: `get_follow_updates()`

**参数**: 无

**返回值**:
```python
{
    "success": bool,
    "data": {
        "count": int,
        "updates": [
            {
                "id": str,
                "title": str,
                "author": str,
                "author_id": str,
                "tags": list[str],
                "bookmark_count": int,
                "view_count": int,
                "created_date": str
            }
        ]
    },
    "message": str  # 仅在success为False时存在
}
```

## 技术实现

### 用户管理

#### 1. 加密存储

该技能实现了以下机制来安全存储用户数据：

- 使用 `Fernet` 对称加密算法加密存储用户的refresh_token
- 加密密钥会自动生成并存储在 `assets/encryption.key` 文件中
- 加密后的数据会进行base64编码，确保可以安全存储在JSON文件中
- 用户数据存储在 `assets/users.json` 文件中，按用户ID组织

#### 2. 多用户支持

- 支持多个用户同时登录，每个用户的refresh_token会分开存储
- 支持用户切换，通过 `switch_user` 函数可以在不同用户之间切换
- 支持用户登出，登出后会删除用户的refresh_token

### API限速处理

该技能实现了以下机制来避免API限速：

- 在获取关注列表时，使用 `next_url` 和 `parse_qs` 方法进行分页
- 在获取用户作品时，使用 `next_url` 和 `parse_qs` 方法进行分页
- 在获取关注画师更新时，每个用户之间添加1秒延迟
- 遇到速率限制时，自动暂停5秒后重试

### 数据处理

- 获取关注列表时会自动去重，确保数据准确性
- 所有返回结果都包含作品的标签信息
- 支持获取公开和私密的关注列表
- 支持获取公开和私密的收藏列表

## 错误处理

该技能会捕获并处理以下错误：

- 认证失败
- API调用错误
- 网络连接错误
- 数据解析错误
- 用户管理相关错误（如用户不存在、加密解密失败等）

所有错误都会以友好的方式返回，确保技能能够稳定运行。