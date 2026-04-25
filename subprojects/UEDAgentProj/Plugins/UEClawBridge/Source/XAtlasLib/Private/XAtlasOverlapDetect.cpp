// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#5.2
// xatlas - Cross-mesh UV overlap detection (AABB broad + SAT narrow)

#include "CoreMinimal.h"
#include "XAtlasInternalTypes.h"

namespace
{
	/** 2D SAT axis-separation test for two triangles. */
	bool TrianglesOverlap2D(
		const FVector2D& A0, const FVector2D& A1, const FVector2D& A2,
		const FVector2D& B0, const FVector2D& B1, const FVector2D& B2)
	{
		auto ProjectOnAxis = [](const FVector2D& Axis,
			const FVector2D& P0, const FVector2D& P1, const FVector2D& P2,
			float& OutMin, float& OutMax)
		{
			const float D0 = FVector2D::DotProduct(Axis, P0);
			const float D1 = FVector2D::DotProduct(Axis, P1);
			const float D2 = FVector2D::DotProduct(Axis, P2);
			OutMin = FMath::Min3(D0, D1, D2);
			OutMax = FMath::Max3(D0, D1, D2);
		};

		auto TestAxis = [&](const FVector2D& Edge) -> bool
		{
			// Perpendicular axis
			const FVector2D Axis(-Edge.Y, Edge.X);
			if (Axis.SizeSquared() < 1e-12f) return true; // degenerate edge

			float AMin, AMax, BMin, BMax;
			ProjectOnAxis(Axis, A0, A1, A2, AMin, AMax);
			ProjectOnAxis(Axis, B0, B1, B2, BMin, BMax);
			return (AMax >= BMin) && (BMax >= AMin);
		};

		// Test 6 axes: 3 edges of A, 3 edges of B
		if (!TestAxis(A1 - A0)) return false;
		if (!TestAxis(A2 - A1)) return false;
		if (!TestAxis(A0 - A2)) return false;
		if (!TestAxis(B1 - B0)) return false;
		if (!TestAxis(B2 - B1)) return false;
		if (!TestAxis(B0 - B2)) return false;

		return true; // No separating axis found = overlap
	}

	bool AABBOverlap(const FBox2D& A, const FBox2D& B)
	{
		return !(A.Max.X < B.Min.X || B.Max.X < A.Min.X ||
		         A.Max.Y < B.Min.Y || B.Max.Y < A.Min.Y);
	}

	int32 UF_Find(TArray<int32>& Parent, int32 X)
	{
		while (Parent[X] != X)
		{
			Parent[X] = Parent[Parent[X]];
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
}

void XAtlas_DetectOverlapGroups(
	const TArray<FXAtlasExtractedMesh>& Meshes,
	const TArray<TArray<FXAtlasUVIsland>>& AllIslands,
	TArray<FXAtlasOverlapGroup>& OutGroups)
{
	OutGroups.Empty();
	if (Meshes.Num() <= 1) return; // Single mesh => no cross-mesh overlap

	// Flatten all islands into a global list with mesh association
	struct FGlobalIsland
	{
		int32 MeshIdx;
		int32 LocalIslandIdx;
		const FXAtlasUVIsland* Island;
	};

	TArray<FGlobalIsland> GlobalIslands;
	for (int32 M = 0; M < AllIslands.Num(); ++M)
	{
		for (int32 I = 0; I < AllIslands[M].Num(); ++I)
		{
			GlobalIslands.Add({ M, I, &AllIslands[M][I] });
		}
	}

	const int32 N = GlobalIslands.Num();
	if (N <= 1) return;

	// Union-Find over global islands
	TArray<int32> Parent, Rank;
	Parent.SetNum(N);
	Rank.SetNum(N);
	for (int32 i = 0; i < N; ++i)
	{
		Parent[i] = i;
		Rank[i] = 0;
	}

	// Pairwise: only cross-mesh pairs
	for (int32 A = 0; A < N; ++A)
	{
		for (int32 B = A + 1; B < N; ++B)
		{
			if (GlobalIslands[A].MeshIdx == GlobalIslands[B].MeshIdx)
			{
				continue; // Same mesh, skip
			}

			const FXAtlasUVIsland& IA = *GlobalIslands[A].Island;
			const FXAtlasUVIsland& IB = *GlobalIslands[B].Island;

			// AABB broad-phase
			if (!AABBOverlap(IA.Bounds, IB.Bounds))
			{
				continue;
			}

			// SAT narrow-phase: check triangle pairs
			const FXAtlasExtractedMesh& MA = Meshes[GlobalIslands[A].MeshIdx];
			const FXAtlasExtractedMesh& MB = Meshes[GlobalIslands[B].MeshIdx];

			bool bOverlap = false;
			for (int32 FA : IA.FaceIndices)
			{
				const FVector2D A0 = MA.UVs[MA.Indices[FA * 3 + 0]];
				const FVector2D A1 = MA.UVs[MA.Indices[FA * 3 + 1]];
				const FVector2D A2 = MA.UVs[MA.Indices[FA * 3 + 2]];

				for (int32 FB : IB.FaceIndices)
				{
					const FVector2D B0 = MB.UVs[MB.Indices[FB * 3 + 0]];
					const FVector2D B1 = MB.UVs[MB.Indices[FB * 3 + 1]];
					const FVector2D B2 = MB.UVs[MB.Indices[FB * 3 + 2]];

					if (TrianglesOverlap2D(A0, A1, A2, B0, B1, B2))
					{
						bOverlap = true;
						break;
					}
				}
				if (bOverlap) break;
			}

			if (bOverlap)
			{
				UF_Merge(Parent, Rank, A, B);
			}
		}
	}

	// Collect groups (only those spanning multiple meshes)
	TMap<int32, TArray<int32>> RootToGlobalIndices;
	for (int32 i = 0; i < N; ++i)
	{
		RootToGlobalIndices.FindOrAdd(UF_Find(Parent, i)).Add(i);
	}

	int32 GroupIdx = 0;
	for (auto& Pair : RootToGlobalIndices)
	{
		// Collect unique mesh indices
		TSet<int32> UniqueMeshes;
		for (int32 GI : Pair.Value)
		{
			UniqueMeshes.Add(GlobalIslands[GI].MeshIdx);
		}
		if (UniqueMeshes.Num() <= 1) continue; // Not a cross-mesh overlap

		FXAtlasOverlapGroup Group;
		Group.GroupIndex = GroupIdx++;
		Group.MeshIndices = UniqueMeshes.Array();

		// Compute group AABB
		FBox2D GroupBounds(FVector2D(MAX_FLT, MAX_FLT), FVector2D(-MAX_FLT, -MAX_FLT));
		for (int32 GI : Pair.Value)
		{
			const FBox2D& IB = GlobalIslands[GI].Island->Bounds;
			GroupBounds.Min.X = FMath::Min(GroupBounds.Min.X, IB.Min.X);
			GroupBounds.Min.Y = FMath::Min(GroupBounds.Min.Y, IB.Min.Y);
			GroupBounds.Max.X = FMath::Max(GroupBounds.Max.X, IB.Max.X);
			GroupBounds.Max.Y = FMath::Max(GroupBounds.Max.Y, IB.Max.Y);
		}
		Group.GroupBounds = GroupBounds;

		OutGroups.Add(MoveTemp(Group));
	}
}
