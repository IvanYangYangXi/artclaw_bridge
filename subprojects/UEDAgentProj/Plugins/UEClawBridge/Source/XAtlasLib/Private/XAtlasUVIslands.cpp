// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#5.1
// xatlas - UV island detection via Union-Find

#include "CoreMinimal.h"
#include "XAtlasInternalTypes.h"

namespace
{
	int32 UF_Find(TArray<int32>& Parent, int32 X)
	{
		while (Parent[X] != X)
		{
			Parent[X] = Parent[Parent[X]]; // path compression
			X = Parent[X];
		}
		return X;
	}

	void UF_Merge(TArray<int32>& Parent, TArray<int32>& Rank, int32 A, int32 B)
	{
		A = UF_Find(Parent, A);
		B = UF_Find(Parent, B);
		if (A == B) return;
		if (Rank[A] < Rank[B]) Swap(A, B);
		Parent[B] = A;
		if (Rank[A] == Rank[B]) ++Rank[A];
	}

	/** Hash key for a UV edge (two vertex indices sharing a UV-space position). */
	struct FUVEdgeKey
	{
		FVector2D UV0;
		FVector2D UV1;

		bool operator==(const FUVEdgeKey& Other) const
		{
			return UV0.Equals(Other.UV0, 1e-6f) && UV1.Equals(Other.UV1, 1e-6f);
		}
	};

	uint32 GetTypeHash(const FUVEdgeKey& Key)
	{
		return HashCombine(
			GetTypeHash(FIntPoint(
				FMath::RoundToInt(Key.UV0.X * 1e5f),
				FMath::RoundToInt(Key.UV0.Y * 1e5f))),
			GetTypeHash(FIntPoint(
				FMath::RoundToInt(Key.UV1.X * 1e5f),
				FMath::RoundToInt(Key.UV1.Y * 1e5f))));
	}
}

void XAtlas_ComputeUVIslands(
	const FXAtlasExtractedMesh& Mesh,
	TArray<FXAtlasUVIsland>& OutIslands)
{
	OutIslands.Empty();
	const int32 NumFaces = Mesh.Indices.Num() / 3;
	if (NumFaces == 0) return;

	// Union-Find over faces
	TArray<int32> Parent, Rank;
	Parent.SetNum(NumFaces);
	Rank.SetNum(NumFaces);
	for (int32 i = 0; i < NumFaces; ++i)
	{
		Parent[i] = i;
		Rank[i] = 0;
	}

	// Build edge -> face map, then merge faces that share a UV edge
	// Key: sorted UV edge (two UV coords), Value: face index
	TMap<FUVEdgeKey, int32> EdgeToFace;
	EdgeToFace.Reserve(NumFaces * 3);

	for (int32 F = 0; F < NumFaces; ++F)
	{
		// Skip faces not in the material filter
		if (Mesh.FilterMaterials.Num() > 0 && !Mesh.FilterMaterials.Contains(Mesh.FaceMaterials[F]))
		{
			continue;
		}

		for (int32 E = 0; E < 3; ++E)
		{
			const uint32 I0 = Mesh.Indices[F * 3 + E];
			const uint32 I1 = Mesh.Indices[F * 3 + ((E + 1) % 3)];
			const FVector2D& UV0 = Mesh.UVs[I0];
			const FVector2D& UV1 = Mesh.UVs[I1];

			// Sort edge so (min, max) is canonical
			FUVEdgeKey Key;
			if (UV0.X < UV1.X || (FMath::IsNearlyEqual(UV0.X, UV1.X, 1e-6f) && UV0.Y < UV1.Y))
			{
				Key = { UV0, UV1 };
			}
			else
			{
				Key = { UV1, UV0 };
			}

			if (int32* ExistingFace = EdgeToFace.Find(Key))
			{
				UF_Merge(Parent, Rank, F, *ExistingFace);
			}
			else
			{
				EdgeToFace.Add(Key, F);
			}
		}
	}

	// Collect faces per root
	TMap<int32, TArray<int32>> RootToFaces;
	for (int32 F = 0; F < NumFaces; ++F)
	{
		if (Mesh.FilterMaterials.Num() > 0 && !Mesh.FilterMaterials.Contains(Mesh.FaceMaterials[F]))
		{
			continue;
		}
		const int32 Root = UF_Find(Parent, F);
		RootToFaces.FindOrAdd(Root).Add(F);
	}

	// Build islands
	int32 IslandIdx = 0;
	for (auto& Pair : RootToFaces)
	{
		FXAtlasUVIsland Island;
		Island.MeshIndex = Mesh.MeshIndex;
		Island.IslandIndex = IslandIdx++;
		Island.FaceIndices = MoveTemp(Pair.Value);

		// Compute bounds + dominant material
		TMap<int32, int32> MatCount;
		for (int32 F : Island.FaceIndices)
		{
			MatCount.FindOrAdd(Mesh.FaceMaterials[F])++;
			for (int32 V = 0; V < 3; ++V)
			{
				const FVector2D& UV = Mesh.UVs[Mesh.Indices[F * 3 + V]];
				Island.Bounds.Min.X = FMath::Min(Island.Bounds.Min.X, UV.X);
				Island.Bounds.Min.Y = FMath::Min(Island.Bounds.Min.Y, UV.Y);
				Island.Bounds.Max.X = FMath::Max(Island.Bounds.Max.X, UV.X);
				Island.Bounds.Max.Y = FMath::Max(Island.Bounds.Max.Y, UV.Y);
			}
		}

		// Dominant material
		int32 MaxCount = 0;
		for (auto& MC : MatCount)
		{
			if (MC.Value > MaxCount)
			{
				MaxCount = MC.Value;
				Island.MaterialID = MC.Key;
			}
		}

		OutIslands.Add(MoveTemp(Island));
	}
}
