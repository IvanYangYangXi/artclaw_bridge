// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Engine/Blueprint.h"
#include "BlueprintGraphEdit.generated.h"

/**
 * Blueprint graph editing API.
 * Provides write operations for adding, removing, and positioning nodes in Blueprint graphs.
 * Supports both regular Blueprints and AnimBlueprints with specialized node types.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UBlueprintGraphEdit : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Add a node to a Blueprint graph.
	 * Supports intelligent auto-positioning and initial property setup.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param NodeClass Node class name (e.g., "K2Node_CallFunction", "K2Node_VariableGet")
	 * @param GraphName Target graph name (default: "EventGraph")
	 * @param PosX X position (ignored if bAutoPosition is true)
	 * @param PosY Y position (ignored if bAutoPosition is true)
	 * @param bAutoPosition Enable intelligent auto-positioning
	 * @param ConnectToNode GUID of node to position relative to (for auto-positioning)
	 * @param ConnectToPin Pin name on ConnectToNode for relative positioning
	 * @param PropertiesJson JSON string with initial node properties
	 * @return JSON string with creation results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString AddGraphNode(
		const FString& AssetPath,
		const FString& NodeClass,
		const FString& GraphName = TEXT("EventGraph"),
		float PosX = 0, 
		float PosY = 0,
		bool bAutoPosition = true,
		const FString& ConnectToNode = TEXT(""),
		const FString& ConnectToPin = TEXT(""),
		const FString& PropertiesJson = TEXT(""));

	/**
	 * Remove a node from Blueprint graph.
	 * Automatically handles connection cleanup and graph refresh.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param NodeGuid GUID of the node to remove
	 * @return true if node was removed successfully
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static bool RemoveGraphNode(
		const FString& AssetPath, 
		const FString& NodeGuid);

	/**
	 * Set positions of multiple nodes in a Blueprint graph.
	 * Efficient batch operation for graph layout adjustments.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param PositionsJson JSON string with node positions: [{"guid": "...", "x": 100, "y": 200}, ...]
	 * @return JSON string with results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString SetNodePositions(
		const FString& AssetPath, 
		const FString& PositionsJson);

	/**
	 * Create a new function graph in Blueprint.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param FunctionName Name of the new function
	 * @param bIsPublic Whether the function should be public (CallInEditor)
	 * @param ReturnTypeJson JSON string with return type specification
	 * @param ParametersJson JSON string with parameter specifications
	 * @return JSON string with creation results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString CreateFunctionGraph(
		const FString& AssetPath,
		const FString& FunctionName,
		bool bIsPublic = false,
		const FString& ReturnTypeJson = TEXT(""),
		const FString& ParametersJson = TEXT(""));

private:
	// Node creation helpers
	static class UEdGraphNode* CreateBlueprintNode(
		UBlueprint* Blueprint,
		class UEdGraph* Graph,
		const FString& NodeClassName,
		const FVector2D& Position,
		bool bAutoPosition,
		const FString& ConnectToNodeGuid,
		const FString& ConnectToPinName,
		const TSharedPtr<class FJsonObject>& Properties,
		FString& OutError);

	static TArray<FString> ApplyNodeProperties(
		UObject* Node, 
		const TSharedPtr<class FJsonObject>& Properties);

	// Utility helpers
	static TSharedPtr<class FJsonObject> ParseJsonString(
		const FString& JsonString, 
		FString& OutError);
};