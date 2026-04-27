// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "AssetManagementAPI.generated.h"

/**
 * Asset management API for ArtClaw.
 * Provides asset creation, deletion, saving, modification, and preview capabilities.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UAssetManagementAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Create new asset (Blueprint, Material, DataTable, World, etc.).
	 * Supports comprehensive asset creation with properties initialization.
	 * 
	 * @param AssetPath Full asset path including name (e.g., '/Game/Blueprints/BP_NewActor')
	 * @param AssetClass Asset class name or path (e.g., 'Blueprint', 'Material', 'DataTable')
	 * @param PropertiesJson Optional JSON string with initial properties to set
	 * @return JSON string with creation result and metadata
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Asset")
	static FString CreateAsset(
		const FString& AssetPath,
		const FString& AssetClass,
		const FString& PropertiesJson = TEXT(""));

	/**
	 * Delete asset from project.
	 * Handles Blueprint generated class cleanup and source control integration.
	 * 
	 * @param AssetPath Asset path to delete
	 * @return true if deleted successfully
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Asset")
	static bool DeleteAsset(const FString& AssetPath);

	/**
	 * Save asset to disk with optional source control checkout.
	 * 
	 * @param AssetPath Asset path to save
	 * @param bCheckout Whether to checkout from source control before saving
	 * @return JSON string with save result and file information
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Asset")
	static FString SaveAsset(const FString& AssetPath, bool bCheckout = false);

	/**
	 * Open asset in appropriate editor.
	 * Supports both assets and editor windows/tabs.
	 * 
	 * @param AssetPath Asset path to open in editor
	 * @return true if opened successfully
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Asset")
	static bool OpenAsset(const FString& AssetPath);

	/**
	 * Set property on Blueprint CDO or component.
	 * Supports nested properties and array indices.
	 * 
	 * @param AssetPath Asset path (must be Blueprint or UObject-based asset)
	 * @param ComponentName Component name (empty for CDO properties)
	 * @param PropertyPath Property path (dot-separated, e.g., 'Stats.MaxHealth' or 'Items[0].Name')
	 * @param ValueJson JSON string representing the new value
	 * @return JSON string with modification result
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Asset")
	static FString SetAssetProperty(
		const FString& AssetPath,
		const FString& ComponentName,
		const FString& PropertyPath,
		const FString& ValueJson);

	/**
	 * Get diff against source control base version.
	 * Works with Git and Perforce, supports structured diff for UE assets.
	 * 
	 * @param AssetPath Asset path to analyze
	 * @return JSON string with diff information
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Asset")
	static FString GetAssetDiff(const FString& AssetPath);

	/**
	 * Export asset thumbnail/preview as image.
	 * Supports various formats and resolutions.
	 * 
	 * @param AssetPath Asset path to generate preview for
	 * @param OutputPath Optional output file path (empty for temp file)
	 * @return JSON string with preview file information
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Asset")
	static FString GetAssetPreview(const FString& AssetPath, const FString& OutputPath = TEXT(""));

private:
	// Asset creation helpers
	static class UObject* CreateBlueprintAsset(const FString& AssetPath, const FString& ParentClass, FString& OutError);
	static class UObject* CreateMaterialAsset(const FString& AssetPath, FString& OutError);
	static class UObject* CreateDataTableAsset(const FString& AssetPath, const FString& RowStruct, FString& OutError);
	static class UObject* CreateWorldAsset(const FString& AssetPath, FString& OutError);
	static class UObject* CreateDataAsset(const FString& AssetPath, class UClass* DataAssetClass, FString& OutError);
	static class UObject* CreateGenericAsset(const FString& AssetPath, class UClass* AssetClass, FString& OutError);

	// Property modification helpers
	static class UObject* GetAssetCDO(class UBlueprint* Blueprint, FString& OutError);
	static class UActorComponent* FindComponent(class AActor* Actor, const FString& ComponentName, FString& OutError);
	
	// Preview generation helpers
	static TArray<uint8> RenderAssetThumbnail(class UObject* Asset, int32 Resolution, const FString& Format);
	static TArray<uint8> ExportTextureData(class UTexture2D* Texture, int32 Resolution, const FString& Format);
	static FString SavePreviewToFile(const TArray<uint8>& ImageData, const FString& Format, const FString& OutputPath = TEXT(""));
};