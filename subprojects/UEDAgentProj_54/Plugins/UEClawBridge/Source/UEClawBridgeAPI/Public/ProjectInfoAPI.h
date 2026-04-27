// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Engine/Engine.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Dom/JsonObject.h"
#include "ProjectInfoAPI.generated.h"

/**
 * Project Information API for retrieving project details and editor status
 * Based on soft-ue-cli project tools implementation
 */
UCLASS()
class UECLAWBRIDGEAPI_API UProjectInfoAPI : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Get project name, engine version, target platforms, modules */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|Project")
    static FString GetProjectInfo();

    /** Get editor runtime status: memory, FPS, uptime */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|Project")
    static FString GetEditorStatus();

private:
    // Helper functions for JSON generation
    static FString JsonToString(const TSharedPtr<FJsonObject>& JsonObject);
    static FString ClawMakeError(const FString& ErrorMessage);
    static void AddMemoryInfo(TSharedPtr<FJsonObject> JsonObject);
    static void AddEngineInfo(TSharedPtr<FJsonObject> JsonObject);
};