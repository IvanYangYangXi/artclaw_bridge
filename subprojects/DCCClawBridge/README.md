# DCCClawBridge

Maya / 3ds Max 共享的 AI Agent 桥接插件，通过统一的 Qt 界面和薄适配层接入 ArtClaw MCP 体系。

## 架构

```
DCCClawBridge/
├── artclaw_ui/      # 通用 Qt 界面（Chat Panel + Skill 管理 + 状态栏）
├── adapters/        # DCC 薄适配层（Maya / Max 各一个）
├── core/            # 共享核心（MCP 通信 / Skill 运行时 / 命令队列）
├── skills/          # DCC 特有 Skill（maya/ / max/）
├── tests/           # 测试
└── resources/       # 图标/样式
```

## 首发平台

**Maya 2023** (Python 3.9.7 / PySide2 / Qt 5.15)

## 文档

- [概述](../../docs/DCCClawBridge/specs/概述.md)
- [系统架构设计](../../docs/DCCClawBridge/specs/系统架构设计.md)
- [开发路线图](../../docs/DCCClawBridge/specs/开发路线图.md)
