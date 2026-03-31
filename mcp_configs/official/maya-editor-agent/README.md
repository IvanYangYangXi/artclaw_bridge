# Maya Editor Agent (maya-editor-agent)

Maya Claw Bridge 的 MCP Server，提供 `run_python` 工具。

## 端口

默认端口: **8081**

## 安装

### OpenClaw

在 `~/.openclaw/openclaw.json` 的 `mcp.servers` 中添加:

```json
"maya-primary": {
  "url": "ws://127.0.0.1:8081/ws",
  "type": "streamable-http"
}
```

或运行安装脚本自动配置:

```bash
python setup_openclaw_config.py --maya
```

### 其他平台

参考 `config_template.json` 中对应平台的配置模板。

## 前置条件

- Maya 已安装 DCCClawBridge 插件
- Maya 已打开并运行
