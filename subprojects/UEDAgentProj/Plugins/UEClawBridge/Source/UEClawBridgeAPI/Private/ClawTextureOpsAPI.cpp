// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#5.4
// Texture read/write/sampling utilities - implementation

#include "ClawTextureOpsAPI.h"
#include "Engine/Texture2D.h"
#include "TextureResource.h"
#include "IImageWrapperModule.h"
#include "IImageWrapper.h"
#include "Misc/FileHelper.h"
#include "Modules/ModuleManager.h"

bool FClawTextureOps::ReadTexturePixels(
	UTexture2D* Texture,
	TArray<FColor>& OutPixels,
	int32& OutWidth, int32& OutHeight)
{
	if (!Texture) return false;

	// Use Source data (editor-only, uncompressed) — works for all texture formats
	FTextureSource& Source = Texture->Source;
	if (!Source.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("[ClawTextureOps] Texture '%s' has no source data"), *Texture->GetName());
		return false;
	}

	OutWidth = Source.GetSizeX();
	OutHeight = Source.GetSizeY();
	const int32 NumPixels = OutWidth * OutHeight;

	// Get source data as BGRA8
	TArray64<uint8> RawData;
	if (!Source.GetMipData(RawData, 0))
	{
		UE_LOG(LogTemp, Warning, TEXT("[ClawTextureOps] Failed to get mip data for '%s'"), *Texture->GetName());
		return false;
	}

	const ETextureSourceFormat SrcFormat = Source.GetFormat();
	OutPixels.SetNum(NumPixels);

	if (SrcFormat == TSF_BGRA8 || SrcFormat == TSF_BGRE8)
	{
		if (RawData.Num() >= NumPixels * 4)
		{
			FMemory::Memcpy(OutPixels.GetData(), RawData.GetData(), NumPixels * sizeof(FColor));
		}
		else
		{
			UE_LOG(LogTemp, Warning, TEXT("[ClawTextureOps] BGRA8 data size mismatch for '%s'"), *Texture->GetName());
			return false;
		}
	}
	else if (SrcFormat == TSF_RGBA8)
	{
		if (RawData.Num() >= NumPixels * 4)
		{
			const uint8* Src = RawData.GetData();
			for (int32 i = 0; i < NumPixels; ++i)
			{
				// RGBA -> BGRA
				OutPixels[i] = FColor(Src[i * 4 + 2], Src[i * 4 + 1], Src[i * 4 + 0], Src[i * 4 + 3]);
			}
		}
		else
		{
			return false;
		}
	}
	else if (SrcFormat == TSF_G8)
	{
		for (int32 i = 0; i < NumPixels && i < RawData.Num(); ++i)
		{
			const uint8 V = RawData[i];
			OutPixels[i] = FColor(V, V, V, 255);
		}
	}
	else if (SrcFormat == TSF_RGBA16F)
	{
		// 16-bit float per channel, 8 bytes per pixel
		if (RawData.Num() >= NumPixels * 8)
		{
			const FFloat16* Src = reinterpret_cast<const FFloat16*>(RawData.GetData());
			for (int32 i = 0; i < NumPixels; ++i)
			{
				const float R = FMath::Clamp(Src[i * 4 + 0].GetFloat(), 0.0f, 1.0f);
				const float G = FMath::Clamp(Src[i * 4 + 1].GetFloat(), 0.0f, 1.0f);
				const float B = FMath::Clamp(Src[i * 4 + 2].GetFloat(), 0.0f, 1.0f);
				const float A = FMath::Clamp(Src[i * 4 + 3].GetFloat(), 0.0f, 1.0f);
				OutPixels[i] = FColor(
					FMath::RoundToInt(B * 255), FMath::RoundToInt(G * 255),
					FMath::RoundToInt(R * 255), FMath::RoundToInt(A * 255));
			}
		}
		else
		{
			return false;
		}
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("[ClawTextureOps] Unsupported source format %d for '%s'"),
			(int32)SrcFormat, *Texture->GetName());
		return false;
	}

	UE_LOG(LogTemp, Log, TEXT("[ClawTextureOps] Read %dx%d pixels from '%s' (format=%d)"),
		OutWidth, OutHeight, *Texture->GetName(), (int32)SrcFormat);
	return true;
}

UTexture2D* FClawTextureOps::CreateTextureFromPixels(
	const TArray<FColor>& Pixels,
	int32 Width, int32 Height,
	const FString& Name)
{
	UTexture2D* Texture = UTexture2D::CreateTransient(Width, Height, PF_B8G8R8A8, *Name);
	if (!Texture) return nullptr;

	FTexture2DMipMap& Mip = Texture->GetPlatformData()->Mips[0];
	void* Data = Mip.BulkData.Lock(LOCK_READ_WRITE);
	FMemory::Memcpy(Data, Pixels.GetData(), Pixels.Num() * sizeof(FColor));
	Mip.BulkData.Unlock();

	Texture->UpdateResource();
	return Texture;
}

bool FClawTextureOps::SavePixelsToFile(
	const TArray<FColor>& Pixels,
	int32 Width, int32 Height,
	const FString& FilePath)
{
	IImageWrapperModule& ImageWrapperModule = FModuleManager::LoadModuleChecked<IImageWrapperModule>("ImageWrapper");
	TSharedPtr<IImageWrapper> ImageWrapper = ImageWrapperModule.CreateImageWrapper(EImageFormat::PNG);

	if (!ImageWrapper.IsValid()) return false;

	ImageWrapper->SetRaw(Pixels.GetData(), Pixels.Num() * sizeof(FColor),
		Width, Height, ERGBFormat::BGRA, 8);

	const TArray64<uint8>& PngData = ImageWrapper->GetCompressed();
	return FFileHelper::SaveArrayToFile(PngData, *FilePath);
}

FColor FClawTextureOps::SampleBilinear(
	const TArray<FColor>& Pixels,
	int32 Width, int32 Height,
	const FVector2D& UV,
	bool bWrap)
{
	double U = UV.X * Width - 0.5;
	double V = UV.Y * Height - 0.5;

	int32 X0 = FMath::FloorToInt(U);
	int32 Y0 = FMath::FloorToInt(V);
	int32 X1 = X0 + 1;
	int32 Y1 = Y0 + 1;

	const float FracX = static_cast<float>(U - X0);
	const float FracY = static_cast<float>(V - Y0);

	auto ClampOrWrap = [&](int32 Coord, int32 Size) -> int32
	{
		if (bWrap) return ((Coord % Size) + Size) % Size;
		return FMath::Clamp(Coord, 0, Size - 1);
	};

	X0 = ClampOrWrap(X0, Width);
	X1 = ClampOrWrap(X1, Width);
	Y0 = ClampOrWrap(Y0, Height);
	Y1 = ClampOrWrap(Y1, Height);

	const FColor& C00 = Pixels[Y0 * Width + X0];
	const FColor& C10 = Pixels[Y0 * Width + X1];
	const FColor& C01 = Pixels[Y1 * Width + X0];
	const FColor& C11 = Pixels[Y1 * Width + X1];

	auto Lerp = [](uint8 A, uint8 B, float T) -> uint8
	{
		return static_cast<uint8>(FMath::Clamp(FMath::RoundToInt(A + (B - A) * T), 0, 255));
	};

	const uint8 R = Lerp(Lerp(C00.R, C10.R, FracX), Lerp(C01.R, C11.R, FracX), FracY);
	const uint8 G = Lerp(Lerp(C00.G, C10.G, FracX), Lerp(C01.G, C11.G, FracX), FracY);
	const uint8 B = Lerp(Lerp(C00.B, C10.B, FracX), Lerp(C01.B, C11.B, FracX), FracY);
	const uint8 A = Lerp(Lerp(C00.A, C10.A, FracX), Lerp(C01.A, C11.A, FracX), FracY);

	return FColor(R, G, B, A);
}

void FClawTextureOps::BleedPixels(
	TArray<FColor>& Pixels,
	TArray<bool>& FilledMask,
	int32 Width, int32 Height,
	int32 Iterations)
{
	static const int32 DX[] = { -1, 1, 0, 0 };
	static const int32 DY[] = { 0, 0, -1, 1 };

	for (int32 Iter = 0; Iter < Iterations; ++Iter)
	{
		TArray<bool> NewMask = FilledMask;
		TArray<FColor> NewPixels = Pixels;

		for (int32 Y = 0; Y < Height; ++Y)
		{
			for (int32 X = 0; X < Width; ++X)
			{
				const int32 Idx = Y * Width + X;
				if (FilledMask[Idx]) continue;

				int32 Count = 0;
				int32 SR = 0, SG = 0, SB = 0, SA = 0;
				for (int32 D = 0; D < 4; ++D)
				{
					const int32 NX = X + DX[D];
					const int32 NY = Y + DY[D];
					if (NX < 0 || NX >= Width || NY < 0 || NY >= Height) continue;
					const int32 NIdx = NY * Width + NX;
					if (!FilledMask[NIdx]) continue;
					SR += Pixels[NIdx].R;
					SG += Pixels[NIdx].G;
					SB += Pixels[NIdx].B;
					SA += Pixels[NIdx].A;
					++Count;
				}
				if (Count > 0)
				{
					NewPixels[Idx] = FColor(SR / Count, SG / Count, SB / Count, SA / Count);
					NewMask[Idx] = true;
				}
			}
		}

		Pixels = MoveTemp(NewPixels);
		FilledMask = MoveTemp(NewMask);
	}
}
