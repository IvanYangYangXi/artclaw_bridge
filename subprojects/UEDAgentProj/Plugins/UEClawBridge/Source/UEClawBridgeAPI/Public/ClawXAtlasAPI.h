// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#4
// xatlas BP/Python API - Blueprint function library

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "XAtlasTypes.h"
#include "ClawXAtlasAPI.generated.h"

/**
 * Blueprint/Python API for xatlas UV repack operations.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UClawXAtlasAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	// --- Repack ---

	/** Repack UVs of a single static mesh. */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|XAtlas")
	static FXAtlasBatchRepackResult RepackUVs(
		UStaticMesh* Mesh,
		int32 SrcUV = 0,
		int32 DstUV = 1,
		FXAtlasRepackOptions Options = FXAtlasRepackOptions());

	/** Batch repack UVs of multiple meshes (supports cross-mesh overlap detection). */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|XAtlas")
	static FXAtlasBatchRepackResult BatchRepackUVs(
		const TArray<FXAtlasMeshEntry>& Meshes,
		FXAtlasRepackOptions Options = FXAtlasRepackOptions());

	// --- Texture Adaptation ---

	/** Adapt source texture(s) to the new UV layout. Returns the new texture. */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|XAtlas")
	static UTexture2D* AdaptTexture(
		const FXAtlasBatchRepackResult& RepackResult,
		FXAtlasTextureAdaptOptions Options);

	/** Adapt source texture(s) to the new UV layout and save to file. */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|XAtlas")
	static bool AdaptTextureToFile(
		const FXAtlasBatchRepackResult& RepackResult,
		FXAtlasTextureAdaptOptions Options,
		const FString& OutputPath);

	// --- Utilities ---

	/** Copy UV channel from Src to Dst on a static mesh. */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|XAtlas")
	static bool CopyUVChannel(
		UStaticMesh* Mesh,
		int32 SrcChannel,
		int32 DstChannel,
		int32 LODIndex = 0);

	/** Detect overlap groups without performing repack. */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|XAtlas")
	static TArray<FXAtlasOverlapGroup> DetectOverlapGroups(
		const TArray<FXAtlasMeshEntry>& Meshes);
};
