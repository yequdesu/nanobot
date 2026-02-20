### 1. 端口冲突检测与处理
- 检测是否有其他容器占用 18790 端口
- 自动停止并删除冲突容器
### 2. 清理旧环境
- 停止并删除旧的 nanobot-dev 容器
- 使用 sudo rm -rf 删除旧的数据目录 ./nanobot-data
### 3. 数据目录准备
- 创建 ./nanobot-data 目录结构：
  - skills/ - 技能目录
  - workspace/ - 工作空间目录
  - memory/ - 记忆目录
### 4. 文件复制
- 复制 workspace/ 到数据目录
- 复制 userskills/ 到数据目录
- 复制 config/config.json 覆盖默认配置
### 5. 初始化配置
- 运行 nanobot onboard 生成默认配置
### 6. 启动服务
- 启动 nanobot gateway 容器
- 暴露端口 18790（NapCat WebSocket）
- 挂载数据目录
### 7. 输出提示
- 显示启动成功信息
- 显示 NapCat 配置指南