# Material Expression Node Types Reference

UE5 MaterialExpression 类名大全。创建节点时使用 `expression_class` 参数传入。
可以省略 `MaterialExpression` 前缀（接口会自动补全）。

## 常量 / 参数

| 类名 | 短名 | 说明 | 关键属性 |
|-------|------|------|----------|
| MaterialExpressionConstant | Constant | 标量常量 | `r` (float) |
| MaterialExpressionConstant2Vector | Constant2Vector | 2D向量 | `r`, `g` |
| MaterialExpressionConstant3Vector | Constant3Vector | RGB颜色/3D向量 | `constant` ({r,g,b,a}) |
| MaterialExpressionConstant4Vector | Constant4Vector | RGBA颜色/4D向量 | `constant` ({r,g,b,a}) |
| MaterialExpressionScalarParameter | ScalarParameter | 标量参数（可实例覆盖） | `parameter_name`, `default_value`, `group` |
| MaterialExpressionVectorParameter | VectorParameter | 向量参数 | `parameter_name`, `default_value`, `group` |
| MaterialExpressionStaticSwitchParameter | StaticSwitchParameter | 静态开关参数 | `parameter_name`, `default_value`, `group` |
| MaterialExpressionStaticBoolParameter | StaticBoolParameter | 静态布尔参数 | `parameter_name`, `default_value`, `group` |

## 纹理

| 类名 | 短名 | 说明 | 关键属性 |
|-------|------|------|----------|
| MaterialExpressionTextureSample | TextureSample | 纹理采样 | `texture` (asset path), `sampler_type` |
| MaterialExpressionTextureSampleParameter2D | TextureSampleParameter2D | 2D纹理参数 | `parameter_name`, `texture`, `group` |
| MaterialExpressionTextureObject | TextureObject | 纹理对象引用 | `texture` |
| MaterialExpressionTextureCoordinate | TextureCoordinate | UV坐标 | `coordinate_index`, `u_tiling`, `v_tiling` |

## 数学运算

| 类名 | 短名 | 说明 | 输入 Pin |
|-------|------|------|----------|
| MaterialExpressionAdd | Add | 加法 | A, B |
| MaterialExpressionSubtract | Subtract | 减法 | A, B |
| MaterialExpressionMultiply | Multiply | 乘法 | A, B |
| MaterialExpressionDivide | Divide | 除法 | A, B |
| MaterialExpressionPower | Power | 幂运算 | Base, Exponent |
| MaterialExpressionSquareRoot | SquareRoot | 平方根 | (default) |
| MaterialExpressionAbs | Abs | 绝对值 | (default) |
| MaterialExpressionCeil | Ceil | 向上取整 | (default) |
| MaterialExpressionFloor | Floor | 向下取整 | (default) |
| MaterialExpressionFrac | Frac | 取小数部分 | (default) |
| MaterialExpressionFmod | Fmod | 取模 | A, B |
| MaterialExpressionClamp | Clamp | 钳制 | Input, Min, Max |
| MaterialExpressionSaturate | Saturate | 钳制到0-1 | (default) |
| MaterialExpressionMin | Min | 取最小值 | A, B |
| MaterialExpressionMax | Max | 取最大值 | A, B |
| MaterialExpressionOneMinus | OneMinus | 1减X | (default) |
| MaterialExpressionDotProduct | DotProduct | 点积 | A, B |
| MaterialExpressionCrossProduct | CrossProduct | 叉积 | A, B |
| MaterialExpressionNormalize | Normalize | 归一化 | (default) |

## 三角函数

| 类名 | 短名 | 说明 |
|-------|------|------|
| MaterialExpressionSine | Sine | 正弦 |
| MaterialExpressionCosine | Cosine | 余弦 |
| MaterialExpressionArcsine | Arcsine | 反正弦 |
| MaterialExpressionArccosine | Arccosine | 反余弦 |
| MaterialExpressionArctangent | Arctangent | 反正切 |
| MaterialExpressionArctangent2 | Arctangent2 | 反正切2（双参数） |

## 插值 / 混合

| 类名 | 短名 | 说明 | 输入 Pin |
|-------|------|------|----------|
| MaterialExpressionLinearInterpolate | Lerp / LinearInterpolate | 线性插值 | A, B, Alpha |
| MaterialExpressionIf | If | 条件分支 | A, B, AGreaterThanB, AEqualsB, ALessThanB |
| MaterialExpressionStaticSwitch | StaticSwitch | 静态开关 | True, False, Value |
| MaterialExpressionBlendMaterialAttributes | BlendMaterialAttributes | 混合材质属性 | A, B, Alpha |

## 向量操作

| 类名 | 短名 | 说明 | 输入 Pin |
|-------|------|------|----------|
| MaterialExpressionComponentMask | ComponentMask | 通道掩码 | (default) — 属性: `r`, `g`, `b`, `a` (bool) |
| MaterialExpressionAppendVector | AppendVector | 向量拼接 | A, B |
| MaterialExpressionBreakMaterialAttributes | BreakMaterialAttributes | 拆分材质属性 | (default) |
| MaterialExpressionMakeMaterialAttributes | MakeMaterialAttributes | 组合材质属性 | BaseColor, Metallic, ... |
| MaterialExpressionTransform | Transform | 空间变换 | (default) |
| MaterialExpressionTransformPosition | TransformPosition | 位置空间变换 | (default) |

## 世界 / 摄像机

| 类名 | 短名 | 说明 |
|-------|------|------|
| MaterialExpressionWorldPosition | WorldPosition | 世界坐标 |
| MaterialExpressionActorPositionWS | ActorPositionWS | Actor世界坐标 |
| MaterialExpressionObjectPositionWS | ObjectPositionWS | 对象世界坐标 |
| MaterialExpressionCameraPositionWS | CameraPositionWS | 摄像机世界坐标 |
| MaterialExpressionPixelNormalWS | PixelNormalWS | 像素世界法线 |
| MaterialExpressionVertexNormalWS | VertexNormalWS | 顶点世界法线 |
| MaterialExpressionVertexColor | VertexColor | 顶点颜色 |
| MaterialExpressionObjectRadius | ObjectRadius | 对象包围球半径 |
| MaterialExpressionObjectBounds | ObjectBounds | 对象包围盒 |
| MaterialExpressionScreenPosition | ScreenPosition | 屏幕位置 |
| MaterialExpressionViewSize | ViewSize | 视口大小 |
| MaterialExpressionPixelDepth | PixelDepth | 像素深度 |
| MaterialExpressionSceneDepth | SceneDepth | 场景深度 |
| MaterialExpressionCameraVectorWS | CameraVectorWS | 摄像机方向 |

## 时间 / 动画

| 类名 | 短名 | 说明 | 关键属性 |
|-------|------|------|----------|
| MaterialExpressionTime | Time | 游戏时间 | `ignore_pause` (bool) |
| MaterialExpressionPanner | Panner | UV平移动画 | Coordinate, Time — 属性: `speed_x`, `speed_y` |
| MaterialExpressionRotator | Rotator | UV旋转动画 | Coordinate, Time — 属性: `speed` |

## 噪声 / 程序化

| 类名 | 短名 | 说明 |
|-------|------|------|
| MaterialExpressionNoise | Noise | 噪声 |
| MaterialExpressionVectorNoise | VectorNoise | 向量噪声 |
| MaterialExpressionPerlinNoiseFunction | PerlinNoiseFunction | Perlin噪声函数 |

## 自定义 / 函数

| 类名 | 短名 | 说明 | 关键属性 |
|-------|------|------|----------|
| MaterialExpressionCustom | Custom | 自定义HLSL代码 | `code` (str), `output_type`, `description` |
| MaterialExpressionMaterialFunctionCall | MaterialFunctionCall | 调用材质函数 | `function` (asset path) |
| MaterialExpressionComment | Comment | 注释框 | `text` |

## 实用工具

| 类名 | 短名 | 说明 |
|-------|------|------|
| MaterialExpressionFresnel | Fresnel | 菲涅尔效果 |
| MaterialExpressionDepthFade | DepthFade | 深度淡出 |
| MaterialExpressionDistance | Distance | 距离计算 |
| MaterialExpressionSphereMask | SphereMask | 球形蒙版 |
| MaterialExpressionAntialiasedTextureMask | AntialiasedTextureMask | 抗锯齿纹理蒙版 |
| MaterialExpressionDDX | DDX | 水平偏导 |
| MaterialExpressionDDY | DDY | 垂直偏导 |
| MaterialExpressionDesaturation | Desaturation | 去饱和 |

## 常用输出 Pin 名称参考

多数节点默认输出用空字符串 `""` 即可。有多输出的节点：

| 节点类型 | 输出 Pin |
|----------|----------|
| TextureSample | `""` (RGBA), `RGB`, `R`, `G`, `B`, `A` |
| ComponentMask | `""` (masked result) |
| BreakMaterialAttributes | `BaseColor`, `Metallic`, `Roughness`, ... |
| Constant3Vector | `""` (RGB), `R`, `G`, `B` |
| VertexColor | `""` (RGBA), `R`, `G`, `B`, `A` |

## 常用输入 Pin 名称参考

| 节点类型 | 输入 Pin |
|----------|----------|
| Add / Subtract / Multiply / Divide | `A`, `B` |
| Lerp | `A`, `B`, `Alpha` |
| Power | `Base`, `Exponent` |
| Clamp | `Input`, `Min`, `Max` |
| If | `A`, `B`, `AGreaterThanB`, `AEqualsB`, `ALessThanB` |
| TextureSample | `UVs` (或 `Coordinates`), `Tex` |
| Panner | `Coordinate`, `Time`, `Speed` |
