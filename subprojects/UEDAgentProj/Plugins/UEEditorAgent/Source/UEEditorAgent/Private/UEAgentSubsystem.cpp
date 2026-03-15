// Fill out your copyright notice in the Description page of Project Settings.


#include "UEAgentSubsystem.h"
#include "Engine/Engine.h"

void UUEAgentSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    bIsConnected = false; // 初始化为断开状态
    ServerPort = 0;
    UE_LOG(LogTemp, Log, TEXT("UEAgent: Subsystem Initialized."));
}

void UUEAgentSubsystem::Deinitialize()
{
    UE_LOG(LogTemp, Log, TEXT("UEAgent: Subsystem Deinitializing."));
    
    // 停止MCP服务器
    // 这里通过Python调用停止服务器
    
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

void UUEAgentSubsystem::SetServerPort(int32 Port)
{
    if (ServerPort != Port)
    {
        ServerPort = Port;
        
        // 广播端口变更
        OnServerPortChanged.Broadcast(Port);
        
        UE_LOG(LogTemp, Log, TEXT("UEAgent: Server Port Set -> %d"), Port);
    }
}

FString UUEAgentSubsystem::GetServerAddress() const
{
    if (ServerPort > 0)
    {
        return FString::Printf(TEXT("ws://localhost:%d"), ServerPort);
    }
    return TEXT("Not Started");
}