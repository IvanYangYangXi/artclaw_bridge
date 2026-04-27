// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "PerformanceAPI.h"
#include "UEClawBridgeAPI.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "ProfilingDebugging/TraceAuxiliary.h"
#include "Misc/Paths.h"
#include "Misc/DateTime.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#include "Engine/Engine.h"

FString UPerformanceAPI::InsightsCapture(const FString& Action, const FString& Channels)
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("InsightsCapture called with Action='%s', Channels='%s'"), *Action, *Channels);

    if (Action.Equals(TEXT("start"), ESearchCase::IgnoreCase))
    {
        return StartCapture(Channels);
    }
    else if (Action.Equals(TEXT("stop"), ESearchCase::IgnoreCase))
    {
        return StopCapture();
    }
    else if (Action.Equals(TEXT("status"), ESearchCase::IgnoreCase))
    {
        return GetCaptureStatus();
    }
    else
    {
        return ClawMakeError(FString::Printf(TEXT("Invalid action: '%s'. Use 'start', 'stop', or 'status'"), *Action));
    }
}

FString UPerformanceAPI::StartCapture(const FString& Channels)
{
    // Check if already running
    if (FTraceAuxiliary::IsConnected())
    {
        return ClawMakeError(TEXT("Trace capture is already running. Stop current trace before starting a new one."));
    }

    // Parse channels
    TArray<FString> ChannelArray;
    Channels.ParseIntoArray(ChannelArray, TEXT(","), true);

    // If no channels specified, use defaults
    if (ChannelArray.Num() == 0)
    {
        ChannelArray = {TEXT("cpu"), TEXT("gpu"), TEXT("frame")};
    }

    // Clean channel names
    for (FString& Channel : ChannelArray)
    {
        Channel = Channel.TrimStartAndEnd();
    }

    // Generate filename with timestamp
    FString Timestamp = FDateTime::Now().ToString(TEXT("%Y%m%d_%H%M%S"));
    FString OutputFile = FString::Printf(TEXT("ArtClawTrace_%s.utrace"), *Timestamp);

    // Build trace file path
    FString TraceDir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Profiling"));
    FString TraceFilePath = FPaths::Combine(TraceDir, OutputFile);

    // Ensure directory exists
    IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
    if (!PlatformFile.DirectoryExists(*TraceDir))
    {
        if (!PlatformFile.CreateDirectoryTree(*TraceDir))
        {
            return ClawMakeError(FString::Printf(TEXT("Failed to create profiling directory: %s"), *TraceDir));
        }
    }

    // Build channel string
    FString ChannelString = FString::Join(ChannelArray, TEXT(","));

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Starting Insights trace with channels: %s"), *ChannelString);
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Output file: %s"), *TraceFilePath);

    // Start trace using command-line interface
    FString StartCommand = FString::Printf(TEXT("Trace.Start %s file=%s"), *ChannelString, *TraceFilePath);

    // Execute trace start via console command
    bool bCommandSucceeded = false;
    if (GEngine)
    {
        bCommandSucceeded = GEngine->Exec(nullptr, *StartCommand);
    }

    if (bCommandSucceeded)
    {
        TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
        Result->SetBoolField(TEXT("success"), true);
        Result->SetStringField(TEXT("status"), TEXT("started"));
        Result->SetStringField(TEXT("trace_file"), TraceFilePath);
        Result->SetStringField(TEXT("channels"), ChannelString);
        Result->SetStringField(TEXT("message"), TEXT("Insights trace capture started successfully"));

        TArray<TSharedPtr<FJsonValue>> ChannelsJson;
        for (const FString& Channel : ChannelArray)
        {
            ChannelsJson.Add(MakeShareable(new FJsonValueString(Channel)));
        }
        Result->SetArrayField(TEXT("channel_list"), ChannelsJson);

        return JsonToString(Result);
    }
    else
    {
        return ClawMakeError(TEXT("Failed to start trace capture. Ensure Trace system is available and channels are valid."));
    }
}

FString UPerformanceAPI::StopCapture()
{
    if (!FTraceAuxiliary::IsConnected())
    {
        return ClawMakeError(TEXT("No active trace capture to stop"));
    }

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Stopping Insights trace capture"));

    // Stop trace
    bool bCommandSucceeded = false;
    if (GEngine)
    {
        bCommandSucceeded = GEngine->Exec(nullptr, TEXT("Trace.Stop"));
    }

    if (bCommandSucceeded)
    {
        TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
        Result->SetBoolField(TEXT("success"), true);
        Result->SetStringField(TEXT("status"), TEXT("stopped"));
        Result->SetStringField(TEXT("message"), TEXT("Trace capture stopped successfully"));

        return JsonToString(Result);
    }
    else
    {
        return ClawMakeError(TEXT("Failed to stop trace capture"));
    }
}

FString UPerformanceAPI::GetCaptureStatus()
{
    bool bIsCapturing = FTraceAuxiliary::IsConnected();

    TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
    Result->SetBoolField(TEXT("success"), true);
    Result->SetBoolField(TEXT("is_capturing"), bIsCapturing);
    Result->SetStringField(TEXT("status"), bIsCapturing ? TEXT("active") : TEXT("idle"));
    
    if (bIsCapturing)
    {
        Result->SetStringField(TEXT("message"), TEXT("Trace capture is currently active"));
    }
    else
    {
        Result->SetStringField(TEXT("message"), TEXT("No active trace capture"));
    }

    return JsonToString(Result);
}

FString UPerformanceAPI::InsightsListTraces()
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("InsightsListTraces called"));

    // Get profiling directory
    FString TraceDir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Profiling"));
    FPaths::NormalizeDirectoryName(TraceDir);

    // Check if directory exists
    IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
    if (!PlatformFile.DirectoryExists(*TraceDir))
    {
        TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
        Result->SetBoolField(TEXT("success"), true);
        Result->SetStringField(TEXT("directory"), TraceDir);
        Result->SetNumberField(TEXT("count"), 0);
        Result->SetArrayField(TEXT("traces"), TArray<TSharedPtr<FJsonValue>>());
        Result->SetStringField(TEXT("message"), TEXT("Profiling directory does not exist"));

        return JsonToString(Result);
    }

    // Find all .utrace files
    TArray<FString> TraceFiles;
    IFileManager& FileManager = IFileManager::Get();
    FString SearchPattern = FPaths::Combine(TraceDir, TEXT("*.utrace"));
    FileManager.FindFiles(TraceFiles, *SearchPattern, true, false);

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Found %d trace files in %s"), TraceFiles.Num(), *TraceDir);

    // Build result array
    TArray<TSharedPtr<FJsonValue>> TracesArray;
    for (const FString& FileName : TraceFiles)
    {
        FString FullPath = FPaths::Combine(TraceDir, FileName);

        // Get file info
        FFileStatData StatData = FileManager.GetStatData(*FullPath);

        TSharedPtr<FJsonObject> TraceObj = MakeShareable(new FJsonObject);
        TraceObj->SetStringField(TEXT("file_path"), FullPath);
        TraceObj->SetStringField(TEXT("file_name"), FileName);
        TraceObj->SetNumberField(TEXT("size_bytes"), StatData.FileSize);
        TraceObj->SetNumberField(TEXT("size_mb"), static_cast<double>(StatData.FileSize) / (1024.0 * 1024.0));
        TraceObj->SetStringField(TEXT("created"), StatData.CreationTime.ToString(TEXT("%Y-%m-%d %H:%M:%S")));
        TraceObj->SetStringField(TEXT("modified"), StatData.ModificationTime.ToString(TEXT("%Y-%m-%d %H:%M:%S")));

        TracesArray.Add(MakeShareable(new FJsonValueObject(TraceObj)));
    }

    TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
    Result->SetBoolField(TEXT("success"), true);
    Result->SetStringField(TEXT("directory"), TraceDir);
    Result->SetNumberField(TEXT("count"), TraceFiles.Num());
    Result->SetArrayField(TEXT("traces"), TracesArray);

    return JsonToString(Result);
}

FString UPerformanceAPI::InsightsAnalyze(const FString& TraceFile, const FString& AnalysisType)
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("InsightsAnalyze called with TraceFile='%s', AnalysisType='%s'"), *TraceFile, *AnalysisType);

    // Handle "latest" special case
    FString ActualTraceFile = TraceFile;
    if (TraceFile.Equals(TEXT("latest"), ESearchCase::IgnoreCase))
    {
        // Find the most recent trace file
        FString TraceDir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Profiling"));
        TArray<FString> TraceFiles;
        IFileManager& FileManager = IFileManager::Get();
        FString SearchPattern = FPaths::Combine(TraceDir, TEXT("*.utrace"));
        FileManager.FindFiles(TraceFiles, *SearchPattern, true, false);

        if (TraceFiles.Num() == 0)
        {
            return ClawMakeError(TEXT("No trace files found in Saved/Profiling directory"));
        }

        // Find the most recent file by modification time
        FString MostRecentFile;
        FDateTime MostRecentTime = FDateTime::MinValue();
        
        for (const FString& FileName : TraceFiles)
        {
            FString FullPath = FPaths::Combine(TraceDir, FileName);
            FFileStatData StatData = FileManager.GetStatData(*FullPath);
            
            if (StatData.ModificationTime > MostRecentTime)
            {
                MostRecentTime = StatData.ModificationTime;
                MostRecentFile = FullPath;
            }
        }
        
        ActualTraceFile = MostRecentFile;
    }

    // Check if file exists
    if (!FPaths::FileExists(ActualTraceFile))
    {
        return ClawMakeError(FString::Printf(TEXT("Trace file not found: %s"), *ActualTraceFile));
    }

    // Currently only support basic_info analysis
    if (!AnalysisType.Equals(TEXT("basic_info"), ESearchCase::IgnoreCase) && 
        !AnalysisType.Equals(TEXT("cpu"), ESearchCase::IgnoreCase))
    {
        return ClawMakeError(FString::Printf(
            TEXT("Analysis type '%s' not implemented. Currently only 'basic_info' is supported. "
                 "Full trace analysis requires TraceAnalysis module integration. Use Unreal Insights standalone application for detailed analysis."),
            *AnalysisType));
    }

    return AnalyzeBasicInfo(ActualTraceFile);
}

FString UPerformanceAPI::AnalyzeBasicInfo(const FString& TraceFile)
{
    IFileManager& FileManager = IFileManager::Get();
    FFileStatData StatData = FileManager.GetStatData(*TraceFile);

    TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
    Result->SetBoolField(TEXT("success"), true);
    Result->SetStringField(TEXT("trace_file"), TraceFile);
    Result->SetStringField(TEXT("file_name"), FPaths::GetCleanFilename(TraceFile));
    Result->SetNumberField(TEXT("size_bytes"), StatData.FileSize);
    Result->SetNumberField(TEXT("size_mb"), static_cast<double>(StatData.FileSize) / (1024.0 * 1024.0));
    Result->SetStringField(TEXT("created"), StatData.CreationTime.ToString(TEXT("%Y-%m-%d %H:%M:%S")));
    Result->SetStringField(TEXT("modified"), StatData.ModificationTime.ToString(TEXT("%Y-%m-%d %H:%M:%S")));
    Result->SetStringField(TEXT("analysis_type"), TEXT("basic_info"));
    Result->SetStringField(TEXT("message"), TEXT("Basic file metadata analysis completed"));
    Result->SetStringField(TEXT("note"), TEXT("Full trace analysis (frame stats, CPU profiling, memory analysis) requires TraceAnalysis module integration. Use Unreal Insights standalone application for detailed performance analysis."));

    return JsonToString(Result);
}

// Helper functions
FString UPerformanceAPI::JsonToString(const TSharedPtr<FJsonObject>& JsonObject)
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

FString UPerformanceAPI::ClawMakeError(const FString& ErrorMessage)
{
    UE_LOG(LogUEClawBridgeAPI, Error, TEXT("PerformanceAPI Error: %s"), *ErrorMessage);
    
    TSharedPtr<FJsonObject> ErrorJson = MakeShareable(new FJsonObject);
    ErrorJson->SetBoolField(TEXT("success"), false);
    ErrorJson->SetStringField(TEXT("error"), ErrorMessage);
    return JsonToString(ErrorJson);
}