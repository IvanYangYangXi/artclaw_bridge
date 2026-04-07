// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "LoggingAPI.h"
#include "UEClawBridgeAPI.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Misc/OutputDeviceRedirector.h"
#include "HAL/IConsoleManager.h"
#include "Algo/Reverse.h"

// ── FLogCapture Implementation ─────────────────────────────────────────

FLogCapture& FLogCapture::Get()
{
    static FLogCapture Instance;
    return Instance;
}

void FLogCapture::Start()
{
    if (!bStarted)
    {
        GLog->AddOutputDevice(this);
        bStarted = true;
        UE_LOG(LogUEClawBridgeAPI, Log, TEXT("FLogCapture started"));
    }
}

void FLogCapture::Stop()
{
    if (bStarted)
    {
        GLog->RemoveOutputDevice(this);
        bStarted = false;
        UE_LOG(LogUEClawBridgeAPI, Log, TEXT("FLogCapture stopped"));
    }
}

void FLogCapture::Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& Category)
{
    FString VerbStr = VerbosityToString(Verbosity);
    FString Line = FString::Printf(TEXT("[%s][%s] %s"), *Category.ToString(), *VerbStr, V);

    FScopeLock ScopeLock(&Lock);
    Lines.Add(MoveTemp(Line));
    if (Lines.Num() > MaxLines)
    {
        Lines.RemoveAt(0, Lines.Num() - MaxLines);
    }
}

TArray<FString> FLogCapture::GetLines(int32 Count, const FString& Filter, const FString& Category, const FString& Severity) const
{
    FScopeLock ScopeLock(&Lock);

    TArray<FString> Result;
    if (Count <= 0) return Result;

    const bool bHasFilter = !Filter.IsEmpty() || !Category.IsEmpty() || !Severity.IsEmpty();
    const FString CategoryBracket = Category.IsEmpty() ? FString() : (TEXT("[") + Category + TEXT("]"));

    // Scan from newest to oldest
    const int32 Start = bHasFilter ? 0 : FMath::Max(0, Lines.Num() - Count);
    Result.Reserve(FMath::Min(Count, Lines.Num()));

    for (int32 i = Lines.Num() - 1; i >= Start; --i)
    {
        const FString& Line = Lines[i];
        
        // Apply filters
        if (!Filter.IsEmpty() && !Line.Contains(Filter, ESearchCase::IgnoreCase)) continue;
        if (!CategoryBracket.IsEmpty() && !Line.Contains(CategoryBracket, ESearchCase::IgnoreCase)) continue;
        
        // Severity filter - extract verbosity from log line format [Category][Verbosity]
        if (!Severity.IsEmpty())
        {
            bool bPassesSeverity = false;
            if (Severity.Equals(TEXT("Error"), ESearchCase::IgnoreCase) && Line.Contains(TEXT("[Error]"))) bPassesSeverity = true;
            else if (Severity.Equals(TEXT("Warning"), ESearchCase::IgnoreCase) && Line.Contains(TEXT("[Warning]"))) bPassesSeverity = true;
            else if (Severity.Equals(TEXT("Display"), ESearchCase::IgnoreCase) && Line.Contains(TEXT("[Display]"))) bPassesSeverity = true;
            else if (Severity.Equals(TEXT("Log"), ESearchCase::IgnoreCase) && Line.Contains(TEXT("[Log]"))) bPassesSeverity = true;
            else if (Severity.Equals(TEXT("Verbose"), ESearchCase::IgnoreCase) && Line.Contains(TEXT("[Verbose]"))) bPassesSeverity = true;
            
            if (!bPassesSeverity) continue;
        }

        Result.Add(Line);
        if (Result.Num() >= Count) break;
    }

    // Reverse so results are chronological (oldest first)
    Algo::Reverse(Result);
    return Result;
}

FString FLogCapture::VerbosityToString(ELogVerbosity::Type Verbosity) const
{
    switch (Verbosity)
    {
    case ELogVerbosity::Fatal:   return TEXT("Fatal");
    case ELogVerbosity::Error:   return TEXT("Error");
    case ELogVerbosity::Warning: return TEXT("Warning");
    case ELogVerbosity::Display: return TEXT("Display");
    case ELogVerbosity::Log:     return TEXT("Log");
    case ELogVerbosity::Verbose: return TEXT("Verbose");
    default:                     return TEXT("Log");
    }
}

bool FLogCapture::PassesSeverityFilter(ELogVerbosity::Type Verbosity, const FString& SeverityFilter) const
{
    if (SeverityFilter.IsEmpty()) return true;
    
    FString VerbStr = VerbosityToString(Verbosity);
    return VerbStr.Equals(SeverityFilter, ESearchCase::IgnoreCase);
}

// ── ULoggingAPI Implementation ─────────────────────────────────────────

FString ULoggingAPI::GetLogs(const FString& Category, const FString& TextFilter, int32 Limit, const FString& Severity)
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GetLogs called: Category='%s', Filter='%s', Limit=%d, Severity='%s'"), 
        *Category, *TextFilter, Limit, *Severity);

    // Ensure log capture is started
    FLogCapture::Get().Start();

    // Clamp limit to reasonable range
    Limit = FMath::Clamp(Limit, 1, 1000);

    TArray<FString> LogLines = FLogCapture::Get().GetLines(Limit, TextFilter, Category, Severity);

    // Build JSON result
    TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
    
    TArray<TSharedPtr<FJsonValue>> LinesArray;
    for (const FString& Line : LogLines)
    {
        LinesArray.Add(MakeShareable(new FJsonValueString(Line)));
    }

    Result->SetArrayField(TEXT("lines"), LinesArray);
    Result->SetNumberField(TEXT("count"), LinesArray.Num());
    Result->SetStringField(TEXT("category_filter"), Category);
    Result->SetStringField(TEXT("text_filter"), TextFilter);
    Result->SetStringField(TEXT("severity_filter"), Severity);
    Result->SetNumberField(TEXT("limit"), Limit);
    Result->SetBoolField(TEXT("success"), true);

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GetLogs returned %d lines"), LinesArray.Num());

    return JsonToString(Result);
}

FString ULoggingAPI::GetConsoleVar(const FString& VarName)
{
    if (VarName.IsEmpty())
    {
        return ClawMakeError(TEXT("VarName is required"));
    }

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GetConsoleVar: %s"), *VarName);

    IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(*VarName);
    if (!CVar)
    {
        return ClawMakeError(FString::Printf(TEXT("Console variable '%s' not found"), *VarName));
    }

    TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
    Result->SetBoolField(TEXT("success"), true);
    Result->SetStringField(TEXT("name"), VarName);
    Result->SetStringField(TEXT("value"), CVar->GetString());
    Result->SetStringField(TEXT("help"), CVar->GetHelp());

    return JsonToString(Result);
}

FString ULoggingAPI::SetConsoleVar(const FString& VarName, const FString& Value)
{
    if (VarName.IsEmpty())
    {
        return ClawMakeError(TEXT("VarName is required"));
    }

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("SetConsoleVar: %s = %s"), *VarName, *Value);

    IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(*VarName);
    if (!CVar)
    {
        return ClawMakeError(FString::Printf(TEXT("Console variable '%s' not found"), *VarName));
    }

    // Set the new value
    CVar->Set(*Value, ECVF_SetByCode);

    TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
    Result->SetBoolField(TEXT("success"), true);
    Result->SetStringField(TEXT("name"), VarName);
    Result->SetStringField(TEXT("old_value"), Value); // We don't store the old value, so just echo
    Result->SetStringField(TEXT("new_value"), CVar->GetString());
    Result->SetStringField(TEXT("message"), FString::Printf(TEXT("Console variable '%s' set to '%s'"), *VarName, *CVar->GetString()));

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("SetConsoleVar: %s successfully set to %s"), *VarName, *CVar->GetString());

    return JsonToString(Result);
}

// Helper functions
FString ULoggingAPI::JsonToString(const TSharedPtr<FJsonObject>& JsonObject)
{
    if (!JsonObject.IsValid())
    {
        return TEXT("{}");
    }

    FString OutputString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
    return OutputString;
}

FString ULoggingAPI::ClawMakeError(const FString& ErrorMessage)
{
    UE_LOG(LogUEClawBridgeAPI, Error, TEXT("LoggingAPI Error: %s"), *ErrorMessage);
    
    TSharedPtr<FJsonObject> ErrorJson = MakeShareable(new FJsonObject);
    ErrorJson->SetBoolField(TEXT("success"), false);
    ErrorJson->SetStringField(TEXT("error"), ErrorMessage);
    return JsonToString(ErrorJson);
}