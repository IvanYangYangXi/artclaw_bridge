# UV Repack 工具设计

**目标**：将 Static Mesh 的 UV 岛重排到 0-1 空间，提高贴图利用率，同时适配贴图。支持多 Mesh 共享贴图的场景。

**适用范围**：☑ UEClawBridge · ☑ ArtClaw Tool (marketplace)

---

## 1. 背景

项目常见 Mesh 的 UV 仅占贴图空间很小比例（如 WallRail 3 个 Mesh 共用 2048² 贴图，UV 仅占 ~3.6%）。通过重排 UV 岛并适配贴图，可以：
- 缩小贴图尺寸（节省内存/带宽）
- 或在相同尺寸下获得更高像素密度

**核心约束**：
- 操作 **UV0**（主 UV 通道），同步修改贴图
- **不旋转** UV 岛（旋转会破坏切线空间→法线贴图出错）
- **保持重叠**（同 mesh 内故意重叠的 UV 岛作为一组整体移动）
- **多 Mesh 共享贴图**时所有相关 Mesh 必须一起处理

---

## 2. 技术方案

### 2.1 方案选型

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| xatlas PackCharts | 成熟排布算法、支持旋转 | 不理解重叠语义、UV→float 精度损失、需去重绕行 | UV 从零生成 |
| **脚本 MaxRects 装箱** | 简单直接、完全可控、天然支持重叠组 | 仅矩形 AABB 排布 | **UV 已有、只需重排** ✅ |

**决定**：UV Repack 工具使用纯脚本实现（Python），不依赖 xatlas。

xatlas 库保留在 XAtlasLib 模块中，作为通用能力供未来其他工具使用（如 UV Unwrap/生成新 UV）。

### 2.2 核心流程

```
输入: mesh 路径列表 + 贴图列表
  ↓
1. 提取 UV 数据 (MeshDescription API)
  ↓
2. UV 岛分割 (Union-Find, 共享 UV 坐标的面归为同组)
   → 重叠面自动归为同一岛（无需额外检测）
  ↓
3. 计算每个岛的 AABB
  ↓
4. MaxRects 装箱 (二分搜索最大缩放系数)
   → 所有岛统一缩放（保证纹理密度一致）排进 0-1 正方形
   → 默认不旋转
  ↓
5. 计算 per-island 变换: 平移 + 等比缩放
  ↓
6. 写回 UV0 (set_vertex_instance_uv + build_from_static_mesh_descriptions)
   → ⚠️ 不增加多余 UV 通道
  ↓
7. 适配贴图 (逆映射 + 双线性采样 + bleed)
   → 对每张关联贴图生成新版本
  ↓
输出: 修改后的 mesh + 新贴图 + 修改资源列表
```

### 2.3 多 Mesh 共享贴图

当多个 Mesh 共用同一张贴图时：
1. 所有 Mesh 的 UV 岛一起提取
2. 一起参与装箱（每个岛带 mesh 来源标记）
3. 统一缩放系数
4. 分别写回各自 Mesh 的 UV0
5. 生成一张新贴图供所有 Mesh 共用

### 2.4 贴图自动查找

`texture_paths` 为空时，从 Mesh 关联的**材质实例（MaterialInstance）**中自动查找贴图：
1. 遍历 Mesh 每个材质槽（受 `material_ids` 过滤限制）
2. 读取材质实例中**覆盖了母材质默认值**的贴图参数（`texture_parameter_values`）
3. 跳过尺寸为 1×1 的占位贴图（母材质默认值）
4. 去重后作为待适配贴图列表

若材质槽对应的是母材质（非实例）或未覆盖任何贴图，则该槽不参与贴图适配。

### 2.5 多引用贴图检测（skip_shared_textures）

一张贴图可能被多个资产引用，修改后其他引用方 UV 与新贴图不匹配会导致渲染错误。

**引用计数范围**：通过 AssetRegistry 查询直接引用该贴图的资产，**只统计以下类型**：
- `Material`（母材质）
- `MaterialInstance` / `MaterialInstanceConstant`
- `StaticMesh`
- `SkeletalMesh`
- `Blueprint`（Actor 蓝图，可能包含覆盖材质）
- `World`（关卡，直接引用贴图的情况）

其他类型（粒子、Niagara、UI 等）忽略不计，不影响引用判定。

| `skip_shared_textures` | 行为 |
|------------------------|------|
| `true`（默认）| 引用数 > 1 时**跳过该贴图及对应材质槽的 UV 修改**，报告列出原因 |
| `false` | 强制处理：适配贴图，并将所有引用该贴图的 **StaticMesh / SkeletalMesh** 纳入统一装箱，同步修改 UV |

`false` 模式下自动扩展的 Mesh 范围：对每张共享贴图，查找引用它的材质/材质实例，再查找引用这些材质的 Mesh，全部纳入同一次装箱。

---

## 3. 参数

```python
def uv_repack(
    mesh_paths,                # 一个或多个 mesh 路径
    src_uv=0,                  # UV 通道（默认 UV0）
    padding=0.002,             # UV 岛间距
    material_ids=None,         # 只处理指定材质 ID 的面（None=全部，[0,1]=材质0和1）
    allow_rotation=False,      # 是否允许旋转（默认 False，避免法线问题）
    texture_paths=None,        # 关联贴图路径列表（None=自动查找材质实例贴图）
    skip_shared_textures=True, # True=跳过多引用贴图；False=强制同步所有引用方 UV
    output_resolution=None,    # 输出贴图分辨率（None=自动按等密度计算）
    bleed_pixels=4,            # 贴图边缘扩展像素
    overwrite_texture=True,    # True=覆盖原贴图，False=生成新贴图（加 _repacked 后缀）
    dry_run=False,             # True=只分析不写回
):
```

---

## 4. 关键实现细节

### 4.1 UV 岛分割与重叠保持

使用 Union-Find，以**共享 UV 坐标**作为连接条件：
- 两个面如果有任意一个 UV 坐标相同 → 归为同一岛
- 故意重叠的面（UV 完全相同）自动归为同一岛
- 不需要额外的重叠检测步骤

### 4.2 MaxRects 装箱

- **Best Short Side Fit** 策略：选剩余空间短边浪费最小的位置，排布更接近正方形
- **统一缩放系数**：所有岛使用同一 scale，保证优化前后各区域纹理密度一致
- **二分搜索**缩放系数（72 次迭代，精度约 1e-6）：找到能让所有岛放入 0-1 正方形的最大 scale
- **按面积降序**放置：大岛先放，小岛填缝
- free list 正确维护：每次放置后对所有 free rect 做四向切割 + 冗余剪枝
- 可选旋转 90°（默认关闭）

### 4.3 贴图尺寸计算

目标尺寸 = `src_size / sqrt(scale)`（等密度基准）：
- 优先取 2^n；若 2^n 比基准大超 **20%** → 改用 4 的倍数
- 结果钳制在 [64, 8192]

示例：1024 贴图 scale=2.84 → 基准 608px，2^n=1024 浪费 68.5% → 取 **608**（4 的倍数）

### 4.4 UV 写回注意事项

- 使用 `MeshDescription.set_vertex_instance_uv()` + `build_from_static_mesh_descriptions()`
- **⚠️ 不要增加多余 UV 通道**：写回时只修改已有的 UV0，不新建通道
- 对共享 UV 坐标的所有面（重叠面）写入相同的新 UV 值

### 4.5 贴图适配

对每个输出像素：
1. 计算 UV 坐标 = (px+0.5)/resolution
2. 找到该 UV 所属的 island
3. 逆变换得到源 UV = (new_uv - place_offset) / scale + island_min
4. 从源贴图双线性采样
5. Bleed 扩展填充空白区域

---

## 5. 模块结构

### 5.1 Python 工具层

```
tools/marketplace/unreal/UV & 贴图利用率优化-UV重排/
  main.py               ← 入口（参数解析、贴图自动查找、多引用检测、结果组织）
  uv_repack.py          ← 主调度（UV提取/装箱/写回/贴图适配）
  uv_repack_islands.py  ← UV 岛提取（Union-Find）
  uv_repack_pack.py     ← MaxRects 装箱 + 二分搜索 scale
  uv_repack_texture.py  ← 贴图适配（逆映射+双线性采样+bleed）+ 尺寸计算
```

### 5.2 C++ API 层（通用能力，已有）

```
UEClawBridgeAPI/
  ClawTextureOpsAPI.h/cpp   ← 贴图读写/采样/bleed（已实现）
  ClawXAtlasAPI.h/cpp       ← xatlas 封装（保留，供其他工具用）

XAtlasLib/                  ← xatlas 模块（保留，不用于本工具）
```

---

## 6. 返回结果

```python
{
    "success": True,
    "report": "...",              # 可读报告（利用率、跳过原因、修改列表）
    "modified_assets": [...],     # 实际写入的资产路径（Mesh + 贴图）
    "skipped_textures": [         # 被跳过的贴图（仅 skip_shared=True 且非 dry_run 时）
        {"texture": "/Game/...", "reason": "被 6 个资产引用，已跳过"}
    ],
    "num_islands": 69,
    "scale": 1.52,
    "utilization_before": 28.77,
    "utilization_after": 66.8,
}
```

---

## 7. 边界情况

| 情况 | 处理 |
|------|------|
| 单 Mesh | 直接处理 |
| 多 Mesh 共享贴图 | 所有 Mesh 一起装箱，统一缩放 |
| UV 岛重叠 | Union-Find 自动归为同组 |
| 极端 aspect ratio | 装箱效率降低但不出错（220:1 已验证） |
| UV 超 0-1 | 按实际 AABB 处理 |
| 材质 ID 过滤 | 只处理指定材质的面，其他面 UV 不动 |
| texture_paths 为空 | 自动从材质实例查找，跳过 1×1 占位贴图 |
| 贴图多引用（skip=True） | 跳过该贴图及对应槽 UV，报告说明原因 |
| 贴图多引用（skip=False） | 扩展所有引用方 Mesh，统一装箱同步 UV |
| overwrite=False | 生成 _repacked 后缀新贴图 |
| overwrite=True | 覆盖原贴图（reimport） |
| Normal Map | 不旋转 → 切线空间不变 → 法线正确 |
| 已有多个 UV 通道 | 不新增通道，只改指定通道 |
| dry_run=True | 只分析，不写回任何资产 |

---

## 8. 验证清单

- [x] 单 mesh UV 岛提取 + 重叠保持
- [x] MaxRects 装箱 + 统一缩放系数优化（Best Short Side Fit）
- [x] UV0 写回（不增加通道）
- [x] 贴图自动从材质实例查找（跳过 1×1 占位图）
- [x] 多引用贴图检测 + skip/expand 两种模式
- [x] 贴图尺寸计算（2^n / 4的倍数规则，浪费阈值 20%）
- [x] 修改资源列表（modified_assets）输出
- [ ] 多 mesh 共享贴图一起处理（WallRail 实测）
- [ ] 贴图适配（BaseColor + Normal）端到端验证
- [ ] 法线贴图正确性（无旋转）
