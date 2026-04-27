// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#3
// xatlas internal data structures shared across implementation files

#pragma once

#include "CoreMinimal.h"
#include "XAtlasTypes.h"

/**
 * Internal extracted mesh data for xatlas processing.
 * Not exported - used only within XAtlasLib.
 */
struct FXAtlasExtractedMesh
{
	int32 MeshIndex = -1;
	UStaticMesh* StaticMesh = nullptr;

	TArray<FVector>    Positions;
	TArray<FVector2D>  UVs;          // Source UV channel
	TArray<uint32>    Indices;      // Triangle indices
	TArray<int32>     FaceMaterials; // Material ID per face
	TSet<int32>       FilterMaterials; // Empty = all

	int32 SourceUVChannel = 0;
	int32 TargetUVChannel = 1;
	int32 LODIndex = 0;
};

/**
 * A UV island: a connected group of faces sharing UV edges.
 */
struct FXAtlasUVIsland
{
	int32 MeshIndex = -1;
	int32 IslandIndex = -1;
	TArray<int32> FaceIndices;
	FBox2D Bounds = FBox2D(FVector2D(MAX_FLT, MAX_FLT), FVector2D(-MAX_FLT, -MAX_FLT));
	int32 MaterialID = -1; // Dominant material
};

// --- Free functions (internal, implemented in separate .cpp files) ---

/** Extract mesh data from UStaticMesh. */
XATLASLIB_API bool XAtlas_ExtractMeshData(
	const FXAtlasMeshEntry& Entry, int32 MeshIndex,
	FXAtlasExtractedMesh& OutMesh, FString& OutError);

/** Compute UV islands via Union-Find. */
XATLASLIB_API void XAtlas_ComputeUVIslands(
	const FXAtlasExtractedMesh& Mesh,
	TArray<FXAtlasUVIsland>& OutIslands);

/** Detect overlap groups across meshes (AABB + SAT). */
XATLASLIB_API void XAtlas_DetectOverlapGroups(
	const TArray<FXAtlasExtractedMesh>& Meshes,
	const TArray<TArray<FXAtlasUVIsland>>& AllIslands,
	TArray<FXAtlasOverlapGroup>& OutGroups);

/** Write repacked UVs back to a static mesh. */
XATLASLIB_API bool XAtlas_WriteUVsToMesh(
	UStaticMesh* Mesh,
	const TArray<FVector2D>& NewUVs,
	const TArray<uint32>& OriginalIndices,
	int32 TargetUVChannel, int32 LODIndex,
	FString& OutError);
