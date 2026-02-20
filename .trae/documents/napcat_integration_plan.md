# Nanobot 与 NapCat 集成计划

## 背景

用户希望将 nanobot 与 NapCat 联动，替代现有的 QQ 官方机器人方案。部署架构：

* **远程阿里云服务器**：部署 nanobot + FRP 服务端

* **本地电脑**：部署 NapCat（登录 QQ 机器人账号）+ FRP 客户端

* **消息流向**：用户QQ → NapCat → FRP客户端 → FRP服务端 → nanobot → 原路返回

## 方案分析

### 方案一：HTTP API 方式（推荐）

NapCat 提供 HTTP API 接口，nanobot 可以通过 HTTP 请求与 NapCat 通信。

**架构**：

```
用户QQ消息 → NapCat → FRP(内网穿透) → nanobot HTTP服务器
nanobot回复 → HTTP POST → FRP → NapCat → 用户QQ
```

**优点**：

* 实现简单，NapCat 原生支持 HTTP API

* 无需 WebSocket 长连接

* 与现有 channel 架构一致

**缺点**：

* 需要 FRP 配置 TCP 端口转发

* 双向 HTTP 请求

### 方案二：WebSocket 方式

NapCat 支持 WebSocket 反向连接。

**架构**：

```
nanobot WebSocket服务器 ← FRP ← NapCat WebSocket客户端
```

**优点**：

* 实时双向通信

* 适合高并发场景

**缺点**：

* 实现复杂

* FRP 需要支持 WebSocket 转发

### 方案三：OneBot 11/12 协议适配

NapCat 支持 OneBot 协议，可以复用现有的 OneBot 适配逻辑。

**优点**：

* 标准化协议

* 生态丰富

**缺点**：

* 需要额外实现 OneBot 适配层

## 推荐方案：HTTP API 方式

### 实现步骤

#### 1. 创建 NapCatChannel 类

新建文件：`nanobot/channels/napcat.py`

```python
"""NapCat channel implementation using HTTP API."""

import asyncio
import aiohttp
from typing import Any
from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import NapCatConfig


class NapCatChannel(BaseChannel):
    """NapCat channel using HTTP API."""
    
    name = "napcat"
    
    def __init__(self, config: NapCatConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: NapCatConfig = config
        self._session: aiohttp.ClientSession | None = None
        self._http_server: asyncio.Task | None = None
        
    async def start(self) -> None:
        """Start NapCat channel.
        
        1. 启动 HTTP 服务器接收 NapCat 消息推送
        2. 初始化 HTTP 客户端发送消息
        """
        if not self.config.http_host or not self.config.http_port:
            logger.error("NapCat HTTP host/port not configured")
            return
            
        self._running = True
        self._session = aiohttp.ClientSession()
        
        # 启动 HTTP 服务器接收消息
        from aiohttp import web
        app = web.Application()
        app.router.add_post('/napcat/webhook', self._handle_webhook)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.config.host, self.config.port)
        await site.start()
        
        logger.info(f"NapCat HTTP server started on {self.config.host}:{self.config.port}")
        
    async def stop(self) -> None:
        """Stop NapCat channel."""
        self._running = False
        if self._session:
            await self._session.close()
        logger.info("NapCat channel stopped")
        
    async def send(self, msg: OutboundMessage) -> None:
        """Send message via NapCat HTTP API."""
        if not self._session:
            logger.error("NapCat session not initialized")
            return
            
        try:
            # 调用 NapCat HTTP API 发送消息
            url = f"{self.config.http_host}:{self.config.http_port}/send_msg"
            payload = {
                "user_id": msg.chat_id,
                "message": msg.content
            }
            
            async with self._session.post(url, json=payload) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to send message: {await resp.text()}")
                    
        except Exception as e:
            logger.error(f"Error sending NapCat message: {e}")
            
    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming message from NapCat."""
        try:
            data = await request.json()
            
            # 解析 NapCat 消息格式
            if data.get("post_type") == "message":
                user_id = str(data.get("user_id"))
                message = data.get("message", "")
                
                # 检查权限
                if not self.is_allowed(user_id):
                    return web.Response(status=403)
                
                # 创建入站消息
                msg = InboundMessage(
                    channel=self.name,
                    sender_id=user_id,
                    chat_id=user_id,
                    content=message,
                    metadata={"raw": data}
                )
                
                # 发布到消息总线
                await self.bus.publish_inbound(msg)
                
            return web.Response(status=200)
            
        except Exception as e:
            logger.error(f"Error handling NapCat webhook: {e}")
            return web.Response(status=500)
```

#### 2. 添加配置项

修改 `nanobot/config/schema.py`：

```python
class NapCatConfig(BaseModel):
    """NapCat channel configuration using HTTP API."""
    enabled: bool = False
    
    # nanobot HTTP 服务器配置（接收 NapCat 消息）
    host: str = "0.0.0.0"
    port: int = 18791  # 不同于 gateway 端口
    
    # NapCat HTTP API 地址（通过 FRP 转发）
    http_host: str = "http://localhost"  # FRP 服务端地址
    http_port: int = 3000  # FRP 服务端端口
    
    # 访问令牌（可选）
    access_token: str = ""
    
    allow_from: list[str] = Field(default_factory=list)


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""
    # ... 其他配置 ...
    qq: QQConfig = Field(default_factory=QQConfig)
    napcat: NapCatConfig = Field(default_factory=NapCatConfig)  # 新增
```

#### 3. 注册 Channel

修改 `nanobot/channels/manager.py`，在 `_init_channels` 方法中添加：

```python
from nanobot.channels.napcat import NapCatChannel

# ...

if self.config.channels.napcat.enabled:
    from nanobot.channels.napcat import NapCatChannel
    self.channels.append(NapCatChannel(
        config=self.config.channels.napcat,
        bus=self.bus
    ))
    logger.info("NapCat channel enabled")
```

#### 4. FRP 配置

**FRP 服务端配置**（阿里云服务器）：

```ini
# frps.ini
[common]
bind_port = 7000
token = your_frp_token

# NapCat HTTP API 转发
[napcat_http]
type = tcp
local_port = 3000  # nanobot 访问的本地端口
remote_port = 3000  # 对外暴露的端口
```

**FRP 客户端配置**（本地电脑）：

```ini
# frpc.ini
[common]
server_addr = your_aliyun_ip
server_port = 7000
token = your_frp_token

# NapCat HTTP API 转发
[napcat_http]
type = tcp
local_ip = 127.0.0.1
local_port = 3000  # NapCat HTTP API 端口
remote_port = 3000

# nanobot webhook 转发（可选，如果需要双向）
[napcat_webhook]
type = tcp
local_ip = 127.0.0.1
local_port = 18791  # nanobot HTTP 服务器端口
remote_port = 18791
```

#### 5. NapCat 配置

在 NapCat 配置文件中启用 HTTP API：

```json
{
  "http": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 3000,
    "access_token": "your_token"
  },
  "webhook": {
    "enable": true,
    "url": "http://your_aliyun_ip:18791/napcat/webhook",
    "access_token": "your_token"
  }
}
```

#### 6. nanobot 配置

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
      "access_token": "your_token",
      "allow_from": ["your_qq_number"]
    }
  }
}
```

## 部署流程

1. **阿里云服务器**：

   ```bash
   # 启动 FRP 服务端
   ./frps -c frps.ini

   # 启动 nanobot
   nanobot gateway
   ```

2. **本地电脑**：

   ```bash
   # 启动 FRP 客户端
   ./frpc -c frpc.ini

   # 启动 NapCat
   # NapCat 会自动连接 QQ 并启动 HTTP API
   ```

## 消息流向

```
用户发送QQ消息
    ↓
NapCat 接收消息
    ↓
NapCat 通过 webhook POST 到 FRP 客户端
    ↓
FRP 客户端转发到 FRP 服务端
    ↓
FRP 服务端转发到 nanobot HTTP 服务器
    ↓
nanobot 处理消息
    ↓
nanobot 调用 NapCat HTTP API (通过 FRP)
    ↓
NapCat 发送回复到用户QQ
```

## 风险与注意事项

1. **FRP 安全性**：

   * 使用强 token

   * 限制 FRP 服务端仅允许特定 IP

   * 考虑使用 TLS 加密

2. **消息顺序**：

   * HTTP 方式可能无法保证消息顺序

   * 需要添加消息队列处理

3. **错误处理**：

   * FRP 连接断开时的重连机制

   * NapCat 离线时的消息缓存

4. **性能考虑**：

   * FRP 转发增加延迟

   * 图片/文件传输可能较慢

## 替代方案

如果 HTTP API 方式不稳定，可以考虑：

1. **直接 TCP 连接**：nanobot 和 NapCat 都部署在同一服务器，无需 FRP
2. **使用 MoChat**：nanobot 已支持 MoChat，可以作为中间层
3. **使用 go-cqhttp**：另一个 QQ 机器人框架，也支持 HTTP API

## 实施建议

1. 先在本地测试 NapCat + nanobot（不经过 FRP）
2. 确认功能正常后再添加 FRP 转发
3. 逐步迁移，保留原有 QQ 渠道作为备份
4. 添加监控和日志，便于排查问题

