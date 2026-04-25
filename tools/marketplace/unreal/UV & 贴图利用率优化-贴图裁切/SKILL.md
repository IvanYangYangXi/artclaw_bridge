# UV & 贴图利用率优化

分析使用同一贴图的所有 StaticMesh 的 UV 分布，计算共用 UV 包围盒，将贴图裁切到实际使用区域并重新映射 UV，大幅提升 texel density 利用率。适用于 Unique UV 型贴图（贴图与模型表面一一对应，不使用 Tiling）。

适合触发场景：用户提到 "UV 利用率低"、"贴图空白太多"、"贴图太大"、"优化贴图内存"，且模型使用非 Tiling 贴图。

## 工作流

整个流程共 5 步，全部由工具自动完成：

1. **分析 UV bbox** — 找出材质实例关联的所有 SM，取所有 SM 在指定 UV channel 上的坐标并集包围盒
2. **导出 TGA** — 用 UE `TextureExporterTGA` 将原始贴图导出到本地临时目录
3. **裁切贴图** — 用 Pillow 将贴图裁切到 UV bbox 对应的像素区域，输出尺寸对齐 4 的倍数
4. **重映射 UV** — 用 `StaticMeshDescription` API 对所有 SM 做线性变换，将原 UV bbox 映射到 `[0,1]²`
5. **导入替换** — 将裁切后的 TGA 导入 UE，覆盖原贴图资产，还原 sRGB 和压缩设置

## 注意事项

- **仅支持 Unique UV 贴图**（贴图像素与模型表面一一对应）。Tiling 贴图不适用此工具
- **所有共用该贴图的 SM 必须使用同一 UV bbox**，否则裁切后会导致部分 SM 贴图错位
- UV 重映射操作通过 `ScopedEditorTransaction` 包裹，可用 `Ctrl+Z` 撤销（单个 SM 级别）；贴图导入**不可撤销**，建议先用 `dry_run=true` 预演
- `v_max > 1.0`（如 Stairs01 的 1.13）表示 UV 超出贴图边界，裁切时会被 clamp 到 `1.0`
- 贴图尺寸会自动对齐到 4 的倍数（DXT 压缩要求）
- **MipGenSettings**：非 2^n 尺寸导入后 UE 会自动设为 `NoMips`，工具在导入后强制设回 `FromTextureGroup` 并保存。如遇异常可手动在 Texture 编辑器里将 Mip Gen Settings 改为 FromTextureGroup。

## 脚本

工具入口：`main.py` → `uv_texture_optimize(raw_params)`

关键内嵌 UE Python 片段（以字符串模板形式嵌入 main.py）：
- `UE_ANALYZE_CODE` — 分析 UV bbox
- `UE_EXPORT_CODE` — 导出 TGA
- `UE_REMAP_UV_CODE` — 重映射 UV
- `UE_IMPORT_CODE` — 导入新贴图

**参数说明：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| material_instance_path | 材质实例 UE 路径 | 必填 |
| texture_param_names | 要优化的贴图参数名（逗号分隔，留空=自动检测） | 空（自动） |
| uv_channel | UV 通道索引 | 0 |
| padding_px | 裁切边距像素 | 4 |
| export_dir | TGA 临时目录 | Saved/UVOptimize/<MatName>/ |
| dry_run | 预演模式，只输出报告不写入 | false |

## 验证过的实际效果

在 `MI_Props_WallRail`（6个 SM 共用 2 张 4096×4096 贴图）上的实测结果：

- UV 利用率：7.87% → ~100%
- 贴图裁切：4096×4096 → 376×3076（_best_size fallback align4，浪费率>20%）
- 贴图导入后 UE 显示：188×1538（UE 内部压缩）
- 节省：**93.1%** 贴图像素
- UV 重映射：6个SM × 全部顶点，`generate_lightmap_u_vs` 在 build 前临时关闭后恢复，不产生额外 UV channel
- FBX 导出：`prompt=False` + `automated=True` + `FbxExportOption()` 完全静默，逐个导出避免超时

## ⚠️ 已知 UE Python 崩溃陷阱

**`get_vertex_instance_uv(vi, ch)` 越界会直接 crash UE，不抛 Python 异常。**

绝对禁止用循环枚举 UV channel 数量：
```python
# ❌ 危险！ch 超出实际 channel 数时 UE 直接 crash
for ch in range(8):
    try:
        desc.get_vertex_instance_uv(vid, ch)  # C++ check() 不被 Python try 捕获
    except:
        break
```

正确做法：始终使用固定已知的 channel 索引（如 `uv_channel=0`），永远不枚举。

## 贴图尺寸策略

`_best_size(exact_px, max_waste=0.20)` 优先选最小 2^n：
- 浪费率 `(2^n - exact) / 2^n ≤ 20%` → 用 2^n
- 否则 fallback 到 align4（4的倍数）

示例：220→256（14%≤20%✅），376→376（26.6%>20% fallback），1800→2048（12.1%≤20%✅）

## 依赖

- UE 编辑器运行中（ArtClaw Bridge 已连接）
- `Pillow` 已安装在外部 Python 环境：`pip install Pillow`
