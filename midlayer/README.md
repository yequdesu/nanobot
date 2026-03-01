# Mid-Layer 服务

NapCat 与 NanoBot 之间的桥梁，通过 Nacos 服务发现实现动态路由。

## 架构

```
NapCat (QQ Bot)
    │ WebSocket (OneBot v11)
    ▼
Mid-Layer (本服务) :18800
    │ Nacos Discovery
    ▼
Nacos (39.106.255.3:8848)
    │
    ▼
NanoBot (动态发现) :18790
```

## 快速开始

### 1. 安装依赖

```bash
cd midlayer
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python midlayer.py
```

输出示例：
```
2024-01-15 10:30:00 - INFO - Connected to Nacos: 39.106.255.3:8848
2024-01-15 10:30:00 - INFO - Mid-layer started
2024-01-15 10:30:00 - INFO -   Nacos: 39.106.255.3:8848
2024-01-15 10:30:00 - INFO -   Listen: ws://0.0.0.0:18800
2024-01-15 10:30:00 - INFO -   Target Service: nanobot-gateway
```

## NapCat 配置

### 1. 打开 NapCat WebUI
访问 http://localhost:6099

### 2. 配置网络
- **启用反向 WebSocket**: ✅ 勾选
- **反向 WebSocket 地址**: `ws://<midlayer-ip>:18800`

### URL 示例

| 场景 | URL |
|------|-----|
| MidLayer 本地运行 | `ws://127.0.0.1:18800` |
| MidLayer 在服务器A | `ws://服务器A-IP:18800` |
| Docker 部署 (Linux) | `ws://host.docker.internal:18800` |
| Docker 部署 (Windows) | `ws://host.docker.internal:18800` |

### 3. 消息格式
- **消息上报格式**: Array
- **消息上报压缩**: 不勾选

## 配置说明

如需修改配置，编辑 `midlayer.py` 中的 `main()` 函数：

```python
nacos_config = NacosConfig(
    server="39.106.255.3:8848",           # Nacos 地址
    namespace="f45fa327-df31-4547-85a3-7d3dabf7fb19",  # 命名空间
    username="nacos",                      # Nacos 用户名
    password="nacos",                      # Nacos 密码
)

midlayer = MidLayer(
    nacos_config=nacos_config,
    listen_host="0.0.0.0",    # 监听地址
    listen_port=18800,          # 监听端口
    service_name="nanobot-gateway",  # 目标服务名
    group="DEFAULT_GROUP",      # 服务分组
)
```

## 工作流程

1. **MidLayer 启动**
   - 连接 Nacos
   - 启动 WebSocket 服务器 (端口 18800)

2. **NapCat 连接**
   - NapCat 作为客户端连接到 MidLayer
   - 发送 OneBot v11 消息

3. **消息处理**
   - MidLayer 接收消息
   - 从 Nacos 查询 `nanobot-gateway` 健康实例
   - 转发消息到 NanoBot
   - 返回 NanoBot 响应给 NapCat

4. **服务发现**
   - 只选择健康实例 (`healthy_only=True`)
   - 当前实现：选择第一个实例（可扩展负载均衡）

## 日志说明

```
INFO - NapCat connected from 127.0.0.1:54321  # NapCat 连接
DEBUG - Forwarding to NanoBot at 192.168.1.100:18790  # 转发目标
DEBUG - Received response from NanoBot  # 收到响应
INFO - NapCat disconnected from 127.0.0.1:54321  # NapCat 断开
```

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| `No NanoBot instance available` | 检查 NanoBot 是否启动并注册到 Nacos |
| `Timeout waiting for NanoBot` | 检查 NanoBot 是否响应正常 |
| `Nacos discovery failed` | 检查 Nacos 连接配置和网络 |
| NapCat 无法连接 | 检查防火墙和端口 18800 是否开放 |

## 扩展功能

当前实现为基础版本，可扩展：
- 负载均衡（轮询、权重等）
- 消息缓存和重试
- 多服务路由
- 认证和限流
