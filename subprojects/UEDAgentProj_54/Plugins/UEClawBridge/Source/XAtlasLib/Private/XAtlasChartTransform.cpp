// Copyright ArtClaw. All Rights Reserved.
// xatlas chart affine transform computation - implementation

#include "XAtlasChartTransform.h"

bool FXAtlasChartTransformUtil::ComputeFromTriangle(
	const FVector2D& Src0, const FVector2D& Src1, const FVector2D& Src2,
	const FVector2D& Dst0, const FVector2D& Dst1, const FVector2D& Dst2,
	FXAtlasChartTransform& OutTransform)
{
	// S matrix:
	// | s0.x  s0.y  1 |
	// | s1.x  s1.y  1 |
	// | s2.x  s2.y  1 |
	//
	// Compute det(S) using Cramer's rule
	const double S00 = Src0.X, S01 = Src0.Y;
	const double S10 = Src1.X, S11 = Src1.Y;
	const double S20 = Src2.X, S21 = Src2.Y;

	const double Det = S00 * (S11 - S21) - S01 * (S10 - S20) + (S10 * S21 - S11 * S20);

	// Degenerate triangle check
	if (FMath::Abs(Det) < 1e-10)
	{
		return false;
	}

	const double InvDet = 1.0 / Det;

	// S^-1 (3x3, third column for the constant terms)
	// Cofactors / det
	const double I00 = (S11 - S21) * InvDet;
	const double I01 = (S21 - S01) * InvDet;
	const double I02 = (S01 * 1.0 - S11 * 1.0) * InvDet; // simplified: (S01-S11)*InvDet
	const double I10 = (S20 - S10) * InvDet;
	const double I11 = (S00 - S20) * InvDet;
	const double I12 = (S10 - S00) * InvDet;
	const double I20 = (S10 * S21 - S20 * S11) * InvDet;
	const double I21 = (S20 * S01 - S00 * S21) * InvDet;
	const double I22 = (S00 * S11 - S10 * S01) * InvDet;

	// A = S^-1 * D
	// D is 3x2:
	// | d0.x  d0.y |
	// | d1.x  d1.y |
	// | d2.x  d2.y |
	//
	// Result A is 3x2, but we store as 2x3 row-major: [a,b,tx, c,d,ty]
	// Row 0 of A^T: a = I00*D0x + I01*D1x + I02*D2x  (coefficient for U)
	// Row 1 of A^T: b = I10*D0x + I11*D1x + I12*D2x  (coefficient for V)
	// Row 2 of A^T: tx = I20*D0x + I21*D1x + I22*D2x  (translation)
	// Same for y component

	const double a  = I00 * Dst0.X + I01 * Dst1.X + I02 * Dst2.X;
	const double b  = I10 * Dst0.X + I11 * Dst1.X + I12 * Dst2.X;
	const double tx = I20 * Dst0.X + I21 * Dst1.X + I22 * Dst2.X;
	const double c  = I00 * Dst0.Y + I01 * Dst1.Y + I02 * Dst2.Y;
	const double d  = I10 * Dst0.Y + I11 * Dst1.Y + I12 * Dst2.Y;
	const double ty = I20 * Dst0.Y + I21 * Dst1.Y + I22 * Dst2.Y;

	OutTransform.AffineMatrix.SetNum(6);
	OutTransform.AffineMatrix[0] = static_cast<float>(a);
	OutTransform.AffineMatrix[1] = static_cast<float>(b);
	OutTransform.AffineMatrix[2] = static_cast<float>(tx);
	OutTransform.AffineMatrix[3] = static_cast<float>(c);
	OutTransform.AffineMatrix[4] = static_cast<float>(d);
	OutTransform.AffineMatrix[5] = static_cast<float>(ty);

	// Compute inverse
	if (!InvertAffine(OutTransform.AffineMatrix, OutTransform.InverseAffineMatrix))
	{
		return false;
	}

	// Decompose
	DecomposeAffine(OutTransform.AffineMatrix,
		OutTransform.Translation,
		OutTransform.RotationDegrees,
		OutTransform.UniformScale,
		OutTransform.bIsMirrored);

	return true;
}

FVector2D FXAtlasChartTransformUtil::ApplyForward(const TArray<float>& AffineMatrix, const FVector2D& UV)
{
	check(AffineMatrix.Num() == 6);
	return FVector2D(
		AffineMatrix[0] * UV.X + AffineMatrix[1] * UV.Y + AffineMatrix[2],
		AffineMatrix[3] * UV.X + AffineMatrix[4] * UV.Y + AffineMatrix[5]);
}

FVector2D FXAtlasChartTransformUtil::ApplyInverse(const TArray<float>& InverseAffineMatrix, const FVector2D& UV)
{
	check(InverseAffineMatrix.Num() == 6);
	return FVector2D(
		InverseAffineMatrix[0] * UV.X + InverseAffineMatrix[1] * UV.Y + InverseAffineMatrix[2],
		InverseAffineMatrix[3] * UV.X + InverseAffineMatrix[4] * UV.Y + InverseAffineMatrix[5]);
}

void FXAtlasChartTransformUtil::DecomposeAffine(
	const TArray<float>& M,
	FVector2D& OutTranslation,
	float& OutRotationDegrees,
	float& OutUniformScale,
	bool& bOutMirrored)
{
	check(M.Num() == 6);
	// M = [a, b, tx, c, d, ty]
	const float a = M[0], b = M[1], tx = M[2];
	const float c = M[3], d = M[4], ty = M[5];

	OutTranslation = FVector2D(tx, ty);

	// Determinant = ad - bc
	const float DetM = a * d - b * c;
	bOutMirrored = (DetM < 0.0f);

	// Scale = sqrt(|det|)
	OutUniformScale = FMath::Sqrt(FMath::Abs(DetM));

	// Rotation = atan2(c, a)  (for non-mirrored case)
	OutRotationDegrees = FMath::RadiansToDegrees(FMath::Atan2(c, a));
}

bool FXAtlasChartTransformUtil::InvertAffine(const TArray<float>& M, TArray<float>& OutInverse)
{
	check(M.Num() == 6);
	// M = [a, b, tx, c, d, ty]
	const double a = M[0], b = M[1], tx = M[2];
	const double c = M[3], d = M[4], ty = M[5];

	const double Det = a * d - b * c;
	if (FMath::Abs(Det) < 1e-10)
	{
		return false;
	}

	const double InvDet = 1.0 / Det;

	OutInverse.SetNum(6);
	OutInverse[0] = static_cast<float>( d * InvDet);
	OutInverse[1] = static_cast<float>(-b * InvDet);
	OutInverse[2] = static_cast<float>((b * ty - d * tx) * InvDet);
	OutInverse[3] = static_cast<float>(-c * InvDet);
	OutInverse[4] = static_cast<float>( a * InvDet);
	OutInverse[5] = static_cast<float>((c * tx - a * ty) * InvDet);

	return true;
}
