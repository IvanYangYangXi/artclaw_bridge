// Copyright ArtClaw. All Rights Reserved.

#include "MeshUVOpsAPI.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshDescription.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"

int32 UMeshUVOpsAPI::RemapMeshUV(
	const FString& MeshPath,
	int32 UVChannel,
	FVector2D Offset,
	FVector2D Scale,
	int32 LODIndex)
{
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *MeshPath);
	if (!Mesh)
	{
		UE_LOG(LogTemp, Error, TEXT("[MeshUVOps] Cannot load mesh: %s"), *MeshPath);
		return -1;
	}

	if (!Mesh->IsSourceModelValid(LODIndex))
	{
		UE_LOG(LogTemp, Error, TEXT("[MeshUVOps] Invalid LOD index %d for %s"), LODIndex, *MeshPath);
		return -1;
	}

	// Get the SourceModel's MeshDescription (the authoritative data)
	FMeshDescription* MeshDesc = Mesh->GetMeshDescription(LODIndex);
	if (!MeshDesc)
	{
		UE_LOG(LogTemp, Error, TEXT("[MeshUVOps] No MeshDescription at LOD %d for %s"), LODIndex, *MeshPath);
		return -1;
	}

	// Access UV attribute
	FStaticMeshAttributes Attributes(*MeshDesc);
	TVertexInstanceAttributesRef<FVector2f> UVs = Attributes.GetVertexInstanceUVs();
	
	if (UVChannel >= UVs.GetNumChannels())
	{
		UE_LOG(LogTemp, Error, TEXT("[MeshUVOps] UV channel %d out of range (max %d) for %s"),
			UVChannel, UVs.GetNumChannels(), *MeshPath);
		return -1;
	}

	// Remap all vertex instance UVs
	int32 Count = 0;
	for (const FVertexInstanceID VertexInstanceID : MeshDesc->VertexInstances().GetElementIDs())
	{
		FVector2f OldUV = UVs.Get(VertexInstanceID, UVChannel);
		FVector2f NewUV;
		NewUV.X = (OldUV.X - (float)Offset.X) * (float)Scale.X;
		NewUV.Y = (OldUV.Y - (float)Offset.Y) * (float)Scale.Y;
		UVs.Set(VertexInstanceID, UVChannel, NewUV);
		Count++;
	}

	// Commit: mark source model dirty and trigger proper rebuild
	Mesh->CommitMeshDescription(LODIndex);
	// PostEditChange will rebuild RenderData with correct UV channel count
	Mesh->PostEditChange();

	UE_LOG(LogTemp, Log, TEXT("[MeshUVOps] Remapped %d vertices UV%d on %s (Offset=%.4f,%.4f Scale=%.4f,%.4f)"),
		Count, UVChannel, *MeshPath, Offset.X, Offset.Y, Scale.X, Scale.Y);

	return Count;
}

int32 UMeshUVOpsAPI::GetRenderDataNumUVChannels(const FString& MeshPath, int32 LODIndex)
{
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *MeshPath);
	if (!Mesh || !Mesh->GetRenderData())
	{
		return -1;
	}

	const FStaticMeshLODResources& LODResources = Mesh->GetRenderData()->LODResources[LODIndex];
	return LODResources.GetNumTexCoords();
}
