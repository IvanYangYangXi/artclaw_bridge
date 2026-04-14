---
name: comfyui-operation-rules
description: >
  ComfyUI 操作通用规则。所有 ComfyUI 操作前必读。
  Use when AI needs to: (1) perform any ComfyUI operation,
  (2) check post-operation best practices, (3) understand ComfyUI API constraints.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 100
---

# ComfyUI 操作规则

> 所有 ComfyUI 操作前必读。ComfyUI 无 Undo，操作不可逆。

---

## 🔴 执行流程（5 阶段）

| 阶段 | 内容 | 说明 |
|------|------|------|
| 1. 环境查询 | 查模型、节点类型、系统状态 | **不要猜！** |
| 2. 规划 | 确定节点链路、参数 | 先查 INPUT_TYPES() |
| 3. 构建 Workflow | 用 Python dict 逐步构建 | 增量构建，非一次性大 dict |
| 4. 提交执行 | `submit_workflow(wf)` | 同步等待，返回结果 |
| 5. 视觉验证 | `save_preview` 展示输出 | 必须让用户看到结果 |

---

## 🔴 预注入变量

`run_python` 已注入以下变量，**直接使用，无需 import**：

| 变量 | 类型 | 说明 |
|------|------|------|
| `S` | `[]` | 无选中概念（始终空） |
| `W` | `None` | 无当前文件概念 |
| `L` | ComfyUI Lib | `L.nodes`, `L.folder_paths`, `L.execution`, `L.server`, `L.model_management` |
| `nodes` | module | 节点注册表，`nodes.NODE_CLASS_MAPPINGS` |
| `folder_paths` | module | 模型/输出路径管理 |
| `client` | ComfyUIClient | HTTP API 客户端 |
| `submit_workflow` | func | 提交 workflow 并等待完成，返回 `{prompt_id, outputs, images}` |
| `save_preview` | func | 保存图片并输出 `[IMAGE:]` 标记 |

---

## 🔴 Workflow JSON 格式

```python
workflow = {
    "1": {                                    # 节点 ID（字符串）
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "sd_xl_base_1.0.safetensors"
        }
    },
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "a cat",
            "clip": ["1", 1]                  # 连接语法: ["源节点ID", 输出索引]
        }
    }
}
```

**连接语法**: `["source_node_id", output_index]` — 引用另一个节点的第 N 个输出（0-indexed）。

---

## 🔴 绝对禁止（Critical Rules）

| 规则 | 说明 |
|------|------|
| ⛔ NEVER 猜 class_type | 先查 `nodes.NODE_CLASS_MAPPINGS.keys()` 或 `client.get_object_info()` |
| ⛔ NEVER 猜参数名 | 先查 `nodes.NODE_CLASS_MAPPINGS["KSampler"].INPUT_TYPES()` |
| ⛔ NEVER 猜模型名 | 先查 `folder_paths.get_filename_list("checkpoints")` |
| ⛔ NEVER 硬编码 seed | 用 `import random; random.randint(0, 2**63)` 除非用户指定 |
| ⛔ NEVER 忘记展示结果 | 生成后必须 `save_preview` 让用户看到 |

---

## 🔴 代码拆分规则

**增量构建 workflow dict，不要一次性写一个巨大字面量。**

```python
# ✅ 推荐：逐步构建
wf = {}
wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}
wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}}
# ... 逐个添加

# ⛔ 避免：一次性巨大 dict（错误难定位）
```

**合理分组原则：**
- 调用1: 查询环境（模型列表、节点参数）
- 调用2: 构建 + 提交 workflow
- 调用3: 展示结果（save_preview）

---

## API 速查

### 查询类

```python
# 列出所有可用节点类型
print(list(nodes.NODE_CLASS_MAPPINGS.keys()))

# 查询特定节点的输入参数
info = nodes.NODE_CLASS_MAPPINGS["KSampler"].INPUT_TYPES()
print(info)  # {"required": {...}, "optional": {...}}

# 列出模型
print(folder_paths.get_filename_list("checkpoints"))
print(folder_paths.get_filename_list("loras"))
print(folder_paths.get_filename_list("vae"))

# 系统信息
print(client.get_system_stats())

# 队列状态
print(client.get_queue())

# VRAM
mm = L.model_management
print(f"Total: {mm.get_total_memory()/(1024**3):.1f}GB")
print(f"Free: {mm.get_free_memory()/(1024**3):.1f}GB")
```

### 执行类

```python
# 提交 workflow 并等待完成
result = submit_workflow(workflow)
# result = {"prompt_id": "xxx", "outputs": {...}, "images": [{filename, subfolder, type, node_id}]}

# 展示输出图片
for img in result["images"]:
    img_bytes = client.get_image(img["filename"], img["subfolder"], img["type"])
    save_preview(img_bytes, f"output_{img['node_id']}")

# 上传图片（用于 img2img）
with open("input.png", "rb") as f:
    uploaded = client.upload_image(f.read(), "input.png")
```

---

## 常用节点 class_type 速查

| 用途 | class_type | 输出 |
|------|-----------|------|
| 加载 Checkpoint | `CheckpointLoaderSimple` | MODEL(0), CLIP(1), VAE(2) |
| 文本编码 | `CLIPTextEncode` | CONDITIONING(0) |
| 空 Latent | `EmptyLatentImage` | LATENT(0) |
| 采样 | `KSampler` | LATENT(0) |
| VAE 解码 | `VAEDecode` | IMAGE(0) |
| VAE 编码 | `VAEEncode` | LATENT(0) |
| 保存图片 | `SaveImage` | — |
| 加载图片 | `LoadImage` | IMAGE(0), MASK(1) |
| LoRA | `LoraLoader` | MODEL(0), CLIP(1) |
| 高级采样 | `KSamplerAdvanced` | LATENT(0) |
| Latent 放大 | `LatentUpscale` | LATENT(0) |

> **输出索引**: 连接时 `["node_id", 0]` 表示第一个输出，`["node_id", 1]` 表示第二个，以此类推。

---

## 错误处理

```python
result = submit_workflow(workflow)

# 检查是否有图片输出
if not result.get("images"):
    print("⚠️ 无图片输出！检查 workflow 连接。")
    print(f"Outputs: {result.get('outputs', {})}")
```

**常见错误**：
- `"xxx" is not a valid node type` → class_type 拼写错误，先查 NODE_CLASS_MAPPINGS
- `required input 'xxx' missing` → 缺少必需输入，先查 INPUT_TYPES()
- `model not found` → 模型文件名错误，先查 get_filename_list
- 超时 → 模型太大或 VRAM 不足，检查 get_free_memory()
