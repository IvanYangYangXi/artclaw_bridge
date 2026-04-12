// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "AssetRegistry/AssetData.h"
#include "UObject/ObjectSaveContext.h"
#include "UEAgentSubsystem.generated.h"

class UFactory;

// ------------------------------------------------------------------
// 日志分类声明 (阶段 0.4)
//
// 宪法约束:
//   - 开发路线图 §0.5: 定义 LogUEAgent 分类，带颜色区分的日志
//   - 系统架构设计 §2.3: C++ 负责生命周期 / UI / 主线程调度
// ------------------------------------------------------------------

/** 通用 Agent 日志 - 插件生命周期、状态变更 */
DECLARE_LOG_CATEGORY_EXTERN(LogUEAgent, Log, All);

/** MCP 通信日志 - 协议交互、连接管理 */
DECLARE_LOG_CATEGORY_EXTERN(LogUEAgent_MCP, Log, All);

/** 错误日志 - 异常、崩溃保护 */
DECLARE_LOG_CATEGORY_EXTERN(LogUEAgent_Error, Log, All);

// 动态多播委托：Blueprint/Python 绑定
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAgentConnectionStatusChanged, bool, bNewStatus);

// 原生多播委托：C++ Slate UI 绑定（性能更优，无需 UObject 上下文）
DECLARE_MULTICAST_DELEGATE_OneParam(FOnAgentConnectionStatusChangedNative, bool /*bNewStatus*/);

// ------------------------------------------------------------------
// DCC 事件委托 — 供 Python DCCEventManager 绑定
// ------------------------------------------------------------------

/** 资源保存前事件（Python 可通过返回值拦截，但 UE delegate 不支持返回值，用单独的阻止接口） */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAssetPreSaveEvent, const FString&, AssetPath);

/** 资源保存后事件 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnAssetPostSaveEvent, const FString&, AssetPath, bool, bSuccess);

/** 资源导入后事件 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnAssetImportEvent, const FString&, AssetPath, const FString&, AssetClass);

/** 资源删除前事件 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAssetDeleteEvent, const FString&, AssetPath);

/** 关卡保存前/后事件 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnLevelPreSaveEvent, const FString&, LevelPath);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnLevelPostSaveEvent, const FString&, LevelPath, bool, bSuccess);

/** 关卡加载后事件 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnLevelLoadEvent, const FString&, LevelPath);

/**
 * 编辑器活跃面板枚举
 * 追踪用户最后操作的是 Viewport 还是 Content Browser，
 * 供 AI 判断"选中的对象"指的是哪边。
 */
UENUM(BlueprintType)
enum class EUEAgentActivePanel : uint8
{
	Unknown        UMETA(DisplayName = "Unknown"),
	Viewport       UMETA(DisplayName = "Viewport"),
	ContentBrowser UMETA(DisplayName = "ContentBrowser"),
};

/**
 * UUEAgentSubsystem
 * 全局单例，负责协调 AI Agent 平台与 UE 编辑器的连接状态。
 * 
 * 宪法约束:
 *   - 统一管理中心，所有业务逻辑在 UE 插件侧统一管理 (概要设计 §1.1)
 *   - EditorSubsystem 生命周期管理 (系统架构设计 §2.3)
 */
UCLASS(BlueprintType)
class UECLAWBRIDGE_API UUEAgentSubsystem : public UEditorSubsystem
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

    /** 获取插件版本号 */
    UFUNCTION(BlueprintPure, Category = "UEAgent")
    FString GetPluginVersion() const;

    // --- MCP 网关接口 (阶段 1.1) ---

    /** 供 Python MCP 网关调用：设置当前监听端口 */
    UFUNCTION(BlueprintCallable, Category = "UEAgent|MCP")
    void SetServerPort(int32 InPort);

    /** 获取 MCP 服务器地址（ws://host:port） */
    UFUNCTION(BlueprintPure, Category = "UEAgent|MCP")
    FString GetServerAddress() const;

    /** 获取当前连接的客户端数量 */
    UFUNCTION(BlueprintPure, Category = "UEAgent|MCP")
    int32 GetClientCount() const { return ClientCount; }

    // --- 暴露属性 ---

    /** 连接状态真值 */
    UPROPERTY(BlueprintReadOnly, Category = "UEAgent")
    bool bIsConnected = false;

    /** MCP 服务器监听端口 (0 表示未启动) */
    UPROPERTY(BlueprintReadOnly, Category = "UEAgent|MCP")
    int32 ServerPort = 0;

    /** 连接的 MCP 客户端数量 */
    UPROPERTY(BlueprintReadOnly, Category = "UEAgent|MCP")
    int32 ClientCount = 0;

    /** 状态变更委托（Blueprint/Python）：UI 层将绑定此事件以实现图标变色 */
    UPROPERTY(BlueprintAssignable, Category = "UEAgent")
    FOnAgentConnectionStatusChanged OnConnectionStatusChanged;

    /** 状态变更委托（C++ Native）：Slate UI 绑定用 */
    FOnAgentConnectionStatusChangedNative OnConnectionStatusChangedNative;

    // --- DCC 事件委托 (Tool Manager 触发规则) ---

    /** 资源保存前 — Python: subsystem.on_asset_pre_save.add_callable(fn) */
    UPROPERTY(BlueprintAssignable, Category = "UEAgent|Events")
    FOnAssetPreSaveEvent OnAssetPreSave;

    /** 资源保存后 — Python: subsystem.on_asset_post_save.add_callable(fn) */
    UPROPERTY(BlueprintAssignable, Category = "UEAgent|Events")
    FOnAssetPostSaveEvent OnAssetPostSave;

    /** 资源导入后 */
    UPROPERTY(BlueprintAssignable, Category = "UEAgent|Events")
    FOnAssetImportEvent OnAssetImported;

    /** 资源删除前 */
    UPROPERTY(BlueprintAssignable, Category = "UEAgent|Events")
    FOnAssetDeleteEvent OnAssetPreDelete;

    /** 关卡保存前 */
    UPROPERTY(BlueprintAssignable, Category = "UEAgent|Events")
    FOnLevelPreSaveEvent OnLevelPreSave;

    /** 关卡保存后 */
    UPROPERTY(BlueprintAssignable, Category = "UEAgent|Events")
    FOnLevelPostSaveEvent OnLevelPostSave;

    /** 关卡/地图加载后 */
    UPROPERTY(BlueprintAssignable, Category = "UEAgent|Events")
    FOnLevelLoadEvent OnLevelLoaded;

    // --- 活跃面板追踪 (选区感知) ---

    /** 获取用户最后操作的编辑面板 (Viewport / ContentBrowser) */
    UFUNCTION(BlueprintPure, Category = "UEAgent")
    EUEAgentActivePanel GetActivePanel() const { return ActivePanel; }

    /** 获取活跃面板的字符串表示 (供 Python 读取) */
    UFUNCTION(BlueprintPure, Category = "UEAgent")
    FString GetActivePanelString() const;

private:
    /** 启动选区变化监听 */
    void SetupSelectionTracking();

    /** 清理选区变化监听 */
    void CleanupSelectionTracking();

    /** 启动 DCC 事件监听 */
    void SetupDCCEventTracking();

    /** 清理 DCC 事件监听 */
    void CleanupDCCEventTracking();

    /** Viewport 选区变化回调 */
    void OnViewportSelectionChanged(UObject* NewSelection);

    /** Content Browser 资产选区变化回调 */
    void OnContentBrowserSelectionChanged(const TArray<FAssetData>& NewSelectedAssets, bool bIsPrimaryBrowser);

    // --- DCC 事件回调（内部，由 UE delegate 触发） ---

    /** UPackage::PackageSavedWithContextEvent 回调 */
    void HandlePackageSaved(const FString& Filename, UPackage* Package, FObjectPostSaveContext Context);

    /** FCoreUObjectDelegates::OnObjectPreSave 回调 */
    void HandleObjectPreSave(UObject* Object, FObjectPreSaveContext Context);

    /** UImportSubsystem::OnAssetPostImport 回调 */
    void HandleAssetPostImport(UFactory* Factory, UObject* CreatedObject);

    /** FEditorDelegates::PreSaveWorldWithContext 回调 */
    void HandlePreSaveWorld(UWorld* World, FObjectPreSaveContext Context);

    /** FEditorDelegates::PostSaveWorldWithContext 回调 */
    void HandlePostSaveWorld(UWorld* World, FObjectPostSaveContext Context);

    /** 当前活跃面板 */
    EUEAgentActivePanel ActivePanel = EUEAgentActivePanel::Viewport;

    /** Content Browser 最近一次设置 ActivePanel 的时间戳 (防抖) */
    double LastContentBrowserSelectionTime = 0.0;

    /** 委托句柄 */
    FDelegateHandle ViewportSelectionHandle;
    FDelegateHandle ContentBrowserSelectionHandle;

    /** DCC 事件委托句柄 */
    FDelegateHandle PackageSavedHandle;
    FDelegateHandle ObjectPreSaveHandle;
    FDelegateHandle AssetPostImportHandle;
    FDelegateHandle PreSaveWorldHandle;
    FDelegateHandle PostSaveWorldHandle;
};