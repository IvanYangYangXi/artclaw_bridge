# UE Editor Agent - MCP 模块开发技术文档

## 1. 架构定位 (Positioning)
在本项目中，**MCP (Model Context Protocol)** 是连接 OpenClaw（大脑）与 Unreal Engine（身体）的标准化通信层。
- **标准化接口**：取代碎片化的自定义 JSON 协议，让 LLM 能够通过标准化的 `ListTools` 和 `CallTool` 协议自动发现并调用 UE 功能。
- **双向感知**：不仅能下发指令（Tools），还能让 AI 实时拉取场景状态、资产元数据等上下文（Resources）。

## 2. 核心概念在 UE 中的映射 (Mapping)

### 2.1 MCP Resources (数据感知层)
将 UE 引擎的内部状态定义为 URI 资源，供 AI 随时检索：
- `unreal://content/browser/selected`: 返回当前选中的资产信息。
- `unreal://level/outliner/all`: 获取当前场景所有 Actor 的层级列表。
- `unreal://project/settings`: 获取当前项目的渲染/物理等配置。

### 2.2 MCP Tools (原子动作层)
将 **UE Python API** 封装为具名工具。
- **基础级**: `spawn_actor`, `set_transform`, `delete_actor`。
- **逻辑级**: `smart_layout` (自动布局), `material_swapper` (材质替换)。
- **万能钥匙**: `execute_python_script` (允许 AI 编写并执行一段临时的 Python 代码)。

### 2.3 MCP Prompts (引导模板层)
预设的对话模板，帮助模型更好理解 UE 开发术语：
- `blueprint_assistant`: 专注于辅助蓝图逻辑编写的提示词集。
- `scene_refactor`: 指导 AI 如何优化关卡性能的规则集。

## 3. 高效集成方案：Python 自动化映射

为了最大化利用 **UE Python API**，采用“**元数据驱动**”的开发模式，避免手动编写大量的 MCP Schema。

### 3.1 装饰器实现原理
通过 Python 装饰器，将现有的 Python 函数自动注册为 MCP Tool。

```python
# UE 插件内部映射逻辑 (Python 示例)
class UEMCPRegistry:
    def __init__(self):
        self.tools_schema = []

    def register_tool(self, name: str):
        def decorator(func):
            # 自动提取函数签名和 Docstring 生成 MCP JSON Schema
            schema = {
                "name": name,
                "description": func.__doc__,
                "inputSchema": self._parse_to_json_schema(func)
            }
            self.tools_schema.append(schema)
            return func
        return decorator

# 开发一个新功能只需：
@ue_agent.register_tool(name="move_actor")
def move_actor(actor_id: str, offset_x: float, offset_y: float):
    """
    平移指定的 Actor。
    :param actor_id: Actor 的唯一标识名
    """
    import unreal
    # 调用 UE 原生 Python 库
    actor = unreal.find_object(None, actor_id)
    if actor:
        location = actor.get_actor_location()
        actor.set_actor_location(location + unreal.Vector(offset_x, offset_y, 0), False, True)
        return "Moved successfully"
```

## 4. 开发工作量优化 (WLM Optimization)


| 模块 | 开发策略 | 工作量等级 |
| :--- | :--- | :--- |
| **通信网关** | 基于 WebSocket 实现 MCP 协议握手，建立 C++ 与 OpenClaw 的连接。 | 中 |
| **Resource 映射** | 编写 3-5 个核心 Python 函数，遍历场景并转为 JSON 供 AI 读取。 | 低 |
| **Tool 自动化** | 编写装饰器逻辑，后续 90% 的功能只需写标准的 Python 函数。 | 低 |
| **C++ 穿透** | 仅针对 Python 无法操作的底层数据（如像素、Slate 句柄）封装 C++ 接口。 | 中 |

## 5. 分发与分享机制 (Distribution)
- **技能打包**：将 Python 脚本与对应的 `mcp_config.json` 打包。
- **OpenClaw 联动**：在 OpenClaw 中配置该 MCP Server 路径，AI 即可瞬间获得对该 UE 版本的操控权限。
- **团队同步**：通过 Git 管理 `Content/Python` 目录，团队成员拉取后，AI 技能库同步更新。

---
**提示**：推荐先实现一个“万能 Python 执行器” MCP Tool，通过 OpenClaw 观察 AI 生成代码的准确度，再逐步将高频代码封装为固定的原子 Tool 以提升稳定性和安全性。
