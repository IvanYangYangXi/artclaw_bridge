# UE Editor Agent (ue-editor-agent)

UE Claw Bridge 的 MCP Server，提供 `run_ue_python` 工具。

## 端口

默认端口: **8080**

## 安装

### OpenClaw

在 `~/.openclaw/openclaw.json` 的 `mcp.servers` 中添加:

```json
"ue-editor-agent": {
  "url": "ws://127.0.0.1:8080/ws",
  "type": "streamable-http"
}
```

或运行安装脚本自动配置:

```bash
python setup_openclaw_config.py
```

### 其他平台

参考 `config_template.json` 中对应平台的配置模板。

## 前置条件

- UE 编辑器已安装 UEClawBridge 插件
- 编辑器已打开并运行
