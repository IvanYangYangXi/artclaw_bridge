# ComfyUI ArtClaw Bridge 安装指南

## 快速安装

### 方法 1: 安装器（推荐）

```bash
python install.py --comfyui --comfyui-path "C:\path\to\ComfyUI"
```

### 方法 2: 手动安装

1. 将 `subprojects/ComfyUIClawBridge/` 复制到 `ComfyUI/custom_nodes/artclaw_bridge/`
2. 将 `subprojects/DCCClawBridge/` 复制到 `ComfyUI/custom_nodes/artclaw_bridge_dcc/`
3. 设置环境变量（可选）：
   ```
   set ARTCLAW_BRIDGE_PATH=D:\MyProject_D\artclaw_bridge
   ```

### 方法 3: 开发模式（symlink）

```powershell
# Windows (以管理员运行)
mklink /D "C:\path\to\ComfyUI\custom_nodes\artclaw_bridge" "D:\MyProject_D\artclaw_bridge\subprojects\ComfyUIClawBridge"
```

开发模式下 `startup.py` 会通过相对路径 `../DCCClawBridge` 找到依赖。

## 配置 OpenClaw

```bash
# 自动配置 mcp-bridge 插件
cd platforms/openclaw
python setup_openclaw_config.py --comfyui

# 重启 Gateway
openclaw gateway restart
```

或手动编辑 `~/.openclaw/openclaw.json`，在 `plugins.entries.mcp-bridge.config.servers` 中添加：

```json
{
  "comfyui-editor": {
    "type": "websocket",
    "url": "ws://127.0.0.1:8087"
  }
}
```

Agent 的 `tools.allow` 使用通配符：`mcp_comfyui-editor_*`

## 验证连接

1. 启动 ComfyUI，日志中应出现：
   ```
   ArtClaw: MCP Server started on port 8087
   ```

2. 通过 OpenClaw Agent 测试：
   ```
   请列出 ComfyUI 中可用的模型
   ```
   
   Agent 会执行：
   ```python
   import folder_paths
   checkpoints = folder_paths.get_filename_list("checkpoints")
   print(f"可用 Checkpoints ({len(checkpoints)}):")
   for c in checkpoints:
       print(f"  - {c}")
   ```

3. 测试生图：
   ```
   帮我用 ComfyUI 生成一张日落的图片
   ```

## MCP 端口

| DCC | 默认端口 |
|-----|---------|
| UE | 8080 |
| Maya | 8081 |
| Max | 8082 |
| **ComfyUI** | **8087** |

端口被占用时会自动递增（最多尝试 10 个端口）。

## 目录结构

```
ComfyUI/custom_nodes/
├── artclaw_bridge/          # ComfyUIClawBridge
│   ├── __init__.py          # 自定义节点入口（NODE_CLASS_MAPPINGS={}）
│   ├── startup.py           # MCP Server 启动逻辑
│   └── install.py           # ComfyUI-Manager 兼容
│
├── artclaw_bridge_dcc/      # DCCClawBridge（依赖库）
│   ├── adapters/
│   │   ├── base_adapter.py
│   │   └── comfyui_adapter.py
│   └── core/
│       ├── mcp_server.py
│       ├── bridge_core.py
│       ├── comfyui_client.py
│       ├── workflow_store.py
│       └── workflow_utils.py
```

## Agent 可用的 API

通过 `run_python` 工具，Agent 可在 ComfyUI 进程内执行任意 Python：

```python
# 预注入变量
S = []                    # 无选中概念
W = None                  # 无当前文件
L = ComfyUILib            # L.nodes, L.folder_paths, L.execution, L.server
client = ComfyUIClient    # HTTP API 封装
submit_workflow = func    # 提交 workflow 并等待结果
save_preview = func       # 输出 [IMAGE:path] 标记
nodes = nodes_module      # ComfyUI 节点注册表
folder_paths = module     # 文件路径管理
```

## 故障排除

| 问题 | 解决 |
|------|------|
| MCP Server 未启动 | 检查 ComfyUI 日志中是否有 `ArtClaw` 相关错误 |
| 找不到 DCCClawBridge | 设置 `ARTCLAW_BRIDGE_PATH` 环境变量 |
| 端口 8087 被占用 | 自动递增，检查日志中实际端口号 |
| websockets 未安装 | ComfyUI 环境中 `pip install websockets` |
| OpenClaw 连接失败 | 确认 Gateway 已重启，`openclaw gateway restart` |
