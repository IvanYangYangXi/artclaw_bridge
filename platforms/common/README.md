# ArtClaw Bridge 公共组件

**状态**: ✅ 已创建  
**日期**: 2026-04-03

---

## 目录结构

```
platforms/common/
├── README.md                          # 本文件
├── __init__.py                        # Python 包标记
├── artclaw_stdio_bridge.py            # stdio→WebSocket MCP 桥接器
└── switch_platform.py                 # 平台切换脚本
```

---

## 组件说明

### 1. artclaw_stdio_bridge.py

**功能**: stdio→WebSocket MCP 协议转换器

**用途**:
- 将 stdio MCP 请求转发到 WebSocket MCP Server
- 供 LobsterAI、Claude Desktop 等仅支持 stdio 的 MCP 客户端使用
- 不执行 Python 代码，只是协议转换

**用法**:
```bash
# 默认连接 UE MCP Server (ws://127.0.0.1:8080)
python platforms/common/artclaw_stdio_bridge.py

# 连接 Maya MCP Server (ws://127.0.0.1:8081)
python platforms/common/artclaw_stdio_bridge.py --port 8081

# 连接 Max MCP Server (ws://127.0.0.1:8082)
python platforms/common/artclaw_stdio_bridge.py --port 8082

# 自定义 WebSocket URL
python platforms/common/artclaw_stdio_bridge.py --url ws://host:port
```

**依赖**:
```bash
pip install websockets
```

**配置示例** (LobsterAI MCP 配置):
```
传输类型：stdio
命令：python
参数：platforms/common/artclaw_stdio_bridge.py --port 8080
```

### 2. switch_platform.py

**功能**: ArtClaw Bridge 平台切换脚本

**用途**:
- 在 OpenClaw 和 LobsterAI 之间切换
- 更新 ArtClaw 配置文件
- 发现 DCC 安装路径

**用法**:
```bash
# 查看当前平台
python platforms/common/switch_platform.py --status

# 切换到 LobsterAI
python platforms/common/switch_platform.py --to lobster

# 切换到 OpenClaw
python platforms/common/switch_platform.py --to openclaw

# 列出可用平台
python platforms/common/switch_platform.py --list

# 指定 UE 项目路径
python platforms/common/switch_platform.py --to lobster --ue-project D:/MyProject
```

---

## 平台目录结构

```
platforms/
├── common/                          # 公共组件（所有平台共享）
│   ├── artclaw_stdio_bridge.py
│   └── switch_platform.py
│
├── lobster/                         # LobsterAI平台特定组件
│   ├── README.md
│   └── setup_lobster_mcp.py        # LobsterAI MCP 配置脚本
│
└── openclaw/                        # OpenClaw 平台特定组件
    ├── README.md
    └── setup_openclaw_config.py    # OpenClaw 配置脚本
```

---

## 依赖安装

```bash
# 安装通用依赖
pip install websockets

# 或从 requirements.txt 安装
pip install -r requirements.txt
```

---

## 参考文档

- [LobsterAI-MCP-配置指南.md](../../docs/features/LobsterAI-MCP-配置指南.md)
- [LobsterAI平台接入方案.md](../../docs/features/LobsterAI平台接入方案.md)
- [Phase 10 验证报告.md](../../docs/features/Phase 10 验证报告.md)

---

## 变更记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-03 | v1.0 | 从 platforms/claude/ 和 scripts/ 迁移到 platforms/common/ |
