// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Engine/Blueprint.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BlueprintGraphQuery.generated.h"

/**
 * Blueprint graph query API.
 * Provides read-only access to Blueprint graph structure, nodes, pins, and connections.
 * Supports both regular Blueprints and AnimBlueprints with specialized graph types.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UBlueprintGraphQuery : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Query Blueprint graph structure with filtering options.
	 * Returns comprehensive JSON containing graphs, nodes, pins, and connections.
	 * 
	 * @param AssetPath Asset path to the Blueprint (e.g., /Game/Blueprints/BP_Character)
	 * @param GraphName Filter by specific graph name (empty = all graphs)
	 * @param GraphType Filter by graph type: event, function, macro, interface, anim_graph, state_machine, state, transition
	 * @param NodeGuid Get specific node by GUID (overrides other filters)
	 * @param Search Filter nodes by title or class name (supports wildcards: *pattern*)
	 * @param bIncludePositions Include node X/Y positions in output
	 * @return JSON string with query results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString QueryBlueprintGraph(
		const FString& AssetPath,
		const FString& GraphName = TEXT(""),
		const FString& GraphType = TEXT(""),
		const FString& NodeGuid = TEXT(""),
		const FString& Search = TEXT(""),
		bool bIncludePositions = true);  // Default true: positions always included

	/**
	 * List all callable entries (events, functions, macros) in Blueprint.
	 * Lightweight version without full graph details.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @return JSON string with callable list or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString ListBlueprintCallables(const FString& AssetPath);

	/**
	 * Query Blueprint basic information (components, variables, interfaces, parent class).
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param Include What to include: "all", "components", "variables", "interfaces", "parent"
	 * @return JSON string with Blueprint info or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString QueryBlueprintInfo(
		const FString& AssetPath,
		const FString& Include = TEXT("all"));

private:
	// Graph conversion helpers
	static TSharedPtr<FJsonObject> GraphToJson(
		class UEdGraph* Graph, 
		const FString& GraphType, 
		bool bIncludePositions, 
		const FString& SearchFilter = TEXT(""));

	static TSharedPtr<FJsonObject> NodeToJson(
		class UEdGraphNode* Node, 
		bool bIncludePositions);

	static TSharedPtr<FJsonObject> PinToJson(
		class UEdGraphPin* Pin);

	// Node search helpers
	static class UEdGraphNode* FindNodeByGuid(
		UBlueprint* Blueprint, 
		const FGuid& NodeGuid, 
		FString& OutGraphName, 
		FString& OutGraphType);

	static class UEdGraph* FindGraphByName(
		UBlueprint* Blueprint, 
		const FString& CallableName, 
		FString& OutGraphType);

	// Callable extraction
	static void ExtractEvents(
		UBlueprint* Blueprint, 
		TArray<TSharedPtr<FJsonValue>>& OutArray);

	static void ExtractFunctions(
		UBlueprint* Blueprint, 
		TArray<TSharedPtr<FJsonValue>>& OutArray);

	static void ExtractMacros(
		UBlueprint* Blueprint, 
		TArray<TSharedPtr<FJsonValue>>& OutArray);

	// AnimBlueprint support
	static FString GetAnimGraphTypeString(class UEdGraph* Graph);
	
	static void ProcessAnimBlueprintGraphs(
		class UAnimBlueprint* AnimBP,
		const FString& GraphNameFilter,
		const FString& GraphTypeFilter,
		bool bIncludePositions,
		const FString& SearchFilter,
		TArray<TSharedPtr<FJsonValue>>& OutGraphsArray);

	// Utility helpers
	static FString GetPinDirectionString(EEdGraphPinDirection Direction);
	static FString GetPinCategoryString(FName Category);
	static bool MatchesWildcard(const FString& Text, const FString& Pattern);
};