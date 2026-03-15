// Fill out your copyright notice in the Description page of Project Settings.


#include "UEAgentSubsystem.h"

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

        // 广播状态变更通知，驱动图标变色
        OnConnectionStatusChanged.Broadcast(bIsConnected);

        UE_LOG(LogTemp, Warning, TEXT("UEAgent: Connection Status Updated -> %s"),
            bIsConnected ? TEXT("CONNECTED") : TEXT("DISCONNECTED"));
    }
}