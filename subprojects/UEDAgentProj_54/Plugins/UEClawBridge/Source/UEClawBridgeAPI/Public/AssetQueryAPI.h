// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "AssetQueryAPI.generated.h"

/**
 * Asset query and search API for ArtClaw.
 * Provides searching, class hierarchy analysis, and reference finding capabilities.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UAssetQueryAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Search Content Browser by name, class, path.
	 * Returns JSON array of matching assets with metadata.
	 * 
	 * @param Name Asset name pattern (supports * and ? wildcards)
	 * @param ClassFilter Filter by asset class (e.g., Blueprint, StaticMesh, Material)
	 * @param PathFilter Filter by path prefix (e.g., /Game/Blueprints)
	 * @param Limit Maximum results to return (default: 100)
	 * @return JSON string with search results
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Asset")
	static FString QueryAsset(
		const FString& Name = TEXT(""),
		const FString& ClassFilter = TEXT(""),
		const FString& PathFilter = TEXT(""),
		int32 Limit = 100);

	/**
	 * Find references to/from an asset using AssetRegistry dependency system.
	 * 
	 * @param AssetPath Asset path to analyze (e.g., /Game/Blueprints/BP_Player)
	 * @param bReferencedBy If true, find what references this asset; if false, find what this asset references
	 * @return JSON string with reference results
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Asset")
	static FString FindReferences(
		const FString& AssetPath,
		bool bReferencedBy = false);

	/**
	 * Query class inheritance hierarchy.
	 * Useful for finding related classes and understanding inheritance chains.
	 * 
	 * @param ClassName Class name to analyze (e.g., Actor, Character, BP_MyClass_C)
	 * @param Direction Direction to traverse: "ancestors", "descendants", or "both"
	 * @param MaxDepth Maximum depth to traverse (default: 10)
	 * @return JSON string with hierarchy information
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Asset")
	static FString ClassHierarchy(
		const FString& ClassName,
		const FString& Direction = TEXT("both"),
		int32 MaxDepth = 10);

private:
	// Helper to match wildcards
	static bool MatchesWildcard(const FString& Text, const FString& Pattern);
	
	// Helper to build class hierarchy
	static void BuildClassHierarchy(
		UClass* Class,
		TSharedPtr<class FJsonObject> Result,
		const FString& Direction,
		int32 CurrentDepth,
		int32 MaxDepth,
		TSet<UClass*>& ProcessedClasses);
};