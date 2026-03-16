// Fill out your copyright notice in the Description page of Project Settings.

#include "UEAgentSubsystem.h"
#include "Interfaces/IPluginManager.h"

// ------------------------------------------------------------------
// 日志分类定义 (阶段 0.4)
//
// 宪法约束:
//   - 开发路线图 §0.5: 定义 LogUEAgent 分类
//   - 可在 Output Log 过滤器中单独查看 Agent 日志
// ------------------------------------------------------------------
DEFINE_LOG_CATEGORY(LogUEAgent);
DEFINE_LOG_CATEGORY(LogUEAgent_MCP);
DEFINE_LOG_CATEGORY(LogUEAgent_Error);

void UUEAgentSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    bIsConnected = false; // 初始化为断开状态
    UE_LOG(LogUEAgent, Log, TEXT("Subsystem Initialized (v%s)"), *GetPluginVersion());
}

void UUEAgentSubsystem::Deinitialize()
{
    UE_LOG(LogUEAgent, Log, TEXT("Subsystem Deinitializing."));
    Super::Deinitialize();
}

void UUEAgentSubsystem::SetConnectionStatus(bool bInIsConnected)
{
    if (bIsConnected != bInIsConnected)
    {
        bIsConnected = bInIsConnected;

        // 广播状态变更通知 —— 同时触发动态 (Blueprint/Python) 和原生 (C++ Slate) 委托
        OnConnectionStatusChanged.Broadcast(bIsConnected);
        OnConnectionStatusChangedNative.Broadcast(bIsConnected);

        UE_LOG(LogUEAgent, Log, TEXT("Connection Status Updated -> %s"),
            bIsConnected ? TEXT("CONNECTED") : TEXT("DISCONNECTED"));
    }
}

FString UUEAgentSubsystem::GetPluginVersion() const
{
    TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("UEEditorAgent"));
    if (Plugin.IsValid())
    {
        return Plugin->GetDescriptor().VersionName;
    }
    return TEXT("Unknown");
}

// ------------------------------------------------------------------
// MCP 网关接口 (阶段 1.1)
// ------------------------------------------------------------------

void UUEAgentSubsystem::SetServerPort(int32 InPort)
{
    ServerPort = InPort;
    UE_LOG(LogUEAgent_MCP, Log, TEXT("MCP Server port set to %d"), InPort);
}

FString UUEAgentSubsystem::GetServerAddress() const
{
    if (ServerPort > 0)
    {
        return FString::Printf(TEXT("ws://localhost:%d"), ServerPort);
    }
    return TEXT("");
}
