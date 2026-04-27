// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "BuildSystemAPI.h"
#include "UEClawBridgeAPI.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformFilemanager.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/DateTime.h"
#include "Engine/Engine.h"
#include "Modules/ModuleManager.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Framework/Notifications/NotificationManager.h"
#include "Widgets/Notifications/SNotificationList.h"
#include "Editor.h"

#if PLATFORM_WINDOWS
    #include "Modules/ModuleManager.h"
    // Use dynamic module loading instead of direct include
#endif

FString UBuildSystemAPI::BuildAndRelaunch(bool bWait)
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("BuildAndRelaunch called with bWait=%s"), bWait ? TEXT("true") : TEXT("false"));

#if !PLATFORM_WINDOWS
    return ClawMakeError(TEXT("BuildAndRelaunch is only supported on Windows"));
#else

    // Get project paths
    FString ProjectPath = FPaths::GetProjectFilePath();
    if (ProjectPath.IsEmpty())
    {
        return ClawMakeError(TEXT("Could not determine project path"));
    }

    FString ProjectName = FPaths::GetBaseFilename(ProjectPath);
    FString ProjectDir = FPaths::GetPath(ProjectPath);
    FString EngineDir = FPaths::EngineDir();
    FString BuildBatchFile = FPaths::Combine(EngineDir, TEXT("Build/BatchFiles/Build.bat"));
    FString EditorExecutable = FPaths::Combine(EngineDir, TEXT("Binaries/Win64/UnrealEditor.exe"));

    // Validate paths
    if (!FPaths::FileExists(BuildBatchFile))
    {
        return ClawMakeError(FString::Printf(TEXT("Build script not found: %s"), *BuildBatchFile));
    }

    if (!FPaths::FileExists(EditorExecutable))
    {
        return ClawMakeError(FString::Printf(TEXT("Editor executable not found: %s"), *EditorExecutable));
    }

    // Create temp script directory
    FString TempScriptPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Temp"), TEXT("ArtClawBuildAndRelaunch.bat"));
    FString TempScriptDir = FPaths::GetPath(TempScriptPath);

    IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
    if (!PlatformFile.DirectoryExists(*TempScriptDir))
    {
        if (!PlatformFile.CreateDirectoryTree(*TempScriptDir))
        {
            return ClawMakeError(FString::Printf(TEXT("Failed to create temp directory: %s"), *TempScriptDir));
        }
    }

    uint32 CurrentPID = FPlatformProcess::GetCurrentProcessId();
    FString BuildLogPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Temp"), TEXT("ArtClawBuild.log"));
    FString BuildStatusPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Temp"), TEXT("ArtClawBuild.status.json"));

    // Remove stale status file
    PlatformFile.DeleteFile(*BuildStatusPath);

    // Build batch script
    FString BatchScript = TEXT("@echo off\n");
    BatchScript += FString::Printf(TEXT("echo Waiting for Unreal Editor (PID: %d) to close...\n"), CurrentPID);
    BatchScript += TEXT("\n");

    // Wait for process to exit
    BatchScript += TEXT(":WAIT_LOOP\n");
    BatchScript += FString::Printf(TEXT("tasklist /FI \"PID eq %d\" 2>NUL | find \"%d\" >NUL\n"), CurrentPID, CurrentPID);
    BatchScript += TEXT("if %ERRORLEVEL% EQU 0 (\n");
    BatchScript += TEXT("    timeout /t 1 /nobreak >nul\n");
    BatchScript += TEXT("    goto WAIT_LOOP\n");
    BatchScript += TEXT(")\n");
    BatchScript += TEXT("echo Editor closed.\n");
    BatchScript += TEXT("\n");

    // Build command with Development configuration
    BatchScript += FString::Printf(TEXT("echo Building %s (Development)...\n"), *ProjectName);
    BatchScript += FString::Printf(TEXT("call \"%s\" %sEditor Win64 Development \"%s\" -waitmutex > \"%s\" 2>&1\n"),
        *BuildBatchFile, *ProjectName, *ProjectPath, *BuildLogPath);
    BatchScript += TEXT("set BUILD_EXIT=%ERRORLEVEL%\n");
    BatchScript += TEXT("\n");

    // Check build result
    BatchScript += TEXT("if %BUILD_EXIT% NEQ 0 (\n");
    BatchScript += TEXT("    echo Build failed with error code %BUILD_EXIT%\n");
    BatchScript += FString::Printf(TEXT("    echo {\"success\":false,\"exit_code\":%%BUILD_EXIT%%,\"message\":\"Build failed\"} > \"%s\"\n"), *BuildStatusPath);
    BatchScript += TEXT("    pause\n");
    BatchScript += TEXT("    exit /b %BUILD_EXIT%\n");
    BatchScript += TEXT(")\n");
    BatchScript += TEXT("\n");

    // Write success status and relaunch
    BatchScript += FString::Printf(TEXT("echo {\"success\":true,\"exit_code\":0,\"message\":\"Build completed successfully\"} > \"%s\"\n"), *BuildStatusPath);
    BatchScript += TEXT("echo Build completed successfully. Relaunching editor...\n");
    BatchScript += TEXT("timeout /t 2 /nobreak >nul\n");
    BatchScript += FString::Printf(TEXT("start \"\" \"%s\" \"%s\"\n"), *EditorExecutable, *ProjectPath);
    BatchScript += TEXT("\n");
    BatchScript += FString::Printf(TEXT("del \"%s\"\n"), *TempScriptPath);

    // Write batch script
    if (!FFileHelper::SaveStringToFile(BatchScript, *TempScriptPath))
    {
        return ClawMakeError(FString::Printf(TEXT("Failed to create batch script: %s"), *TempScriptPath));
    }

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Created batch script at: %s"), *TempScriptPath);

    // Launch batch script
    FString CmdArgs = FString::Printf(TEXT("/c \"%s\""), *TempScriptPath);
    FProcHandle ProcHandle = FPlatformProcess::CreateProc(
        TEXT("cmd.exe"), *CmdArgs, true, false, false, nullptr, 0, nullptr, nullptr);

    if (!ProcHandle.IsValid())
    {
        return ClawMakeError(TEXT("Failed to launch build script"));
    }

    // Build JSON result
    TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
    Result->SetBoolField(TEXT("success"), true);
    Result->SetStringField(TEXT("status"), TEXT("initiated"));
    Result->SetStringField(TEXT("project"), *ProjectName);
    Result->SetStringField(TEXT("build_config"), TEXT("Development"));
    Result->SetBoolField(TEXT("will_relaunch"), true);
    Result->SetNumberField(TEXT("editor_pid"), CurrentPID);
    Result->SetStringField(TEXT("build_log_path"), *BuildLogPath);
    Result->SetStringField(TEXT("build_status_path"), *BuildStatusPath);
    Result->SetStringField(TEXT("message"), FString::Printf(TEXT("Build and relaunch workflow initiated for PID: %d. Editor will close momentarily."), CurrentPID));

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("BuildAndRelaunch: Batch script launched, requesting editor shutdown..."));

    // Request editor shutdown with small delay
    FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float DeltaTime) -> bool
    {
        FPlatformMisc::RequestExit(false);
        return false;
    }), 1.0f);

    return JsonToString(Result);

#endif // PLATFORM_WINDOWS
}

FString UBuildSystemAPI::TriggerLiveCoding()
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("TriggerLiveCoding called"));

#if !PLATFORM_WINDOWS
    return ClawMakeError(TEXT("Live Coding is only supported on Windows"));
#else

    // Use console command instead of module interface to avoid header dependency
    if (!GEngine || !GEngine->Exec(nullptr, TEXT("LiveCoding.Compile")))
    {
        return ClawMakeError(TEXT("Failed to trigger Live Coding. Enable it in Editor Preferences > General > Live Coding."));
    }

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("TriggerLiveCoding: Live Coding triggered via console command"));

    return ClawMakeSuccess(TEXT("triggered_async"), TEXT("Live Coding compilation triggered via console command. Check Output Log for results. Shortcut: Ctrl+Alt+F11"));

#endif // PLATFORM_WINDOWS
}

// Helper functions
FString UBuildSystemAPI::JsonToString(const TSharedPtr<FJsonObject>& JsonObject)
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

FString UBuildSystemAPI::ClawMakeError(const FString& ErrorMessage)
{
    UE_LOG(LogUEClawBridgeAPI, Error, TEXT("BuildSystemAPI Error: %s"), *ErrorMessage);
    
    TSharedPtr<FJsonObject> ErrorJson = MakeShareable(new FJsonObject);
    ErrorJson->SetBoolField(TEXT("success"), false);
    ErrorJson->SetStringField(TEXT("error"), ErrorMessage);
    return JsonToString(ErrorJson);
}

FString UBuildSystemAPI::ClawMakeSuccess(const FString& Status, const FString& Message)
{
    TSharedPtr<FJsonObject> ResultJson = MakeShareable(new FJsonObject);
    ResultJson->SetBoolField(TEXT("success"), true);
    ResultJson->SetStringField(TEXT("status"), Status);
    ResultJson->SetStringField(TEXT("message"), Message);
    return JsonToString(ResultJson);
}