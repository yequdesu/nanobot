# NapCat-OpenClaw 插件原理分析与 nanobot 应用

## 背景

用户发现 `napcat-plugin-openclaw` 插件可以实现 OpenClaw 与 NapCat 的连接，希望了解其原理并应用到 nanobot 上。

## 可能的实现原理分析

由于无法直接访问该插件源码，基于 NapCat 和 OpenClaw 的常见集成方式，分析可能的实现方案：

### 方案一：OneBot 11/12 协议适配（最可能）

**原理**：
- NapCat 原生支持 OneBot 11/12 协议
- OpenClaw 通过 OneBot 适配器与 NapCat 通信
- 插件可能是在 NapCat 侧做了一层协议转换或增强

**应用到 nanobot**：
```python
# nanobot/channels/onebot.py
class OneBotChannel(BaseChannel):
    """OneBot 协议适配器，支持 NapCat/go-cqhttp 等"""
    
    name = "onebot"
    
    async def start(self):
        # 启动 HTTP 服务器接收 OneBot 事件
        # 或通过 WebSocket 连接 OneBot 服务端
        pass
```

**优点**：
- 标准化协议，兼容多个 QQ 机器人框架
- 生态成熟，文档完善

### 方案二：HTTP API + Webhook（与之前计划类似）

**原理**：
- NapCat 提供 HTTP API 发送消息
- OpenClaw 启动 HTTP 服务器接收 webhook 回调
- 插件可能简化了配置流程或添加了额外功能

**应用到 nanobot**：
参考之前的 `napcat.py` 实现，这是最直接的方式。

### 方案三：WebSocket 反向连接

**原理**：
- OpenClaw 作为 WebSocket 服务端
- NapCat 通过反向 WebSocket 连接到 OpenClaw
- 插件可能处理了连接管理和心跳保活

**应用到 nanobot**：
```python
# WebSocket 服务端实现
class NapCatWebSocketChannel(BaseChannel):
    async def start(self):
        # 启动 WebSocket 服务器
        # 等待 NapCat 反向连接
        pass
```

**优点**：
- 实时双向通信
- 适合高并发场景

### 方案四：内置代理/桥接模式

**原理**：
- 插件作为中间层，同时连接 NapCat 和 OpenClaw
- 可能做了协议转换或消息格式适配

**应用到 nanobot**：
需要开发独立的桥接服务，复杂度较高。

---

## 推荐方案：OneBot 协议适配

基于分析，最推荐实现 **OneBot 11 协议适配器**，原因：

1. **标准化**：OneBot 是 QQ 机器人社区标准协议
2. **兼容性**：同时支持 NapCat、go-cqhttp、Lagrange 等
3. **可维护性**：协议文档完善，社区支持好

### OneBot 协议核心概念

**消息格式**：
```json
{
  "post_type": "message",
  "message_type": "private",
  "user_id": 123456789,
  "message": "Hello"
}
```

**API 调用**：
- 发送私聊消息：`/send_private_msg`
- 发送群消息：`/send_group_msg`
- 获取登录信息：`/get_login_info`

### nanobot OneBotChannel 实现计划

```python
# nanobot/channels/onebot.py

class OneBotChannel(BaseChannel):
    """
    OneBot 11/12 协议适配器
    支持 NapCat、go-cqhttp、Lagrange 等 OneBot 实现
    """
    
    name = "onebot"
    
    def __init__(self, config: OneBotConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: OneBotConfig = config
        
    async def start(self):
        """启动 OneBot 适配器"""
        if self.config.connection_type == "http":
            await self._start_http_mode()
        elif self.config.connection_type == "websocket":
            await self._start_ws_mode()
    
    async def _start_http_mode(self):
        """HTTP 模式：启动服务器接收事件，主动调用 API"""
        # 1. 启动 HTTP 服务器接收 OneBot 事件推送
        # 2. 初始化 aiohttp session 调用 OneBot API
        pass
    
    async def _start_ws_mode(self):
        """WebSocket 模式：反向 WebSocket 连接"""
        # 1. 启动 WebSocket 服务器
        # 2. 等待 OneBot 客户端连接
        # 3. 处理双向通信
        pass
    
    async def send(self, msg: OutboundMessage):
        """发送消息"""
        # 调用 OneBot API 发送消息
        pass
```

### 配置示例

```json
{
  "channels": {
    "onebot": {
      "enabled": true,
      "connection_type": "http",
      "http": {
        "host": "0.0.0.0",
        "port": 18791,
        "api_url": "http://localhost:3000"
      },
      "allow_from": ["123456789"]
    }
  }
}
```

---

## 实施建议

1. **先验证 NapCat OneBot 支持**
   ```bash
   # 检查 NapCat 是否启用了 OneBot HTTP
   curl "http://localhost:3000/get_version_info"
   ```

2. **查看插件文档**
   - 如果能访问 `napcat-plugin-openclaw` 仓库，查看 README
   - 了解具体的配置参数和连接方式

3. **选择实现方式**
   - 如果 NapCat 已支持标准 OneBot HTTP，直接实现 OneBotChannel
   - 如果需要特殊适配，参考插件源码实现类似逻辑

4. **测试验证**
   - 本地测试通过后，再添加 FRP 转发
   - 保留原有 QQ 渠道作为备份

---

## 下一步行动

请确认：
1. 能否访问 `napcat-plugin-openclaw` 的 README 或文档？
2. NapCat 的 OneBot HTTP 是否已启用？
3. 希望实现 HTTP 模式还是 WebSocket 模式？

根据反馈，我可以提供具体的实现代码。