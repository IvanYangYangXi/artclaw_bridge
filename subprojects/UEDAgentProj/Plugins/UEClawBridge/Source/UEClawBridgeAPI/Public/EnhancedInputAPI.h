// Copyright ArtClaw. All Rights Reserved.
// NOTE: Requires additional modules in UEClawBridgeAPI.Build.cs:
//   "EnhancedInput"

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "EnhancedInputAPI.generated.h"

/**
 * Blueprint Function Library for Enhanced Input system operations.
 * Provides tools to query, create, and manage Input Actions and Mapping Contexts.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UEnhancedInputAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Query Input Mapping Context bindings.
	 * 
	 * @param AssetPath Path to the Input Mapping Context asset (e.g., "/Game/Input/IMC_Default")
	 * @return JSON string with context information or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|Input")
	static FString QueryInputMappingContext(const FString& AssetPath);

	/**
	 * Create Input Action asset.
	 * 
	 * @param AssetPath Path where to create the Input Action asset
	 * @param ValueType Type of input value ("Bool", "Axis1D", "Axis2D", "Axis3D")
	 * @return JSON string with success status or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|Input")
	static FString CreateInputAction(
		const FString& AssetPath,
		const FString& ValueType = TEXT("Bool"));

	/**
	 * Add mapping to Input Mapping Context.
	 * 
	 * @param ContextPath Path to the Input Mapping Context asset
	 * @param ActionPath Path to the Input Action asset
	 * @param Key Key name to bind (e.g., "W", "LeftMouseButton", "Gamepad_LeftThumbstick")
	 * @param ModifiersJson JSON array of modifier class names (optional)
	 * @return JSON string with success status or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|Input")
	static FString AddInputMapping(
		const FString& ContextPath,
		const FString& ActionPath,
		const FString& Key,
		const FString& ModifiersJson = TEXT(""));

	/**
	 * Query Input Action details.
	 * 
	 * @param AssetPath Path to the Input Action asset
	 * @return JSON string with action information or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|Input")
	static FString QueryInputAction(const FString& AssetPath);
};