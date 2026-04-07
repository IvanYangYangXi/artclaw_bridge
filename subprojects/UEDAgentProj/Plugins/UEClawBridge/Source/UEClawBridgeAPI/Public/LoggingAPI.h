// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Engine/Engine.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Dom/JsonObject.h"
#include "Misc/OutputDeviceRedirector.h"
#include "HAL/IConsoleManager.h"
#include "LoggingAPI.generated.h"

/**
 * Simple log capture device for intercepting UE output logs
 * Based on soft-ue-cli FBridgeLogCapture implementation
 */
class FLogCapture : public FOutputDevice
{
public:
    static FLogCapture& Get();

    void Start();
    void Stop();
    TArray<FString> GetLines(int32 Count, const FString& Filter, const FString& Category, const FString& Severity) const;

protected:
    virtual void Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& Category) override;

private:
    TArray<FString> Lines;
    mutable FCriticalSection Lock;
    bool bStarted = false;
    static constexpr int32 MaxLines = 10000;

    FString VerbosityToString(ELogVerbosity::Type Verbosity) const;
    bool PassesSeverityFilter(ELogVerbosity::Type Verbosity, const FString& SeverityFilter) const;
};

/**
 * Logging API for reading UE logs and managing console variables
 * Based on soft-ue-cli logging tools implementation
 */
UCLASS()
class UECLAWBRIDGEAPI_API ULoggingAPI : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Read UE output log with filtering */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|Logging")
    static FString GetLogs(
        const FString& Category = TEXT(""),
        const FString& TextFilter = TEXT(""),
        int32 Limit = 100,
        const FString& Severity = TEXT(""));

    /** Read console variable value */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|Logging")
    static FString GetConsoleVar(const FString& VarName);

    /** Set console variable value */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|Logging")
    static FString SetConsoleVar(const FString& VarName, const FString& Value);

private:
    // Helper functions for JSON generation
    static FString JsonToString(const TSharedPtr<FJsonObject>& JsonObject);
    static FString ClawMakeError(const FString& ErrorMessage);
};