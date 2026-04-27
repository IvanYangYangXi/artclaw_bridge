// Copyright ArtClaw. All Rights Reserved.

#include "MeshAnalysisAPI.h"
#include "Engine/StaticMesh.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/TextureRenderTarget.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/SkeletalMeshLODRenderData.h"
#include "RawIndexBuffer.h"
#include "StaticMeshResources.h"
#include "TextureResource.h"

#if ENGINE_MAJOR_VERSION > 4
#include "TextureCompiler.h"
#endif

namespace
{
    // Constants
    const float CM_TO_M = 0.01f;

    // Texture size cache to avoid repeated UpdateResource() calls
    struct FTextureSizeEntry
    {
        float Width = 0.f;
        float Height = 0.f;
    };
    static TMap<FString, FTextureSizeEntry> TextureSizeCache;

    /**
     * Get cached texture size or fetch and cache it.
     * Handles texture loading and compilation properly.
     */
    bool GetCachedTextureSize(UTexture* Texture, float& OutWidth, float& OutHeight)
    {
        if (!Texture)
        {
            return false;
        }

        const FString TexturePath = Texture->GetPathName();
        if (FTextureSizeEntry* Cached = TextureSizeCache.Find(TexturePath))
        {
            OutWidth = Cached->Width;
            OutHeight = Cached->Height;
            return true;
        }

        // Load and compile texture to get proper size
#if ENGINE_MAJOR_VERSION > 4
        FTextureCompilingManager::Get().FinishCompilation({ Texture });
#endif
        Texture->ConditionalPostLoad();
        Texture->UpdateResource();

        FTextureResource* Resource = Texture->GetResource();
        if (!Resource)
        {
            return false;
        }

        OutWidth = Resource->GetSizeX();
        OutHeight = Resource->GetSizeY();
        TextureSizeCache.Add(TexturePath, { OutWidth, OutHeight });
        return true;
    }

    /**
     * Calculate surface area and UV area for StaticMesh sections.
     * Returns pair of (SurfaceArea in m², UVArea in 0-1 space).
     */
    TPair<float, float> CalculateStaticMeshAreas(
        UStaticMesh* Mesh,
        int32 LODIndex,
        int32 UVChannel,
        int32 SectionIndex = -1)
    {
        if (!Mesh || !Mesh->GetRenderData() || LODIndex >= Mesh->GetNumLODs())
        {
            return TPair<float, float>(0.f, 0.f);
        }

        const FStaticMeshLODResources& LODResource = Mesh->GetRenderData()->LODResources[LODIndex];

        // Check UV channel validity
        if (UVChannel >= (int32)LODResource.GetNumTexCoords())
        {
            UE_LOG(LogTemp, Warning, TEXT("[MeshAnalysis] UV channel %d out of range (max %d) for %s"),
                UVChannel, (int32)LODResource.GetNumTexCoords(), *Mesh->GetPathName());
            return TPair<float, float>(0.f, 0.f);
        }

        float TotalSurfaceArea = 0.f;
        float TotalUVArea = 0.f;

        // Process specific section or all sections
        int32 StartSection = (SectionIndex >= 0) ? SectionIndex : 0;
        int32 EndSection = (SectionIndex >= 0) ? SectionIndex : LODResource.Sections.Num() - 1;

        for (int32 SecIdx = StartSection; SecIdx <= EndSection && SecIdx < LODResource.Sections.Num(); ++SecIdx)
        {
            const FStaticMeshSection& Section = LODResource.Sections[SecIdx];
            const uint32 NumTriangles = Section.NumTriangles;

            for (uint32 TriangleIndex = 0; TriangleIndex < NumTriangles; ++TriangleIndex)
            {
                const FIndexArrayView IndexBuffer = LODResource.IndexBuffer.GetArrayView();
                const int32 Index0 = IndexBuffer[Section.FirstIndex + TriangleIndex * 3 + 0];
                const int32 Index1 = IndexBuffer[Section.FirstIndex + TriangleIndex * 3 + 1];
                const int32 Index2 = IndexBuffer[Section.FirstIndex + TriangleIndex * 3 + 2];

                // Get positions (convert cm to m)
                const FVector Vertex0 = FVector(LODResource.VertexBuffers.PositionVertexBuffer.VertexPosition(Index0)) * CM_TO_M;
                const FVector Vertex1 = FVector(LODResource.VertexBuffers.PositionVertexBuffer.VertexPosition(Index1)) * CM_TO_M;
                const FVector Vertex2 = FVector(LODResource.VertexBuffers.PositionVertexBuffer.VertexPosition(Index2)) * CM_TO_M;

                // Calculate surface area using cross product
                const float TriangleSurfaceArea = FVector::CrossProduct(Vertex1 - Vertex0, Vertex2 - Vertex0).Size() * 0.5f;
                TotalSurfaceArea += TriangleSurfaceArea;

                // Get UV coordinates
                const FVector2D UV0 = FVector2D(LODResource.VertexBuffers.StaticMeshVertexBuffer.GetVertexUV(Index0, UVChannel));
                const FVector2D UV1 = FVector2D(LODResource.VertexBuffers.StaticMeshVertexBuffer.GetVertexUV(Index1, UVChannel));
                const FVector2D UV2 = FVector2D(LODResource.VertexBuffers.StaticMeshVertexBuffer.GetVertexUV(Index2, UVChannel));

                // Calculate UV area using 2D cross product
                const float TriangleUVArea = FMath::Abs(FVector2D::CrossProduct(UV1 - UV0, UV2 - UV0)) * 0.5f;
                TotalUVArea += TriangleUVArea;
            }
        }

        return TPair<float, float>(TotalSurfaceArea, TotalUVArea);
    }

    /**
     * Calculate surface area and UV area for SkeletalMesh sections.
     */
    TPair<float, float> CalculateSkeletalMeshAreas(
        USkeletalMesh* Mesh,
        int32 LODIndex,
        int32 UVChannel,
        int32 SectionIndex = -1)
    {
        if (!Mesh || !Mesh->GetResourceForRendering() || LODIndex >= Mesh->GetResourceForRendering()->LODRenderData.Num())
        {
            return TPair<float, float>(0.f, 0.f);
        }

        const FSkeletalMeshLODRenderData& LODResource = Mesh->GetResourceForRendering()->LODRenderData[LODIndex];

        // Check UV channel validity
        if (UVChannel >= (int32)LODResource.StaticVertexBuffers.StaticMeshVertexBuffer.GetNumTexCoords())
        {
            UE_LOG(LogTemp, Warning, TEXT("[MeshAnalysis] UV channel %d out of range (max %d) for %s"),
                UVChannel, LODResource.StaticVertexBuffers.StaticMeshVertexBuffer.GetNumTexCoords(), *Mesh->GetPathName());
            return TPair<float, float>(0.f, 0.f);
        }

        float TotalSurfaceArea = 0.f;
        float TotalUVArea = 0.f;

        // Process specific section or all sections
        int32 StartSection = (SectionIndex >= 0) ? SectionIndex : 0;
        int32 EndSection = (SectionIndex >= 0) ? SectionIndex : LODResource.RenderSections.Num() - 1;

        for (int32 SecIdx = StartSection; SecIdx <= EndSection && SecIdx < LODResource.RenderSections.Num(); ++SecIdx)
        {
            const FSkelMeshRenderSection& Section = LODResource.RenderSections[SecIdx];
            const uint32 NumTriangles = Section.NumTriangles;

            for (uint32 TriangleIndex = 0; TriangleIndex < NumTriangles; ++TriangleIndex)
            {
                const FRawStaticIndexBuffer16or32Interface& IndexBuffer = *LODResource.MultiSizeIndexContainer.GetIndexBuffer();
                const int32 Index0 = IndexBuffer.Get(Section.BaseIndex + TriangleIndex * 3 + 0);
                const int32 Index1 = IndexBuffer.Get(Section.BaseIndex + TriangleIndex * 3 + 1);
                const int32 Index2 = IndexBuffer.Get(Section.BaseIndex + TriangleIndex * 3 + 2);

                // Get positions (convert cm to m)
                const FVector Vertex0 = FVector(LODResource.StaticVertexBuffers.PositionVertexBuffer.VertexPosition(Index0)) * CM_TO_M;
                const FVector Vertex1 = FVector(LODResource.StaticVertexBuffers.PositionVertexBuffer.VertexPosition(Index1)) * CM_TO_M;
                const FVector Vertex2 = FVector(LODResource.StaticVertexBuffers.PositionVertexBuffer.VertexPosition(Index2)) * CM_TO_M;

                // Calculate surface area
                const float TriangleSurfaceArea = FVector::CrossProduct(Vertex1 - Vertex0, Vertex2 - Vertex0).Size() * 0.5f;
                TotalSurfaceArea += TriangleSurfaceArea;

                // Get UV coordinates
                const FVector2D UV0 = FVector2D(LODResource.StaticVertexBuffers.StaticMeshVertexBuffer.GetVertexUV(Index0, UVChannel));
                const FVector2D UV1 = FVector2D(LODResource.StaticVertexBuffers.StaticMeshVertexBuffer.GetVertexUV(Index1, UVChannel));
                const FVector2D UV2 = FVector2D(LODResource.StaticVertexBuffers.StaticMeshVertexBuffer.GetVertexUV(Index2, UVChannel));

                // Calculate UV area
                const float TriangleUVArea = FMath::Abs(FVector2D::CrossProduct(UV1 - UV0, UV2 - UV0)) * 0.5f;
                TotalUVArea += TriangleUVArea;
            }
        }

        return TPair<float, float>(TotalSurfaceArea, TotalUVArea);
    }

    /**
     * Get textures used by a material, excluding render targets.
     */
    TArray<UTexture*> GetMaterialTextures(const UMaterialInterface* Material)
    {
        TArray<UTexture*> Textures;
        if (!Material)
        {
            return Textures;
        }

        Material->GetUsedTextures(Textures, EMaterialQualityLevel::Num, true, ERHIFeatureLevel::SM5, true);
        
        // Filter out render targets
        Textures.RemoveAll([](UTexture* Texture) {
            return Cast<UTextureRenderTarget>(Texture) != nullptr;
        });

        return Textures;
    }

    /**
     * Calculate texture density data for materials.
     */
    TArray<FTextureDensityData> CalculateTextureDensities(
        const TArray<UMaterialInterface*>& Materials,
        const TArray<TPair<float, float>>& SectionAreas, // (SurfaceArea, UVArea) per section
        const FString& MeshPath)
    {
        TArray<FTextureDensityData> Results;

        for (int32 MaterialIndex = 0; MaterialIndex < Materials.Num(); ++MaterialIndex)
        {
            const UMaterialInterface* Material = Materials[MaterialIndex];
            if (!Material)
            {
                continue;
            }

            // Get areas for this section (or total if sections don't match)
            float SectionSurfaceArea = 0.f;
            float SectionUVArea = 0.f;
            if (MaterialIndex < SectionAreas.Num())
            {
                SectionSurfaceArea = SectionAreas[MaterialIndex].Key;
                SectionUVArea = SectionAreas[MaterialIndex].Value;
            }
            else if (SectionAreas.Num() > 0)
            {
                // Use total areas if section count doesn't match material count
                for (const auto& AreaPair : SectionAreas)
                {
                    SectionSurfaceArea += AreaPair.Key;
                    SectionUVArea += AreaPair.Value;
                }
            }

            if (SectionSurfaceArea <= 0.f)
            {
                continue;
            }

            // Get textures from this material
            TArray<UTexture*> Textures = GetMaterialTextures(Material);

            for (UTexture* Texture : Textures)
            {
                if (!Texture)
                {
                    continue;
                }

                float TextureWidth, TextureHeight;
                if (!GetCachedTextureSize(Texture, TextureWidth, TextureHeight))
                {
                    continue;
                }

                FTextureDensityData DensityData;
                DensityData.TexturePath = Texture->GetPathName();
                DensityData.MaterialPath = Material->GetPathName();
                DensityData.TextureWidth = FMath::RoundToInt(TextureWidth);
                DensityData.TextureHeight = FMath::RoundToInt(TextureHeight);
                DensityData.SurfaceAreaM2 = SectionSurfaceArea;
                DensityData.UVArea = SectionUVArea;

                // Calculate density: sqrt(UVArea * TexW * TexH / SurfaceArea) px/m
                if (SectionSurfaceArea > 0.f && SectionUVArea > 0.f)
                {
                    DensityData.Density = FMath::Sqrt((SectionUVArea * TextureWidth * TextureHeight) / SectionSurfaceArea);
                }

                Results.Add(DensityData);
            }
        }

        return Results;
    }

    /**
     * Get materials from StaticMesh.
     */
    TArray<UMaterialInterface*> GetStaticMeshMaterials(UStaticMesh* Mesh)
    {
        TArray<UMaterialInterface*> Materials;
        if (!Mesh)
        {
            return Materials;
        }

        for (const FStaticMaterial& StaticMaterial : Mesh->GetStaticMaterials())
        {
            Materials.Add(StaticMaterial.MaterialInterface);
        }

        return Materials;
    }

    /**
     * Get materials from SkeletalMesh.
     */
    TArray<UMaterialInterface*> GetSkeletalMeshMaterials(USkeletalMesh* Mesh)
    {
        TArray<UMaterialInterface*> Materials;
        if (!Mesh)
        {
            return Materials;
        }

        for (const FSkeletalMaterial& SkeletalMaterial : Mesh->GetMaterials())
        {
            Materials.Add(SkeletalMaterial.MaterialInterface);
        }

        return Materials;
    }
}

FMeshAnalysisResult UMeshAnalysisAPI::AnalyzeStaticMesh(const FString& MeshPath, int32 LODIndex, int32 UVChannel)
{
    FMeshAnalysisResult Result;

    UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *MeshPath);
    if (!Mesh)
    {
        UE_LOG(LogTemp, Error, TEXT("[MeshAnalysis] Cannot load StaticMesh: %s"), *MeshPath);
        return Result;
    }

    if (!Mesh->GetRenderData() || LODIndex >= Mesh->GetNumLODs())
    {
        UE_LOG(LogTemp, Error, TEXT("[MeshAnalysis] Invalid LOD index %d for %s"), LODIndex, *MeshPath);
        return Result;
    }

    const FStaticMeshLODResources& LODResource = Mesh->GetRenderData()->LODResources[LODIndex];

    // Basic surface data
    Result.SurfaceData.MeshPath = MeshPath;
    Result.SurfaceData.UVChannelCount = LODResource.GetNumTexCoords();

    // Calculate total areas
    TPair<float, float> TotalAreas = CalculateStaticMeshAreas(Mesh, LODIndex, UVChannel);
    Result.SurfaceData.SurfaceAreaM2 = TotalAreas.Key;
    Result.SurfaceData.UVArea = TotalAreas.Value;
    Result.SurfaceData.SurfaceEfficiency = Result.SurfaceData.UVArea; // UVArea itself is the efficiency

    // Count triangles
    for (const FStaticMeshSection& Section : LODResource.Sections)
    {
        Result.SurfaceData.TriangleCount += Section.NumTriangles;
    }

    // Calculate mesh density
    if (Result.SurfaceData.SurfaceAreaM2 > 0.f)
    {
        Result.MeshDensity = FMath::Sqrt(float(Result.SurfaceData.TriangleCount) / Result.SurfaceData.SurfaceAreaM2);
    }

    // Calculate per-section areas for texture density
    TArray<TPair<float, float>> SectionAreas;
    for (int32 SectionIndex = 0; SectionIndex < LODResource.Sections.Num(); ++SectionIndex)
    {
        TPair<float, float> SectionArea = CalculateStaticMeshAreas(Mesh, LODIndex, UVChannel, SectionIndex);
        SectionAreas.Add(SectionArea);
    }

    // Get materials and calculate texture densities
    TArray<UMaterialInterface*> Materials = GetStaticMeshMaterials(Mesh);
    Result.TextureDensities = CalculateTextureDensities(Materials, SectionAreas, MeshPath);

    // Find max texture density
    for (const FTextureDensityData& DensityData : Result.TextureDensities)
    {
        Result.MaxTextureDensity = FMath::Max(Result.MaxTextureDensity, DensityData.Density);
    }

    return Result;
}

FMeshAnalysisResult UMeshAnalysisAPI::AnalyzeSkeletalMesh(const FString& MeshPath, int32 LODIndex, int32 UVChannel)
{
    FMeshAnalysisResult Result;

    USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, *MeshPath);
    if (!Mesh)
    {
        UE_LOG(LogTemp, Error, TEXT("[MeshAnalysis] Cannot load SkeletalMesh: %s"), *MeshPath);
        return Result;
    }

    if (!Mesh->GetResourceForRendering() || LODIndex >= Mesh->GetResourceForRendering()->LODRenderData.Num())
    {
        UE_LOG(LogTemp, Error, TEXT("[MeshAnalysis] Invalid LOD index %d for %s"), LODIndex, *MeshPath);
        return Result;
    }

    const FSkeletalMeshLODRenderData& LODResource = Mesh->GetResourceForRendering()->LODRenderData[LODIndex];

    // Basic surface data
    Result.SurfaceData.MeshPath = MeshPath;
    Result.SurfaceData.UVChannelCount = LODResource.StaticVertexBuffers.StaticMeshVertexBuffer.GetNumTexCoords();

    // Calculate total areas
    TPair<float, float> TotalAreas = CalculateSkeletalMeshAreas(Mesh, LODIndex, UVChannel);
    Result.SurfaceData.SurfaceAreaM2 = TotalAreas.Key;
    Result.SurfaceData.UVArea = TotalAreas.Value;
    Result.SurfaceData.SurfaceEfficiency = Result.SurfaceData.UVArea;

    // Count triangles
    for (const FSkelMeshRenderSection& Section : LODResource.RenderSections)
    {
        Result.SurfaceData.TriangleCount += Section.NumTriangles;
    }

    // Calculate mesh density
    if (Result.SurfaceData.SurfaceAreaM2 > 0.f)
    {
        Result.MeshDensity = FMath::Sqrt(float(Result.SurfaceData.TriangleCount) / Result.SurfaceData.SurfaceAreaM2);
    }

    // Calculate per-section areas for texture density
    TArray<TPair<float, float>> SectionAreas;
    for (int32 SectionIndex = 0; SectionIndex < LODResource.RenderSections.Num(); ++SectionIndex)
    {
        TPair<float, float> SectionArea = CalculateSkeletalMeshAreas(Mesh, LODIndex, UVChannel, SectionIndex);
        SectionAreas.Add(SectionArea);
    }

    // Get materials and calculate texture densities
    TArray<UMaterialInterface*> Materials = GetSkeletalMeshMaterials(Mesh);
    Result.TextureDensities = CalculateTextureDensities(Materials, SectionAreas, MeshPath);

    // Find max texture density
    for (const FTextureDensityData& DensityData : Result.TextureDensities)
    {
        Result.MaxTextureDensity = FMath::Max(Result.MaxTextureDensity, DensityData.Density);
    }

    return Result;
}

TArray<FMeshAnalysisResult> UMeshAnalysisAPI::AnalyzeActors(const TArray<AActor*>& Actors, int32 LODIndex, int32 UVChannel)
{
    TArray<FMeshAnalysisResult> Results;
    TSet<FString> ProcessedMeshPaths; // Avoid duplicates

    for (AActor* Actor : Actors)
    {
        if (!Actor)
        {
            continue;
        }

        // Find StaticMeshComponents
        TArray<UStaticMeshComponent*> StaticMeshComponents;
        Actor->GetComponents<UStaticMeshComponent>(StaticMeshComponents);

        for (UStaticMeshComponent* Component : StaticMeshComponents)
        {
            if (!Component || !Component->GetStaticMesh())
            {
                continue;
            }

            FString MeshPath = Component->GetStaticMesh()->GetPathName();
            if (!ProcessedMeshPaths.Contains(MeshPath))
            {
                ProcessedMeshPaths.Add(MeshPath);
                FMeshAnalysisResult Result = AnalyzeStaticMesh(MeshPath, LODIndex, UVChannel);
                if (!Result.SurfaceData.MeshPath.IsEmpty())
                {
                    Results.Add(Result);
                }
            }
        }

        // Find SkeletalMeshComponents
        TArray<USkeletalMeshComponent*> SkeletalMeshComponents;
        Actor->GetComponents<USkeletalMeshComponent>(SkeletalMeshComponents);

        for (USkeletalMeshComponent* Component : SkeletalMeshComponents)
        {
            if (!Component || !Component->GetSkeletalMeshAsset())
            {
                continue;
            }

            FString MeshPath = Component->GetSkeletalMeshAsset()->GetPathName();
            if (!ProcessedMeshPaths.Contains(MeshPath))
            {
                ProcessedMeshPaths.Add(MeshPath);
                FMeshAnalysisResult Result = AnalyzeSkeletalMesh(MeshPath, LODIndex, UVChannel);
                if (!Result.SurfaceData.MeshPath.IsEmpty())
                {
                    Results.Add(Result);
                }
            }
        }
    }

    return Results;
}

TArray<FMeshAnalysisResult> UMeshAnalysisAPI::BatchAnalyzeMeshes(const TArray<FString>& MeshPaths, int32 LODIndex, int32 UVChannel)
{
    TArray<FMeshAnalysisResult> Results;

    for (const FString& MeshPath : MeshPaths)
    {
        if (MeshPath.IsEmpty())
        {
            continue;
        }

        // Try as StaticMesh first, then SkeletalMesh
        FMeshAnalysisResult Result = AnalyzeStaticMesh(MeshPath, LODIndex, UVChannel);
        if (Result.SurfaceData.MeshPath.IsEmpty())
        {
            Result = AnalyzeSkeletalMesh(MeshPath, LODIndex, UVChannel);
        }

        if (!Result.SurfaceData.MeshPath.IsEmpty())
        {
            Results.Add(Result);
        }
    }

    return Results;
}