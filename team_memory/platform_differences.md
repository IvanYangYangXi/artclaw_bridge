# Platform Differences

> 跨 DCC/平台的关键差异。仅首条消息注入。

- [UE] 坐标系: Z-Up 左手系 (X=前 Y=右 Z=上)
- [Maya] 坐标系: Y-Up 右手系 (X=右 Y=上 Z=屏幕外)
- [Max] 坐标系: Z-Up 右手系 (X=右 Y=屏幕里 Z=上)
- [Blender] 坐标系: Z-Up 右手系 (X=右 Y=前 Z=上)，旋转用弧度
- [UE] MCP 端口: 8080, Session: agent/ue-editor
- [Maya] MCP 端口: 8081, Session: agent/maya-editor
- [Max] MCP 端口: 8082, Session: agent/max-editor
- [Blender] MCP 端口: 8083, Session: agent/blender-editor
- [Houdini] MCP 端口: 8084, Session: agent/houdini-editor
- [SP] MCP 端口: 8085, Session: agent/sp-editor
- [SD] MCP 端口: 8086, Session: agent/sd-editor
- [ComfyUI] MCP 端口: 8087, Session: agent/comfyui-editor
- [UE] UI 技术: Slate+C++, 回传方式: 文件轮询(stream.jsonl)
- [All] DCC 共用 UI 技术: Qt+纯Python (PySide2/Qt 5.15), 回传方式: Qt signal/slot
- [All] Gateway: OpenClaw 端口 18789
- [All] Skills 目录: OpenClaw: ~/.openclaw/workspace/skills/
