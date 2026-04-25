// Copyright ArtClaw. All Rights Reserved.
// Mesh UV manipulation — proper SourceModel write + PostEditChange rebuild.
// Avoids build_from_static_mesh_descriptions which creates 8 UV channels in RenderData.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "MeshUVOpsAPI.generated.h"

/**
 * Mesh UV operations that correctly rebuild RenderData.
 * All functions modify the SourceModel MeshDescription and trigger PostEditChange
 * so UV channel count stays correct (no phantom 8-channel issue).
 */
UCLASS()
class UECLAWBRIDGEAPI_API UMeshUVOpsAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Remap UV0 of a StaticMesh: newUV = (oldUV - Offset) * Scale.
	 * Modifies SourceModel MeshDescription and triggers proper rebuild.
	 *
	 * @param MeshPath   Package path, e.g. "/Game/Meshes/SM_Foo"
	 * @param UVChannel  Which UV channel to remap (usually 0)
	 * @param Offset     Subtracted from each UV before scaling (min corner of UV bbox)
	 * @param Scale      Multiplied after offset (1/span of UV bbox)
	 * @param LODIndex   LOD to modify (default 0)
	 * @return Number of vertex instances remapped, or -1 on error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|MeshUV", CallInEditor)
	static int32 RemapMeshUV(
		const FString& MeshPath,
		int32 UVChannel,
		FVector2D Offset,
		FVector2D Scale,
		int32 LODIndex = 0);

	/**
	 * Get the actual number of UV channels in RenderData (not MeshDescription).
	 * This is what the editor UI shows.
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|MeshUV", CallInEditor)
	static int32 GetRenderDataNumUVChannels(const FString& MeshPath, int32 LODIndex = 0);
};
