# Max Editor Agent (max-editor-agent)

3ds Max Claw Bridge 的 MCP Server，提供 `run_python` 工具。

## 端口

默认端口: **8082**

## 安装

### OpenClaw

在 `~/.openclaw/openclaw.json` 的 `mcp.servers` 中添加:

```json
"max-primary": {
  "url": "ws://127.0.0.1:8082/ws",
  "type": "streamable-http"
}
```

或运行安装脚本自动配置:

```bash
python setup_openclaw_config.py --max
```

### 其他平台

参考 `config_template.json` 中对应平台的配置模板。

## 前置条件

- 3ds Max 已安装 DCCClawBridge 插件
- 3ds Max 已打开并运行
