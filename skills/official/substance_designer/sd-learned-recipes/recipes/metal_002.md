# metal_002 — 金属

## 来源
- 文件: `materials/pbr/metal_002.sbs`
- 节点数: 120

## 输出通道
basecolor, normal, roughness, metallic, ambient_occlusion, height

## 库节点使用 (19 个)
| 库节点 | 用途推断 |
|--------|----------|
| creased | 褶皱/凹痕纹理 |
| moisture_noise | 湿度/腐蚀噪波 |
| perlin_noise_1/2 | 通用噪波（两种尺度） |
| dirt_1, dirt_6 | 脏污/氧化 |
| fractal_sum_base ×2 | 分形细节（两处使用） |
| scratches_1 | 划痕 |
| Bullets_Holes_Filter | 弹孔/凹坑 |
| non_uniform_blur_grayscale | 非均匀模糊 |
| noise_upscale_1 | 噪波放大 |
| replace_color ×3 | 颜色替换（三处，大量着色） |
| ambient_occlusion_2 | AO |
| histogram_scan/range | 直方图调整 |

## 原子节点统计
| 节点 | 数量 |
|------|------|
| blend | 41 |
| levels | 30 |
| gradient | 13 |
| warp | 1 |
| directionalwarp | 1 |
| blur | 1 |
| normal | 1 |
| uniform | 1 |

## 关键管线特征
- **着色**: 13 个 gradient + 3 个 replace_color，大量颜色映射
- **纹理分层**: creased(大尺度凹痕) + perlin(中频) + scratches(微细节) + dirt(脏污)
- **Blend 主导**: 41 个 blend 节点，材质效果主要通过大量混合叠加实现
- **Levels 密集**: 30 个 levels 精细控制每层对比度和范围
- **输出来源**: basecolor/normal/roughness ← levels, metallic ← blend(非简单常量！有混合遮罩), height ← histogram_range
- **金属特殊**: metallic 通道通过 blend 混合，不是简单 uniform=1（有氧化/脏污区域降低金属度）
