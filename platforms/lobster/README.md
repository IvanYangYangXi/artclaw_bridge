# LobsterAI平台适配层

**状态**: ✅ Phase 10.1-10.2 已完成  
**日期**: 2026-04-03

---

## 快速开始

### 安装

```bash
# 安装时指定 LobsterAI平台
python install.py --platform lobster
```

### 配置 MCP Server

```bash
# 自动配置 LobsterAI MCP Server
python platforms/lobster/setup_lobster_mcp.py
```

或手动配置：
1. 打开 LobsterAI 客户端
2. 设置 → MCP 服务
3. 添加 MCP 服务
   - 名称：`artclaw-ue`
   - 传输类型：`stdio`
   - 命令：`python`
   - 参数：`D:\MyProject_D\artclaw_bridge\platforms\common\artclaw_stdio_bridge.py --port 8080`
4. 保存并重启 LobsterAI

### 测试

在 LobsterAI 聊天中：
```
使用 run_ue_python 执行：print("Hello from ArtClaw!")
```

---

## 平台切换

### 查看当前平台

```bash
python platforms/common/switch_platform.py --status
```

### 切换到 LobsterAI

```bash
python platforms/common/switch_platform.py --to lobster
```

### 切换到 OpenClaw

```bash
python platforms/common/switch_platform.py --to openclaw
```

---

## 目录结构

```
platforms/lobster/
├── README.md                          # 本文件
├── __init__.py                        # Python 包标记
├── setup_lobster_mcp.py               # MCP 配置注入脚本
└── lobster_chat.py                    # LobsterAI 聊天桥接层

platforms/common/                      # 公共组件（所有平台共享）
├── artclaw_stdio_bridge.py            # stdio→WebSocket MCP 桥接器
└── switch_platform.py                 # 平台切换脚本
```

---

## 配置说明

### bridge_config.py 配置

```python
"lobster": {
    "gateway_url": "http://127.0.0.1:18790",
    "mcp_port": 8080,
    "skills_installed_path": "~/.openclaw/skills",
    "mcp_config_path": "%APPDATA%/LobsterAI/openclaw/state/openclaw.json",
    "mcp_config_via_ui": True,  # 需通过客户端界面配置
},
```

### MCP 连接方式

```
LobsterAI 客户端
  ↓ stdio
artclaw_stdio_bridge.py
  ↓ WebSocket (ws://127.0.0.1:8080)
UE MCP Server
```

---

## 已知问题

1. **配置同步**：LobsterAI 使用集中式 MCP 管理，直接编辑配置文件可能无效
2. **插件 ID 警告**：启动时有 `plugin id mismatch` 警告（不影响功能）
3. **DCC 内嵌面板**：当前只能在 LobsterAI 客户端操作，DCC 内嵌面板未集成

---

## 参考文档

- [LobsterAI-MCP-配置指南.md](../../docs/features/LobsterAI-MCP-配置指南.md)
- [LobsterAI平台接入方案.md](../../docs/features/LobsterAI平台接入方案.md)
- [Phase 10 问题诊断与修正方案.md](../../docs/features/Phase 10 问题诊断与修正方案.md)

---

## 变更记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-03 | v1.0 | 初始版本 |
| 2026-04-03 | v1.1 | Phase 10.1-10.2 完成，添加配置和切换脚本 |
