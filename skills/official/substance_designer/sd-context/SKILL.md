---
name: sd-context
description: >
  查询 SD 编辑器上下文：包信息、图列表、节点结构、参数详情。
  Use when AI needs to: (1) get package info, (2) list graphs,
  (3) inspect node network, (4) check node parameters.
  Substance Designer only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: substance_designer
---

# SD 编辑器上下文查询

> 查询 Substance Designer 当前状态：包、图、节点、参数、连接关系。
> 所有操作为**只读**，不修改任何内容。

---

## 前置条件

`run_python` 已预注入以下变量，**直接使用，无需 import**：

- `sd`, `app`, `graph`, `S`, `W`, `L`
- `SDPropertyCategory`, `float2`, `float3`, `float4`, `ColorRGBA`
- `SDValueFloat`, `SDValueInt`, `SDValueBool`, `SDValueString`

```python
# ✅ 直接使用预注入变量
pkg_mgr = app.getPackageMgr()
ui_mgr = app.getUIMgr()

# ❌ 禁止在 exec 中 import sd.api 子模块（会超时死锁）
# from sd.api.sdapplication import SDApplication  # 禁止！
# from sd.api.sdproperty import SDPropertyCategory  # 禁止！
```

---

## 1. 获取用户包列表

列出当前加载的所有用户包（排除系统/库包）：

```python
pkg_mgr = app.getPackageMgr()

user_packages = pkg_mgr.getUserPackages()
result = []
for pkg in user_packages:
    file_path = pkg.getFilePath()
    pkg_id = pkg.getIdentifier() if hasattr(pkg, 'getIdentifier') else "N/A"
    resources = pkg.getChildrenResources(False)
    graph_count = len(resources) if resources else 0
    result.append({
        "identifier": pkg_id,
        "file_path": file_path,
        "graph_count": graph_count
    })
    print(f"包: {pkg_id} | 路径: {file_path} | 图数量: {graph_count}")

if not result:
    print("没有加载的用户包")
```

---

## 2. 获取包内图列表

列出指定包的所有子图（Substance Graph）：

```python
pkg_mgr = app.getPackageMgr()

# 获取第一个用户包
user_packages = pkg_mgr.getUserPackages()
if not user_packages:
    print("没有加载的用户包")
else:
    pkg = user_packages[0]
    resources = pkg.getChildrenResources(False)
    for res in resources:
        res_id = res.getIdentifier()
        res_type = type(res).__name__
        print(f"资源: {res_id} | 类型: {res_type}")
```

---

## 3. 获取当前图信息

```python
if graph is None:
    print("没有打开的图")
else:
    graph_id = graph.getIdentifier()
    nodes = graph.getNodes()
    node_count = nodes.getSize() if nodes else 0
    
    # 获取图的输出定义
    outputs = graph.getProperties(SDPropertyCategory.Output)
    output_count = len(outputs) if outputs else 0
    
    print(f"当前图: {graph_id}")
    print(f"节点数量: {node_count}")
    print(f"输出数量: {output_count}")
```

---

## 4. 获取当前图的节点列表

```python
if graph is None:
    print("没有打开的图")
else:
    nodes = graph.getNodes()
    if nodes is None or nodes.getSize() == 0:
        print("图中没有节点")
    else:
        for i in range(nodes.getSize()):
            node = nodes.getItem(i)
            node_id = node.getIdentifier()
            definition = node.getDefinition()
            def_id = definition.getId() if definition else "unknown"
            pos = node.getPosition()
            print(f"[{i}] ID: {node_id} | 定义: {def_id} | 位置: ({pos.x:.0f}, {pos.y:.0f})")
```

---

## 5. 获取节点参数

查看节点的所有输入参数及其当前值：

```python
if graph is None:
    print("没有打开的图")
else:
    nodes = graph.getNodes()
    if nodes and nodes.getSize() > 0:
        # 检查第一个节点的参数
        node = nodes.getItem(0)
        node_id = node.getIdentifier()
        definition = node.getDefinition()
        def_id = definition.getId() if definition else "unknown"
        print(f"节点: {node_id} ({def_id})")
        print("--- 输入参数 ---")
        
        input_props = node.getProperties(SDPropertyCategory.Input)
        if input_props:
            for prop in input_props:
                prop_id = prop.getId()
                prop_label = prop.getLabel()
                value = node.getPropertyValue(prop)
                type_name = type(value).__name__ if value else "None"
                print(f"  {prop_id} ({prop_label}): {value} [{type_name}]")
        else:
            print("  无输入参数")
        
        print("--- 注解参数 ---")
        anno_props = node.getProperties(SDPropertyCategory.Annotation)
        if anno_props:
            for prop in anno_props:
                prop_id = prop.getId()
                value = node.getPropertyValue(prop)
                print(f"  {prop_id}: {value}")
```

---

## 6. 获取节点连接关系

查看节点之间的输入/输出连接：

```python
if graph is None:
    print("没有打开的图")
else:
    nodes = graph.getNodes()
    if nodes is None or nodes.getSize() == 0:
        print("图中没有节点")
    else:
        print("=== 连接关系 ===")
        for i in range(nodes.getSize()):
            node = nodes.getItem(i)
            node_id = node.getIdentifier()
            
            # 查看输入连接
            input_props = node.getProperties(SDPropertyCategory.Input)
            if input_props:
                for prop in input_props:
                    conns = node.getPropertyConnections(prop)
                    if conns and conns.getSize() > 0:
                        for ci in range(conns.getSize()):
                            conn = conns.getItem(ci)
                            # ⚠️ SDConnection 方向语义（反直觉但实测确认）：
                            # getInputPropertyNode()  → 源节点
                            # getInputProperty()      → 源端口
                            src_node = conn.getInputPropertyNode()
                            src_node_id = src_node.getIdentifier() if src_node else "?"
                            src_prop_id = conn.getInputProperty().getId()
                            print(f"  {src_node_id}.{src_prop_id} --> {node_id}.{prop.getId()}")
```

---

## 7. 获取图的输出节点

找到图中所有 Output 类型节点及其 usage：

```python
if graph is None:
    print("没有打开的图")
else:
    nodes = graph.getNodes()
    output_nodes = []
    
    if nodes:
        for i in range(nodes.getSize()):
            node = nodes.getItem(i)
            definition = node.getDefinition()
            if definition and "output" in definition.getId().lower():
                node_id = node.getIdentifier()
                
                # 尝试获取 usage 属性（使用便捷 API）
                usage = "unknown"
                try:
                    val = node.getAnnotationPropertyValueFromId("identifier")
                    if val:
                        usage = str(val)
                except Exception:
                    # 回退：遍历注解属性
                    anno_props = node.getProperties(SDPropertyCategory.Annotation)
                    if anno_props:
                        for prop in anno_props:
                            if prop.getId() == "identifier":
                                val = node.getPropertyValue(prop)
                                if val:
                                    usage = str(val)
                
                output_nodes.append({"id": node_id, "usage": usage})
                print(f"输出节点: {node_id} | Usage: {usage}")
    
    if not output_nodes:
        print("没有找到输出节点")
    else:
        print(f"\n共 {len(output_nodes)} 个输出节点")
```

---

## 快速参考：属性类别

| SDPropertyCategory | 说明 |
|---------------------|------|
| `Input` | 节点的输入端口和参数 |
| `Output` | 节点的输出端口 |
| `Annotation` | 注解属性（identifier、label 等） |
