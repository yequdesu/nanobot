# NapCat 本地测试计划

## 目标
在本地环境搭建 NapCat + nanobot 测试环境，不经过 FRP 转发，验证基本功能。

## 环境要求
- Windows 或 Linux 系统
- 一个 QQ 账号（建议使用小号）
- Python 3.11+（已安装 nanobot）

---

## 步骤一：安装 NapCat

### Windows 安装

1. **下载 NapCat**
   - 访问 https://github.com/NapNeko/NapCatQQ/releases
   - 下载最新版本的 NapCat.win32.x64.zip 或 NapCat.win32.ia32.zip

2. **解压文件**
   ```
   解压到任意目录，例如：D:\NapCat
   ```

3. **启动 NapCat**
   - 双击 `NapCatWinBootMain.exe`
   - 首次启动会要求登录 QQ
   - 按提示扫码登录

### Linux 安装

1. **下载并安装**
   ```bash
   # 创建目录
   mkdir -p ~/napcat
   cd ~/napcat
   
   # 下载最新版本（以 v4.2.0 为例，请检查最新版本）
   wget https://github.com/NapNeko/NapCatQQ/releases/download/v4.2.0/NapCat.linux.x64.zip
   
   # 解压
   unzip NapCat.linux.x64.zip
   
   # 安装依赖（Ubuntu/Debian）
   sudo apt update
   sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
   ```

2. **启动 NapCat**
   ```bash
   cd ~/napcat
   ./NapCatBootMain
   ```

---

## 步骤二：配置 NapCat HTTP API

### 1. 找到配置文件

NapCat 首次启动后会生成配置文件：

- **Windows**: `D:\NapCat\config\napcat.json`
- **Linux**: `~/napcat/config/napcat.json`

### 2. 修改配置文件

编辑 `napcat.json`，启用 HTTP API：

```json
{
  "http": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 3000,
    "access_token": "your_token_here",
    "cors": ["*"]
  },
  "ws": {
    "enable": false
  },
  "reverse_ws": {
    "enable": false
  },
  "webhook": {
    "enable": false
  }
}
```

**关键配置说明**：
- `enable`: true - 启用 HTTP API
- `host`: "0.0.0.0" - 允许外部访问（本地测试可改为 "127.0.0.1"）
- `port`: 3000 - HTTP API 端口
- `access_token`: 设置访问令牌（可选但建议设置）

### 3. 重启 NapCat

修改配置后重启 NapCat 使配置生效。

---

## 步骤三：测试 NapCat API

### 1. 验证 NapCat 运行状态

打开浏览器或使用 curl 测试：

```bash
# 获取登录信息
curl "http://localhost:3000/get_login_info"
```

应该返回类似：
```json
{
  "data": {
    "nickname": "你的QQ昵称",
    "user_id": 123456789
  },
  "retcode": 0,
  "status": "ok"
}
```

### 2. 测试发送消息

给自己或测试账号发送消息：

```bash
# 发送私聊消息
curl -X POST "http://localhost:3000/send_private_msg" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 目标QQ号,
    "message": "Hello from NapCat!"
  }'
```

### 3. 查看支持的 API 列表

```bash
curl "http://localhost:3000/get_version_info"
```

---

## 步骤四：创建简单的 nanobot NapCat 适配器

### 1. 创建测试脚本

在 nanobot 项目目录下创建测试文件：

```python
# test_napcat.py
import asyncio
import aiohttp
from aiohttp import web

NAPCAT_HTTP_URL = "http://localhost:3000"

async def send_message(user_id: int, message: str):
    """通过 NapCat 发送消息"""
    async with aiohttp.ClientSession() as session:
        payload = {
            "user_id": user_id,
            "message": message
        }
        async with session.post(f"{NAPCAT_HTTP_URL}/send_private_msg", json=payload) as resp:
            result = await resp.json()
            print(f"Send result: {result}")
            return result

async def handle_webhook(request):
    """接收 NapCat 消息推送"""
    data = await request.json()
    print(f"Received message: {data}")
    
    # 简单回复
    if data.get("post_type") == "message":
        user_id = data.get("user_id")
        message = data.get("message")
        
        # 回复测试
        await send_message(user_id, f"收到消息: {message}")
    
    return web.Response(text="OK")

async def main():
    # 启动 HTTP 服务器接收消息
    app = web.Application()
    app.router.add_post('/napcat/webhook', handle_webhook)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 18791)
    await site.start()
    
    print("NapCat test server started on http://localhost:18791")
    print("请配置 NapCat webhook 指向: http://localhost:18791/napcat/webhook")
    
    # 保持运行
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. 运行测试脚本

```bash
# 在 nanobot 项目目录下
python test_napcat.py
```

### 3. 配置 NapCat Webhook

修改 `napcat.json`，启用 webhook：

```json
{
  "http": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 3000
  },
  "webhook": {
    "enable": true,
    "url": "http://localhost:18791/napcat/webhook",
    "timeout": 5000
  }
}
```

重启 NapCat。

### 4. 测试完整流程

1. 运行测试脚本：`python test_napcat.py`
2. 用手机 QQ 给机器人账号发送消息
3. 观察测试脚本输出，应该能看到收到的消息并自动回复

---

## 步骤五：集成到 nanobot

在本地测试通过后，可以开始正式集成到 nanobot：

### 1. 创建 NapCatChannel 类

参考前面的计划，创建 `nanobot/channels/napcat.py`

### 2. 修改配置

在 `~/.nanobot/config.json` 中添加：

```json
{
  "channels": {
    "napcat": {
      "enabled": true,
      "host": "0.0.0.0",
      "port": 18791,
      "http_host": "http://localhost",
      "http_port": 3000,
      "allow_from": ["你的QQ号"]
    }
  }
}
```

### 3. 测试集成

```bash
nanobot gateway
```

发送消息给机器人，检查 nanobot 是否能正常接收和回复。

---

## 常见问题排查

### 1. NapCat 启动失败

- 检查 QQ 版本是否兼容
- 检查是否安装了必要的依赖库
- 查看日志文件定位问题

### 2. HTTP API 无法访问

- 检查防火墙是否放行 3000 端口
- 检查配置文件是否正确
- 使用 `netstat -an | grep 3000` 检查端口监听

### 3. Webhook 无法接收消息

- 检查 webhook URL 是否可访问
- 检查网络连接
- 查看 NapCat 日志确认消息是否发送

### 4. 消息发送失败

- 检查 QQ 是否在线
- 检查目标 QQ 号是否正确
- 检查是否被风控限制

---

## 下一步

本地测试成功后，可以：
1. 完善 nanobot 的 NapCatChannel 实现
2. 添加 FRP 内网穿透配置
3. 部署到阿里云服务器
