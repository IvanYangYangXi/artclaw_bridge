// Copyright ArtClaw. All Rights Reserved.
// xatlas UV Repack integration - data types

#pragma once

#include "CoreMinimal.h"
#include "XAtlasTypes.generated.h"

// --- Input ---

USTRUCT(BlueprintType)
struct XATLASLIB_API FXAtlasMeshEntry
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	UStaticMesh* StaticMesh = nullptr;

	/** Material indices to include. Empty = all materials. */
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	TArray<int32> MaterialIDs;

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	int32 SourceUVChannel = 0;

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	int32 TargetUVChannel = 1;

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	int32 LODIndex = 0;
};

USTRUCT(BlueprintType)
struct XATLASLIB_API FXAtlasRepackOptions
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	int32 Resolution = 1024;

	/** Padding between charts in texels. */
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	int32 Padding = 4;

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	bool bAllowRotation = true;

	/** If false, UV islands that extend beyond 0-1 will be clamped. */
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	bool bAllowTilingUV = false;

	/** Texels per world unit. 0 = auto-estimate. */
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	float TexelsPerUnit = 0.0f;

	/** If true, write repacked UVs back to the mesh. If false, only calculate transforms. */
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	bool bWriteToMesh = true;
};

// --- Chart Transform ---

USTRUCT(BlueprintType)
struct XATLASLIB_API FXAtlasChartTransform
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	int32 ChartIndex = -1;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	int32 MaterialID = -1;

	/**
	 * 2x3 affine matrix [a,b,tx, c,d,ty]:
	 * NewUV = M * [OldU, OldV, 1]^T
	 */
	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	TArray<float> AffineMatrix;

	/** Pre-computed inverse of AffineMatrix. */
	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	TArray<float> InverseAffineMatrix;

	// Decomposed form
	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	FVector2D Translation = FVector2D::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	float RotationDegrees = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	float UniformScale = 1.0f;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	bool bIsMirrored = false;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	FBox2D SourceBounds = FBox2D(FVector2D::ZeroVector, FVector2D::ZeroVector);

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	FBox2D TargetBounds = FBox2D(FVector2D::ZeroVector, FVector2D::ZeroVector);

	/** Face indices in the original mesh that belong to this chart. */
	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	TArray<int32> FaceIndices;
};

// --- Overlap Group ---

USTRUCT(BlueprintType)
struct XATLASLIB_API FXAtlasOverlapGroup
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	int32 GroupIndex = -1;

	/** Indices into the input FXAtlasMeshEntry array for meshes in this group. */
	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	TArray<int32> MeshIndices;

	/** AABB of the entire overlap group in source UV space. */
	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	FBox2D GroupBounds = FBox2D(FVector2D::ZeroVector, FVector2D::ZeroVector);

	/** The affine transform applied to the whole group. */
	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	FXAtlasChartTransform GroupTransform;
};

// --- Per-Mesh Result ---

USTRUCT(BlueprintType)
struct XATLASLIB_API FXAtlasMeshRepackResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	int32 MeshIndex = -1;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	UStaticMesh* StaticMesh = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	TArray<FXAtlasChartTransform> ChartTransforms;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	int32 OriginalVertexCount = 0;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	int32 NewVertexCount = 0;
};

// --- Batch Result ---

USTRUCT(BlueprintType)
struct XATLASLIB_API FXAtlasBatchRepackResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	bool bSuccess = false;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	FString ErrorMessage;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	TArray<FXAtlasMeshRepackResult> MeshResults;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	TArray<FXAtlasOverlapGroup> OverlapGroups;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	int32 AtlasWidth = 0;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	int32 AtlasHeight = 0;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	int32 TotalChartCount = 0;

	UPROPERTY(BlueprintReadOnly, Category = "ArtClaw|XAtlas")
	float Utilization = 0.0f;
};

// --- Texture Adapt Options ---

USTRUCT(BlueprintType)
struct XATLASLIB_API FXAtlasTextureAdaptOptions
{
	GENERATED_BODY()

	/** Single source texture (used if SourceTexturesByMaterial is empty). */
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	UTexture2D* SourceTexture = nullptr;

	/** Per-material source textures (takes priority over SourceTexture). */
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	TMap<int32, UTexture2D*> SourceTexturesByMaterial;

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	int32 OutputResolution = 1024;

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	FLinearColor BackgroundColor = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	int32 BleedPixels = 4;

	/** If true, UV coordinates outside 0-1 will wrap. */
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "ArtClaw|XAtlas")
	bool bWrapUV = false;
};
