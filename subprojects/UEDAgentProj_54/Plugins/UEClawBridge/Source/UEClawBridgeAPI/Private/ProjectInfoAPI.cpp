// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "ProjectInfoAPI.h"
#include "UEClawBridgeAPI.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Misc/Paths.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformMemory.h"
#include "HAL/PlatformFilemanager.h"
#include "Interfaces/IPluginManager.h"
#include "Engine/Engine.h"
#include "Framework/Application/SlateApplication.h"
#include "Stats/Stats.h"

FString UProjectInfoAPI::GetProjectInfo()
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GetProjectInfo called"));

    TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
    Result->SetBoolField(TEXT("success"), true);

    // Basic project information
    FString ProjectName = FApp::GetProjectName();
    FString ProjectPath = FPaths::GetProjectFilePath();
    FString ProjectDir = FPaths::ProjectDir();

    Result->SetStringField(TEXT("project_name"), ProjectName);
    Result->SetStringField(TEXT("project_path"), ProjectPath);
    Result->SetStringField(TEXT("project_directory"), ProjectDir);

    // Engine information
    AddEngineInfo(Result);

    // Platform information
    Result->SetStringField(TEXT("platform"), FPlatformProperties::PlatformName());
    Result->SetStringField(TEXT("architecture"), FString(FPlatformMisc::GetCPUBrand()));
    Result->SetBoolField(TEXT("is_editor"), WITH_EDITOR);
    Result->SetBoolField(TEXT("is_development"), UE_BUILD_DEVELOPMENT);
    Result->SetBoolField(TEXT("is_shipping"), UE_BUILD_SHIPPING);

    // Process information
    uint32 ProcessId = FPlatformProcess::GetCurrentProcessId();
    Result->SetNumberField(TEXT("process_id"), ProcessId);

    // Plugin information (ArtClaw specific)
    TSharedPtr<FJsonObject> PluginInfo = MakeShareable(new FJsonObject);
    PluginInfo->SetStringField(TEXT("name"), TEXT("UEClawBridge"));
    
    TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("UEClawBridge"));
    if (Plugin.IsValid())
    {
        const FPluginDescriptor& Desc = Plugin->GetDescriptor();
        PluginInfo->SetStringField(TEXT("version"), Desc.VersionName);
        PluginInfo->SetStringField(TEXT("friendly_name"), Desc.FriendlyName);
        PluginInfo->SetStringField(TEXT("description"), Desc.Description);
        PluginInfo->SetBoolField(TEXT("enabled"), Plugin->IsEnabled());
    }
    Result->SetObjectField(TEXT("artclaw_plugin"), PluginInfo);

    // Content directories
    TArray<TSharedPtr<FJsonValue>> ContentDirs;
    TArray<FString> ContentPaths;
    FPackageName::QueryRootContentPaths(ContentPaths);
    for (const FString& ContentPath : ContentPaths)
    {
        ContentDirs.Add(MakeShareable(new FJsonValueString(ContentPath)));
    }
    Result->SetArrayField(TEXT("content_paths"), ContentDirs);

    // Build configuration
#if UE_BUILD_DEBUG
    Result->SetStringField(TEXT("build_configuration"), TEXT("Debug"));
#elif UE_BUILD_DEVELOPMENT
    Result->SetStringField(TEXT("build_configuration"), TEXT("Development"));
#elif UE_BUILD_TEST
    Result->SetStringField(TEXT("build_configuration"), TEXT("Test"));
#elif UE_BUILD_SHIPPING
    Result->SetStringField(TEXT("build_configuration"), TEXT("Shipping"));
#else
    Result->SetStringField(TEXT("build_configuration"), TEXT("Unknown"));
#endif

    return JsonToString(Result);
}

FString UProjectInfoAPI::GetEditorStatus()
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GetEditorStatus called"));

    TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
    Result->SetBoolField(TEXT("success"), true);

    // Memory information
    AddMemoryInfo(Result);

    // Engine uptime
    double AppTime = FPlatformTime::Seconds();
    Result->SetNumberField(TEXT("uptime_seconds"), AppTime);

    FString UptimeFormatted;
    int32 Hours = static_cast<int32>(AppTime) / 3600;
    int32 Minutes = (static_cast<int32>(AppTime) % 3600) / 60;
    int32 Seconds = static_cast<int32>(AppTime) % 60;
    UptimeFormatted = FString::Printf(TEXT("%02d:%02d:%02d"), Hours, Minutes, Seconds);
    Result->SetStringField(TEXT("uptime_formatted"), UptimeFormatted);

    // Frame rate information
    float DeltaTime = FApp::GetDeltaTime();
    float CurrentFPS = (DeltaTime > 0.0f) ? (1.0f / DeltaTime) : 0.0f;
    Result->SetNumberField(TEXT("current_fps"), CurrentFPS);

    // Game thread time and render thread time (if available)
    if (GEngine && GEngine->GetGameViewportWidget().IsValid())
    {
        Result->SetBoolField(TEXT("has_viewport"), true);
        Result->SetBoolField(TEXT("is_playing"), GEditor ? (GEditor->GetPIEWorldContext() != nullptr) : false);
    }
    else
    {
        Result->SetBoolField(TEXT("has_viewport"), false);
        Result->SetBoolField(TEXT("is_playing"), false);
    }

    // Editor-specific status
#if WITH_EDITOR
    Result->SetBoolField(TEXT("is_in_editor"), true);
    
    if (GEditor)
    {
        Result->SetBoolField(TEXT("has_pie_world"), GEditor->GetPIEWorldContext() != nullptr);
        
        // Get current level name
        if (GEditor->GetEditorWorldContext().World())
        {
            FString LevelName = GEditor->GetEditorWorldContext().World()->GetName();
            Result->SetStringField(TEXT("current_level"), LevelName);
        }
    }
#else
    Result->SetBoolField(TEXT("is_in_editor"), false);
#endif

    // Slate Application info (if available)
    if (FSlateApplication::IsInitialized())
    {
        TSharedPtr<FJsonObject> SlateInfo = MakeShareable(new FJsonObject);
        SlateInfo->SetBoolField(TEXT("initialized"), true);
        SlateInfo->SetNumberField(TEXT("average_delta_time"), FSlateApplication::Get().GetAverageDeltaTime());
        Result->SetObjectField(TEXT("slate_application"), SlateInfo);
    }

    // Garbage collector stats
    TSharedPtr<FJsonObject> GCInfo = MakeShareable(new FJsonObject);
    GCInfo->SetNumberField(TEXT("num_objects"), GUObjectArray.GetObjectArrayNumMinusAvailable());
    Result->SetObjectField(TEXT("garbage_collector"), GCInfo);

    // Current timestamp
    Result->SetStringField(TEXT("timestamp"), FDateTime::Now().ToString(TEXT("%Y-%m-%d %H:%M:%S")));

    return JsonToString(Result);
}

void UProjectInfoAPI::AddMemoryInfo(TSharedPtr<FJsonObject> JsonObject)
{
    if (!JsonObject.IsValid())
    {
        return;
    }

    FPlatformMemoryStats MemStats = FPlatformMemory::GetStats();

    TSharedPtr<FJsonObject> MemoryInfo = MakeShareable(new FJsonObject);
    
    // Memory sizes in bytes
    MemoryInfo->SetNumberField(TEXT("physical_total_bytes"), static_cast<double>(MemStats.TotalPhysical));
    MemoryInfo->SetNumberField(TEXT("physical_available_bytes"), static_cast<double>(MemStats.AvailablePhysical));
    MemoryInfo->SetNumberField(TEXT("physical_used_bytes"), static_cast<double>(MemStats.UsedPhysical));
    MemoryInfo->SetNumberField(TEXT("virtual_total_bytes"), static_cast<double>(MemStats.TotalVirtual));
    MemoryInfo->SetNumberField(TEXT("virtual_used_bytes"), static_cast<double>(MemStats.UsedVirtual));

    // Memory sizes in MB for readability
    MemoryInfo->SetNumberField(TEXT("physical_total_mb"), static_cast<double>(MemStats.TotalPhysical) / (1024.0 * 1024.0));
    MemoryInfo->SetNumberField(TEXT("physical_available_mb"), static_cast<double>(MemStats.AvailablePhysical) / (1024.0 * 1024.0));
    MemoryInfo->SetNumberField(TEXT("physical_used_mb"), static_cast<double>(MemStats.UsedPhysical) / (1024.0 * 1024.0));
    MemoryInfo->SetNumberField(TEXT("virtual_used_mb"), static_cast<double>(MemStats.UsedVirtual) / (1024.0 * 1024.0));

    // Peak memory usage
    MemoryInfo->SetNumberField(TEXT("peak_used_physical_mb"), static_cast<double>(MemStats.PeakUsedPhysical) / (1024.0 * 1024.0));
    MemoryInfo->SetNumberField(TEXT("peak_used_virtual_mb"), static_cast<double>(MemStats.PeakUsedVirtual) / (1024.0 * 1024.0));

    JsonObject->SetObjectField(TEXT("memory"), MemoryInfo);
}

void UProjectInfoAPI::AddEngineInfo(TSharedPtr<FJsonObject> JsonObject)
{
    if (!JsonObject.IsValid())
    {
        return;
    }

    TSharedPtr<FJsonObject> EngineInfo = MakeShareable(new FJsonObject);
    
    FEngineVersion Version = FEngineVersion::Current();
    EngineInfo->SetStringField(TEXT("version"), Version.ToString());
    EngineInfo->SetNumberField(TEXT("major_version"), Version.GetMajor());
    EngineInfo->SetNumberField(TEXT("minor_version"), Version.GetMinor());
    EngineInfo->SetNumberField(TEXT("patch_version"), Version.GetPatch());
    EngineInfo->SetStringField(TEXT("branch_name"), Version.GetBranch());
    EngineInfo->SetNumberField(TEXT("changelist"), Version.GetChangelist());
    EngineInfo->SetBoolField(TEXT("is_licensee_version"), Version.IsLicenseeVersion());

    // Engine directories
    EngineInfo->SetStringField(TEXT("engine_dir"), FPaths::EngineDir());
    EngineInfo->SetStringField(TEXT("engine_content_dir"), FPaths::EngineContentDir());
    EngineInfo->SetStringField(TEXT("engine_plugins_dir"), FPaths::EnginePluginsDir());

    JsonObject->SetObjectField(TEXT("engine"), EngineInfo);
}

// Helper functions
FString UProjectInfoAPI::JsonToString(const TSharedPtr<FJsonObject>& JsonObject)
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

FString UProjectInfoAPI::ClawMakeError(const FString& ErrorMessage)
{
    UE_LOG(LogUEClawBridgeAPI, Error, TEXT("ProjectInfoAPI Error: %s"), *ErrorMessage);
    
    TSharedPtr<FJsonObject> ErrorJson = MakeShareable(new FJsonObject);
    ErrorJson->SetBoolField(TEXT("success"), false);
    ErrorJson->SetStringField(TEXT("error"), ErrorMessage);
    return JsonToString(ErrorJson);
}