// Fill out your copyright notice in the Description page of Project Settings.

#include "UEAgentSubsystem.h"
#include "Interfaces/IPluginManager.h"
#include "Selection.h"
#include "ContentBrowserModule.h"
#include "GameFramework/Actor.h"
#include "UObject/SavePackage.h"
#include "UObject/ObjectSaveContext.h"
#include "Editor.h"
#include "Subsystems/ImportSubsystem.h"

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

    SetupSelectionTracking();
    SetupDCCEventTracking();

    UE_LOG(LogUEAgent, Log, TEXT("Subsystem Initialized (v%s)"), *GetPluginVersion());
}

void UUEAgentSubsystem::Deinitialize()
{
    CleanupDCCEventTracking();
    CleanupSelectionTracking();

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
    TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("UEClawBridge"));
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

// ------------------------------------------------------------------
// 活跃面板追踪 (选区感知)
// ------------------------------------------------------------------

FString UUEAgentSubsystem::GetActivePanelString() const
{
    switch (ActivePanel)
    {
    case EUEAgentActivePanel::Viewport:       return TEXT("viewport");
    case EUEAgentActivePanel::ContentBrowser: return TEXT("content_browser");
    default:                                  return TEXT("unknown");
    }
}

void UUEAgentSubsystem::SetupSelectionTracking()
{
    // 1. 监听 Viewport 选区变化 (USelection::SelectionChangedEvent)
    ViewportSelectionHandle = USelection::SelectionChangedEvent.AddUObject(
        this, &UUEAgentSubsystem::OnViewportSelectionChanged);

    // 2. 监听 Content Browser 资产选区变化
    FContentBrowserModule& CBModule = FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser"));
    ContentBrowserSelectionHandle = CBModule.GetOnAssetSelectionChanged().AddUObject(
        this, &UUEAgentSubsystem::OnContentBrowserSelectionChanged);

    UE_LOG(LogUEAgent, Log, TEXT("Selection tracking initialized (Viewport + ContentBrowser)"));
}

void UUEAgentSubsystem::CleanupSelectionTracking()
{
    if (ViewportSelectionHandle.IsValid())
    {
        USelection::SelectionChangedEvent.Remove(ViewportSelectionHandle);
        ViewportSelectionHandle.Reset();
    }

    if (ContentBrowserSelectionHandle.IsValid())
    {
        if (FModuleManager::Get().IsModuleLoaded(TEXT("ContentBrowser")))
        {
            FContentBrowserModule& CBModule = FModuleManager::GetModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser"));
            CBModule.GetOnAssetSelectionChanged().Remove(ContentBrowserSelectionHandle);
        }
        ContentBrowserSelectionHandle.Reset();
    }
}

void UUEAgentSubsystem::OnViewportSelectionChanged(UObject* NewSelection)
{
    // USelection::SelectionChangedEvent 是全局事件，
    // Content Browser 选资产时也会触发（UE 内部的 UObject selection 变化）。
    // 用时间窗口防抖：如果 CB 刚刚设置了 ActivePanel，忽略紧随其后的 Viewport 事件。
    const double Now = FPlatformTime::Seconds();
    constexpr double DebounceWindow = 0.1; // 100ms 防抖

    if (ActivePanel == EUEAgentActivePanel::ContentBrowser
        && (Now - LastContentBrowserSelectionTime) < DebounceWindow)
    {
        // Content Browser 刚触发过，忽略这次连带的 SelectionChangedEvent
        return;
    }

    // 额外检查：只有当 NewSelection 是 Actor selection set 时才标记 Viewport
    // USelection::SelectionChangedEvent 传入的 UObject* 就是 USelection 本身
    USelection* Selection = Cast<USelection>(NewSelection);
    if (Selection)
    {
        // 检查这个 selection set 是否包含 Actor（而非 UObject/资产）
        bool bHasActor = false;
        for (int32 i = 0; i < Selection->Num(); ++i)
        {
            if (Selection->GetSelectedObject(i) && Selection->GetSelectedObject(i)->IsA<AActor>())
            {
                bHasActor = true;
                break;
            }
        }

        if (!bHasActor)
        {
            return; // 不是 Actor 选择变化，不更新面板
        }
    }

    ActivePanel = EUEAgentActivePanel::Viewport;
}

void UUEAgentSubsystem::OnContentBrowserSelectionChanged(const TArray<FAssetData>& NewSelectedAssets, bool bIsPrimaryBrowser)
{
    if (NewSelectedAssets.Num() > 0)
    {
        ActivePanel = EUEAgentActivePanel::ContentBrowser;
        LastContentBrowserSelectionTime = FPlatformTime::Seconds();
    }
}

// ------------------------------------------------------------------
// DCC 事件追踪 — 供 Tool Manager 触发规则使用
//
// 将 UE 编辑器原生 delegate 转发为 Python 可绑定的动态委托。
// Python 侧通过 subsystem.on_asset_pre_save.add_callable(fn) 绑定。
// ------------------------------------------------------------------

void UUEAgentSubsystem::SetupDCCEventTracking()
{
    // 1. 资源保存后 — UPackage::PackageSavedWithContextEvent
    PackageSavedHandle = UPackage::PackageSavedWithContextEvent.AddUObject(
        this, &UUEAgentSubsystem::HandlePackageSaved);

    // 2. 对象保存前 — FCoreUObjectDelegates::OnObjectPreSave
    ObjectPreSaveHandle = FCoreUObjectDelegates::OnObjectPreSave.AddUObject(
        this, &UUEAgentSubsystem::HandleObjectPreSave);

    // 3. 资源导入后 — UImportSubsystem::OnAssetPostImport
    if (GEditor)
    {
        UImportSubsystem* ImportSubsystem = GEditor->GetEditorSubsystem<UImportSubsystem>();
        if (ImportSubsystem)
        {
            AssetPostImportHandle = ImportSubsystem->OnAssetPostImport.AddUObject(
                this, &UUEAgentSubsystem::HandleAssetPostImport);
        }
    }

    // 4. 关卡保存前 — FEditorDelegates::PreSaveWorldWithContext
    PreSaveWorldHandle = FEditorDelegates::PreSaveWorldWithContext.AddUObject(
        this, &UUEAgentSubsystem::HandlePreSaveWorld);

    // 5. 关卡保存后 — FEditorDelegates::PostSaveWorldWithContext
    PostSaveWorldHandle = FEditorDelegates::PostSaveWorldWithContext.AddUObject(
        this, &UUEAgentSubsystem::HandlePostSaveWorld);

    UE_LOG(LogUEAgent, Log, TEXT("DCC event tracking initialized (asset save/import, level save/load)"));
}

void UUEAgentSubsystem::CleanupDCCEventTracking()
{
    if (PackageSavedHandle.IsValid())
    {
        UPackage::PackageSavedWithContextEvent.Remove(PackageSavedHandle);
        PackageSavedHandle.Reset();
    }

    if (ObjectPreSaveHandle.IsValid())
    {
        FCoreUObjectDelegates::OnObjectPreSave.Remove(ObjectPreSaveHandle);
        ObjectPreSaveHandle.Reset();
    }

    if (AssetPostImportHandle.IsValid())
    {
        if (GEditor)
        {
            UImportSubsystem* ImportSubsystem = GEditor->GetEditorSubsystem<UImportSubsystem>();
            if (ImportSubsystem)
            {
                ImportSubsystem->OnAssetPostImport.Remove(AssetPostImportHandle);
            }
        }
        AssetPostImportHandle.Reset();
    }

    if (PreSaveWorldHandle.IsValid())
    {
        FEditorDelegates::PreSaveWorldWithContext.Remove(PreSaveWorldHandle);
        PreSaveWorldHandle.Reset();
    }

    if (PostSaveWorldHandle.IsValid())
    {
        FEditorDelegates::PostSaveWorldWithContext.Remove(PostSaveWorldHandle);
        PostSaveWorldHandle.Reset();
    }

    UE_LOG(LogUEAgent, Log, TEXT("DCC event tracking cleaned up"));
}

// --- 事件回调实现 ---

void UUEAgentSubsystem::HandlePackageSaved(const FString& Filename, UPackage* Package, FObjectPostSaveContext Context)
{
    if (!Package) return;

    const FString PackagePath = Package->GetPathName();

    // 过滤掉引擎/临时包，只转发用户资源
    if (PackagePath.StartsWith(TEXT("/Engine/")) || PackagePath.StartsWith(TEXT("/Temp/")))
    {
        return;
    }

    UE_LOG(LogUEAgent, Verbose, TEXT("Asset post-save: %s"), *PackagePath);
    OnAssetPostSave.Broadcast(PackagePath, true);
}

void UUEAgentSubsystem::HandleObjectPreSave(UObject* Object, FObjectPreSaveContext Context)
{
    if (!Object) return;

    UPackage* Package = Object->GetOutermost();
    if (!Package) return;

    const FString PackagePath = Package->GetPathName();

    // 过滤引擎包
    if (PackagePath.StartsWith(TEXT("/Engine/")) || PackagePath.StartsWith(TEXT("/Temp/")))
    {
        return;
    }

    UE_LOG(LogUEAgent, Verbose, TEXT("Asset pre-save: %s"), *PackagePath);
    OnAssetPreSave.Broadcast(PackagePath);
}

void UUEAgentSubsystem::HandleAssetPostImport(UFactory* Factory, UObject* CreatedObject)
{
    if (!CreatedObject) return;

    const FString AssetPath = CreatedObject->GetPathName();
    const FString AssetClass = CreatedObject->GetClass() ? CreatedObject->GetClass()->GetName() : TEXT("Unknown");

    UE_LOG(LogUEAgent, Log, TEXT("Asset imported: %s (%s)"), *AssetPath, *AssetClass);
    OnAssetImported.Broadcast(AssetPath, AssetClass);
}

void UUEAgentSubsystem::HandlePreSaveWorld(UWorld* World, FObjectPreSaveContext Context)
{
    if (!World) return;

    const FString LevelPath = World->GetPathName();
    UE_LOG(LogUEAgent, Log, TEXT("Level pre-save: %s"), *LevelPath);
    OnLevelPreSave.Broadcast(LevelPath);
}

void UUEAgentSubsystem::HandlePostSaveWorld(UWorld* World, FObjectPostSaveContext Context)
{
    if (!World) return;

    const FString LevelPath = World->GetPathName();
    UE_LOG(LogUEAgent, Log, TEXT("Level post-save: %s"), *LevelPath);
    OnLevelPostSave.Broadcast(LevelPath, true);
}
