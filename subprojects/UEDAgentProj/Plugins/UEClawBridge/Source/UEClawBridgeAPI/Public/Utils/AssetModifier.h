// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Engine/Blueprint.h"
#include "Engine/World.h"
#include "Materials/Material.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "Animation/AnimBlueprint.h"
#include "Dom/JsonObject.h"

class FProperty;
class UEdGraphNode;
class FScopedTransaction;

/**
 * Asset modification utility for Blueprint, Material, and other UE assets.
 * Provides transaction management, loading/saving, compilation, and property modification.
 */
class UECLAWBRIDGEAPI_API FAssetModifier
{
public:
	// === Transaction Management ===

	/**
	 * Begin a transaction for undo/redo support.
	 * 
	 * @param Description Transaction description shown in Undo menu
	 * @return Scoped transaction object (auto-destructs to commit)
	 */
	static TSharedPtr<FScopedTransaction> BeginTransaction(const FString& Description);

	// === Asset Loading ===

	/**
	 * Load asset by path with validation.
	 * 
	 * @param AssetPath Asset path (e.g., "/Game/MyBlueprint.MyBlueprint")
	 * @param OutError Error message if loading fails
	 * @return Loaded asset, or nullptr if failed
	 */
	static UObject* LoadAssetByPath(const FString& AssetPath, FString& OutError);

	/**
	 * Load and cast asset by path.
	 * 
	 * @param AssetPath Asset path
	 * @param OutError Error message if loading fails
	 * @return Loaded asset cast to T, or nullptr if failed
	 */
	template<typename T>
	static T* LoadAssetByPath(const FString& AssetPath, FString& OutError)
	{
		UObject* LoadedAsset = LoadAssetByPath(AssetPath, OutError);
		if (!LoadedAsset)
		{
			return nullptr;
		}

		T* CastAsset = Cast<T>(LoadedAsset);
		if (!CastAsset)
		{
			OutError = FString::Printf(TEXT("Asset is not of type %s: %s"), *T::StaticClass()->GetName(), *AssetPath);
			return nullptr;
		}

		return CastAsset;
	}

	/**
	 * Validate asset path format.
	 * 
	 * @param AssetPath Path to validate
	 * @return true if path format is valid
	 */
	static bool ValidateAssetPath(const FString& AssetPath);

	/**
	 * Check if asset exists using AssetRegistry.
	 * 
	 * @param AssetPath Asset path to check
	 * @return true if asset exists
	 */
	static bool AssetExists(const FString& AssetPath);

	// === Asset Modification ===

	/**
	 * Mark object as modified for undo system.
	 * Call this before making changes to enable undo/redo.
	 * 
	 * @param Object Object to mark as modified
	 */
	static void MarkModified(UObject* Object);

	/**
	 * Mark package as dirty (needs saving).
	 * 
	 * @param Object Object whose package to mark dirty
	 */
	static void MarkPackageDirty(UObject* Object);

	// === Asset Saving ===

	/**
	 * Save asset to disk with comprehensive error handling.
	 * 
	 * @param Asset Asset to save
	 * @param OutError Error message if saving fails
	 * @return true if saved successfully
	 */
	static bool SaveAsset(UObject* Asset, FString& OutError);

	/**
	 * Checkout file from source control (if available).
	 * 
	 * @param FilePath File path to checkout
	 * @param OutError Error message if checkout fails
	 * @return true if checked out successfully or no source control
	 */
	static bool CheckoutFile(const FString& FilePath, FString& OutError);

	// === Blueprint Tools ===

	/**
	 * Compile Blueprint and check for errors.
	 * 
	 * @param Blueprint Blueprint to compile
	 * @param OutError Error message if compilation fails
	 * @return true if compiled without errors
	 */
	static bool CompileBlueprint(UBlueprint* Blueprint, FString& OutError);

	/**
	 * Refresh all nodes in Blueprint graphs.
	 * Call after structural changes to update node connections.
	 * 
	 * @param Blueprint Blueprint to refresh
	 */
	static void RefreshBlueprintNodes(UBlueprint* Blueprint);

	/**
	 * Refresh Material editor after changes.
	 * Triggers recompilation and UI updates.
	 * 
	 * @param Material Material to refresh
	 */
	static void RefreshMaterial(UMaterial* Material);

	/**
	 * Find graph by name in Blueprint.
	 * Supports both regular and AnimBlueprint graphs.
	 * 
	 * @param Blueprint Blueprint to search
	 * @param GraphName Name of graph to find
	 * @return Found graph, or nullptr if not found
	 */
	static UEdGraph* FindGraphByName(UBlueprint* Blueprint, const FString& GraphName);

	/**
	 * Find node by GUID across all graphs in Blueprint.
	 * 
	 * @param Blueprint Blueprint to search
	 * @param NodeGuid GUID of node to find
	 * @return Found node, or nullptr if not found
	 */
	static UEdGraphNode* FindNodeByGuid(UBlueprint* Blueprint, const FGuid& NodeGuid);

	/**
	 * Get all searchable graphs from Blueprint.
	 * Includes AnimBlueprint-specific graphs.
	 * 
	 * @param Blueprint Blueprint to analyze
	 * @return Array of graphs that can contain nodes
	 */
	static TArray<UEdGraph*> GetAllSearchableGraphs(UBlueprint* Blueprint);

	// === Property Tools ===

	/**
	 * Find property by path in object.
	 * Supports nested properties (e.g., "Stats.MaxHealth") and array indices (e.g., "Items[0]").
	 * 
	 * @param Object Object to search
	 * @param PropertyPath Path to property (dot-separated)
	 * @param OutContainer Pointer to container holding the property
	 * @param OutError Error message if property not found
	 * @return Found property, or nullptr if not found
	 */
	static FProperty* FindPropertyByPath(
		UObject* Object,
		const FString& PropertyPath,
		void*& OutContainer,
		FString& OutError);

	/**
	 * Set property value from JSON.
	 * Delegates to FPropertySerializer::DeserializePropertyValue.
	 * 
	 * @param Property Property to set
	 * @param Container Container holding the property
	 * @param JsonValue JSON value to deserialize
	 * @param OutError Error message if deserialization fails
	 * @return true if set successfully
	 */
	static bool SetPropertyFromJson(
		FProperty* Property,
		void* Container,
		const TSharedPtr<FJsonValue>& JsonValue,
		FString& OutError);

private:
	/**
	 * Parse array index from property path segment.
	 * Converts "Items[0]" to name="Items", index=0.
	 * 
	 * @param PathSegment Property path segment
	 * @param OutName Property name without index
	 * @param OutIndex Array index, or INDEX_NONE if not an array
	 * @return true if parsing succeeded
	 */
	static bool ParseArrayIndex(const FString& PathSegment, FString& OutName, int32& OutIndex);
};