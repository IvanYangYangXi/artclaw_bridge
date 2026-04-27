// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "WidgetBlueprintAPI.generated.h"

class UWidgetBlueprint;
class UWidget;

/**
 * Blueprint function library for Widget Blueprint operations.
 * Provides APIs for inspecting, modifying, and managing Widget Blueprint assets.
 * 
 * Supports both design-time inspection and runtime widget analysis during PIE.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UWidgetBlueprintAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Inspect Widget Blueprint hierarchy, bindings, properties, and animations.
	 * Returns comprehensive JSON analysis of Widget Blueprint asset structure.
	 * 
	 * @param AssetPath Path to Widget Blueprint asset (e.g., /Game/UI/WBP_MainMenu)
	 * @return JSON string containing Widget Blueprint structure data or error
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Widget")
	static FString InspectWidgetBlueprint(const FString& AssetPath);

	/**
	 * Inspect runtime widgets during PIE sessions.
	 * Analyzes live widget tree with computed geometry and runtime properties.
	 * 
	 * @return JSON string containing runtime widget data or error
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Widget")
	static FString InspectRuntimeWidgets();

	/**
	 * Add widget to Widget Blueprint.
	 * Creates new widget in Widget Blueprint hierarchy with specified properties.
	 * 
	 * @param AssetPath Path to Widget Blueprint asset
	 * @param ParentSlotName Name of parent widget or slot (empty for root)
	 * @param WidgetClass Widget class name (e.g., "TextBlock", "Button")
	 * @param PropertiesJson JSON string with widget properties (optional)
	 * @return JSON string with operation result or error
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Widget")
	static FString AddWidget(
		const FString& AssetPath,
		const FString& ParentSlotName = TEXT(""),
		const FString& WidgetClass = TEXT("TextBlock"),
		const FString& PropertiesJson = TEXT(""));

private:
	/** Helper to build widget hierarchy JSON recursively */
	static TSharedPtr<FJsonObject> BuildWidgetNode(
		UWidget* Widget,
		int32 CurrentDepth,
		int32 MaxDepth,
		bool bIncludeDefaults);

	/** Helper to extract widget properties to JSON */
	static TSharedPtr<FJsonObject> ExtractWidgetProperties(UWidget* Widget, bool bIncludeDefaults);

	/** Helper to extract property bindings from Widget Blueprint */
	static TArray<TSharedPtr<FJsonValue>> ExtractBindings(UWidgetBlueprint* WidgetBP);

	/** Helper to extract animations from Widget Blueprint */
	static TArray<TSharedPtr<FJsonValue>> ExtractAnimations(UWidgetBlueprint* WidgetBP);

	/** Helper to collect all widget names for flat listing */
	static void CollectWidgetNames(UWidget* Widget, TArray<FString>& OutNames);

	/** Helper to find PIE world by index */
	static UWorld* GetPIEWorldByIndex(int32 Index, int32& OutTotalCount);

	/** Helper to collect runtime widgets from PIE world */
	static TArray<class UUserWidget*> CollectPIEWidgets(UWorld* PIEWorld);

	/** Helper to find widget by name in hierarchy */
	static UWidget* FindWidgetByName(UWidget* Root, const FString& Name);

	/** Helper to build runtime widget node with geometry */
	static TSharedPtr<FJsonObject> BuildRuntimeWidgetNode(
		UWidget* Widget,
		int32 CurrentDepth,
		int32 MaxDepth,
		bool bIncludeGeometry,
		bool bIncludeProperties);

	/** Helper to extract runtime geometry from widget */
	static TSharedPtr<FJsonObject> ExtractGeometry(UWidget* Widget);

	/** Helper to extract runtime properties from widget */
	static TSharedPtr<FJsonObject> ExtractRuntimeProperties(UWidget* Widget);

	/** Helper to resolve widget class by name */
	static UClass* ResolveWidgetClass(const FString& WidgetClassName, FString& OutError);

	/** Helper to convert JSON object to string */
	static FString ClawJsonObjectToString(const TSharedPtr<FJsonObject>& JsonObject);

	/** Helper to create error JSON response */
	static FString ClawMakeError(const FString& ErrorMessage);
};