// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#5.1
// xatlas - Apply repack results: write new UVs + apply overlap group transforms

#include "XAtlasRepackWrite.h"
#include "XAtlasInternalTypes.h"
#include "XAtlasChartTransform.h"
#include "xatlas.h"

/**
 * Write repacked UVs from xatlas output back to meshes (independent islands).
 */
void XAtlas_ApplyIndependentRepack(
	const xatlas::Atlas* Atlas,
	const TArray<int32>& XAtlasMeshToSourceMesh,
	const TArray<FXAtlasExtractedMesh>& ExtractedMeshes)
{
	for (int32 XM = 0; XM < (int32)Atlas->meshCount; ++XM)
	{
		const int32 M = XAtlasMeshToSourceMesh[XM];
		if (M < 0) continue; // Virtual rect

		const xatlas::Mesh& OutMesh = Atlas->meshes[XM];
		const auto& EM = ExtractedMeshes[M];

		// Build new UV array, start with original
		TArray<FVector2D> NewUVs = EM.UVs;

		// Use max dimension to normalize — preserves UV island aspect ratio
		const float MaxDim = static_cast<float>(FMath::Max(Atlas->width, Atlas->height));

		// Overwrite with repacked UVs
		for (uint32 V = 0; V < OutMesh.vertexCount; ++V)
		{
			const uint32 OrigIdx = OutMesh.vertexArray[V].xref;
			if (OrigIdx < static_cast<uint32>(NewUVs.Num()))
			{
				NewUVs[OrigIdx] = FVector2D(
					OutMesh.vertexArray[V].uv[0] / MaxDim,
					OutMesh.vertexArray[V].uv[1] / MaxDim);
			}
		}

		FString Error;
		if (!XAtlas_WriteUVsToMesh(EM.StaticMesh, NewUVs, EM.Indices,
			EM.TargetUVChannel, EM.LODIndex, Error))
		{
			UE_LOG(LogTemp, Warning,
				TEXT("UV write failed for mesh %d ('%s'): %s"),
				M, *EM.StaticMesh->GetName(), *Error);
		}
	}
}

/**
 * Apply overlap group transforms to meshes.
 */
void XAtlas_ApplyOverlapGroupTransforms(
	const TArray<FXAtlasOverlapGroup>& OverlapGroups,
	const TArray<FXAtlasExtractedMesh>& ExtractedMeshes)
{
	for (const auto& Group : OverlapGroups)
	{
		if (Group.GroupTransform.AffineMatrix.Num() != 6) continue;

		for (int32 MI : Group.MeshIndices)
		{
			const auto& EM = ExtractedMeshes[MI];
			TArray<FVector2D> NewUVs = EM.UVs;

			const int32 NumFaces = EM.Indices.Num() / 3;
			for (int32 F = 0; F < NumFaces; ++F)
			{
				for (int32 V = 0; V < 3; ++V)
				{
					const uint32 Idx = EM.Indices[F * 3 + V];
					const FVector2D& Src = EM.UVs[Idx];
					if (Group.GroupBounds.IsInside(Src))
					{
						NewUVs[Idx] = FXAtlasChartTransformUtil::ApplyForward(
							Group.GroupTransform.AffineMatrix, Src);
					}
				}
			}

			FString Error;
			if (!XAtlas_WriteUVsToMesh(EM.StaticMesh, NewUVs, EM.Indices,
				EM.TargetUVChannel, EM.LODIndex, Error))
			{
				UE_LOG(LogTemp, Warning,
					TEXT("UV write (overlap group %d) failed for mesh %d: %s"),
					Group.GroupIndex, MI, *Error);
			}
		}
	}
}
