// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "UEAgentSubsystem.generated.h"

// 声明动态多播委托
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAgentConnectionStatusChanged, bool, bIsConnected);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnServerPortChanged, int32, Port);

/**
 * UUEAgentSubsystem
 * 全局单例，负责协调 OpenClaw 与 UE 编辑器的连接状态
 */
UCLASS(BlueprintType)
class UEEDITORAGENT_API UUEAgentSubsystem : public UEditorSubsystem
{
	GENERATED_BODY()

public:
    // --- 框架钩子 ---
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // --- 核心接口 ---

    /** 供 Python 网关调用：更新连接状态 */
    UFUNCTION(BlueprintCallable, Category = "UEAgent")
    void SetConnectionStatus(bool bInIsConnected);

    /** 供 UI 绑定使用：查询当前是否在线 */
    UFUNCTION(BlueprintPure, Category = "UEAgent")
    bool GetConnectionStatus() const { return bIsConnected; }
    
    /** 设置服务器端口 */
    UFUNCTION(BlueprintCallable, Category = "UEAgent")
    void SetServerPort(int32 Port);
    
    /** 获取服务器端口 */
    UFUNCTION(BlueprintPure, Category = "UEAgent")
    int32 GetServerPort() const { return ServerPort; }
    
    /** 获取WebSocket服务器地址 */
    UFUNCTION(BlueprintPure, Category = "UEAgent")
    FString GetServerAddress() const;

    // --- 暴露属性 ---

    /** 连接状态真值 */
    UPROPERTY(BlueprintReadOnly, Category = "UEAgent")
    bool bIsConnected = false;
    
    /** 服务器端口 */
    UPROPERTY(BlueprintReadOnly, Category = "UEAgent")
    int32 ServerPort = 0;

    /** 状态变更委托：UI 层将绑定此事件以实现图标变色 */
    UPROPERTY(BlueprintAssignable, Category = "UEAgent")
    FOnAgentConnectionStatusChanged OnConnectionStatusChanged;
    
    /** 服务器端口变更委托 */
    UPROPERTY(BlueprintAssignable, Category = "UEAgent")
    FOnServerPortChanged OnServerPortChanged;
};
