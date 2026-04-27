# Mesh & Texture Analysis API (MeshAnalysisAPI)

## 概述
从 CheckEverything 插件提取模型面积、UV面积、贴图利用率、贴图密度等核心计算方法，封装为 ArtClaw 标准 BlueprintFunctionLibrary API，暴露给 Python 脚本层调用。

## 来源分析
CheckEverything 源码位置：`D:\SVNRes_D\s18resource\P4\G83US_UE5\Plugins\CheckEverything\CheckEverything\Source\Private\Calculator\`

### 需提取的关键计算
| 指标 | 原始类 | 原始方法 | 说明 |
|------|--------|----------|------|
| Surface Area (模型表面积 m²) | FMeshDensityCalculator | CalculateStaticMesh / CalculateSkeletalMesh | 遍历三角形叉积求和 ÷ 2 |
| UV Area (UV面积, 0-1空间) | FTextureDensityCalculator | CalculateStaticTexture / CalculateSkeletalTexture | UV空间叉积求和 ÷ 2 |
| Surface Efficiency (UV利用率) | (组合计算) | SumUVArea / 1.0 | UV面积占UV空间的比例 |
| Texture Density (贴图密度, px/m) | FTextureDensityCalculator | 同上 | `ScaleRatio * sqrt(UVArea * TexW * TexH / SurfaceArea)` |
| Triangle Count | FMeshDensityCalculator | 同上 | LOD0 三角形数 |
| Mesh Density (面密度, tri/m²) | FMeshDensityCalculator | 同上 | `(1/Scale) * sqrt(TriCount / SurfaceArea)` |

### 关键公式
```
SurfaceArea = Σ |Cross(V1-V0, V2-V0)| * 0.5  (单位: m², 坐标 × 0.01)
UVArea = Σ |Cross2D(UV1-UV0, UV2-UV0)| * 0.5  (无量纲, 0-1空间)
SurfaceEfficiency = UVArea  (UV面积 ≤ 1.0 时即为利用率)
TextureDensity = (1/Scale) * sqrt(UVArea * TexWidth * TexHeight / SurfaceArea)  (px/m)
MeshDensity = (1/Scale) * sqrt(TriCount / SurfaceArea)
```

## API 设计

### 新文件
- `Public/MeshAnalysisAPI.h`
- `Private/MeshAnalysisAPI.cpp`

### 类: UMeshAnalysisAPI (UBlueprintFunctionLibrary)

#### 返回数据结构
```cpp
USTRUCT(BlueprintType)
struct FMeshSurfaceData
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) FString MeshPath;
    UPROPERTY(BlueprintReadOnly) int32 TriangleCount = 0;
    UPROPERTY(BlueprintReadOnly) float SurfaceAreaM2 = 0.f;    // m²
    UPROPERTY(BlueprintReadOnly) float UVArea = 0.f;           // 0-1 空间
    UPROPERTY(BlueprintReadOnly) float SurfaceEfficiency = 0.f; // UVArea 即利用率
    UPROPERTY(BlueprintReadOnly) int32 UVChannelCount = 0;
};

USTRUCT(BlueprintType)
struct FTextureDensityData
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) FString TexturePath;
    UPROPERTY(BlueprintReadOnly) FString MaterialPath;
    UPROPERTY(BlueprintReadOnly) int32 TextureWidth = 0;
    UPROPERTY(BlueprintReadOnly) int32 TextureHeight = 0;
    UPROPERTY(BlueprintReadOnly) float Density = 0.f;          // px/m
    UPROPERTY(BlueprintReadOnly) float SurfaceAreaM2 = 0.f;    // 该 Section 的表面积
    UPROPERTY(BlueprintReadOnly) float UVArea = 0.f;           // 该 Section 的 UV 面积
};

USTRUCT(BlueprintType)
struct FMeshAnalysisResult
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) FMeshSurfaceData SurfaceData;
    UPROPERTY(BlueprintReadOnly) TArray<FTextureDensityData> TextureDensities;
    UPROPERTY(BlueprintReadOnly) float MaxTextureDensity = 0.f; // 最大贴图密度
    UPROPERTY(BlueprintReadOnly) float MeshDensity = 0.f;       // 面密度
};
```

#### 静态函数
```cpp
// 分析单个 StaticMesh (按资产路径)
UFUNCTION(BlueprintCallable, Category = "ArtClaw|MeshAnalysis")
static FMeshAnalysisResult AnalyzeStaticMesh(
    const FString& MeshPath,
    int32 LODIndex = 0,
    int32 UVChannel = 0);

// 分析单个 SkeletalMesh
UFUNCTION(BlueprintCallable, Category = "ArtClaw|MeshAnalysis")
static FMeshAnalysisResult AnalyzeSkeletalMesh(
    const FString& MeshPath,
    int32 LODIndex = 0,
    int32 UVChannel = 0);

// 分析场景中选中 Actor 的所有 MeshComponent
UFUNCTION(BlueprintCallable, Category = "ArtClaw|MeshAnalysis")
static TArray<FMeshAnalysisResult> AnalyzeActors(
    const TArray<AActor*>& Actors,
    int32 LODIndex = 0,
    int32 UVChannel = 0);

// 批量分析资产路径列表
UFUNCTION(BlueprintCallable, Category = "ArtClaw|MeshAnalysis")
static TArray<FMeshAnalysisResult> BatchAnalyzeMeshes(
    const TArray<FString>& MeshPaths,
    int32 LODIndex = 0,
    int32 UVChannel = 0);
```

### Build.cs 依赖
现有 `MeshDescription`, `StaticMeshDescription` 已在 Build.cs 中，无需额外添加。

## 与 CheckEverything 的差异
1. **独立实现，不依赖** CheckEverything 插件（项目可能没装）
2. **按资产路径** 查询，不需要 CompData 采集流程
3. **支持 UV 通道参数**（CheckEverything 固定 UV0）
4. **返回结构化数据**，而非写入 DataTable
5. **暴露给 Python** 通过 `unreal.MeshAnalysisAPI.xxx()` 直接调用

## Python 调用示例
```python
result = unreal.MeshAnalysisAPI.analyze_static_mesh("/Game/Meshes/SM_Chair")
print(f"三角形: {result.surface_data.triangle_count}")
print(f"表面积: {result.surface_data.surface_area_m2:.4f} m²")
print(f"UV面积: {result.surface_data.uv_area:.4f}")
print(f"UV利用率: {result.surface_data.surface_efficiency:.2%}")
print(f"最大贴图密度: {result.max_texture_density:.1f} px/m")
for td in result.texture_densities:
    print(f"  {td.texture_path}: {td.texture_width}x{td.texture_height} density={td.density:.1f}")
```

## 开发注意事项
1. 坐标单位转换: UE cm → m 乘 0.01
2. 使用 `GET_RENDER_DATA` 宏需自定义，或直接用 `StaticMesh->GetRenderData()`
3. SkeletalMesh IndexBuffer 读取方式与 StaticMesh 不同（`MultiSizeIndexContainer`）
4. Texture 需要 `UpdateResource()` 才能读取尺寸，建议加缓存
5. 不要在 `GetVertexUV` 时用超出范围的通道号（会 crash）— 先检查 UV 通道数
6. 遵循 ArtClaw 已有 API 模式：`UBlueprintFunctionLibrary` + `UFUNCTION(BlueprintCallable)`
