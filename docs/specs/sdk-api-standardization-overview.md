<!-- Ref: docs/specs/sdk-api-standardization-overview.md -->
# ArtClaw Bridge SDK/API 大纲指引

> **文档性质：** 大纲指引（入口导航）
> **适用读者：** 新接入方、集成开发者、想了解整体架构的成员
> **最后更新：** 2026 年 4 月

本文是 ArtClaw Bridge 标准化 SDK/API 体系的**统一入口**。阅读本文可以快速了解：

- 体系由哪几层构成
- 每层当前的接入状态
- 各模块（平台/DCC/Tool Manager/UE）是否已对齐标准接口
- 每个条目指向哪份详细文档或实现文件

---

## 体系层次一览

ArtClaw Bridge 的 SDK/API 分为四层，层间相互独立，可单独使用：

```
┌─────────────────────────────────────────────┐
│              Skill SDK 层  (S)               │  ← Tool/Skill 注册、manifest、生命周期
├─────────────────────────────────────────────┤
│         Agent 平台适配器层  (P)               │  ← AI 平台统一接口（OpenClaw/LobsterAI…）
├─────────────────────────────────────────────┤
│          DCC 插件接口层  (D)                  │  ← DCC 软件统一接口（Maya/UE/Blender…）
├─────────────────────────────────────────────┤
│            共享核心层  (C)                    │  ← 配置、版本、内存、日志等基础设施
└─────────────────────────────────────────────┘
```

| 前缀 | 层名称 | 核心文件入口 | 详细规范 |
|------|--------|------------|---------|
| **S** | Skill SDK | `core/skill_decorator.py` | [sdk-skill-spec.md](./sdk-skill-spec.md) |
| **P** | 平台适配器 | `core/interfaces/platform_adapter.py` | [sdk-platform-adapter-spec.md](./sdk-platform-adapter-spec.md) |
| **D** | DCC 插件接口 | `subprojects/DCCClawBridge/adapters/base_adapter.py` | [sdk-dcc-interface-spec.md](./sdk-dcc-interface-spec.md) |
| **C** | 共享核心 | `core/` | [sdk-core-api-spec.md](./sdk-core-api-spec.md) |

---

## 一、DCC 插件接口层（D）

> 详细规范：[DCC 接口标准化规范](./sdk-dcc-interface-spec.md)

**目标**：让所有 DCC 工具共享一套统一的插件接入契约（`BaseDCCAdapter`），上层业务逻辑无需感知具体 DCC。

### 核心接口

`BaseDCCAdapter`（`subprojects/DCCClawBridge/adapters/base_adapter.py`）定义了 **13 个抽象方法**，分 6 个职责组：

| 职责组 | 方法 | 说明 |
|--------|------|------|
| 基础信息 | `get_software_name()` `get_software_version()` `get_python_version()` | 返回 DCC 标识与版本 |
| 生命周期 | `on_startup()` `on_shutdown()` | 注册菜单/资源清理 |
| 主线程调度 | `execute_on_main_thread()` `execute_deferred()` | 场景 API 安全调用 |
| 上下文采集 | `get_selected_objects()` `get_scene_info()` `get_current_file()` | 场景上下文查询 |
| UI 集成 | `get_main_window()` `register_menu()` | 窗口与菜单集成 |
| 代码执行 | `execute_code()` | Python 代码执行器 |

另有 1 个非抽象方法：`clear_exec_namespace()`，清空持久化执行命名空间。

### 各 DCC 接入状态

所有受支持的 DCC 均已**完整继承 `BaseDCCAdapter`** 并实现全部方法：

| DCC | 适配器文件 | 主线程调度方案 | 状态 |
|-----|-----------|--------------|------|
| **Maya** | `adapters/maya_adapter.py` | `maya.utils.executeInMainThreadWithResult()` | ✅ |
| **3ds Max** | `adapters/max_adapter.py` | MaxPlus 内置，直接执行 | ✅ |
| **Blender** | `adapters/blender_adapter.py` | 自定义队列 + `bpy.app.timers`（50ms 轮询） | ✅ |
| **Houdini** | `adapters/houdini_adapter.py` | `hdefereval` 模块 | ✅ |
| **Substance Painter** | `adapters/substance_painter_adapter.py` | `QTimer.singleShot(0, ...)` | ✅ |
| **Substance Designer** | `adapters/substance_designer_adapter.py` | `threading.Lock` 序列化 | ✅ |
| **ComfyUI** | `adapters/comfyui_adapter.py` | 纯异步，直接执行 | ✅ |
| **Unreal Engine** | `adapters/ue_adapter.py` | 已在游戏线程，直接执行；支持 `unreal.call_deferred()` | ✅ |

> **说明**：主线程调度各 DCC 实现方案不同，是各自平台的最优实践，属于合理多态，而非不一致。

### 条目状态索引

| # | 条目 | 状态 | 参考文件 |
|---|------|------|---------|
| D1 | DCC Adapter 抽象基类 | ✅ 8 个 DCC 全部完整实现 13 个抽象方法 | `adapters/base_adapter.py` |
| D2 | MCP Server 初始化接口 | ✅ 各 DCC 驱动模式合理分化 | `core/mcp_server.py` |
| D3 | 主线程调度抽象 | ✅ 各 DCC 采用本地最优方案 | 见上表 |
| D4 | Tool 注册标准签名 | 🟡 装饰器（UE/CLI）与 `register_tool`（DCC）并存 | `skill_hub.py`；`mcp_server.py` |
| D5 | Tool Handler 返回值契约 | 🟡 约定一致，暂无运行时强制校验 | — |
| D6 | ExecutionContext 数据类 | ✅ 跨 DCC 通用定义 | `core/interfaces/execution_context.py` |
| D7 | 选择/上下文查询接口 | 🟢 ContextProvider 协议已定义 | — |
| D8 | 场景信息查询接口 | 🟢 返回字段尚不统一 | — |
| D9 | MCP Resources 支持 | ✅ 引擎专属扩展（UE） | — |
| D10 | UI 集成接口 | 🟢 三类已覆盖：Slate / Qt / Web | — |

---

## 二、Agent 平台适配器层（P）

> 详细规范：[平台适配器标准化规范](./sdk-platform-adapter-spec.md)

**目标**：将不同 AI 平台（OpenClaw、LobsterAI 等）统一抽象，上层业务逻辑无需感知具体平台。

### 核心接口

`PlatformAdapter`（`core/interfaces/platform_adapter.py`）定义了 **11 个方法**（10 个抽象 + 1 个属性）：

| 职责组 | 方法 | 说明 |
|--------|------|------|
| P2 连接管理 | `connect()` `disconnect()` `is_connected()` | 平台连接生命周期 |
| P3 消息发送 | `send_message()` `send_message_async()` `cancel_current_request()` | 同步/异步消息收发 |
| P5 会话管理 | `reset_session()` `set_session_key()` `get_session_key()` | 会话标识与重置 |
| P7 诊断 | `diagnose_connection()` | 返回可读的连接诊断报告 |
| 元信息 | `platform_type`（property） | 平台唯一标识符 |

可选覆盖（有默认空实现）：`get_agent_id()` `list_agents()` `set_agent()` `fetch_history()` `display_name`

### 各平台接入状态

| 平台 | 适配器文件 | 接入方式 | 状态 |
|------|-----------|---------|------|
| **OpenClaw** | `platforms/openclaw/openclaw_adapter.py` | 委托 `OpenClawBridge` + `openclaw_chat` | ✅ 完整实现 |
| **LobsterAI** | `platforms/lobster/lobster_adapter.py` | 组合 `OpenClawAdapter`（相同 Gateway 协议）+ `configure_mcp_servers()` | ✅ 完整实现 |
| **Claude Desktop** | `platforms/claude/claude_adapter.py` | stdio→MCP 桥接 | 🟡 POC，消息发送待实现 |

**适配器工厂**（`platforms/common/adapter_factory.py`）：统一注册入口，支持 `create_adapter(platform_type, **kwargs)` 和 `list_platforms()`。

### 条目状态索引

| # | 条目 | 状态 | 参考文件 |
|---|------|------|---------|
| P1 | PlatformAdapter 抽象基类 | ✅ 含完整抽象方法组（10 抽象 + 1 属性） | `core/interfaces/platform_adapter.py` |
| P2 | 连接管理标准接口 | ✅ OpenClaw / LobsterAI 完整实现 | `openclaw_adapter.py` |
| P3 | 消息发送标准接口 | ✅ OpenClaw / LobsterAI 完整实现 | `openclaw_adapter.py` |
| P4 | 流事件格式 StreamEvent | ✅ 枚举 + Schema 已定义 | `core/interfaces/stream_event.py` |
| P5 | 会话管理标准接口 | ✅ OpenClaw / LobsterAI 完整实现 | `openclaw_adapter.py` |
| P6 | Agent 管理接口 | 🟡 可选，OpenClaw 已实现主要方法 | `core/bridge_core.py` |
| P7 | 诊断/健康检查接口 | 🟡 各平台分别实现，未统一基类 | `core/bridge_diagnostics.py` |
| P8 | 平台配置 Schema | 🟡 `_PLATFORM_DEFAULTS` 无强类型 | `core/bridge_config.py` |
| P9 | MCP Tool 命名空间规范 | ✅ `mcp_{server}_{tool}` 模式 | `platforms/openclaw/gateway/index.ts` |
| P10 | 文件协议路径规范 | 🔴 硬编码 `_openclaw_*` 前缀 | `platforms/openclaw/openclaw_ws.py` |
| P11 | Gateway 插件接口规范 | 🟡 仅 TypeScript 实现，无独立文档 | `platforms/openclaw/gateway/index.ts` |

---

## 三、Skill SDK 层（S）

> 详细规范：[Skill SDK 标准化规范](./sdk-skill-spec.md)

**目标**：统一 Tool/Skill 的注册方式、元数据格式和生命周期管理，使 Skill 可跨平台、跨 DCC 复用。

### 核心接口

| 接口 | 文件 | 说明 |
|------|------|------|
| `@artclaw_tool` 装饰器 | `core/skill_decorator.py` | 平台无关的统一 Tool 注册，支持 type hints → JSON Schema 自动生成 |
| `manifest.json` Schema | `skills/manifest.schema.json` | Skill 元数据格式规范，支持 `jsonschema` 可选验证 |
| `check_skill_dependencies()` | `cli/artclaw_bridge/manifest.py` | 检查 Skill 依赖是否满足，返回缺失依赖列表 |
| Skill 分层加载 | `cli/artclaw_bridge/skill_hub.py` | `00_official > 01_team > 02_user > 99_custom`，高优先级覆盖低优先级 |
| 禁用状态持久化 | `~/.artclaw/config.json` | `disabled_skills` 列表，SkillHub 初始化时读取并过滤 |

### 条目状态索引

| # | 条目 | 状态 | 参考文件 |
|---|------|------|---------|
| S1 | manifest.json JSON Schema | ✅ 已创建并可用 | `skills/manifest.schema.json` |
| S2 | Skill 入口函数签名 | ✅ `@artclaw_tool` 标准化；`@ue_tool` 向后兼容 | `core/skill_decorator.py` |
| S3 | Skill 返回值 Schema | 🟡 约定存在，无运行时强制校验 | `docs/skills/SKILL_DEVELOPMENT_GUIDE.md` |
| S4 | 错误处理三层契约 | 🟡 文档描述，无运行时校验 | 同上 |
| S6 | Skill 依赖解析 | ✅ `check_skill_dependencies()` 已实现；加载时打 warning | `cli/artclaw_bridge/manifest.py` |
| S7 | Skill Enable/Disable 持久化 | ✅ 持久化 + 加载时过滤均已实现 | `cli/artclaw_bridge/skill_hub.py` |
| S8 | Skill 模板 | ✅ SKILL.md 规范 | `skills/templates/` |

> 注：原 S5（多 DCC Skill 适配模式）已取消，通用 Skill 直接使用 `software: universal` 标记。

---

## 四、共享核心层（C）

> 详细规范：[共享核心模块 API 规范](./sdk-core-api-spec.md)

**目标**：为所有层提供通用基础能力，避免重复实现。

### 核心模块

| 模块 | 文件 | 说明 |
|------|------|------|
| VersionManager | `core/version_manager.py` | 版本解析、比较、匹配；`install`/`publish`/`enable`/`disable`/`check_sync` 操作封装 |
| MemoryManagerV2 | `core/memory_core.py` | 三层存储（内存/文件/向量），跨 DCC 统一 |
| 配置中心 Schema | `core/schemas/config.schema.json` | `~/.artclaw/config.json` 的 JSON Schema 校验 |
| BridgeLogger | `core/bridge_core.py` | 已抽象，各模块适配不一致（低优先级） |
| 共享模块同步 | `install.py` | MD5 校验 + 部署，保证 `core/` 跨子项目一致 |
| 统一导出 | `core/__init__.py` | 公共符号统一导出入口 |

### 条目状态索引

| # | 条目 | 状态 | 参考文件 |
|---|------|------|---------|
| C1 | 核心模块 API 文档 | 🟡 有 docstring，无独立对外文档 | `core/*.py` |
| C2 | 配置中心 Schema 校验 | ✅ JSON Schema 已创建 | `core/schemas/config.schema.json` |
| C3 | Memory API 标准化 | ✅ 接口完整 | `core/memory_core.py` |
| C4 | 日志接口 BridgeLogger | 🟢 已抽象，适配不一致 | `core/bridge_core.py` |
| C5 | 安装部署接口 | ✅ 功能完整 | `install.py` |

---

## 五、已完成标准化的接口速查表

以下接口均处于**可用**状态，可直接参考或集成：

| 接口 | 参考文件 |
|------|---------|
| `BaseDCCAdapter` — DCC 适配器基类 | `subprojects/DCCClawBridge/adapters/base_adapter.py` |
| `PlatformAdapter` — 平台适配器基类 | `core/interfaces/platform_adapter.py` |
| `ExecutionContext` — 跨 DCC 执行上下文 | `core/interfaces/execution_context.py` |
| `StreamEvent` — 流事件枚举 + Schema | `core/interfaces/stream_event.py` |
| `create_adapter()` — 平台工厂 | `platforms/common/adapter_factory.py` |
| `@artclaw_tool` — Tool 注册装饰器 | `core/skill_decorator.py` |
| `check_skill_dependencies()` — 依赖检查 | `cli/artclaw_bridge/manifest.py` |
| Skill manifest JSON Schema | `skills/manifest.schema.json` |
| 配置中心 JSON Schema | `core/schemas/config.schema.json` |
| `VersionManager` — 版本管理 SDK | `core/version_manager.py` |
| Skill 分层加载（优先级规则） | `cli/artclaw_bridge/skill_hub.py` |
| 共享模块同步机制 | `install.py` + `docs/specs/共享模块同步保障方案.md` |
| OpenClaw 集成方案（Phase 0–4） | `docs/specs/openClaw集成方案.md` |
| MCP Tool 命名空间规范 | `platforms/openclaw/gateway/index.ts` |

---

## 六、如何接入

### 新增 AI 平台

1. 在 `platforms/<platform_name>/` 下新建包
2. 创建适配器类继承 `PlatformAdapter`，实现 9 个抽象方法
3. 在 `platforms/common/adapter_factory.py` 注册新平台
4. 参考：`platforms/openclaw/openclaw_adapter.py`（完整实现）、`platforms/lobster/lobster_adapter.py`（组合模式）

### 新增 DCC 支持

1. 在 `subprojects/DCCClawBridge/adapters/` 下新建 `<dcc>_adapter.py`
2. 继承 `BaseDCCAdapter`，实现 11 个抽象方法
3. 主线程调度参考同目录已有实现（各 DCC 选择本地最优方案）
4. 在 `subprojects/DCCClawBridge/core/mcp_server.py` 中注册新适配器

### 新建 Skill/Tool

1. 使用 `@artclaw_tool` 装饰器注册工具函数
2. 创建 `manifest.json` 声明元数据（使用 Schema 验证）
3. 放入 `skills/` 对应分层目录
4. 参考：`docs/skills/SKILL_DEVELOPMENT_GUIDE.md`

---

## 七、详细规范文档索引

| 文档 | 内容 |
|------|------|
| [DCC 接口标准化规范](./sdk-dcc-interface-spec.md) | `BaseDCCAdapter` 所有方法签名、字段定义、各 DCC 实现说明 |
| [平台适配器标准化规范](./sdk-platform-adapter-spec.md) | `PlatformAdapter` 所有方法签名、StreamEvent 格式、Gateway 协议 |
| [Skill SDK 标准化规范](./sdk-skill-spec.md) | `@artclaw_tool` 完整用法、manifest.json 字段规范、返回值 Schema |
| [共享核心模块 API 规范](./sdk-core-api-spec.md) | VersionManager、MemoryManager、BridgeLogger 完整 API 文档 |
| [Skill 开发指南](../skills/SKILL_DEVELOPMENT_GUIDE.md) | Skill 开发实践、错误处理、测试方式 |
| [项目概要说明](./项目概要说明.md) | 整体架构、子项目关系 |
| [代码规范](./代码规范.md) | 文件长度、命名、注释约定 |
| [AI 文档编写规范](./AI文档编写规范.md) | 文档结构、路径引用、标签规范 |