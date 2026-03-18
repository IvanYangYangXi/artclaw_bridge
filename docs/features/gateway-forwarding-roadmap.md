# OpenClaw Gateway 转发流程 — 开发路线图

> **目标**：将 UE Chat Panel ↔ OpenClaw Gateway ↔ AI Agent ↔ MCP Server 的完整转发链路从"能用"打磨到"好用、稳定、可维护、可复用"。
>
> **前提**：当前转发流程已跑通（阶段 3.7），本路线图聚焦于**加固、优化、DCC 复用、部署体验**。

---

## 当前状态盘点

### ✅ 已完成

| 组件 | 文件 | 状态 |
|------|------|------|
| UE 内 MCP Server | `mcp_server.py` (~32KB) | 稳定运行，22 个 MCP 工具 |
| OpenClaw Gateway Bridge | `openclaw_bridge.py` (~46KB) | 基本功能完成，含断连重连/流式/cancel |
| mcp-bridge 插件 | `mcp-bridge/index.ts` (~11KB) | 稳定，自动重连+ping keepalive |
| C++ Chat Panel | `UEAgentDashboard.cpp` (~60KB) | 含 /connect /disconnect /cancel /status |
| 部署文档 | `openclaw-mcp-bridge/README.md` | 完整步骤，含配置模板 |

### 🔶 已知问题

1. **启动时序**：Gateway 先启动但 UE 没开 → mcp-bridge 工具标记为 unknown → 需重启 Gateway
2. **数据回传**：Python → 临时文件 → C++ FTSTicker 轮询，延迟 ~500ms，不够优雅
3. **会话管理**：session_key 管理简陋，/new 靠清空 key 实现
4. **openclaw_bridge.py 体积**：46KB 单文件过大，混杂通信/诊断/上下文收集
5. **C++ Dashboard 耦合**：60KB 中约 200 行直接调用 Python bridge 函数，无抽象层
6. **DCC 复用性**：openclaw_bridge.py 内含 UE 特有逻辑（unreal 模块引用），Maya/Max 无法直接用

---

## 阶段划分

### 阶段 G1：加固与稳定性 (Hardening) ✅

> **目标**：解决已知痛点，让转发链路在生产环境中可靠运行
> **实际工时**：~2 小时 | **完成日期**：2026-03-18

- [x] **G1.1 启动时序修复 — mcp-bridge 延迟发现** ✅
  - mcp-bridge 插件初始连接失败不再阻塞，后台自动重试
  - 重连后通过 `onToolsDiscovered` 回调自动注册工具
  - 工具执行时检查连接状态，离线返回友好中文错误
  - 插件版本 1.0.0 → 1.1.0

- [x] **G1.2 连接状态同步强化** ✅
  - Python bridge 连接/断连/关闭时写入 `_bridge_status.json`
  - C++ Dashboard 新增 `BridgeStatusPollHandle` 持续轮询（2s 间隔）
  - 状态变更自动更新 `UUEAgentSubsystem`（驱动图标颜色）

- [x] **G1.3 流式响应稳定性** ✅ (评估后确认现有机制已足够)
  - JSONL + 累积文本机制：中间 delta 丢失不影响最终显示
  - 不完整 JSON 行被 `FJsonSerializer::Deserialize` 静默跳过

- [x] **G1.4 错误消息本地化** ✅
  - `openclaw_bridge.py` 所有用户可见错误从英文改为中文
  - `[Error]` → `[错误]`, `[Connection lost]` → `[连接中断]` 等

---

### 阶段 G2：重构与解耦 (Refactoring) ✅

> **目标**：拆分大文件，抽象平台无关层，为 DCCClawBridge 复用做准备
> **实际工时**：~3 小时 | **完成日期**：2026-03-18

- [x] **G2.1 openclaw_bridge.py 拆分** ✅
  - 新增 `bridge_core.py` (20KB) — 平台无关 WebSocket 核心
  - 新增 `bridge_config.py` (1KB) — 配置加载
  - 新增 `bridge_diagnostics.py` (8KB) — 连接诊断
  - `openclaw_bridge.py` 从 46KB 瘦身至 13KB（UE 适配层）
  - 向后兼容：C++ 侧零改动

- [x] **G2.2 C++ 平台通信抽象层** ✅
  - 新增 `IAgentPlatformBridge` 接口（8 个方法）
  - 新增 `FOpenClawPlatformBridge` 实现
  - Dashboard 中不再出现 `openclaw_bridge` 字符串
  - 换平台只需实现新的 `IAgentPlatformBridge` 子类

- [x] **G2.3 mcp-bridge 插件增强** ✅
  - 健康指标追踪：reconnects / toolCallCount / toolErrorCount
  - 断连日志包含重连计数
  - dispose 时输出汇总统计
  - **现状**：Dashboard 直接拼 Python 字符串调用 bridge 函数
  - **方案**：新增 `IAgentPlatformBridge` C++ 接口
    ```cpp
    class IAgentPlatformBridge {
    public:
        virtual void Connect() = 0;
        virtual void Disconnect() = 0;
        virtual void SendMessage(const FString& Message) = 0;
        virtual bool IsConnected() const = 0;
        virtual void CancelCurrentRequest() = 0;
    };
    ```
  - **实现**：`FOpenClawBridge : IAgentPlatformBridge`，封装所有 Python ExecCommand 调用
  - **改动**：新增 `OpenClawBridge.h/.cpp`，Dashboard 改为持有 `IAgentPlatformBridge*`
  - **验收**：Dashboard 代码中不再出现 `openclaw_bridge` 字符串

- [ ] **G2.3 mcp-bridge 插件增强**
  - **新增功能**：
    - 动态工具刷新（配合 G1.1）
    - 工具变更通知日志
    - 连接健康指标暴露（连接数、重连次数、延迟）
  - **改动**：`mcp-bridge/index.ts`

---

### 阶段 G3：DCC 复用适配 (DCC Portability) ✅

> **目标**：将 bridge 通信层适配到 DCCClawBridge（Maya/Max），实现 DCC 共享同一套 Gateway 转发逻辑
> **实际工时**：~1 小时 | **完成日期**：2026-03-18

- [x] **G3.1 bridge_dcc.py — 通用 DCC 适配器** ✅
  - `DCCBridgeManager` 单例，Qt signal/slot 回传（替代文件轮询）
  - `_DCCBridgeLogger`: 路由到 Python logging
  - PySide2 可选: 无 Qt 环境自动降级为纯回调模式
  - 便捷函数: `connect` / `disconnect` / `is_connected` / `send_message` / `cancel`

- [x] **G3.2 mcp-bridge 多实例配置** ✅
  - 模板: `templates/multi-dcc-config.json` (UE + Maya)
  - 工具命名空间隔离: `mcp_ue-editor_xxx` / `mcp_maya-primary_xxx`

- [x] **G3.3 DCCClawBridge 集成测试** ✅
  - `tests/test_bridge_dcc.py`: 5 项测试全部通过
  - 验证导入链: bridge_config → bridge_core → bridge_diagnostics → bridge_dcc
  - 验证 Manager 单例 + 无 Qt 降级

---

### 阶段 G4：部署与体验优化 (Deployment & DX) ✅

> **目标**：降低部署门槛，提升开发者体验
> **实际工时**：~30 分钟 | **完成日期**：2026-03-18

- [x] **G4.1 一键部署脚本升级** ✅
  - `setup_openclaw_config.py`: 自动合并 mcp-bridge 配置到 openclaw.json
  - 支持 `--ue` / `--maya` / `--max` 多 DCC 组合 + 自定义端口
  - 安全操作: 写入前自动备份 + `--dry-run` 预览模式

- [x] **G4.2 连接诊断增强** ✅ (评估后确认现有 health_check.py 已覆盖)
  - `_check_openclaw_mcp_bridge`: 验证插件启用状态 + server 配置
  - 9 项全面检测已满足需求

- [x] **G4.3 OpenClaw Agent 配置模板** ✅
  - `templates/ue-single-config.json`: UE 单实例最小配置 + Agent system prompt + tools.allow
  - `templates/multi-dcc-config.json`: UE + Maya 多实例配置

---

## 时间线总览

```
全部在 2026-03-18 完成（单次 session）:

  G1 加固 ✅ → G2 重构 ✅ → G3 DCC复用 ✅ → G4 部署体验 ✅
  (~2h)         (~3h)         (~1h)          (~0.5h)
```

**实际总工时**：~6.5 小时（原预估 4 周）

---

## 文件改动影响矩阵

| 文件 | G1 | G2 | G3 | G4 | 说明 |
|------|:--:|:--:|:--:|:--:|------|
| `openclaw_bridge.py` | ✏️ | 🔄 拆分 | — | — | G2 后被拆为 5 个文件 |
| `mcp-bridge/index.ts` | ✏️ | ✏️ | ✅ 验证 | — | G1.1+G2.3 改动 |
| `UEAgentDashboard.cpp` | ✏️ | 🔄 重构 | — | — | G2.2 引入抽象层 |
| `UEAgentLocalization.cpp` | ✏️ | — | — | — | G1.4 新增文本对 |
| `health_check.py` | — | — | — | ✏️ | G4.2 新增检测项 |
| `bridge_core.py` | — | 🆕 | ✅ 复用 | — | G2.1 新增，G3 复用 |
| `bridge_dcc.py` | — | — | 🆕 | — | G3.1 新增 |
| `setup.bat/sh` | — | — | — | ✏️ | G4.1 升级 |

---

## 与其他路线图的关系

| 路线图 | 关系 |
|--------|------|
| UE 开发路线图 (阶段 0~4) | G 系列是对阶段 3.7 (Chat Bridge) 的深化 |
| DCCClawBridge 路线图 | G3 是 DCCClawBridge 阶段 2 (MCP通信) 的前置 |
| Skill 管理体系 | 无直接依赖，Skill 层完全平台无关 |

---

**版本**：1.1 | **创建**：2026-03-18 | **完成**：2026-03-18 | **作者**：小优
