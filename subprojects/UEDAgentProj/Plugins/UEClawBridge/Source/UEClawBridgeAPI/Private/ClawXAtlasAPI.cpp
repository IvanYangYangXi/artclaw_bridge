// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#4
// xatlas BP/Python API - Implementation

#include "ClawXAtlasAPI.h"
#include "ClawTextureOpsAPI.h"
#include "XAtlasRepack.h"
#include "XAtlasInternalTypes.h"
#include "XAtlasChartTransform.h"
#include "Engine/StaticMesh.h"

FXAtlasBatchRepackResult UClawXAtlasAPI::RepackUVs(
	UStaticMesh* Mesh, int32 SrcUV, int32 DstUV, FXAtlasRepackOptions Options)
{
	if (!Mesh)
	{
		FXAtlasBatchRepackResult Result;
		Result.ErrorMessage = TEXT("Mesh is null");
		return Result;
	}

	FXAtlasMeshEntry Entry;
	Entry.StaticMesh = Mesh;
	Entry.SourceUVChannel = SrcUV;
	Entry.TargetUVChannel = DstUV;

	TArray<FXAtlasMeshEntry> Entries;
	Entries.Add(Entry);

	return FXAtlasRepack::BatchRepack(Entries, Options);
}

FXAtlasBatchRepackResult UClawXAtlasAPI::BatchRepackUVs(
	const TArray<FXAtlasMeshEntry>& Meshes, FXAtlasRepackOptions Options)
{
	return FXAtlasRepack::BatchRepack(Meshes, Options);
}

UTexture2D* UClawXAtlasAPI::AdaptTexture(
	const FXAtlasBatchRepackResult& RepackResult,
	FXAtlasTextureAdaptOptions Options)
{
	if (!RepackResult.bSuccess || RepackResult.AtlasWidth == 0 || RepackResult.AtlasHeight == 0)
	{
		return nullptr;
	}

	const int32 OutW = Options.OutputResolution > 0 ? Options.OutputResolution : RepackResult.AtlasWidth;
	const int32 OutH = OutW; // Square output

	// Read source texture pixels
	TMap<int32, TArray<FColor>> SourcePixelsMap; // MaterialID -> pixels
	TMap<int32, FIntPoint> SourceSizeMap;         // MaterialID -> (W, H)

	// Collect all source textures
	if (Options.SourceTexturesByMaterial.Num() > 0)
	{
		for (auto& Pair : Options.SourceTexturesByMaterial)
		{
			int32 W, H;
			if (FClawTextureOps::ReadTexturePixels(Pair.Value, SourcePixelsMap.FindOrAdd(Pair.Key), W, H))
			{
				SourceSizeMap.Add(Pair.Key, FIntPoint(W, H));
			}
		}
	}
	else if (Options.SourceTexture)
	{
		int32 W, H;
		if (FClawTextureOps::ReadTexturePixels(Options.SourceTexture, SourcePixelsMap.FindOrAdd(0), W, H))
		{
			SourceSizeMap.Add(0, FIntPoint(W, H));
		}
	}

	if (SourcePixelsMap.Num() == 0)
	{
		UE_LOG(LogTemp, Error, TEXT("[XAtlas] AdaptTexture: no readable source textures"));
		return nullptr;
	}

	// Initialize output
	const FColor BgColor = Options.BackgroundColor.ToFColor(true);
	TArray<FColor> OutPixels;
	OutPixels.SetNum(OutW * OutH);
	for (FColor& P : OutPixels) P = BgColor;

	TArray<bool> FilledMask;
	FilledMask.SetNumZeroed(OutW * OutH);

	// Inverse mapping: for each chart transform, iterate target bounds and sample source
	for (const auto& MeshResult : RepackResult.MeshResults)
	{
		for (const auto& CT : MeshResult.ChartTransforms)
		{
			if (CT.InverseAffineMatrix.Num() != 6) continue;

			// Find source pixels for this chart's material
			const int32 MatKey = SourcePixelsMap.Contains(CT.MaterialID) ? CT.MaterialID : 0;
			const TArray<FColor>* SrcPixels = SourcePixelsMap.Find(MatKey);
			const FIntPoint* SrcSize = SourceSizeMap.Find(MatKey);
			if (!SrcPixels || !SrcSize) continue;

			// Iterate over target bounding box in output image
			const int32 MinPX = FMath::Max(0, FMath::FloorToInt(CT.TargetBounds.Min.X * OutW) - 1);
			const int32 MaxPX = FMath::Min(OutW - 1, FMath::CeilToInt(CT.TargetBounds.Max.X * OutW) + 1);
			const int32 MinPY = FMath::Max(0, FMath::FloorToInt(CT.TargetBounds.Min.Y * OutH) - 1);
			const int32 MaxPY = FMath::Min(OutH - 1, FMath::CeilToInt(CT.TargetBounds.Max.Y * OutH) + 1);

			for (int32 PY = MinPY; PY <= MaxPY; ++PY)
			{
				for (int32 PX = MinPX; PX <= MaxPX; ++PX)
				{
					const FVector2D TargetUV(
						(PX + 0.5) / OutW,
						(PY + 0.5) / OutH);

					// Inverse map to source UV
					const FVector2D SourceUV = FXAtlasChartTransformUtil::ApplyInverse(
						CT.InverseAffineMatrix, TargetUV);

					// Check if source UV is within the chart's source bounds
					if (SourceUV.X < CT.SourceBounds.Min.X - 0.001 ||
						SourceUV.X > CT.SourceBounds.Max.X + 0.001 ||
						SourceUV.Y < CT.SourceBounds.Min.Y - 0.001 ||
						SourceUV.Y > CT.SourceBounds.Max.Y + 0.001)
					{
						continue;
					}

					const int32 Idx = PY * OutW + PX;
					OutPixels[Idx] = FClawTextureOps::SampleBilinear(
						*SrcPixels, SrcSize->X, SrcSize->Y, SourceUV, Options.bWrapUV);
					FilledMask[Idx] = true;
				}
			}
		}
	}

	// Bleed
	if (Options.BleedPixels > 0)
	{
		FClawTextureOps::BleedPixels(OutPixels, FilledMask, OutW, OutH, Options.BleedPixels);
	}

	return FClawTextureOps::CreateTextureFromPixels(OutPixels, OutW, OutH, TEXT("XAtlas_Adapted"));
}

bool UClawXAtlasAPI::AdaptTextureToFile(
	const FXAtlasBatchRepackResult& RepackResult,
	FXAtlasTextureAdaptOptions Options,
	const FString& OutputPath)
{
	if (!RepackResult.bSuccess || RepackResult.AtlasWidth == 0) return false;

	// Reuse AdaptTexture logic but save to file
	const int32 OutW = Options.OutputResolution > 0 ? Options.OutputResolution : RepackResult.AtlasWidth;
	const int32 OutH = OutW;

	// Read source
	TArray<FColor> SrcPixels;
	int32 SrcW = 0, SrcH = 0;
	UTexture2D* SrcTex = Options.SourceTexture;
	if (Options.SourceTexturesByMaterial.Num() > 0)
	{
		// Use first available
		for (auto& Pair : Options.SourceTexturesByMaterial)
		{
			if (Pair.Value) { SrcTex = Pair.Value; break; }
		}
	}
	if (!SrcTex || !FClawTextureOps::ReadTexturePixels(SrcTex, SrcPixels, SrcW, SrcH))
	{
		return false;
	}

	// Initialize output
	const FColor BgColor = Options.BackgroundColor.ToFColor(true);
	TArray<FColor> OutPixels;
	OutPixels.SetNum(OutW * OutH);
	for (FColor& P : OutPixels) P = BgColor;

	TArray<bool> FilledMask;
	FilledMask.SetNumZeroed(OutW * OutH);

	for (const auto& MR : RepackResult.MeshResults)
	{
		for (const auto& CT : MR.ChartTransforms)
		{
			if (CT.InverseAffineMatrix.Num() != 6) continue;

			const int32 MinPX = FMath::Max(0, FMath::FloorToInt(CT.TargetBounds.Min.X * OutW) - 1);
			const int32 MaxPX = FMath::Min(OutW - 1, FMath::CeilToInt(CT.TargetBounds.Max.X * OutW) + 1);
			const int32 MinPY = FMath::Max(0, FMath::FloorToInt(CT.TargetBounds.Min.Y * OutH) - 1);
			const int32 MaxPY = FMath::Min(OutH - 1, FMath::CeilToInt(CT.TargetBounds.Max.Y * OutH) + 1);

			for (int32 PY = MinPY; PY <= MaxPY; ++PY)
			{
				for (int32 PX = MinPX; PX <= MaxPX; ++PX)
				{
					const FVector2D TgtUV((PX + 0.5) / OutW, (PY + 0.5) / OutH);
					const FVector2D SrcUV = FXAtlasChartTransformUtil::ApplyInverse(CT.InverseAffineMatrix, TgtUV);

					if (SrcUV.X < CT.SourceBounds.Min.X - 0.001 || SrcUV.X > CT.SourceBounds.Max.X + 0.001 ||
						SrcUV.Y < CT.SourceBounds.Min.Y - 0.001 || SrcUV.Y > CT.SourceBounds.Max.Y + 0.001)
					{
						continue;
					}

					const int32 Idx = PY * OutW + PX;
					OutPixels[Idx] = FClawTextureOps::SampleBilinear(SrcPixels, SrcW, SrcH, SrcUV, Options.bWrapUV);
					FilledMask[Idx] = true;
				}
			}
		}
	}

	if (Options.BleedPixels > 0)
	{
		FClawTextureOps::BleedPixels(OutPixels, FilledMask, OutW, OutH, Options.BleedPixels);
	}

	return FClawTextureOps::SavePixelsToFile(OutPixels, OutW, OutH, OutputPath);
}

bool UClawXAtlasAPI::CopyUVChannel(
	UStaticMesh* Mesh, int32 SrcChannel, int32 DstChannel, int32 LODIndex)
{
	if (!Mesh || !Mesh->HasValidRenderData())
	{
		return false;
	}

	const FStaticMeshLODResources& LODRes = Mesh->GetLODForExport(LODIndex);
	const int32 NumUVs = LODRes.VertexBuffers.StaticMeshVertexBuffer.GetNumTexCoords();
	if (SrcChannel >= NumUVs)
	{
		return false;
	}

	const int32 NumVerts = LODRes.VertexBuffers.StaticMeshVertexBuffer.GetNumVertices();

	// Read source UVs
	TArray<FVector2D> UVs;
	UVs.SetNum(NumVerts);
	for (int32 i = 0; i < NumVerts; ++i)
	{
		UVs[i] = FVector2D(LODRes.VertexBuffers.StaticMeshVertexBuffer.GetVertexUV(i, SrcChannel));
	}

	// Read indices
	FIndexArrayView IdxView = LODRes.IndexBuffer.GetArrayView();
	TArray<uint32> Indices;
	Indices.SetNum(IdxView.Num());
	for (int32 i = 0; i < IdxView.Num(); ++i)
	{
		Indices[i] = IdxView[i];
	}

	FString Error;
	return XAtlas_WriteUVsToMesh(Mesh, UVs, Indices, DstChannel, LODIndex, Error);
}

TArray<FXAtlasOverlapGroup> UClawXAtlasAPI::DetectOverlapGroups(
	const TArray<FXAtlasMeshEntry>& Meshes)
{
	TArray<FXAtlasOverlapGroup> Result;
	if (Meshes.Num() <= 1) return Result;

	TArray<FXAtlasExtractedMesh> ExtractedMeshes;
	ExtractedMeshes.SetNum(Meshes.Num());
	for (int32 M = 0; M < Meshes.Num(); ++M)
	{
		FString Error;
		if (!XAtlas_ExtractMeshData(Meshes[M], M, ExtractedMeshes[M], Error))
		{
			UE_LOG(LogTemp, Warning, TEXT("DetectOverlapGroups: %s"), *Error);
			return Result;
		}
	}

	TArray<TArray<FXAtlasUVIsland>> AllIslands;
	AllIslands.SetNum(Meshes.Num());
	for (int32 M = 0; M < Meshes.Num(); ++M)
	{
		XAtlas_ComputeUVIslands(ExtractedMeshes[M], AllIslands[M]);
	}

	XAtlas_DetectOverlapGroups(ExtractedMeshes, AllIslands, Result);
	return Result;
}
