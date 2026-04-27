// Copyright ArtClaw. All Rights Reserved.
// xatlas chart affine transform computation

#pragma once

#include "CoreMinimal.h"
#include "XAtlasTypes.h"

/**
 * Utility class for computing 2x3 affine transforms from UV coordinate pairs.
 * Used to map source UV islands to their repacked positions.
 */
class XATLASLIB_API FXAtlasChartTransformUtil
{
public:
	/**
	 * Compute affine transform from three UV coordinate pairs.
	 * S * A = D  =>  A = S^-1 * D  (Cramer's rule)
	 *
	 * @param Src0,Src1,Src2  Source UV coordinates
	 * @param Dst0,Dst1,Dst2  Destination UV coordinates
	 * @param OutTransform     Populated with affine matrix + decomposition
	 * @return true if the transform was computed successfully (non-degenerate triangle)
	 */
	static bool ComputeFromTriangle(
		const FVector2D& Src0, const FVector2D& Src1, const FVector2D& Src2,
		const FVector2D& Dst0, const FVector2D& Dst1, const FVector2D& Dst2,
		FXAtlasChartTransform& OutTransform);

	/**
	 * Apply a forward affine transform: NewUV = M * [OldU, OldV, 1]^T
	 */
	static FVector2D ApplyForward(const TArray<float>& AffineMatrix, const FVector2D& UV);

	/**
	 * Apply an inverse affine transform: OldUV = M^-1 * [NewU, NewV, 1]^T
	 */
	static FVector2D ApplyInverse(const TArray<float>& InverseAffineMatrix, const FVector2D& UV);

	/**
	 * Decompose a 2x3 affine matrix into translation, rotation, scale, mirror.
	 */
	static void DecomposeAffine(
		const TArray<float>& AffineMatrix,
		FVector2D& OutTranslation,
		float& OutRotationDegrees,
		float& OutUniformScale,
		bool& bOutMirrored);

	/**
	 * Compute the inverse of a 2x3 affine matrix.
	 * @return false if matrix is singular
	 */
	static bool InvertAffine(const TArray<float>& AffineMatrix, TArray<float>& OutInverse);
};
