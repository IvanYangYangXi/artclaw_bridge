// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#5.1
// xatlas - Core repack orchestration: extract -> islands -> overlap -> xatlas -> transform -> write

#include "XAtlasRepack.h"
#include "XAtlasInternalTypes.h"
#include "XAtlasChartTransform.h"
#include "XAtlasRepackWrite.h"
#include "xatlas.h"
#include "Misc/ScopedSlowTask.h"

namespace
{
	/** xatlas progress callback -> UE ScopedSlowTask */
	struct FProgressContext
	{
		FScopedSlowTask* SlowTask = nullptr;
	};

	bool XAtlasProgressCallback(xatlas::ProgressCategory Category, int Progress, void* UserData)
	{
		auto* Ctx = static_cast<FProgressContext*>(UserData);
		if (Ctx && Ctx->SlowTask)
		{
			Ctx->SlowTask->EnterProgressFrame(1.0f,
				FText::FromString(FString::Printf(TEXT("xatlas %s: %d%%"),
					UTF8_TO_TCHAR(xatlas::StringForEnum(Category)), Progress)));
		}
		return true; // continue
	}

	/** Build virtual rectangle mesh for an overlap group (4 verts, 2 tris). */
	void BuildVirtualRectUVMesh(const FBox2D& Bounds, TArray<FVector2f>& OutUVs, TArray<uint32>& OutIndices)
	{
		OutUVs.SetNum(4);
		OutUVs[0] = FVector2f(Bounds.Min.X, Bounds.Min.Y);
		OutUVs[1] = FVector2f(Bounds.Max.X, Bounds.Min.Y);
		OutUVs[2] = FVector2f(Bounds.Max.X, Bounds.Max.Y);
		OutUVs[3] = FVector2f(Bounds.Min.X, Bounds.Max.Y);
		OutIndices = { 0, 1, 2, 0, 2, 3 };
	}

	/** Check if a face belongs to any overlap group. */
	bool FaceInOverlapGroup(
		int32 MeshIdx, int32 FaceIdx,
		const TArray<FXAtlasOverlapGroup>& Groups,
		const TArray<TArray<FXAtlasUVIsland>>& AllIslands)
	{
		for (const auto& Group : Groups)
		{
			if (!Group.MeshIndices.Contains(MeshIdx)) continue;
			for (const auto& Island : AllIslands[MeshIdx])
			{
				if (Island.Bounds.Max.X < Group.GroupBounds.Min.X ||
					Group.GroupBounds.Max.X < Island.Bounds.Min.X ||
					Island.Bounds.Max.Y < Group.GroupBounds.Min.Y ||
					Group.GroupBounds.Max.Y < Island.Bounds.Min.Y)
				{
					continue;
				}
				if (Island.FaceIndices.Contains(FaceIdx))
				{
					return true;
				}
			}
		}
		return false;
	}

	/** Extract chart transforms from xatlas output for independent meshes. */
	void ExtractChartTransforms(
		const xatlas::Atlas* Atlas,
		int32 XAtlasMeshIdx, int32 SourceMeshIdx,
		const FXAtlasExtractedMesh& EM,
		FXAtlasMeshRepackResult& MeshResult)
	{
		const xatlas::Mesh& OutMesh = Atlas->meshes[XAtlasMeshIdx];
		MeshResult.NewVertexCount = OutMesh.vertexCount;

		// Use max dimension to normalize UVs — preserves aspect ratio of UV islands
		const float MaxDim = static_cast<float>(FMath::Max(Atlas->width, Atlas->height));

		for (uint32 C = 0; C < OutMesh.chartCount; ++C)
		{
			const xatlas::Chart& Chart = OutMesh.chartArray[C];
			if (Chart.faceCount == 0) continue;

			// Use first face for transform computation
			const uint32 FI = Chart.faceArray[0];
			const uint32 I0 = OutMesh.indexArray[FI * 3 + 0];
			const uint32 I1 = OutMesh.indexArray[FI * 3 + 1];
			const uint32 I2 = OutMesh.indexArray[FI * 3 + 2];

			const FVector2D& SrcUV0 = EM.UVs[OutMesh.vertexArray[I0].xref];
			const FVector2D& SrcUV1 = EM.UVs[OutMesh.vertexArray[I1].xref];
			const FVector2D& SrcUV2 = EM.UVs[OutMesh.vertexArray[I2].xref];

			const FVector2D DstUV0(OutMesh.vertexArray[I0].uv[0] / MaxDim, OutMesh.vertexArray[I0].uv[1] / MaxDim);
			const FVector2D DstUV1(OutMesh.vertexArray[I1].uv[0] / MaxDim, OutMesh.vertexArray[I1].uv[1] / MaxDim);
			const FVector2D DstUV2(OutMesh.vertexArray[I2].uv[0] / MaxDim, OutMesh.vertexArray[I2].uv[1] / MaxDim);

			FXAtlasChartTransform CT;
			CT.ChartIndex = static_cast<int32>(C);
			CT.MaterialID = static_cast<int32>(Chart.material);

			if (!FXAtlasChartTransformUtil::ComputeFromTriangle(
				SrcUV0, SrcUV1, SrcUV2, DstUV0, DstUV1, DstUV2, CT))
			{
				continue; // Degenerate, skip
			}

			// Collect face indices
			CT.FaceIndices.SetNum(Chart.faceCount);
			for (uint32 F = 0; F < Chart.faceCount; ++F)
			{
				CT.FaceIndices[F] = static_cast<int32>(Chart.faceArray[F]);
			}

			// Compute source/target bounds
			CT.SourceBounds = FBox2D(FVector2D(MAX_FLT, MAX_FLT), FVector2D(-MAX_FLT, -MAX_FLT));
			CT.TargetBounds = CT.SourceBounds;
			for (uint32 F = 0; F < Chart.faceCount; ++F)
			{
				for (int32 V = 0; V < 3; ++V)
				{
					const uint32 VI = OutMesh.indexArray[Chart.faceArray[F] * 3 + V];
					const FVector2D Src = EM.UVs[OutMesh.vertexArray[VI].xref];
					const FVector2D Dst(OutMesh.vertexArray[VI].uv[0] / MaxDim, OutMesh.vertexArray[VI].uv[1] / MaxDim);

					CT.SourceBounds += Src;
					CT.TargetBounds += Dst;
				}
			}

			MeshResult.ChartTransforms.Add(MoveTemp(CT));
		}
	}
}

FXAtlasBatchRepackResult FXAtlasRepack::BatchRepack(
	const TArray<FXAtlasMeshEntry>& Meshes,
	const FXAtlasRepackOptions& Options)
{
	FXAtlasBatchRepackResult Result;
	if (Meshes.Num() == 0)
	{
		Result.ErrorMessage = TEXT("No meshes provided");
		return Result;
	}

	FScopedSlowTask SlowTask(Meshes.Num() + 3, FText::FromString(TEXT("UV Repack")));
	SlowTask.MakeDialog();

	// --- Step 1: Extract mesh data ---
	SlowTask.EnterProgressFrame(1.0f, FText::FromString(TEXT("Extracting mesh data...")));
	TArray<FXAtlasExtractedMesh> ExtractedMeshes;
	ExtractedMeshes.SetNum(Meshes.Num());
	for (int32 M = 0; M < Meshes.Num(); ++M)
	{
		FString Error;
		if (!XAtlas_ExtractMeshData(Meshes[M], M, ExtractedMeshes[M], Error))
		{
			Result.ErrorMessage = Error;
			return Result;
		}
	}

	// --- Step 2: Compute UV islands ---
	SlowTask.EnterProgressFrame(1.0f, FText::FromString(TEXT("Computing UV islands...")));
	TArray<TArray<FXAtlasUVIsland>> AllIslands;
	AllIslands.SetNum(Meshes.Num());
	for (int32 M = 0; M < Meshes.Num(); ++M)
	{
		XAtlas_ComputeUVIslands(ExtractedMeshes[M], AllIslands[M]);
	}

	// --- Step 3: Detect overlap groups ---
	TArray<FXAtlasOverlapGroup> OverlapGroups;
	XAtlas_DetectOverlapGroups(ExtractedMeshes, AllIslands, OverlapGroups);

	// --- Step 4: Build xatlas input + PackCharts ---
	SlowTask.EnterProgressFrame(1.0f, FText::FromString(TEXT("Packing charts...")));
	xatlas::Atlas* Atlas = xatlas::Create();

	FProgressContext ProgCtx;
	ProgCtx.SlowTask = &SlowTask;
	xatlas::SetProgressCallback(Atlas, XAtlasProgressCallback, &ProgCtx);

	// Mapping: xatlas mesh index -> source mesh index (-1 for virtual rects)
	TArray<int32> XAtlasMeshToSource;

	// 4a: Add overlap group virtual rectangles
	for (int32 G = 0; G < OverlapGroups.Num(); ++G)
	{
		TArray<FVector2f> RectUVs;
		TArray<uint32> RectIndices;
		BuildVirtualRectUVMesh(OverlapGroups[G].GroupBounds, RectUVs, RectIndices);

		xatlas::UvMeshDecl Decl;
		Decl.vertexUvData = RectUVs.GetData();
		Decl.vertexCount = RectUVs.Num();
		Decl.vertexStride = sizeof(FVector2f);
		Decl.indexData = RectIndices.GetData();
		Decl.indexCount = RectIndices.Num();
		Decl.indexFormat = xatlas::IndexFormat::UInt32;

		xatlas::AddMeshError Err = xatlas::AddUvMesh(Atlas, Decl);
		if (Err != xatlas::AddMeshError::Success)
		{
			Result.ErrorMessage = FString::Printf(
				TEXT("AddUvMesh for overlap group %d failed: %s"),
				G, UTF8_TO_TCHAR(xatlas::StringForEnum(Err)));
			xatlas::Destroy(Atlas);
			return Result;
		}
		XAtlasMeshToSource.Add(-1); // Virtual rect, no source mesh
	}

	// 4b: Add independent islands per mesh
	for (int32 M = 0; M < ExtractedMeshes.Num(); ++M)
	{
		const auto& EM = ExtractedMeshes[M];
		const int32 NumFaces = EM.Indices.Num() / 3;

		// Deduplicate overlapping faces: group faces by their UV signature
		// Faces with identical UV coordinates (all 3 verts) are intentionally overlapping
		TMap<uint64, int32> UVSignatureToFirstFace; // hash -> first face index
		TArray<int32> UniqueFaceIndices;             // faces to submit to xatlas

		for (int32 F = 0; F < NumFaces; ++F)
		{
			if (EM.FilterMaterials.Num() > 0 && !EM.FilterMaterials.Contains(EM.FaceMaterials[F]))
			{
				continue;
			}
			if (FaceInOverlapGroup(M, F, OverlapGroups, AllIslands))
			{
				continue;
			}

			// Compute UV signature hash: sorted UV coords of the 3 verts
			FVector2D UVs[3];
			for (int32 V = 0; V < 3; ++V)
			{
				UVs[V] = EM.UVs[EM.Indices[F * 3 + V]];
			}
			// Sort to make order-independent
			if (UVs[0].X > UVs[1].X || (UVs[0].X == UVs[1].X && UVs[0].Y > UVs[1].Y))
				Swap(UVs[0], UVs[1]);
			if (UVs[1].X > UVs[2].X || (UVs[1].X == UVs[2].X && UVs[1].Y > UVs[2].Y))
				Swap(UVs[1], UVs[2]);
			if (UVs[0].X > UVs[1].X || (UVs[0].X == UVs[1].X && UVs[0].Y > UVs[1].Y))
				Swap(UVs[0], UVs[1]);

			// Hash the 6 floats
			uint64 Hash = 0;
			for (int32 V = 0; V < 3; ++V)
			{
				Hash ^= GetTypeHash(FVector2f(UVs[V])) + 0x9e3779b97f4a7c15ULL + (Hash << 6) + (Hash >> 2);
			}

			if (!UVSignatureToFirstFace.Contains(Hash))
			{
				UVSignatureToFirstFace.Add(Hash, F);
				UniqueFaceIndices.Add(F);
			}
		}

		// Build index array from unique faces only
		TArray<uint32> IndependentIndices;
		for (int32 F : UniqueFaceIndices)
		{
			IndependentIndices.Add(EM.Indices[F * 3 + 0]);
			IndependentIndices.Add(EM.Indices[F * 3 + 1]);
			IndependentIndices.Add(EM.Indices[F * 3 + 2]);
		}

		UE_LOG(LogTemp, Log, TEXT("[XAtlas] Mesh %d '%s': %d total faces, %d unique faces (deduplicated %d overlapping)"),
			M, *EM.StaticMesh->GetName(), NumFaces, UniqueFaceIndices.Num(), NumFaces - UniqueFaceIndices.Num());
		if (IndependentIndices.Num() == 0) continue;

		// Convert FVector2D (double) to FVector2f (float) for xatlas
		TArray<FVector2f> FloatUVs;
		FloatUVs.SetNum(EM.UVs.Num());
		for (int32 i = 0; i < EM.UVs.Num(); ++i)
		{
			FloatUVs[i] = FVector2f(EM.UVs[i].X, EM.UVs[i].Y);
		}

		UE_LOG(LogTemp, Log, TEXT("[XAtlas] Mesh %d '%s': %d verts, %d indices (%d faces), UV range: stride=%d"),
			M, *EM.StaticMesh->GetName(), FloatUVs.Num(), IndependentIndices.Num(),
			IndependentIndices.Num() / 3, (int32)sizeof(FVector2f));

		// Log first few UVs for debugging
		for (int32 i = 0; i < FMath::Min(3, FloatUVs.Num()); ++i)
		{
			UE_LOG(LogTemp, Log, TEXT("[XAtlas]   UV[%d] = (%.4f, %.4f)"), i, FloatUVs[i].X, FloatUVs[i].Y);
		}

		xatlas::UvMeshDecl Decl;
		Decl.vertexUvData = FloatUVs.GetData();
		Decl.vertexCount = FloatUVs.Num();
		Decl.vertexStride = sizeof(FVector2f);
		Decl.indexData = IndependentIndices.GetData();
		Decl.indexCount = IndependentIndices.Num();
		Decl.indexFormat = xatlas::IndexFormat::UInt32;

		xatlas::AddMeshError Err = xatlas::AddUvMesh(Atlas, Decl);
		UE_LOG(LogTemp, Log, TEXT("[XAtlas] AddUvMesh mesh %d: result=%s"),
			M, UTF8_TO_TCHAR(xatlas::StringForEnum(Err)));
		if (Err != xatlas::AddMeshError::Success)
		{
			Result.ErrorMessage = FString::Printf(
				TEXT("AddUvMesh for mesh %d ('%s') failed: %s"),
				M, *EM.StaticMesh->GetName(), UTF8_TO_TCHAR(xatlas::StringForEnum(Err)));
			xatlas::Destroy(Atlas);
			return Result;
		}
		XAtlasMeshToSource.Add(M);
	}

	// Compute charts (required even for UvMesh - organizes UV data into charts)
	xatlas::ComputeCharts(Atlas);

	// Pack
	xatlas::PackOptions PackOpts;
	PackOpts.resolution = Options.Resolution;
	PackOpts.padding = Options.Padding;
	PackOpts.texelsPerUnit = Options.TexelsPerUnit;
	PackOpts.rotateCharts = Options.bAllowRotation;
	PackOpts.createImage = true;
	PackOpts.bruteForce = false;
	xatlas::PackCharts(Atlas, PackOpts);

	UE_LOG(LogTemp, Log, TEXT("[XAtlas] PackCharts done: %dx%d, %d charts, %d meshes, atlasCount=%d"),
		Atlas->width, Atlas->height, Atlas->chartCount, Atlas->meshCount, Atlas->atlasCount);

	// --- Step 5: Extract results ---
	Result.AtlasWidth = Atlas->width;
	Result.AtlasHeight = Atlas->height;
	Result.TotalChartCount = Atlas->chartCount;
	Result.Utilization = (Atlas->atlasCount > 0 && Atlas->utilization) ? Atlas->utilization[0] : 0.0f;

	Result.MeshResults.SetNum(Meshes.Num());
	for (int32 M = 0; M < Meshes.Num(); ++M)
	{
		Result.MeshResults[M].MeshIndex = M;
		Result.MeshResults[M].StaticMesh = Meshes[M].StaticMesh;
		Result.MeshResults[M].OriginalVertexCount = ExtractedMeshes[M].UVs.Num();
	}

	// Extract transforms
	for (int32 XM = 0; XM < (int32)Atlas->meshCount; ++XM)
	{
		const int32 M = XAtlasMeshToSource[XM];

		if (M < 0)
		{
			// Virtual rect -> overlap group transform
			const int32 G = XM; // Virtual rects are added first, 1:1 with groups
			if (G < OverlapGroups.Num())
			{
				auto& Group = OverlapGroups[G];
				const xatlas::Mesh& OutMesh = Atlas->meshes[XM];
				if (OutMesh.vertexCount >= 3)
				{
					const float W = static_cast<float>(Atlas->width);
					const float H = static_cast<float>(Atlas->height);
					FXAtlasChartTransformUtil::ComputeFromTriangle(
						Group.GroupBounds.Min,
						FVector2D(Group.GroupBounds.Max.X, Group.GroupBounds.Min.Y),
						Group.GroupBounds.Max,
						FVector2D(OutMesh.vertexArray[0].uv[0] / W, OutMesh.vertexArray[0].uv[1] / H),
						FVector2D(OutMesh.vertexArray[1].uv[0] / W, OutMesh.vertexArray[1].uv[1] / H),
						FVector2D(OutMesh.vertexArray[2].uv[0] / W, OutMesh.vertexArray[2].uv[1] / H),
						Group.GroupTransform);
					Group.GroupTransform.SourceBounds = Group.GroupBounds;
				}
			}
			continue;
		}

		ExtractChartTransforms(Atlas, XM, M, ExtractedMeshes[M], Result.MeshResults[M]);
	}

	Result.OverlapGroups = MoveTemp(OverlapGroups);

	// --- Step 6: Write UVs ---
	if (Options.bWriteToMesh)
	{
		XAtlas_ApplyIndependentRepack(Atlas, XAtlasMeshToSource, ExtractedMeshes);
		XAtlas_ApplyOverlapGroupTransforms(Result.OverlapGroups, ExtractedMeshes);
	}

	xatlas::Destroy(Atlas);
	Result.bSuccess = true;
	return Result;
}
