<!-- Ref: docs/specs/sdk-core-api-spec.md -->
# 共享核心模块 API 规范

> 定义 `core/` 目录下各模块的公开 API 接口。
> 索引文档：[SDK/API 标准化总览](./sdk-api-standardization-overview.md)

## 概述

`core/` 目录是项目的单一源（Single Source），部署到所有 DCC。
所有模块必须保持平台无关性，不依赖任何特定 DCC 或 Agent 平台。

### 模块清单

| 模块 | 行数 | 职责 |
|------|------|------|
| `bridge_core.py` | ~350 | WebSocket RPC 客户端 |
| `bridge_config.py` | ~300 | 配置加载与平台路由 |
| `bridge_diagnostics.py` | ~150 | 连接诊断 |
| `health_check.py` | ~300 | 环境健康检查 |
| `memory_core.py` | ~1000 | 三层记忆管理系统 |
| `retry_tracker.py` | ~150 | 工具调用失败追踪 |
| `skill_sync.py` | ~400 | Skill 源↔运行时同步 |

## C1 — bridge_core.py

### 公开类：`OpenClawBridge`

```python
class OpenClawBridge:
    def __init__(self, gateway_url, agent_id, token, client_id,
                 logger, on_status_changed): ...

    # 连接管理
    def start(self) -> bool: ...
    def stop(self) -> None: ...
    def is_connected(self) -> bool: ...

    # 消息发送
    def send_message(self, message: str, timeout=1800.0) -> str: ...
    def send_message_async(self, message: str, callback) -> None: ...
    def cancel_current(self) -> None: ...

    # 会话管理
    def reset_session(self) -> None: ...
    def set_session_key(self, session_key: str) -> None: ...
    def get_session_key(self) -> str: ...

    # Agent 管理
    def get_agent_id(self) -> str: ...
    def set_agent(self, agent_id: str) -> None: ...
    def list_agents(self) -> list[dict]: ...
    def fetch_history(self, session_key: str, limit=50) -> list[dict]: ...

    # 用量查询
    def get_last_usage(self) -> dict: ...
```

### 回调注入点

```python
bridge.on_ai_message = lambda role, text: ...    # AI 消息流
bridge.on_ai_thinking = lambda id, text: ...     # 思考内容
bridge.on_usage_update = lambda usage: ...        # Token 用量
```

### 公开类：`BridgeLogger`

```python
class BridgeLogger:
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
    def debug(self, msg: str) -> None: ...
```

DCC 适配层可子类化 `BridgeLogger`，将日志路由到 DCC 输出窗口。

## C2 — bridge_config.py

### 公开函数

```python
def load_config() -> dict:
    """加载平台配置，优先级：构造参数 > artclaw.json > 平台配置 > 默认值"""

def get_gateway_url() -> str:
    """获取 Gateway URL（5 级回退查找）"""

def get_gateway_token() -> str:
    """获取认证 Token"""

def get_platform_type() -> str:
    """获取当前平台类型（openclaw/claude/lobster 等）"""

def get_available_platforms() -> list[dict]:
    """获取所有 visible=True 的已注册平台列表（供 UI ComboBox 使用）"""

def switch_platform(platform_type: str) -> bool:
    """热切换平台"""

def get_skill_checker_dirs() -> dict:
    """获取各 DCC 安装检测目录"""
```

> 📎 配置 JSON Schema 文件：`core/schemas/config.schema.json`（可用于 IDE 自动补全和配置验证）

### 配置 Schema（C2 待标准化）

> `_PLATFORM_DEFAULTS` 每条记录包含 `display_name`（UI 显示名）和 `visible`（是否在平台选择列表中可见）字段。
> `get_available_platforms()` 回退逻辑基于 `visible` 字段过滤（而非 `gateway_url` 是否非空）。

```json
{
  "$schema": "artclaw-config.schema.json",
  "platform": {
    "type": "string (enum: openclaw|claude|lobster|claudecode|cursor|workbuddy)",
    "gateway_url": "string (ws:// URL)",
    "token": "string"
  },
  "mcp": {
    "config_path": "string (文件路径)",
    "config_key": "string (JSON 键路径)"
  },
  "skills": {
    "installed_path": "string (目录路径)"
  },
  "disabled_skills": ["string"],
  "pinned_skills": ["string"],
  "last_agent_id": "string"
}
```

## C3 — memory_core.py

### 公开类：`MemoryManagerV2`

```python
class MemoryManagerV2:
    def __init__(self, storage_path: str, dcc_name: str = ""): ...

    # 读写操作
    def set(self, key: str, value: Any, tag: str = "fact",
            importance: float = 0.5, source: str = "") -> None: ...
    def get(self, key: str) -> Optional[MemoryEntry]: ...
    def delete(self, key: str) -> bool: ...

    # 搜索
    def search(self, query: str, limit: int = 10,
               tag: str = "") -> list[MemoryEntry]: ...
    def list_all(self, tag: str = "") -> list[MemoryEntry]: ...

    # 生命周期
    def flush(self) -> None: ...
    def get_briefing(self, max_entries: int = 20) -> str: ...
```

### 数据类：`MemoryEntry`

```python
class MemoryEntry:
    key: str
    value: Any
    tag: str        # fact/preference/convention/operation/crash/pattern/context
    importance: float  # 0.0 ~ 1.0
    source: str
    created_at: str
    last_accessed: str
    access_count: int
    expires_at: Optional[str]
    promoted_from: Optional[str]
```

### 三层存储

| 层 | TTL | 容量 | 说明 |
|----|-----|------|------|
| 短期 | 4 小时 | 200 条 | 最近操作和上下文 |
| 中期 | 7 天 | 500 条 | 规则、模式、教训 |
| 长期 | 永久 | 1000 条 | 事实、约定、关键知识 |

> 详细设计见：`docs/specs/记忆管理系统设计.md`

## C4 — bridge_diagnostics.py

### 公开函数

```python
def diagnose_connection(gateway_url: str = "",
                        token: str = "") -> str:
    """运行 6 项连接诊断，返回格式化报告"""
```

### 诊断项

1. `websockets` 包是否安装
2. Gateway URL 格式检查
3. TCP 端口可达性
4. 认证 Token 有效性
5. Client ID 白名单校验
6. WebSocket 握手测试

## C5 — health_check.py

### 公开函数

```python
def run_health_check() -> str:
    """运行 7 项环境检查，返回格式化报告"""
```

### 检查项

1. Python 环境（≥3.9）
2. 必需依赖包（websockets, pydantic）
3. DCC 环境（unreal/maya/bpy 等模块可用性）
4. MCP Server 端口（8080）
5. Gateway 可达性（18789）
6. MCP Bridge 插件注册
7. 文件系统权限

## C6 — retry_tracker.py

### 公开类：`RetryTracker`

```python
class RetryTracker:
    def on_tool_result(self, tool_name: str, code: str,
                       is_error: bool, error_msg: str,
                       result_text: str) -> Optional[str]: ...
    def set_memory_manager(self, mm: MemoryManagerV2) -> None: ...
    def clear(self) -> None: ...
```

### 行为

- 连续失败 ≥2 次 → 在 Memory 中搜索相关提示
- 失败后成功 → 提取教训存入 Memory
- 按 API 调用指纹（非代码哈希）识别"相同操作"

## C7 — skill_sync.py

### 公开函数

```python
def sync_skills() -> dict:
    """比较源与已安装 Skill，返回差异报告"""

def install_skill(skill_name: str) -> bool:
    """安装 Skill 到运行时目录"""

def uninstall_skill(skill_name: str) -> bool:
    """卸载 Skill"""

def get_skill_versions() -> dict:
    """检查 Skill 版本更新"""

def publish_skill(skill_name: str) -> bool:
    """发布 Skill（Git 提交）"""
```

## 文件长度说明

所有 `core/` 模块遵循代码规范：

- 黄金区间：100-300 行
- 硬性上限：500 行
- 例外：`memory_core.py` (~1000 行) 因三层存储复杂性超限，
  已在 `docs/specs/代码规范.md` 中记录豁免理由

> 参考：`docs/specs/代码规范.md`
