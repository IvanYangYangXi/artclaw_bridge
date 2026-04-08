# wood_american_cherry — 美国樱桃木

## 来源
- 文件: `materials/pbr/wood_american_cherry.sbs`
- 节点数: 152

## 输出通道
basecolor, normal, roughness, metallic, ambient_occlusion, height (+ diffuse/specular/glossiness 转换)

## 库节点使用 (17 个)
| 库节点 | 输出端口 | 用途推断 |
|--------|----------|----------|
| wood_fibers_2 | Wood_Noise | 木纹纤维主体 |
| perlin_noise_zoom | Noise_Zoom | 大尺度噪波变化（5次引用，关键分支） |
| directionnal_noise | Directionnal_Noise | 方向性细节（4次引用） |
| herb_1 | Herb | 纹理细节叠加（4次引用） |
| tile_generator ×4 | TileGenerator | 图案生成（年轮/木板排列） |
| white_noise | White_Noise | 随机种子/变化 |
| gradient_linear_1/2 | Simple_Gradient | 渐变遮罩 |
| dirt_4 | Horizontal_Scratch | 水平划痕 |
| bnw_spots_1 | BnW_Spots | 斑点/瑕疵 |
| ambient_occlusion_2 | ambient_occlusion | AO 生成 |
| replace_color | ToTargetColor | 颜色替换/着色 |
| histogram_range | output | 直方图范围调整 |

## 原子节点统计
| 节点 | 数量 | 用途 |
|------|------|------|
| blend | 38 | 大量混合操作（着色、叠加、遮罩） |
| levels | 18 | 色阶调整（对比度、范围映射） |
| transformation | 17 | 2D 变换（平铺、缩放） |
| warp | 17 | 扭曲（自然弯曲） |
| gradient | 13 | 渐变映射（灰度→颜色，大量用于着色） |
| blur | 8 | 模糊（柔化过渡） |
| dirmotionblur | 5 | 方向运动模糊（木纹方向拉伸） |
| uniform | 4 | 常量值 |
| directionalwarp | 2 | 方向性扭曲 |
| normal | 1 | 法线生成 |

## 关键管线特征
- **着色方案**: 使用大量 gradient (13个) 做灰度→颜色映射，配合 replace_color 库节点
- **纹理来源**: wood_fibers_2 + perlin_noise_zoom + directional_noise 三层叠加
- **自然感**: 17 个 warp 节点 + 5 个 dirmotionblur 产生方向性木纹流动感
- **细节层次**: 从大尺度（perlin_noise_zoom）到中尺度（wood_fibers）到微细节（herb/bnw_spots/dirt）
- **输出来源**: basecolor/normal/roughness ← levels, metallic ← uniform(常量), height ← histogram_range, AO ← ambient_occlusion_2
