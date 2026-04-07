// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ActorReflectionAPI.generated.h"

/**
 * Unified actor reflection API for function calling and property access.
 * Provides high-level interface for runtime and editor operations.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UActorReflectionAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Call any BlueprintCallable UFUNCTION on an actor.
	 * Supports simple argument types: bool, int, float, string, vectors, rotators.
	 * Returns function output parameters and return values as JSON.
	 * 
	 * @param ActorName Actor name or label to call function on
	 * @param FunctionName Function/event name to call
	 * @param ArgsJson Named arguments as JSON object (e.g., {"Speed": 100, "Direction": "forward"})
	 * @param WorldType World context: "editor" (editor world), "pie" (Play-In-Editor), "game" (runtime)
	 * @return JSON result with success status, return values, and output parameters
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Actor", CallInEditor)
	static FString CallFunction(
		const FString& ActorName,
		const FString& FunctionName,
		const FString& ArgsJson = TEXT(""),
		const FString& WorldType = TEXT("editor"));

	/**
	 * Read a UPROPERTY by path with nested property support.
	 * Supports dot notation for component properties and nested structs.
	 * Examples:
	 *   - "Health" - direct actor property
	 *   - "Mesh.RelativeLocation" - component property
	 *   - "Stats.MaxHealth" - nested struct property
	 *   - "Items[0].Name" - array element property
	 * 
	 * @param TargetPath Actor name/label or asset path (e.g., "/Game/BP_Actor")
	 * @param PropertyPath Property path with dot notation
	 * @param WorldType World context for actor lookup
	 * @return JSON result with property value, type, and metadata
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Actor", CallInEditor)
	static FString GetProperty(
		const FString& TargetPath,
		const FString& PropertyPath,
		const FString& WorldType = TEXT("editor"));

	/**
	 * Write a UPROPERTY by path with nested property support.
	 * Same path syntax as GetProperty. Value is deserialized from JSON.
	 * Automatically creates undo transactions in editor.
	 * 
	 * @param TargetPath Actor name/label or asset path
	 * @param PropertyPath Property path with dot notation
	 * @param ValueJson Property value as JSON (string, number, object, array)
	 * @param WorldType World context for actor lookup
	 * @return JSON result with success status and applied value
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Actor", CallInEditor)
	static FString SetProperty(
		const FString& TargetPath,
		const FString& PropertyPath,
		const FString& ValueJson,
		const FString& WorldType = TEXT("editor"));

private:
	// Helper to find world by type string
	static UWorld* FindWorldByType(const FString& WorldType);

	// Helper to find actor in world by name or label (supports wildcards)
	static AActor* FindActor(UWorld* World, const FString& ActorName);

	// Helper to resolve target object from path (actor or asset)
	static UObject* ResolveTargetObject(const FString& TargetPath, const FString& WorldType, FString& OutError);

	// Helper to resolve nested property path with component and struct support
	static FProperty* ResolvePropertyPath(
		UObject* Object,
		const FString& PropertyPath,
		UObject*& OutTargetObject,
		void*& OutContainer,
		FString& OutError);

	// Helper to match actor names with wildcard support
	static bool MatchesWildcard(const FString& Text, const FString& Pattern);

	// Helper to get actor label safely (fallback to GetName())
	static FString GetActorLabelSafe(AActor* Actor);
};