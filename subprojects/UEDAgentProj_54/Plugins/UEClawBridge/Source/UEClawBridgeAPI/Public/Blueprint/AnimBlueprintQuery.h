// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Animation/AnimBlueprint.h"
#include "AnimBlueprintQuery.generated.h"

/**
 * AnimBlueprint specialized query API.
 * Provides read-only access to AnimBlueprint-specific features:
 * AnimGraph, StateMachine graphs, State/Transition hierarchies, and FAnimNode properties.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UAnimBlueprintQuery : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Query AnimBlueprint state machine hierarchy.
	 * Returns states, transitions, conduits with connections and nested graphs.
	 * 
	 * @param AssetPath Asset path to the AnimBlueprint
	 * @param StateMachineName Filter by specific state machine name (empty = all)
	 * @param bIncludePositions Include node X/Y positions
	 * @param bIncludeNestedGraphs Include nested state/transition graph details
	 * @return JSON string with state machine hierarchy or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|AnimBlueprint")
	static FString QueryStateMachineHierarchy(
		const FString& AssetPath,
		const FString& StateMachineName = TEXT(""),
		bool bIncludePositions = false,
		bool bIncludeNestedGraphs = false);

	/**
	 * Query AnimGraph nodes with FAnimNode properties.
	 * Returns AnimGraph nodes with their embedded FAnimNode_* struct properties.
	 * 
	 * @param AssetPath Asset path to the AnimBlueprint
	 * @param GraphName Filter by specific AnimGraph name (empty = all AnimGraphs)
	 * @param bIncludeAnimNodeProperties Include FAnimNode_* struct properties
	 * @return JSON string with AnimGraph nodes or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|AnimBlueprint")
	static FString QueryAnimGraphNodes(
		const FString& AssetPath,
		const FString& GraphName = TEXT(""),
		bool bIncludeAnimNodeProperties = true);

	/**
	 * List all animation layer interfaces and their functions.
	 * For AnimLayerInterface Blueprints, returns interface functions that can be implemented.
	 * 
	 * @param AssetPath Asset path to the AnimBlueprint or AnimLayerInterface
	 * @return JSON string with interface functions or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|AnimBlueprint")
	static FString QueryAnimLayerInterfaces(const FString& AssetPath);

private:
	// State machine helpers
	static TSharedPtr<FJsonObject> StateMachineToJson(
		class UAnimationStateMachineGraph* StateMachineGraph,
		bool bIncludePositions,
		bool bIncludeNestedGraphs);

	static TSharedPtr<FJsonObject> AnimStateNodeToJson(
		class UAnimStateNode* StateNode,
		bool bIncludePositions,
		bool bIncludeNestedGraph);

	static TSharedPtr<FJsonObject> TransitionNodeToJson(
		class UAnimStateTransitionNode* TransitionNode,
		bool bIncludePositions,
		bool bIncludeNestedGraph);

	// AnimGraph helpers
	static TSharedPtr<FJsonObject> ExtractAnimNodeProperties(
		class UAnimGraphNode_Base* AnimGraphNode);

	// Utility helpers
	static class UAnimationStateMachineGraph* FindStateMachineByName(
		UAnimBlueprint* AnimBP,
		const FString& StateMachineName);

	static TArray<class UAnimationGraph*> GetAllAnimGraphs(UAnimBlueprint* AnimBP);
};