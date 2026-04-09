---
name: sd-node-capture
description: >
  捕获 SD 节点输出纹理用于 AI 视觉分析。支持按节点 ID、按输出通道批量截图。
  Use when AI needs to: (1) see what a node's output looks like,
  (2) capture all PBR outputs for quality review,
  (3) inspect intermediate node results to guide optimization,
  (4) visually verify material correctness after building a graph.
  NOT for: final production export, 3D viewport screenshot.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 2.0.0
    author: ArtClaw
    software: substance_designer
---

# SD 节点输出捕获与视觉分析

## 核心机制

### save_preview — 预注入的截图函数

`save_preview` 是预注入到 exec 命名空间的辅助函数，**自动完成：缩放 1/4 → jpg 压缩 → [IMAGE:] 标记输出**。
AI 在 tool result 中可直接看到图片。

```python
# 最简用法：传入节点，自动截图
node = graph.getNodeFromId("node_id")
save_preview(node, "height")

# 传入纹理对象也行
tex = node.getPropertyValue(out_props[0]).get()
save_preview(tex, "height")

# 自定义缩放比（默认 4 即 1/4）
save_preview(node, "height_hires", scale=2)  # 1/2 大小
save_preview(node, "height_full", scale=1)   # 原始大小
```

**参数：**
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `texture_or_node` | SDTexture / SDNode | 必填 | 传 node 时自动取第一个输出端口 |
| `label` | str | "preview" | 显示标签，也用于文件名 |
| `scale` | int | 4 | 缩小倍数（1=原始, 2=半, 4=四分之一） |
| `quality` | int | 80 | JPEG 质量 |

### [IMAGE:path] 标记（底层机制）

`save_preview` 内部调用 `print(f"[IMAGE:{path}]")`，MCP Server 自动将图片 base64 嵌入返回。
也可以手动使用这个标记：

```python
tex.save("path/to/file.jpg")
print(f"[IMAGE:path/to/file.jpg]")  # AI 看到图片
```

---

## 操作示例

### 1. 截图单个节点

```python
node = graph.getNodeFromId("1567699435")
save_preview(node, "weave_pattern")
```

### 2. 截取所有 PBR 输出

```python
output_nodes = graph.getOutputNodes()
for i in range(output_nodes.getSize()):
    on = output_nodes.getItem(i)
    usage = "unknown"
    try:
        val = on.getAnnotationPropertyValueFromId("identifier")
        if val:
            usage = str(val.get()) if hasattr(val, 'get') else str(val)
    except Exception:
        pass
    save_preview(on, f"output_{usage}")
```

### 3. 截取关键中间节点

```python
check_nodes = {
    "1567699435": "weave_pattern",
    "1567699547": "height_levels",
    "1567699553": "final_blend",
}
for nid, label in check_nodes.items():
    node = graph.getNodeFromId(nid)
    if node:
        save_preview(node, label)
    else:
        print(f"节点 {nid} ({label}) 未找到")
```

### 4. 多输出端口的库节点

```python
node = graph.getNodeFromId("target_node_id")
if node:
    out_props = node.getProperties(SDPropertyCategory.Output)
    for p in out_props:
        port_id = p.getId()
        val = node.getPropertyValue(p)
        if val:
            tex = val.get()
            if tex:
                save_preview(tex, f"port_{port_id}")
```

---

## AI 分析工作流

### 推荐流程

```
1. 完成节点连接/参数调整
2. graph.compute()  (通常连接操作会自动触发)
3. save_preview 截取关键节点 + 最终输出
4. AI 看到图片，对照规划目标判断效果
5. 根据视觉反馈决定是否需要调整
```

### 分析维度（与 sd-operation-rules 对齐）

截图后必须按以下 4 个维度分析，参见 `sd-operation-rules` 的截图分析两步法：

| 维度 | 关注内容 |
|------|----------|
| **A. 亮度/对比度** | 全黑？接近全黑？灰蒙蒙？还是有清晰的动态范围？全黑=上游数值衰减，必须排查 |
| **B. 图案正确性** | 输出图案是否符合预期？有无 artifact？与上一步是否有因果关系？ |
| **C. 密度/比例尺** | 基于物理尺度声明，特征数量和尺寸是否合理？ |
| **D. CG感** | 过于规则/硬边/几何感？需要后处理打破 |

### 📏 尺度分析

每次分析时声明物理尺度：
```
"1024² = [X]cm×[X]cm 下：[N] 个特征，每个约 [Y]cm → [符合/偏大/偏小]"
```

### graph.compute() 注意

- 通常连接操作会自动触发 compute
- 修改参数后可显式调用 `graph.compute()`
- **⚠️ 大图 compute 可能耗时较长**

---

## 技术细节

### API 链路

```
SDNode
  .getProperties(SDPropertyCategory.Output)  → [SDProperty]
  .getPropertyValue(prop)                     → SDValueTexture
    .get()                                    → SDTexture
      .save(filepath)                         → 保存为图片文件
      .getSize()                              → int2(width, height)
      .getPixelFormat()                       → SBSPixelFormat enum
```

### 注意事项

- 节点必须已 compute 过才有纹理数据（未计算的节点返回 None）
- `save_preview` 默认缩放到 1/4 并转 jpg，节省约 80% 的 base64 传输量
- 如果 QImage 不可用（极端情况），自动 fallback 到原始 png
- save_preview 输出目录：`~/.openclaw/workspace-xiaoyou/sd_captures/`
