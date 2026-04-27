// Copyright ArtClaw. All Rights Reserved.

// NOTE: Requires additional modules in UEClawBridgeAPI.Build.cs:
//   "AIModule", "GameplayTasks"

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BehaviorTreeAPI.generated.h"

/**
 * Behavior Tree API for AI behavior tree and blackboard management
 */
UCLASS()
class UECLAWBRIDGEAPI_API UBehaviorTreeAPI : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Query Behavior Tree structure */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|AI")
    static FString QueryBehaviorTree(const FString& AssetPath);

    /** Add node to Behavior Tree */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|AI")
    static FString AddBTNode(
        const FString& AssetPath,
        const FString& ParentNodeIndex,  // index or "root"
        const FString& NodeClass,        // "BTTask_Wait", "BTDecorator_Blackboard", etc.
        const FString& PropertiesJson = TEXT(""));

    /** Add key to Blackboard asset */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|AI")
    static FString AddBlackboardKey(
        const FString& AssetPath,
        const FString& KeyName,
        const FString& KeyType);  // "Bool", "Int", "Float", "String", "Object", "Vector", "Rotator", "Enum", "Class"

    /** Get Blackboard info */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|AI")
    static FString QueryBlackboard(const FString& AssetPath);
};