---
name: pixiv-updates
description: 获取Pixiv关注画师的更新作品、收藏列表和关注用户的新作
version: 1.1.0
author: nanobot
updated: 2026-02-14
---

# Pixiv Updates Skill

## 功能描述

该技能是一个命令行工具，用于从Pixiv获取最新作品信息。支持三种数据获取模式：

- **关注画师更新**：获取你关注的画师发布的新作品
- **收藏作品**：获取你的收藏列表中的作品
- **关注用户**：获取你关注的用户信息

支持按日期筛选（今天、昨天、最近N天）和数量限制。

## 依赖要求

### Python库依赖
```bash
pip install pixivpy3 requests
```

### 必需库版本
- `pixivpy3` >= 3.9.0
- `requests` >= 2.32.0

## 认证方式

支持两种认证方式（二选一）：

### 1. Refresh Token方式（推荐）
```bash
python pixiv.py --refresh-token "你的refresh_token" [其他参数]
```

### 2. PHPSESSID方式
```bash
python pixiv.py --phpsessid "你的PHPSESSID" [其他参数]
```

## 使用方法

### 基本命令格式
```bash
cd /root/.nanobot/workspace/skills/pixiv-updates
python pixiv.py [认证参数] [数据参数] [筛选参数] [输出参数]
```

### 参数详解

#### 认证参数（必需）
- `--refresh-token TOKEN`：使用Pixiv refresh_token认证
- `--phpsessid SESSID`：使用PHPSESSID认证

#### 数据参数（必需，至少选一个）
- `--followed`：获取关注画师的作品
- `--bookmarks`：获取收藏作品
- `--following`：获取关注用户

#### 筛选参数（可选）
- `--days N`：获取最近N天的数据（0=今天，1=昨天，2=前天，以此类推）
- `--limit N`：限制返回结果数量（默认：10）
- `--user-id ID`：指定用户ID（用于bookmarks和following模式）

#### 输出参数（可选）
- `--json`：以JSON格式输出
- `--verbose`：显示详细日志

## 使用示例

### 示例1：获取今天关注画师的更新
```bash
python pixiv.py --refresh-token "你的token" --followed --days 0 --limit 20
```

### 示例2：获取最近3天的收藏作品
```bash
python pixiv.py --phpsessid "你的sessid" --bookmarks --days 3 --limit 15
```

### 示例3：获取关注用户（JSON格式）
```bash
python pixiv.py --refresh-token "你的token" --following --json
```

### 示例4：获取特定用户的收藏
```bash
python pixiv.py --refresh-token "你的token" --bookmarks --user-id 123456 --limit 10
```

## 输出格式

### 默认输出（表格格式）
```
作品ID | 标题 | 画师 | 时间 | 浏览 | 收藏 | 标签
------ | ---- | ---- | ---- | ---- | ---- | ----
```

### JSON输出（使用--json参数）
```json
{
  "status": "success",
  "count": 10,
  "data": [
    {
      "id": 12345678,
      "title": "作品标题",
      "artist": "画师名",
      "create_date": "2026-02-14T18:00:00+09:00",
      "view_count": 7025,
      "bookmark_count": 1211,
      "tags": ["R-18", "标签1", "标签2"]
    }
  ]
}
```

## 常见问题与解决

### Q1: 认证失败，错误代码1508
**问题**：Invalid refresh token
**解决**：
1. 检查refresh_token格式（应为32-40位字母数字组合）
2. 确认token未过期（refresh_token通常有效期为30天）
3. 重新从Pixiv获取有效的refresh_token

### Q2: 获取不到今天的数据
**问题**：使用`--days 0`但返回空结果
**解决**：
1. Pixiv使用日本时区（UTC+9），"今天"指日本时间的今天
2. 确认关注的画师今天确实发布了新作品
3. 尝试`--days 1`获取昨天的数据作为测试

### Q3: 返回结果数量少于限制
**问题**：设置了`--limit 20`但只返回了10个结果
**解决**：
1. 可能没有足够的新作品满足筛选条件
2. 尝试增加`--days`参数值
3. 某些画师可能设置了隐私限制

### Q4: API限制错误
**问题**：收到速率限制错误
**解决**：
1. 技能已内置延迟机制避免触发API限制
2. 如果频繁调用，建议增加调用间隔
3. 避免短时间内多次调用相同API

## 安全注意事项

1. **Token安全**：
   - 不要将refresh_token硬编码在脚本中
   - 建议通过环境变量或命令行参数传递
   - 使用后及时清理命令行历史

2. **数据隐私**：
   - 获取的数据仅用于个人查看
   - 不要公开分享他人的Pixiv作品
   - 尊重画师的版权设置

3. **API使用**：
   - 遵守Pixiv API使用条款
   - 不要用于商业用途
   - 避免过度调用影响服务

## 更新日志

### v1.1.0 (2026-02-14)
- 修复API方法调用错误（`user_following_illusts` → `illust_follow`）
- 改进日期过滤逻辑，支持时区处理
- 添加详细的错误处理和日志
- 优化输出格式和可读性

### v1.0.0 (初始版本)
- 基础功能：关注画师、收藏作品、关注用户获取
- 支持日期筛选和数量限制
- 支持JSON格式输出

## 技术支持

如遇问题，请：
1. 检查依赖是否安装：`pip list | grep pixivpy3`
2. 验证认证信息是否正确
3. 查看详细错误信息：添加`--verbose`参数
4. 检查网络连接是否可访问Pixiv

---

*注意：本技能仅供个人学习使用，请遵守Pixiv服务条款和版权法律。*