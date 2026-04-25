// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#5.1
// xatlas - Static Mesh data extraction

#include "CoreMinimal.h"
#include "XAtlasInternalTypes.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "MeshDescription.h"

bool XAtlas_ExtractMeshData(
	const FXAtlasMeshEntry& Entry, int32 MeshIndex,
	FXAtlasExtractedMesh& OutMesh, FString& OutError)
{
	if (!Entry.StaticMesh)
	{
		OutError = FString::Printf(TEXT("Mesh entry %d: StaticMesh is null"), MeshIndex);
		return false;
	}

	UStaticMesh* SM = Entry.StaticMesh;
	const int32 LOD = Entry.LODIndex;

	if (!SM->HasValidRenderData())
	{
		OutError = FString::Printf(TEXT("Mesh '%s': no valid render data"), *SM->GetName());
		return false;
	}

	const FStaticMeshLODResources& LODRes = SM->GetLODForExport(LOD);
	const int32 NumVerts = LODRes.VertexBuffers.StaticMeshVertexBuffer.GetNumVertices();
	const int32 NumUVChannels = LODRes.VertexBuffers.StaticMeshVertexBuffer.GetNumTexCoords();

	if (Entry.SourceUVChannel >= NumUVChannels)
	{
		OutError = FString::Printf(
			TEXT("Mesh '%s': SourceUVChannel %d >= NumUVChannels %d"),
			*SM->GetName(), Entry.SourceUVChannel, NumUVChannels);
		return false;
	}

	// Populate output
	OutMesh.MeshIndex = MeshIndex;
	OutMesh.StaticMesh = SM;
	OutMesh.SourceUVChannel = Entry.SourceUVChannel;
	OutMesh.TargetUVChannel = Entry.TargetUVChannel;
	OutMesh.LODIndex = LOD;

	// Material filter
	for (int32 MatID : Entry.MaterialIDs)
	{
		OutMesh.FilterMaterials.Add(MatID);
	}

	// Extract positions
	OutMesh.Positions.SetNum(NumVerts);
	for (int32 i = 0; i < NumVerts; ++i)
	{
		OutMesh.Positions[i] = FVector(LODRes.VertexBuffers.PositionVertexBuffer.VertexPosition(i));
	}

	// Extract UVs
	OutMesh.UVs.SetNum(NumVerts);
	for (int32 i = 0; i < NumVerts; ++i)
	{
		OutMesh.UVs[i] = FVector2D(LODRes.VertexBuffers.StaticMeshVertexBuffer.GetVertexUV(i, Entry.SourceUVChannel));
	}

	// Extract indices + per-face material
	FIndexArrayView IdxView = LODRes.IndexBuffer.GetArrayView();
	const int32 NumIndices = IdxView.Num();
	const int32 NumFaces = NumIndices / 3;

	OutMesh.Indices.SetNum(NumIndices);
	for (int32 i = 0; i < NumIndices; ++i)
	{
		OutMesh.Indices[i] = IdxView[i];
	}

	// Build per-face material ID from mesh sections
	OutMesh.FaceMaterials.SetNum(NumFaces);
	for (int32 SecIdx = 0; SecIdx < LODRes.Sections.Num(); ++SecIdx)
	{
		const FStaticMeshSection& Sec = LODRes.Sections[SecIdx];
		const int32 FirstFace = Sec.FirstIndex / 3;
		const int32 FaceCount = Sec.NumTriangles;
		for (int32 F = 0; F < FaceCount; ++F)
		{
			if ((FirstFace + F) < NumFaces)
			{
				OutMesh.FaceMaterials[FirstFace + F] = Sec.MaterialIndex;
			}
		}
	}

	return true;
}
