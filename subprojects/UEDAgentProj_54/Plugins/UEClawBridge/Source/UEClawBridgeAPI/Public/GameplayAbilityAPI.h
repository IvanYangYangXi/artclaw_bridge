// Copyright ArtClaw. All Rights Reserved.
// NOTE: Requires additional modules in UEClawBridgeAPI.Build.cs:
//   "GameplayAbilities", "GameplayTags", "GameplayTasks"

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "GameplayAbilityAPI.generated.h"

/**
 * Blueprint Function Library for Gameplay Ability System (GAS) operations.
 * Provides tools to create, modify, and query Gameplay Abilities and Effects.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UGameplayAbilityAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Create Gameplay Ability Blueprint asset.
	 * 
	 * @param AssetPath Path where to create the Gameplay Ability asset
	 * @param ParentClass Base class for the ability ("GameplayAbility" or custom class name)
	 * @return JSON string with success status or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|GAS")
	static FString CreateGameplayAbility(
		const FString& AssetPath,
		const FString& ParentClass = TEXT("GameplayAbility"));

	/**
	 * Create Gameplay Effect asset.
	 * 
	 * @param AssetPath Path where to create the Gameplay Effect asset
	 * @return JSON string with success status or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|GAS")
	static FString CreateGameplayEffect(const FString& AssetPath);

	/**
	 * Set modifier on Gameplay Effect.
	 * 
	 * @param AssetPath Path to the Gameplay Effect asset
	 * @param Attribute Attribute name to modify (e.g., "Health", "Mana")
	 * @param ModOp Modifier operation ("Add", "Multiply", "Divide", "Override")
	 * @param Value Modifier value
	 * @return JSON string with success status or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|GAS")
	static FString SetGEModifier(
		const FString& AssetPath,
		const FString& Attribute,
		const FString& ModOp,
		float Value);

	/**
	 * Query Gameplay Ability/Effect info.
	 * 
	 * @param AssetPath Path to the Gameplay Ability asset
	 * @return JSON string with ability information or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|GAS")
	static FString QueryAbilityInfo(const FString& AssetPath);

	/**
	 * Query Gameplay Effect details: modifiers, duration, tags.
	 * 
	 * @param AssetPath Path to the Gameplay Effect asset
	 * @return JSON string with effect information or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|GAS")
	static FString QueryEffectInfo(const FString& AssetPath);
};