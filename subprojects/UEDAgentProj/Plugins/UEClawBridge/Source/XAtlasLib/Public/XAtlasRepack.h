// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#5
// xatlas UV Repack - core orchestration header

#pragma once

#include "CoreMinimal.h"
#include "XAtlasTypes.h"
#include "XAtlasInternalTypes.h"

/**
 * Core repack orchestration. Calls extract -> islands -> overlap -> xatlas -> transform -> write.
 */
class XATLASLIB_API FXAtlasRepack
{
public:
	/**
	 * Run the full batch repack pipeline.
	 */
	static FXAtlasBatchRepackResult BatchRepack(
		const TArray<FXAtlasMeshEntry>& Meshes,
		const FXAtlasRepackOptions& Options);
};
