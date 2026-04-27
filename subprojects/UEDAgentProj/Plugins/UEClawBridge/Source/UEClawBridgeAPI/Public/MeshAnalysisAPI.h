// Copyright ArtClaw. All Rights Reserved.
// Mesh & Texture Analysis API — surface area, UV area, texture density calculation

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Engine/Texture.h"
#include "MeshAnalysisAPI.generated.h"

USTRUCT(BlueprintType)
struct UECLAWBRIDGEAPI_API FMeshSurfaceData
{
    GENERATED_BODY()

    /** Source mesh path */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    FString MeshPath;

    /** Total triangle count */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    int32 TriangleCount = 0;

    /** Surface area in square meters (m²) */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    float SurfaceAreaM2 = 0.f;

    /** UV area in 0-1 space (dimensionless) */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    float UVArea = 0.f;

    /** UV surface efficiency (UVArea / 1.0) */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    float SurfaceEfficiency = 0.f;

    /** Number of UV channels available */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    int32 UVChannelCount = 0;
};

USTRUCT(BlueprintType)
struct UECLAWBRIDGEAPI_API FTextureDensityData
{
    GENERATED_BODY()

    /** Texture asset path */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    FString TexturePath;

    /** Material that uses this texture */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    FString MaterialPath;

    /** Texture width in pixels */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    int32 TextureWidth = 0;

    /** Texture height in pixels */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    int32 TextureHeight = 0;

    /** Texture density in pixels per meter (px/m) */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    float Density = 0.f;

    /** Surface area for this section in m² */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    float SurfaceAreaM2 = 0.f;

    /** UV area for this section */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    float UVArea = 0.f;
};

USTRUCT(BlueprintType)
struct UECLAWBRIDGEAPI_API FMeshAnalysisResult
{
    GENERATED_BODY()

    /** Basic mesh surface data */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    FMeshSurfaceData SurfaceData;

    /** Per-material texture density data */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    TArray<FTextureDensityData> TextureDensities;

    /** Maximum texture density across all textures (px/m) */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    float MaxTextureDensity = 0.f;

    /** Mesh density in triangles per square meter (tri/m²) */
    UPROPERTY(BlueprintReadOnly, Category = "MeshAnalysis")
    float MeshDensity = 0.f;
};

/**
 * Mesh and texture analysis functions for calculating surface area,
 * UV area, texture density, and mesh density.
 * 
 * Extracted from CheckEverything plugin algorithms but implemented
 * as standalone API without external dependencies.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UMeshAnalysisAPI : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /**
     * Analyze a StaticMesh asset by package path.
     * 
     * @param MeshPath   Package path like "/Game/Meshes/SM_Chair"
     * @param LODIndex   LOD level to analyze (default 0)
     * @param UVChannel  UV channel to use for area calculation (default 0)
     * @return Analysis result with surface data and texture densities
     */
    UFUNCTION(BlueprintCallable, Category = "ArtClaw|MeshAnalysis", CallInEditor)
    static FMeshAnalysisResult AnalyzeStaticMesh(
        const FString& MeshPath,
        int32 LODIndex = 0,
        int32 UVChannel = 0);

    /**
     * Analyze a SkeletalMesh asset by package path.
     * 
     * @param MeshPath   Package path like "/Game/Characters/SK_Hero"
     * @param LODIndex   LOD level to analyze (default 0)
     * @param UVChannel  UV channel to use for area calculation (default 0)
     * @return Analysis result with surface data and texture densities
     */
    UFUNCTION(BlueprintCallable, Category = "ArtClaw|MeshAnalysis", CallInEditor)
    static FMeshAnalysisResult AnalyzeSkeletalMesh(
        const FString& MeshPath,
        int32 LODIndex = 0,
        int32 UVChannel = 0);

    /**
     * Analyze all mesh components from a list of actors.
     * 
     * @param Actors     Array of actors to analyze
     * @param LODIndex   LOD level to analyze (default 0)
     * @param UVChannel  UV channel to use for area calculation (default 0)
     * @return Array of analysis results, one per unique mesh found
     */
    UFUNCTION(BlueprintCallable, Category = "ArtClaw|MeshAnalysis", CallInEditor)
    static TArray<FMeshAnalysisResult> AnalyzeActors(
        const TArray<AActor*>& Actors,
        int32 LODIndex = 0,
        int32 UVChannel = 0);

    /**
     * Batch analyze multiple mesh assets by package path.
     * 
     * @param MeshPaths  Array of mesh package paths to analyze
     * @param LODIndex   LOD level to analyze (default 0)
     * @param UVChannel  UV channel to use for area calculation (default 0)
     * @return Array of analysis results, one per mesh
     */
    UFUNCTION(BlueprintCallable, Category = "ArtClaw|MeshAnalysis", CallInEditor)
    static TArray<FMeshAnalysisResult> BatchAnalyzeMeshes(
        const TArray<FString>& MeshPaths,
        int32 LODIndex = 0,
        int32 UVChannel = 0);
};