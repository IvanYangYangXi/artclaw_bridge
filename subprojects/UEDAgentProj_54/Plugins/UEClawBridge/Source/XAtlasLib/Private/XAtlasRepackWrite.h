// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#5.1
// xatlas - Apply repack results helpers (forward declarations)

#pragma once

#include "CoreMinimal.h"

struct FXAtlasExtractedMesh;
struct FXAtlasOverlapGroup;

namespace xatlas { struct Atlas; }

/** Write repacked UVs from xatlas output back to meshes (independent islands). */
void XAtlas_ApplyIndependentRepack(
	const xatlas::Atlas* Atlas,
	const TArray<int32>& XAtlasMeshToSourceMesh,
	const TArray<FXAtlasExtractedMesh>& ExtractedMeshes);

/** Apply overlap group transforms to meshes. */
void XAtlas_ApplyOverlapGroupTransforms(
	const TArray<FXAtlasOverlapGroup>& OverlapGroups,
	const TArray<FXAtlasExtractedMesh>& ExtractedMeshes);
