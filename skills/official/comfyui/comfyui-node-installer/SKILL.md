---
name: comfyui-node-installer
description: >
  ComfyUI 缺失自定义节点自动检测与安装。
  Use when AI needs to: (1) install missing custom nodes for a workflow,
  (2) check if required nodes are available,
  (3) search and install node packages from ComfyUI registry.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.2.0
    author: ArtClaw
    dcc: comfyui
    priority: 98
---

# ComfyUI 节点安装器

> 自动检测 workflow 所需的自定义节点，并从 ComfyUI-Manager 或 GitHub 安装。

---

## 预注入变量

`run_python` 已注入以下变量，**直接使用，无需 import**：

| 变量 | 类型 | 说明 |
|------|------|------|
| `S` | `[]` | 无选中概念 |
| `W` | `None` | 无当前文件概念 |
| `L` | ComfyUI Lib | `L.nodes`, `L.folder_paths` |
| `nodes` | module | 节点注册表 |
| `client` | ComfyUIClient | HTTP API 客户端（含 Manager API） |

---

## 核心功能

### 1. 检测缺失节点

```python
from comfyui_node_installer import diagnose_workflow

# 诊断当前 workflow
wf = {...}  # workflow JSON
report = diagnose_workflow(wf)

print(report)
# {
#   "status": "missing_found",
#   "missing_count": 3,
#   "missing": [
#     {
#       "node_id": "15",
#       "node_type": "ComfyrollStudio",
#       "package": "ComfyUI_Comfyroll_CustomNodes",
#       "install_url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"
#     },
#     ...
#   ],
#   "available": [...],
#   "suggestions": [...]
# }
```

### 2. 安装缺失节点

```python
from comfyui_node_installer import install_missing_nodes

# 自动安装所有缺失节点
result = install_missing_nodes(wf)
print(result)
# {
#   "success": True,
#   "installed": ["ComfyUI_Comfyroll_CustomNodes"],
#   "failed": [],
#   "reboot_required": True  # 需要重启 ComfyUI
# }
```

### 3. 搜索节点包

```python
from comfyui_node_installer import search_packages

# 搜索节点包
results = search_packages("controlnet")
print(results)
# [
#   {
#     "title": "ComfyUI ControlNet Aux",
#     "reference": "https://github.com/Fannovel16/comfyui_controlnet_aux",
#     "author": "Fannovel16",
#     "install_type": "git-clone",
#     "description": "Preprocessors for ControlNet"
#   },
#   ...
# ]
```

---

## 完整使用流程

### 场景1: 加载 workflow 时自动修复

```python
# 1. 加载 workflow
wf = load_template("marketplace/awesome-portrait-v2")

# 2. 诊断缺失节点
diagnosis = diagnose_workflow(wf)

if diagnosis["missing_count"] > 0:
    print(f"发现 {diagnosis['missing_count']} 个缺失节点:")
    for m in diagnosis["missing"]:
        print(f"  - {m['node_type']} (来自: {m['package']})")
    
    # 3. 询问用户是否安装（或自动安装）
    result = install_missing_nodes(wf, auto_install=True)
    
    if result["reboot_required"]:
        print("⚠️ 需要重启 ComfyUI 才能使用新节点")
        print("请重启后重新加载此 workflow")
```

### 场景2: 手动安装特定节点包

```python
from comfyui_node_installer import install_package

# 通过 Git URL 安装
result = install_package(
    url="https://github.com/Fannovel16/comfyui_controlnet_aux",
    method="git-clone"
)

# 或通过 ComfyUI-Manager 安装
result = install_package(
    package_name="comfyui_controlnet_aux",
    method="manager"
)

print(result)
# {"success": True, "message": "Installation queued", "reboot_required": True}
```

---

## API 参考

### `diagnose_workflow(workflow: dict) -> dict`

检测 workflow 中使用的节点是否在系统中可用。

**参数**:
- `workflow`: Workflow JSON dict

**返回**:
```python
{
    "status": "ok" | "missing_found",
    "missing_count": int,
    "missing": [
        {
            "node_id": str,        # workflow 中的节点 ID
            "node_type": str,      # 节点类型名
            "package": str,        # 所属包名
            "install_url": str,    # 安装 URL
            "alternative": str     # 替代节点（如有）
        }
    ],
    "available": [str],            # 已可用的节点类型列表
    "suggestions": [               # 安装建议
        {
            "package": str,
            "nodes": [str],
            "install_url": str
        }
    ]
}
```

### `install_missing_nodes(workflow: dict, auto_install: bool = False) -> dict`

安装 workflow 所需的所有缺失节点。

**参数**:
- `workflow`: Workflow JSON
- `auto_install`: 是否自动安装（False 时只返回安装计划）

**返回**:
```python
{
    "success": bool,
    "installed": [str],        # 成功安装的包名
    "failed": [                 # 安装失败的包
        {"package": str, "error": str}
    ],
    "reboot_required": bool,   # 是否需要重启 ComfyUI
    "plan": [                  # 安装计划（auto_install=False 时）
        {"package": str, "url": str, "nodes": [str]}
    ]
}
```

### `search_packages(query: str, limit: int = 10) -> list`

搜索 ComfyUI 节点包。

**参数**:
- `query`: 搜索关键词
- `limit`: 最大返回数量

**返回**:
```python
[
    {
        "title": str,
        "reference": str,      # GitHub URL
        "author": str,
        "install_type": "git-clone" | "unzip",
        "description": str,
        "stars": int,
        "last_update": str
    }
]
```

### `install_package(url: str, method: str = "git-clone") -> dict`

安装单个节点包。

**参数**:
- `url`: GitHub URL 或包名
- `method`: "git-clone" | "manager" | "unzip"

**返回**:
```python
{
    "success": bool,
    "message": str,
    "reboot_required": bool
}
```

### `list_installed_packages() -> list`

列出已安装的节点包。

**返回**:
```python
[
    {
        "name": str,
        "version": str,
        "path": str,
        "enabled": bool
    }
]
```

### `uninstall_package(package_name: str) -> dict`

卸载节点包。

---

## 实现原理

### 节点类型检测

```python
def diagnose_workflow(workflow: dict) -> dict:
    """检测 workflow 中的节点类型是否可用"""
    
    # 1. 获取系统中所有可用节点
    available_nodes = set(nodes.NODE_CLASS_MAPPINGS.keys())
    
    # 2. 提取 workflow 中使用的节点类型
    used_types = set()
    for node_id, node_data in workflow.items():
        class_type = node_data.get("class_type")
        if class_type:
            used_types.add(class_type)
    
    # 3. 找出缺失的节点
    missing_types = used_types - available_nodes
    
    # 4. 查询节点包映射表
    missing_packages = []
    for node_type in missing_types:
        package_info = NODE_TYPE_TO_PACKAGE.get(node_type)
        if package_info:
            missing_packages.append({
                "node_type": node_type,
                "package": package_info["name"],
                "install_url": package_info["url"]
            })
    
    return {
        "status": "missing_found" if missing_packages else "ok",
        "missing": missing_packages,
        "available": list(used_types & available_nodes)
    }
```

### 节点包映射表

内置常用节点类型的包映射：

```python
NODE_TYPE_TO_PACKAGE = {
    # ControlNet
    "ControlNetApply": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/..."},
    "CannyEdgePreprocessor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/..."},
    
    # 动画
    "AnimateDiffLoader": {"name": "ComfyUI-AnimateDiff-Evolved", "url": "https://github.com/..."},
    
    # 工具节点
    "CR_Image_Panel": {"name": "ComfyUI_Comfyroll_CustomNodes", "url": "https://github.com/..."},
    
    # ... 更多映射
}
```

### ComfyUI-Manager 集成

如果用户安装了 ComfyUI-Manager，使用其 API：

```python
# 通过 Manager API 获取节点列表
def get_manager_node_list():
    response = client.manager_get("/customnode/getlist")
    return response.get("custom_nodes", [])

# 通过 Manager 安装节点
def install_via_manager(package_url: str):
    response = client.manager_post("/customnode/install", {
        "url": package_url
    })
    return response
```

---

## 注意事项

### ⛔ 重要限制

| 限制 | 说明 |
|------|------|
| 需要重启 | 安装新节点后需要重启 ComfyUI 才能使用 |
| 依赖安装 | 某些节点有 Python 依赖，可能需要 pip install |
| Manager 依赖 | 部分功能依赖 ComfyUI-Manager 安装 |

### ⚠️ 安全提示

- 只从可信来源安装节点（官方仓库、高星项目）
- 安装前检查节点代码（避免恶意脚本）
- 某些节点可能需要额外模型文件

---

## 与其他 Skill 的关系

```
comfyui-workflow-manager
    │
    ├── 加载模板 → 调用 diagnose_workflow 检查节点
    │           → 调用 install_missing_nodes 自动安装
    │
    └── 发布模板 → 记录所需节点包信息

comfyui-workflow-repair
    │
    └── 修复 workflow → 调用 diagnose_workflow 获取缺失信息
```

---

*Skill 版本: 0.1.0*
