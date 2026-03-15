// Fill out your copyright notice in the Description page of Project Settings.

#include "UEAgentSubsystem.h"
#include "Interfaces/IPluginManager.h"

void UUEAgentSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    bIsConnected = false; // 初始化为断开状态
    UE_LOG(LogTemp, Log, TEXT("UEAgent: Subsystem Initialized."));
}

void UUEAgentSubsystem::Deinitialize()
{
    UE_LOG(LogTemp, Log, TEXT("UEAgent: Subsystem Deinitializing."));
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

        UE_LOG(LogTemp, Warning, TEXT("UEAgent: Connection Status Updated -> %s"),
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