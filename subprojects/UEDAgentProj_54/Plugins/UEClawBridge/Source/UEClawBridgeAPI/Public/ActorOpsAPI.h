// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ActorOpsAPI.generated.h"

/**
 * High-level actor operations API for spawning, modifying, and batch operations.
 * Complements ActorReflectionAPI with creation and bulk modification tools.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UActorOpsAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Spawn actor with full transform and property setup.
	 * Supports both native classes and Blueprint assets.
	 * 
	 * @param ClassName Class name (e.g., "StaticMeshActor") or Blueprint path (e.g., "/Game/BP_MyActor")
	 * @param LocX Location X coordinate in world units
	 * @param LocY Location Y coordinate in world units  
	 * @param LocZ Location Z coordinate in world units
	 * @param RotPitch Rotation pitch in degrees
	 * @param RotYaw Rotation yaw in degrees
	 * @param RotRoll Rotation roll in degrees
	 * @param PropertiesJson Additional properties to set after spawn as JSON object
	 * @param WorldType World context: "editor" (editor world), "pie" (PIE world), "game" (runtime)
	 * @return JSON result with spawned actor info and any property errors
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Actor", CallInEditor)
	static FString SpawnActor(
		const FString& ClassName,
		float LocX = 0, float LocY = 0, float LocZ = 0,
		float RotPitch = 0, float RotYaw = 0, float RotRoll = 0,
		const FString& PropertiesJson = TEXT(""),
		const FString& WorldType = TEXT("editor"));

	/**
	 * Add component to existing actor with property setup.
	 * Creates component, attaches to specified parent, and sets properties.
	 * 
	 * @param ActorName Actor name or label to add component to
	 * @param ComponentClass Component class name (e.g., "StaticMeshComponent", "PointLightComponent")
	 * @param PropertiesJson Component properties to set as JSON object
	 * @return JSON result with component info and success status
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Actor", CallInEditor)
	static FString AddComponent(
		const FString& ActorName,
		const FString& ComponentClass,
		const FString& PropertiesJson = TEXT(""));

	/**
	 * Batch spawn multiple actors in single transaction.
	 * Reduces undo overhead and provides atomic operations.
	 * 
	 * JSON Format:
	 * {
	 *   "actors": [
	 *     {
	 *       "class": "StaticMeshActor",
	 *       "location": [0, 0, 0],
	 *       "rotation": [0, 0, 0],
	 *       "scale": [1, 1, 1],
	 *       "properties": {"Mesh": "/Game/MyMesh.MyMesh"}
	 *     }
	 *   ]
	 * }
	 * 
	 * @param ActorsJson JSON array of actor definitions
	 * @return JSON result with spawned/failed counts and details
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Actor", CallInEditor)
	static FString BatchSpawnActors(const FString& ActorsJson);

	/**
	 * Batch modify actor properties in single transaction.
	 * Allows efficient bulk property updates across multiple actors.
	 * 
	 * JSON Format:
	 * {
	 *   "modifications": [
	 *     {
	 *       "actor": "ActorName",
	 *       "properties": {
	 *         "Mesh.RelativeLocation": [0, 100, 0],
	 *         "Health": 50
	 *       }
	 *     }
	 *   ]
	 * }
	 * 
	 * @param ModificationsJson JSON array of property modifications
	 * @return JSON result with modified/failed counts and details
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Actor", CallInEditor)
	static FString BatchModifyActors(const FString& ModificationsJson);

	/**
	 * Batch delete actors by name in single transaction.
	 * Provides atomic delete operations with undo support.
	 * 
	 * JSON Format:
	 * {
	 *   "actors": ["ActorName1", "ActorName2", "ActorName3"]
	 * }
	 * 
	 * @param ActorNamesJson JSON array of actor names to delete
	 * @return JSON result with deleted/failed counts and details
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Actor", CallInEditor)
	static FString BatchDeleteActors(const FString& ActorNamesJson);

private:
	// Helper to find world by type string
	static UWorld* FindWorldByType(const FString& WorldType);

	// Helper to find actor by name or label
	static AActor* FindActor(UWorld* World, const FString& ActorName);

	// Helper to resolve actor class from string (native or Blueprint)
	static UClass* ResolveActorClass(const FString& ClassName, FString& OutError);

	// Helper to resolve component class from string
	static UClass* ResolveComponentClass(const FString& ComponentClass, FString& OutError);

	// Helper to apply properties from JSON to object
	static bool ApplyPropertiesFromJson(
		UObject* Object, 
		const TSharedPtr<FJsonObject>& Properties, 
		TArray<FString>& OutErrors);

	// Helper for wildcard matching
	static bool MatchesWildcard(const FString& Text, const FString& Pattern);

	// Helper to get actor label safely
	static FString GetActorLabelSafe(AActor* Actor);
};