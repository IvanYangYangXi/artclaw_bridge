# Material Properties Reference

UE5 材质属性输入端口（Material Property Inputs）参考。
使用 `connect_material_property` 工具将节点连接到这些属性。

## 属性列表

| 属性名 | 类型 | 说明 | 适用 BlendMode |
|--------|------|------|----------------|
| BaseColor | RGB | 基础颜色，0-1 范围 | 所有 |
| Metallic | Scalar | 金属度，0=非金属 1=全金属 | Opaque, Masked |
| Specular | Scalar | 高光强度，默认0.5 | Opaque, Masked |
| Roughness | Scalar | 粗糙度，0=镜面 1=完全粗糙 | Opaque, Masked |
| Anisotropy | Scalar | 各向异性，-1到1 | Opaque, Masked |
| Normal | RGB | 法线贴图，切线空间 | 所有 |
| Tangent | RGB | 切线方向 | Opaque, Masked |
| EmissiveColor | RGB | 自发光颜色，可超过1.0（HDR） | 所有 |
| Opacity | Scalar | 不透明度，0=全透明 1=不透明 | Translucent, Additive |
| OpacityMask | Scalar | 不透明度蒙版（结合 clip value） | Masked |
| WorldPositionOffset | RGB | 世界空间顶点偏移 | 所有 |
| SubsurfaceColor | RGB | 次表面散射颜色 | Subsurface 模型 |
| AmbientOcclusion | Scalar | 环境遮蔽 | 所有 |
| Refraction | Scalar | 折射率 | Translucent |

## BlendMode 说明

| 模式 | 字符串值 | 说明 |
|------|----------|------|
| 不透明 | `Opaque` | 默认，无透明 |
| 半透明 | `Translucent` | 支持 Opacity |
| 蒙版 | `Masked` | 支持 OpacityMask + clip |
| 叠加 | `Additive` | 加法混合 |
| 调制 | `Modulate` | 乘法混合 |

## ShadingModel 说明

| 模型 | 字符串值 | 说明 |
|------|----------|------|
| 默认光照 | `DefaultLit` | 标准PBR |
| 无光照 | `Unlit` | 仅 EmissiveColor |
| 次表面 | `Subsurface` | SSS 效果 |
| 次表面Profile | `SubsurfaceProfile` | 基于 Profile 的 SSS |
| 清漆 | `ClearCoat` | 双层材质 |
| 双面植被 | `TwoSidedFoliage` | 叶片透光 |

## 典型材质配方

### PBR 金属材质
```
BaseColor  ← Constant3Vector (颜色)
Metallic   ← Constant (0.9-1.0)
Roughness  ← Constant (0.2-0.8)
Normal     ← TextureSample (法线贴图)
```

### PBR 非金属材质
```
BaseColor  ← TextureSample (漫反射贴图)
Metallic   ← Constant (0.0)
Roughness  ← TextureSample (粗糙度贴图)
Normal     ← TextureSample (法线贴图)
```

### 自发光材质
```
EmissiveColor ← Multiply(Constant3Vector(颜色), Constant(强度))
```

### 半透明材质
```
BlendMode: Translucent
BaseColor  ← Constant3Vector
Opacity    ← Constant (0.0-1.0)
```

### 蒙版材质（植被/镂空）
```
BlendMode: Masked
BaseColor     ← TextureSample.RGB
OpacityMask   ← TextureSample.A
opacity_mask_clip_value: 0.333
two_sided: true
```

### 动态 UV 平移
```
Panner(speed_x, speed_y) → TextureSample.UVs
TextureSample → BaseColor
```
