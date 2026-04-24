// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#5.1
// xatlas - Write repacked UVs back to UStaticMesh

#include "CoreMinimal.h"
#include "XAtlasInternalTypes.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"

bool XAtlas_WriteUVsToMesh(
	UStaticMesh* Mesh,
	const TArray<FVector2D>& NewUVs,
	const TArray<uint32>& OriginalIndices,
	int32 TargetUVChannel, int32 LODIndex,
	FString& OutError)
{
	if (!Mesh)
	{
		OutError = TEXT("Mesh is null");
		return false;
	}

	FMeshDescription* MeshDesc = Mesh->GetMeshDescription(LODIndex);
	if (!MeshDesc)
	{
		OutError = FString::Printf(TEXT("Mesh '%s': no MeshDescription for LOD %d"), *Mesh->GetName(), LODIndex);
		return false;
	}

	FStaticMeshAttributes Attributes(*MeshDesc);

	// Ensure target UV channel exists
	const int32 CurrentUVCount = Attributes.GetVertexInstanceUVs().GetNumChannels();
	if (TargetUVChannel >= CurrentUVCount)
	{
		const int32 ChannelsToAdd = TargetUVChannel - CurrentUVCount + 1;
		for (int32 i = 0; i < ChannelsToAdd; ++i)
		{
			Attributes.GetVertexInstanceUVs().InsertChannel(CurrentUVCount + i);
		}
	}

	TVertexInstanceAttributesRef<FVector2f> UVs = Attributes.GetVertexInstanceUVs();
	const int32 NumVertexInstances = MeshDesc->VertexInstances().Num();

	if (NumVertexInstances == NewUVs.Num())
	{
		// Direct 1:1 mapping
		int32 Idx = 0;
		for (const FVertexInstanceID VertInstID : MeshDesc->VertexInstances().GetElementIDs())
		{
			UVs.Set(VertInstID, TargetUVChannel, FVector2f(NewUVs[Idx].X, NewUVs[Idx].Y));
			++Idx;
		}
	}
	else
	{
		// Fallback: map via render-vertex index -> new UV
		TMap<uint32, FVector2D> VertToUV;
		const int32 NumIndices = OriginalIndices.Num();
		for (int32 i = 0; i < NumIndices; ++i)
		{
			const uint32 VertIdx = OriginalIndices[i];
			if (VertIdx < static_cast<uint32>(NewUVs.Num()))
			{
				VertToUV.Add(VertIdx, NewUVs[VertIdx]);
			}
		}

		int32 Idx = 0;
		for (const FVertexInstanceID VertInstID : MeshDesc->VertexInstances().GetElementIDs())
		{
			if (const FVector2D* UV = VertToUV.Find(static_cast<uint32>(Idx)))
			{
				UVs.Set(VertInstID, TargetUVChannel, FVector2f(UV->X, UV->Y));
			}
			++Idx;
		}
	}

	// Commit changes
	Mesh->CommitMeshDescription(LODIndex);
	Mesh->Build(false);
	Mesh->PostEditChange();
	Mesh->MarkPackageDirty();

	return true;
}
