// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/xatlas-integration/design.md#5.4
// Texture read/write/sampling utilities for UV repack texture adaptation

#pragma once

#include "CoreMinimal.h"
#include "Engine/Texture2D.h"

/**
 * Texture pixel read/write utilities.
 */
class UECLAWBRIDGEAPI_API FClawTextureOps
{
public:
	/**
	 * Read all pixels from a Texture2D as BGRA8.
	 * @return true if successful, false if texture is not readable
	 */
	static bool ReadTexturePixels(
		UTexture2D* Texture,
		TArray<FColor>& OutPixels,
		int32& OutWidth, int32& OutHeight);

	/**
	 * Create a new transient Texture2D from pixel data.
	 */
	static UTexture2D* CreateTextureFromPixels(
		const TArray<FColor>& Pixels,
		int32 Width, int32 Height,
		const FString& Name);

	/**
	 * Save pixel data to a file (PNG).
	 */
	static bool SavePixelsToFile(
		const TArray<FColor>& Pixels,
		int32 Width, int32 Height,
		const FString& FilePath);

	/**
	 * Bilinear sample from pixel array at UV coordinates.
	 * @param UV in 0-1 range
	 * @param bWrap if true, wrap UV; if false, clamp
	 */
	static FColor SampleBilinear(
		const TArray<FColor>& Pixels,
		int32 Width, int32 Height,
		const FVector2D& UV,
		bool bWrap = false);

	/**
	 * Expand filled pixels into unfilled neighbors (bleed / dilation).
	 * @param Iterations number of expansion passes
	 */
	static void BleedPixels(
		TArray<FColor>& Pixels,
		TArray<bool>& FilledMask,
		int32 Width, int32 Height,
		int32 Iterations);
};
