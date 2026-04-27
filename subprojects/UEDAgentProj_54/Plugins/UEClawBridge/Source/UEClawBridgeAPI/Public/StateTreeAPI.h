// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "StateTreeAPI.generated.h"

/**
 * Blueprint function library for StateTree operations.
 * Provides APIs for querying, modifying, and managing StateTree assets.
 * 
 * NOTE: Requires StateTree module which may not be available in all UE versions.
 * Code uses conditional compilation to handle missing modules gracefully.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UStateTreeAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Query StateTree structure: states, tasks, transitions, evaluators, and parameters.
	 * Returns comprehensive JSON analysis of StateTree asset.
	 * 
	 * @param AssetPath Path to StateTree asset (e.g., /Game/AI/ST_EnemyBehavior)
	 * @return JSON string containing StateTree structure data or error
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|StateTree")
	static FString QueryStateTree(const FString& AssetPath);

	/**
	 * Add a state to StateTree.
	 * Creates new state in StateTree hierarchy with specified properties.
	 * 
	 * @param AssetPath Path to StateTree asset
	 * @param ParentStateName Name of parent state (empty for root)
	 * @param StateName Name of new state
	 * @param StateType Type of state: "State", "Group", "Linked", "Subtree"
	 * @return JSON string with operation result or error
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|StateTree")
	static FString AddStateTreeState(
		const FString& AssetPath,
		const FString& ParentStateName = TEXT(""),
		const FString& StateName = TEXT("NewState"),
		const FString& StateType = TEXT("State"));

	/**
	 * Add a task to a state.
	 * Adds task instance to specified state with optional properties.
	 * 
	 * @param AssetPath Path to StateTree asset
	 * @param StateName Name of target state
	 * @param TaskClass Task class name (e.g., "StateTreeTask_Wait")
	 * @param PropertiesJson JSON string with task properties (optional)
	 * @return JSON string with operation result or error
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|StateTree")
	static FString AddStateTreeTask(
		const FString& AssetPath,
		const FString& StateName,
		const FString& TaskClass,
		const FString& PropertiesJson = TEXT(""));

	/**
	 * Add a transition between states.
	 * Creates transition from source to target state with specified trigger.
	 * 
	 * @param AssetPath Path to StateTree asset
	 * @param SourceState Name of source state
	 * @param TargetState Name of target state or special: "Succeeded", "Failed", "Next"
	 * @param Trigger Transition trigger: "OnStateCompleted", "OnStateFailed", "OnTick", "OnEvent"
	 * @return JSON string with operation result or error
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|StateTree")
	static FString AddStateTreeTransition(
		const FString& AssetPath,
		const FString& SourceState,
		const FString& TargetState,
		const FString& Trigger = TEXT("OnStateCompleted"));

	/**
	 * Remove a state from StateTree.
	 * Removes state and all its children from StateTree hierarchy.
	 * 
	 * @param AssetPath Path to StateTree asset
	 * @param StateName Name of state to remove
	 * @return true if state was removed successfully
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|StateTree")
	static bool RemoveStateTreeState(const FString& AssetPath, const FString& StateName);

private:
	/** Check if StateTree module is available at runtime */
	static bool IsStateTreeModuleAvailable();

	/** Helper to convert JSON object to string */
	static FString JsonObjectToString(const TSharedPtr<FJsonObject>& JsonObject);

	/** Helper to create error JSON response */
	static FString ClawMakeError(const FString& ErrorMessage);
};