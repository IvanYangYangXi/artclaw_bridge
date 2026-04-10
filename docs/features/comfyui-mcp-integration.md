# ComfyUI MCP 接入规划文档

> 创建日期: 2026-04-09  
> 作者: 小优 + Ivan  
> 状态: 规划阶段  
> 更新: 2026-04-09 23:51 — 架构方向调整（Ivan 反馈）

---

## 1. 目标

将 ComfyUI 作为 ArtClaw Bridge 的新 DCC 平台接入，实现：

1. **AI Agent 通过文字描述直接操作 ComfyUI** — 创建节点、连接节点、设置参数、执行 workflow、获取输出
2. **与现有 DCC 平台统一架构** — 复用 adapter + bridge_core + mcp_server + artclaw_ui
3. **交互入口为 OpenClaw 等 Agent 平台** — 不单独定制 UI，ComfyUI 内部不嵌入聊天面板

---

## 2. 架构决策

### 2.1 Ivan 的核心需求

> "希望能直接通过文字描述让 agent 直接操作 comfyUI 创建节点输出内容"

这意味着：
- 不是模板填参式操作（MeiGen 模式），而是**动态构建 workflow**
- Agent 需要能像操作 SD 节点图一样操作 ComfyUI 节点图
- 类比：SD 的 `run_python` → ComfyUI 的 `run_comfyui`

### 2.2 ComfyUI 与其他 DCC 的本质差异

| 维度 | Maya/Max/SD/SP/Blender | ComfyUI |
|------|----------------------|---------|
| 进程模式 | DCC 内嵌 Python → 同进程执行 | Web 服务 → HTTP API |
| 代码执行 | `exec()` 在 DCC 主线程 | 无原生 exec（除非自定义节点） |
| 操作粒度 | 单个 API 调用（创建节点、设参数…） | API 以 Workflow JSON 为单位提交 |
| UI 嵌入 | PySide2/Qt dock panel | Web UI (浏览器) |

### 2.3 接入方案：ComfyUI 自定义节点 + 外部 Bridge 进程（混合方案）

**核心思路**：在 ComfyUI 中安装一个轻量自定义节点（ArtClawBridge node），该节点提供 Python exec 能力 + WebSocket MCP Server，使得 Agent 可以通过 `run_python` 在 ComfyUI 进程内执行任意 Python 代码——**与 Maya/SD/Blender 完全同构**。

```
┌──────────────────────────────────────────────────────┐
│  OpenClaw Gateway                                     │
│    └── mcp-bridge plugin ←WebSocket→                  │
│                                                        │
│  ┌──────────────────────────────────────────────┐     │
│  │  ComfyUI 进程                                 │     │
│  │  ┌────────────────────────────────────┐      │     │
│  │  │  ArtClaw Bridge 自定义节点         │      │     │
│  │  │  ┌──────────────┐  ┌────────────┐  │      │     │
│  │  │  │  mcp_server   │  │ comfyui_   │  │      │     │
│  │  │  │  (WS :8087)   │  │ adapter    │  │      │     │
│  │  │  └──────────────┘  └────────────┘  │      │     │
│  │  │          │                │         │      │     │
│  │  │  ┌───────▼────────────────▼──────┐  │      │     │
│  │  │  │  bridge_core / bridge_dcc     │  │      │     │
│  │  │  └───────────────────────────────┘  │      │     │
│  │  └────────────────────────────────────┘      │     │
│  │                                               │     │
│  │  ComfyUI 内置模块（adapter 通过 import 访问） │     │
│  │  - nodes / folder_paths / execution           │     │
│  │  - comfy.model_management / comfy.utils        │     │
│  │  - PromptServer (server.py)                    │     │
│  └──────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

**为什么选这个方案**：
1. ✅ **与 DCC 架构同构** — 同样是 adapter + mcp_server + bridge_core，代码复用最大化
2. ✅ **支持 run_python** — Agent 可以 exec 任意代码操作 ComfyUI Python API
3. ✅ **可以动态构建 workflow** — 不限于模板填参，通过 Python API 创建/连接/设置节点
4. ✅ **不需要单独 UI** — 复用 OpenClaw 聊天（Discord/CLI/其他 Agent 平台）
5. ⚠️ 需要用户安装自定义节点 — 但 ComfyUI 装节点是标准操作，生态成熟

### 2.4 UI 策略

**不在 ComfyUI 内嵌入聊天面板**，原因：
- ComfyUI 的 UI 是 Web 前端（不是 Qt），嵌入 chat panel 需要写 JS 扩展，维护成本高
- Ivan 的需求是通过 OpenClaw 等 Agent 平台交互，不需要 ComfyUI 内部有聊天窗口
- artclaw_ui（PySide2 聊天面板）主要服务于 Maya/Max/SD/SP/Blender 这些有 Qt 环境的 DCC

**交互方式**：
- OpenClaw Discord / CLI 直接与 ComfyUI Bridge 通信
- 未来可选：ComfyUI Web 扩展显示连接状态/历史记录（但不是 MVP）

---

## 3. 开源方案分析与复用

### 3.1 MeiGen-AI-Design-MCP

| 维度 | 详情 |
|------|------|
| 语言 | TypeScript (Node.js MCP Server) |
| 核心 | `ComfyUIProvider`：HTTP POST `/prompt` → poll `/history` → download `/view` |
| Workflow 管理 | 模板 CRUD + `detectNodes` 自动检测关键节点 |
| 参考图 | 上传 `/upload/image` → 注入 LoadImage 节点 |
| **可复用** | ⭐ ComfyUI HTTP API 交互模式（Python 重写）<br>⭐ `detectNodes` 节点检测算法<br>⭐ Workflow 模板 CRUD<br>⭐ 图片上传 + 注入逻辑 |
| **不能用** | TypeScript 实现 / 定位是模板填参不是动态构建 |

### 3.2 Pixelle-MCP

| 维度 | 详情 |
|------|------|
| 语言 | Python (fastmcp) |
| 核心 | "一个 workflow = 一个 MCP Tool"，DSL 声明参数 |
| **可复用** | ⭐ ComfyUI API Python 交互参考 |
| **不能用** | 依赖太重 / DSL 侵入性 / 独立产品定位 |

### 3.3 复用策略总结

**从 MeiGen 移植到 Python（作为 ComfyUI adapter 的 HTTP 客户端层）**：

| 模块 | MeiGen 来源 | 用途 |
|------|------------|------|
| `ComfyUIClient` | `ComfyUIProvider` class | HTTP API 封装：submit/poll/download/upload/models/queue |
| `WorkflowStore` | workflow file management | Workflow 模板 CRUD |
| `detect_nodes()` | `detectNodes()` | 自动检测 sampler/prompt/checkpoint/loadimage 等 |
| `get_editable_nodes()` | `getEditableNodes()` | 列出可编辑参数 |

**在此基础上自研**：
- `comfyui_adapter.py` — 继承 `BaseDCCAdapter`，提供 `execute_code()` + ComfyUI API
- ComfyUI Python API 封装（通过 exec 在进程内直接操作节点图）
- Skill 体系

---

## 4. ComfyUI Adapter 设计

### 4.1 核心实现

```python
# adapters/comfyui_adapter.py

class ComfyUIAdapter(BaseDCCAdapter):
    """
    ComfyUI 适配层
    
    在 ComfyUI 进程内运行（作为自定义节点加载）。
    通过 import ComfyUI 内部模块直接操作：
    - nodes: 节点注册表
    - execution: 执行引擎
    - folder_paths: 模型/输出路径
    - server.PromptServer: 提交 workflow
    """
    
    def __init__(self):
        super().__init__()
        self._comfyui_url = "http://localhost:8188"  # 自身的 HTTP API
        self._client = ComfyUIClient(self._comfyui_url)  # 用于提交 workflow 等
    
    # ── BaseDCCAdapter 标准实现 ──
    
    def get_software_name(self) -> str:
        return "comfyui"
    
    def get_software_version(self) -> str:
        from comfyui_version import __version__
        return __version__
    
    def get_python_version(self) -> str:
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def execute_on_main_thread(self, fn, *args):
        # ComfyUI 的自定义节点代码本身就在事件循环线程
        # 但耗时操作（如生成）是异步的，需要 asyncio 调度
        return fn(*args)
    
    def get_selected_objects(self) -> list:
        # ComfyUI 无"选中"概念 → 返回当前 queue 状态
        return []
    
    def get_scene_info(self) -> dict:
        # 返回 ComfyUI 系统信息
        import comfy.model_management
        return {
            "type": "comfyui",
            "vram_total": comfy.model_management.get_total_memory(),
            "vram_free": comfy.model_management.get_free_memory(),
            "queue": self._get_queue_info(),
        }
    
    def get_current_file(self) -> str:
        return None  # ComfyUI 无"当前文件"概念
    
    def get_main_window(self):
        return None  # Web UI，无 Qt 窗口
    
    def register_menu(self, menu_name, callback):
        pass  # Web UI，无菜单
    
    # ── 代码执行（核心！与 SD/Maya 同构） ──
    
    def execute_code(self, code: str, context=None) -> dict:
        """
        在 ComfyUI 进程内执行 Python 代码。
        
        预注入变量：
        - S: [] (无选中概念)
        - W: None (无当前文件)
        - L: comfyui 辅助模块 (nodes, folder_paths, execution 等)
        - client: ComfyUIClient 实例 (HTTP API 封装)
        - submit_workflow: 便捷函数，提交 workflow JSON 并等待结果
        
        Agent 可以：
        1. 动态构建 workflow JSON 并提交执行
        2. 查询可用节点类型和参数
        3. 列出/管理模型文件
        4. 操作 ComfyUI 队列
        """
        # 与 SD/Maya adapter 相同的 exec() 模式
        ns = dict(self._exec_namespace)
        ns.update({
            "S": [],
            "W": None,
            "L": self._get_comfyui_lib(),
            "client": self._client,
            "submit_workflow": self._submit_and_wait,
        })
        if context:
            ns.update(context)
        
        output_buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output_buffer
        try:
            exec(code, ns)
            # 保存用户定义的变量到持久命名空间
            for k, v in ns.items():
                if k not in ("__builtins__", "S", "W", "L"):
                    self._exec_namespace[k] = v
            return {
                "success": True,
                "output": output_buffer.getvalue(),
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "output": output_buffer.getvalue(),
                "error": str(e),
            }
        finally:
            sys.stdout = old_stdout
```

### 4.2 Agent 可用的 ComfyUI Python API（通过 run_python exec）

```python
# === Agent 通过 run_python 可以执行的操作 ===

# 1. 查询可用节点类型
import nodes
all_nodes = nodes.NODE_CLASS_MAPPINGS
print(list(all_nodes.keys())[:20])  # ['KSampler', 'CheckpointLoaderSimple', ...]

# 2. 查询节点输入/输出 schema
node_info = nodes.NODE_CLASS_MAPPINGS["KSampler"]
print(node_info.INPUT_TYPES())  # {'required': {'model': ('MODEL',), 'seed': ('INT', {...}), ...}}
print(node_info.RETURN_TYPES)   # ('LATENT',)

# 3. 列出可用模型
import folder_paths
checkpoints = folder_paths.get_filename_list("checkpoints")
loras = folder_paths.get_filename_list("loras")
print(f"Checkpoints: {checkpoints}")
print(f"LoRAs: {loras}")

# 4. 动态构建并提交 workflow
workflow = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}
    },
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "a beautiful sunset", "clip": ["1", 1]}
    },
    "3": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "ugly, blurry", "clip": ["1", 1]}
    },
    "4": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 1024, "height": 1024, "batch_size": 1}
    },
    "5": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0], "seed": 42, "steps": 20, "cfg": 7.0,
            "sampler_name": "euler", "scheduler": "normal",
            "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]
        }
    },
    "6": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["5", 0], "vae": ["1", 2]}
    },
    "7": {
        "class_type": "SaveImage",
        "inputs": {"images": ["6", 0], "filename_prefix": "artclaw_gen"}
    }
}

result = submit_workflow(workflow)
print(f"Generated: {result['images']}")
# [IMAGE:/path/to/output.png]  ← 自动触发 ImageContent 返回

# 5. 查询队列状态
queue_info = client.get_queue_sync()
print(f"Running: {queue_info['queue_running']}, Pending: {queue_info['queue_pending']}")

# 6. 列出输出图片
import os
output_dir = folder_paths.get_output_directory()
recent = sorted(os.listdir(output_dir), key=lambda f: os.path.getmtime(os.path.join(output_dir, f)))[-5:]
print(recent)
```

### 4.3 MCP Tool: `run_comfyui` (唯一核心 Tool)

与 SD 的 `run_python` / UE 的 `run_ue_python` 对应：

```python
# mcp_server.py 中注册
{
    "name": "run_comfyui",
    "description": "Execute Python code in ComfyUI environment. "
                   "Pre-injected: L=comfyui lib (nodes, folder_paths, execution), "
                   "client=ComfyUIClient (HTTP API), "
                   "submit_workflow=submit and wait for result. "
                   "Use [IMAGE:path] to return images.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"}
        },
        "required": ["code"]
    }
}
```

**单一 Tool 的优势**（与 SD/Maya 一致）：
- Agent 通过 Skill 学习 ComfyUI API，不需要记忆多个 Tool 名
- 灵活度最高：可以做任何 ComfyUI Python API 允许的操作
- Skill 管理系统（official/marketplace/user）全部复用

---

## 5. 自定义节点结构

```
custom_nodes/
└── artclaw_bridge/              # ComfyUI 自定义节点包
    ├── __init__.py              # NODE_CLASS_MAPPINGS + WEB_DIRECTORY
    ├── artclaw_node.py          # ArtClawBridge 节点类（可选，占位用）
    ├── startup.py               # ComfyUI 启动时执行：启动 MCP Server
    ├── core/                    # 从 DCCClawBridge/core/ 复用
    │   ├── bridge_core.py       # (symlink 或 copy)
    │   ├── bridge_dcc.py
    │   ├── mcp_server.py
    │   ├── comfyui_client.py    # 新增：HTTP API 客户端
    │   ├── workflow_store.py    # 新增：Workflow 模板管理
    │   └── workflow_utils.py    # 新增：detect_nodes 等
    ├── adapters/
    │   ├── base_adapter.py      # (symlink 或 copy)
    │   └── comfyui_adapter.py   # 新增
    └── install.py               # ComfyUI-Manager 兼容安装脚本
```

### 5.1 `__init__.py`（ComfyUI 节点注册入口）

```python
"""ArtClaw Bridge - AI Agent integration for ComfyUI"""

# ComfyUI 加载自定义节点时执行此文件
# 我们不需要注册可见节点，只需要启动 MCP Server

from .startup import start_bridge

# 启动 Bridge（在 ComfyUI 事件循环就绪后）
start_bridge()

# ComfyUI 要求导出这些，可以为空
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
```

### 5.2 `startup.py`（启动 MCP Server）

```python
"""在 ComfyUI 启动时启动 ArtClaw Bridge MCP Server"""

import threading
import logging

logger = logging.getLogger("artclaw.comfyui")

def start_bridge():
    """启动 MCP WebSocket Server（后台线程）"""
    from .adapters.comfyui_adapter import ComfyUIAdapter
    from .core.mcp_server import MCPWebSocketServer
    
    adapter = ComfyUIAdapter()
    adapter.on_startup()
    
    # MCP Server 在独立线程运行（与 SD/Maya 相同模式）
    server = MCPWebSocketServer(adapter, port=8087)
    thread = threading.Thread(target=server.run_forever, daemon=True)
    thread.start()
    
    logger.info("ArtClaw Bridge started on ws://127.0.0.1:8087")
```

---

## 6. Skill 体系

### 6.1 核心 Skills

| Skill 名 | 功能 | 优先级 |
|----------|------|--------|
| `comfyui-operation-rules` | 通用操作规则（必读）— 节点图构建方法、workflow JSON 格式、API 使用约束 | P0 |
| `comfyui-context` | 查询 ComfyUI 状态 — 系统信息、可用模型、队列状态、可用节点 | P0 |
| `comfyui-workflow-builder` | 动态构建 workflow JSON — 节点类型参考、连接语法、常用 pipeline 模板 | P0 |
| `comfyui-txt2img` | 文生图标准流程 — checkpoint + CLIP + KSampler + VAEDecode + SaveImage | P1 |
| `comfyui-img2img` | 图生图 + ControlNet 工作流 | P1 |
| `comfyui-node-catalog` | 常用节点速查 — class_type + 输入输出 + 用途 | P1 |

### 6.2 operation-rules 核心规则

```markdown
## 执行流程
1. 查询环境：可用模型、可用节点、系统资源
2. 构建 workflow JSON：根据用户需求组装节点图
3. 提交执行：submit_workflow(workflow) 
4. 获取输出：等待完成 → 返回生成图片（[IMAGE:path]）
5. 视觉分析：查看生成结果 → 判断是否需要调整参数

## 节点连接语法
- ComfyUI workflow JSON 中，节点输入引用格式: ["node_id", output_index]
- 例: "model": ["1", 0] 表示引用节点 1 的第 0 个输出

## 关键约束
- 先 `nodes.NODE_CLASS_MAPPINGS` 确认节点存在，不要猜
- 先 `node.INPUT_TYPES()` 查询参数 schema，不要猜参数名
- 模型名必须从 `folder_paths.get_filename_list()` 获取，不要猜
- seed 用随机数，除非用户指定
```

---

## 7. 端口分配

| DCC | MCP 端口 |
|-----|---------|
| UE | 8080 |
| Maya | 8081 |
| Max | 8082 |
| **ComfyUI** | **8087** |
| SD | 动态 |
| SP | 动态 |
| Blender | 动态 |
| Houdini | 动态 |

---

## 8. 开发计划

### Phase 1: ComfyUI 自定义节点 + Adapter (3天) ✅ 完成

- [x] `adapters/comfyui_adapter.py` — 继承 BaseDCCAdapter，实现 execute_code
- [x] `core/comfyui_client.py` — ComfyUI HTTP API 封装（从 MeiGen 移植）
- [x] `core/workflow_store.py` — Workflow 模板 CRUD（从 MeiGen 移植）
- [x] `core/workflow_utils.py` — detect_nodes / get_editable_nodes（从 MeiGen 移植）
- [x] `ComfyUIClawBridge/` — ComfyUI 自定义节点包结构
- [x] `startup.py` — MCP Server 启动逻辑
- [ ] 验证：ComfyUI 启动后自动加载 → MCP Server 可连接

### Phase 2: MCP 集成 + 端到端 (2天) ✅ 大部分完成

- [x] mcp_server.py 复用 `run_python` Tool（ComfyUI 与其他 DCC 共用）
- [x] OpenClaw 配置模板 `platforms/openclaw/config/comfyui-config.json`
- [x] setup_openclaw_config.py 新增 `--comfyui` 选项
- [x] bridge_dcc.py `_PREFIX_MAP` 新增 comfyui
- [x] [IMAGE:] 标记支持（复用现有 _parse_image_markers）
- [ ] 端到端测试：OpenClaw → run_python → 查询节点 / 构建 workflow / 生成图片

### Phase 3: Skill 体系 (2天) ✅ 完成

- [x] `comfyui-operation-rules` SKILL.md (138行，priority 100)
- [x] `comfyui-context` SKILL.md (163行)
- [x] `comfyui-workflow-builder` SKILL.md (158行，priority 90)
- [x] `comfyui-txt2img` SKILL.md (200行)

### Phase 4: 安装部署 (1天) ✅ 完成

- [x] install.py 支持 `--comfyui` + `--comfyui-path` 安装目标
- [x] install_dcc_ext.py 新增 install_comfyui / uninstall_comfyui
- [x] ComfyUI-Manager 兼容（install.py in ComfyUIClawBridge）
- [x] 文档：comfyui-install-guide.md

### Phase 5: 增强 (后续)

- [ ] WebSocket 实时进度推送（ComfyUI 原生 ws:// 的进度事件转发）
- [ ] 预置 workflow 模板库（txt2img / img2img / controlnet / inpainting）
- [ ] ComfyUI Web 扩展（可选）— 显示 ArtClaw 连接状态
- [ ] 图片预览回传（save_preview 类似 SD 的实现）

---

## 9. 与其他 DCC 对照

| 维度 | UE | Maya/Max | SD/SP | Blender | **ComfyUI** |
|------|-----|---------|-------|---------|-------------|
| 连接方式 | 同进程 C++ | 同进程 Python | 同进程 Python | 同进程 Python | **同进程 Python（自定义节点）** |
| 核心 Tool | run_ue_python | run_python | run_python | run_python | **run_comfyui** |
| 主线程调度 | Slate Tick | QTimer | QTimer | bpy.timers | **asyncio 事件循环** |
| MCP 端口 | 8080 | 8081/8082 | 动态 | 动态 | **8087** |
| UI | UE Slate | Qt dock | Qt dock | Qt dock(独立窗) | **无（OpenClaw 交互）** |
| 预注入 L | unreal | cmds/pymel | sd | bpy | **nodes/folder_paths/execution** |

---

## 10. 从 MeiGen 移植的模块清单

| Python 目标文件 | MeiGen TS 来源 | 移植范围 |
|----------------|---------------|---------|
| `core/comfyui_client.py` | `src/lib/providers/comfyui.ts` → `ComfyUIProvider` | HTTP 方法: submit_prompt / poll_history / get_image / upload_image / list_checkpoints / get_queue / cancel / clear |
| `core/workflow_store.py` | `src/lib/providers/comfyui.ts` → workflow file mgmt | list / load / save / delete / exists |
| `core/workflow_utils.py` | `src/lib/providers/comfyui.ts` → `detectNodes` + `getWorkflowSummary` + `getEditableNodes` | fuzzy class_type 匹配 + 可编辑参数列出 |

---

## 11. 风险与待定项

| 风险 | 影响 | 缓解 |
|------|------|------|
| ComfyUI 自定义节点加载时序 | MCP Server 启动可能早于 ComfyUI 完全就绪 | 延迟启动（等 PromptServer.instance 可用） |
| ComfyUI 版本差异 | 内部 API（nodes/execution）可能变化 | 版本检测 + 防御性 import |
| exec 安全性 | 与其他 DCC 同等风险 | 信任本地 Agent，与 SD/Maya 一致策略 |
| 长时间生成 | KSampler 执行可能几分钟 | submit_workflow 异步等待 + 超时配置 |
| 多用户/多 Agent 并发 | ComfyUI queue 是串行的 | queue 排队是正确行为，不需要特殊处理 |
| ComfyUI-Manager 兼容 | 需要 install.py 符合规范 | 参考主流自定义节点的 install.py 写法 |
