# Platform Differences

> 跨 DCC/平台的关键差异。仅首条消息注入。

- [坐标系] UE: Z-Up 左手系 (X=前 Y=右 Z=上)
- [坐标系] Maya: Y-Up 右手系 (X=右 Y=上 Z=屏幕外)
- [坐标系] Max: Z-Up 右手系 (X=右 Y=屏幕里 Z=上)
- [MCP端口] UE:8080, Maya:8081, Max:8082
- [Session] UE=agent/ue-editor, Maya=agent/maya-editor, Max=agent/max-editor
- [UI技术] UE 用 Slate+C++，DCC 用 Qt+纯Python (PySide2/Qt 5.15)
- [回传方式] UE 用文件轮询(stream.jsonl)，DCC 用 Qt signal/slot
- [Gateway] OpenClaw 端口 18789，LobsterAI 端口 18790
- [Skills目录] OpenClaw: ~/.openclaw/workspace/skills/，LobsterAI: %APPDATA%/LobsterAI/SKILLs/
