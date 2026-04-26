// Fill out your copyright notice in the Description page of Project Settings.

#include "UEAgentSubsystem.h"
#include "Interfaces/IPluginManager.h"
#include "Selection.h"
#include "ContentBrowserModule.h"
#include "GameFramework/Actor.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "UObject/SavePackage.h"
#include "UObject/ObjectSaveContext.h"
#include "Editor.h"
#include "Subsystems/ImportSubsystem.h"
#include "Framework/Notifications/NotificationManager.h"
#include "Widgets/Notifications/SNotificationList.h"
#include "Misc/MessageDialog.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "IPythonScriptPlugin.h"
#include "UEAgentManageUtils.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Misc/FileHelper.h"
#include "HAL/FileManager.h"

// ------------------------------------------------------------------
// 鏃ュ織鍒嗙被瀹氫箟 (闃舵 0.4)
//
// 瀹硶绾︽潫:
//   - 寮€鍙戣矾绾垮浘 搂0.5: 瀹氫箟 LogUEAgent 鍒嗙被
//   - 鍙湪 Output Log 杩囨护鍣ㄤ腑鍗曠嫭鏌ョ湅 Agent 鏃ュ織
// ------------------------------------------------------------------
DEFINE_LOG_CATEGORY(LogUEAgent);
DEFINE_LOG_CATEGORY(LogUEAgent_MCP);
DEFINE_LOG_CATEGORY(LogUEAgent_Error);

void UUEAgentSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    bIsConnected = false; // 鍒濆鍖栦负鏂紑鐘舵€?

    SetupSelectionTracking();
    SetupDCCEventTracking();

    // 鑷姩妫€娴嬪苟鎷夎捣 Tool Manager
    AutoLaunchToolManager();

    // 璇诲彇淇濆瓨鎷︽埅閰嶇疆
    LoadSaveInterceptConfig();

    UE_LOG(LogUEAgent, Log, TEXT("Subsystem Initialized (v%s)"), *GetPluginVersion());
    
    // 骞挎挱缂栬緫鍣ㄥ惎鍔ㄥ畬鎴愪簨浠?
    OnEditorStartup.Broadcast();
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

        // 骞挎挱鐘舵€佸彉鏇撮€氱煡 鈥斺€?鍚屾椂瑙﹀彂鍔ㄦ€?(Blueprint/Python) 鍜屽師鐢?(C++ Slate) 濮旀墭
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
// MCP 缃戝叧鎺ュ彛 (闃舵 1.1)
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
// 娲昏穬闈㈡澘杩借釜 (閫夊尯鎰熺煡)
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
    // 1. 鐩戝惉 Viewport 閫夊尯鍙樺寲 (USelection::SelectionChangedEvent)
    ViewportSelectionHandle = USelection::SelectionChangedEvent.AddUObject(
        this, &UUEAgentSubsystem::OnViewportSelectionChanged);

    // 2. 鐩戝惉 Content Browser 璧勪骇閫夊尯鍙樺寲
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
    // USelection::SelectionChangedEvent 鏄叏灞€浜嬩欢锛?
    // Content Browser 閫夎祫浜ф椂涔熶細瑙﹀彂锛圲E 鍐呴儴鐨?UObject selection 鍙樺寲锛夈€?
    // 鐢ㄦ椂闂寸獥鍙ｉ槻鎶栵細濡傛灉 CB 鍒氬垰璁剧疆浜?ActivePanel锛屽拷鐣ョ揣闅忓叾鍚庣殑 Viewport 浜嬩欢銆?
    const double Now = FPlatformTime::Seconds();
    constexpr double DebounceWindow = 0.1; // 100ms 闃叉姈

    if (ActivePanel == EUEAgentActivePanel::ContentBrowser
        && (Now - LastContentBrowserSelectionTime) < DebounceWindow)
    {
        // Content Browser 鍒氳Е鍙戣繃锛屽拷鐣ヨ繖娆¤繛甯︾殑 SelectionChangedEvent
        return;
    }

    // 棰濆妫€鏌ワ細鍙湁褰?NewSelection 鏄?Actor selection set 鏃舵墠鏍囪 Viewport
    // USelection::SelectionChangedEvent 浼犲叆鐨?UObject* 灏辨槸 USelection 鏈韩
    USelection* Selection = Cast<USelection>(NewSelection);
    if (Selection)
    {
        // 妫€鏌ヨ繖涓?selection set 鏄惁鍖呭惈 Actor锛堣€岄潪 UObject/璧勪骇锛?
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
            return; // 涓嶆槸 Actor 閫夋嫨鍙樺寲锛屼笉鏇存柊闈㈡澘
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
// DCC 浜嬩欢杩借釜 鈥?渚?Tool Manager 瑙﹀彂瑙勫垯浣跨敤
//
// 灏?UE 缂栬緫鍣ㄥ師鐢?delegate 杞彂涓?Python 鍙粦瀹氱殑鍔ㄦ€佸鎵樸€?
// Python 渚ч€氳繃 subsystem.on_asset_pre_save.add_callable(fn) 缁戝畾銆?
// ------------------------------------------------------------------

void UUEAgentSubsystem::SetupDCCEventTracking()
{
    // 1. 璧勬簮淇濆瓨鍚?鈥?UPackage::PackageSavedWithContextEvent
    PackageSavedHandle = UPackage::PackageSavedWithContextEvent.AddUObject(
        this, &UUEAgentSubsystem::HandlePackageSaved);

    // 2. 瀵硅薄淇濆瓨鍓?鈥?FCoreUObjectDelegates::OnObjectPreSave
    ObjectPreSaveHandle = FCoreUObjectDelegates::OnObjectPreSave.AddUObject(
        this, &UUEAgentSubsystem::HandleObjectPreSave);

    // 3. 璧勬簮瀵煎叆鍚?鈥?UImportSubsystem::OnAssetPostImport
    if (GEditor)
    {
        UImportSubsystem* ImportSubsystem = GEditor->GetEditorSubsystem<UImportSubsystem>();
        if (ImportSubsystem)
        {
            AssetPostImportHandle = ImportSubsystem->OnAssetPostImport.AddUObject(
                this, &UUEAgentSubsystem::HandleAssetPostImport);
        }
    }

    // TODO: 3.5. 璧勬簮瀵煎叆鍓?鈥?UE 5.7 娌℃湁鍐呯疆鐨?pre-import delegate
    // 闇€瑕侀€氳繃 ImportSubsystem 鐨勮嚜瀹氫箟閽╁瓙鎴栧叾浠栨柟娉曞疄鐜?
    // 鏆傛椂鍦ㄥご鏂囦欢涓０鏄?OnAssetPreImport锛屼絾涓嶇粦瀹氬埌浠讳綍鍘熺敓浜嬩欢

    // 4. 璧勬簮鍒犻櫎鍓?鈥?FEditorDelegates::OnAssetsPreDelete
    AssetsPreDeleteHandle = FEditorDelegates::OnAssetsPreDelete.AddUObject(
        this, &UUEAgentSubsystem::HandleAssetsPreDelete);

    // 5. 璧勬簮鍒犻櫎鍚?鈥?FAssetRegistryModule::AssetRemovedEvent
    FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
    AssetRemovedHandle = AssetRegistryModule.Get().OnAssetRemoved().AddUObject(
        this, &UUEAgentSubsystem::HandleAssetRemoved);

    // 6. 鍏冲崱淇濆瓨鍓?鈥?FEditorDelegates::PreSaveWorldWithContext
    PreSaveWorldHandle = FEditorDelegates::PreSaveWorldWithContext.AddUObject(
        this, &UUEAgentSubsystem::HandlePreSaveWorld);

    // 7. 关卡保存后 — FEditorDelegates::PostSaveWorldWithContext
    PostSaveWorldHandle = FEditorDelegates::PostSaveWorldWithContext.AddUObject(
        this, &UUEAgentSubsystem::HandlePostSaveWorld);

    // 8. 资源放置到场景后 — 用 PostEditChangeProperty / MapChange 不可靠
    //    改用 OnNewActorsDropped: 在用户松开鼠标确认放置后触发（UE5.4+）
    //    注意：OnNewActorsPlaced 在预览阶段就触发，不用它
    ActorsPlacedHandle = FEditorDelegates::OnNewActorsDropped.AddUObject(
        this, &UUEAgentSubsystem::HandleActorsDropped);

    UE_LOG(LogUEAgent, Log, TEXT("DCC event tracking initialized (asset save/import/delete/place, level save/load)"));

    // 8. 淇濆瓨鎷︽埅 鈥?IsPackageOKToSaveDelegate
    HookIsPackageOKToSave();
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

    if (AssetsPreDeleteHandle.IsValid())
    {
        FEditorDelegates::OnAssetsPreDelete.Remove(AssetsPreDeleteHandle);
        AssetsPreDeleteHandle.Reset();
    }

    if (AssetRemovedHandle.IsValid())
    {
        if (FModuleManager::Get().IsModuleLoaded("AssetRegistry"))
        {
            FAssetRegistryModule& AssetRegistryModule = FModuleManager::GetModuleChecked<FAssetRegistryModule>("AssetRegistry");
            AssetRegistryModule.Get().OnAssetRemoved().Remove(AssetRemovedHandle);
        }
        AssetRemovedHandle.Reset();
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

    if (ActorsPlacedHandle.IsValid())
    {
        FEditorDelegates::OnNewActorsDropped.Remove(ActorsPlacedHandle);
        ActorsPlacedHandle.Reset();
    }

    UE_LOG(LogUEAgent, Log, TEXT("DCC event tracking cleaned up"));

    // 淇濆瓨鎷︽埅娓呯悊
    UnhookIsPackageOKToSave();
}

// --- 浜嬩欢鍥炶皟瀹炵幇 ---

// ------------------------------------------------------------------
// 淇濆瓨鎷︽埅杈呭姪鍑芥暟
// ------------------------------------------------------------------

namespace
{
    /** silent mode: auto-dismiss toast in bottom-right, no user action required */
    void ShowSaveBlockedNotification(const FString& PackagePath, const FString& Reason)
    {
        FNotificationInfo Info(FText::FromString(
            FString::Printf(TEXT("[ArtClaw] Save Blocked\n%s\n%s"), *PackagePath, *Reason)));
        Info.bFireAndForget = true;
        Info.FadeOutDuration = 1.0f;
        Info.ExpireDuration = 8.0f;
        Info.bUseThrobber = false;
        Info.bUseSuccessFailIcons = true;

        FSlateNotificationManager::Get().AddNotification(Info)->SetCompletionState(SNotificationItem::CS_Fail);
    }

    /** notify mode: blocking modal dialog, user must click OK to close */
    void ShowSaveBlockedDialog(const FString& PackagePath, const FString& Reason)
    {
        const FText Title   = FText::FromString(TEXT("[ArtClaw] Save Blocked"));
        const FText Message = FText::FromString(
            FString::Printf(TEXT("Asset: %s\n\nReason: %s"), *PackagePath, *Reason));

        FMessageDialog::Open(EAppMsgType::Ok, Message, Title);
    }

    /**
     * Read ~/.artclaw/_pending_notify.json written by Python _notify_ue(),
     * show the appropriate native notification, then delete the file.
     */
    void FlushPendingNotify()
    {
        // Resolve path: %USERPROFILE%\.artclaw\_pending_notify.json
        FString NotifyPath = FPlatformMisc::GetEnvironmentVariable(TEXT("USERPROFILE"));
        if (NotifyPath.IsEmpty())
        {
            NotifyPath = FPlatformMisc::GetEnvironmentVariable(TEXT("HOME"));
        }
        NotifyPath = NotifyPath / TEXT(".artclaw") / TEXT("_pending_notify.json");

        if (!FPaths::FileExists(NotifyPath))
        {
            return;
        }

        // Read JSON
        FString JsonStr;
        if (!FFileHelper::LoadFileToString(JsonStr, *NotifyPath))
        {
            return;
        }

        // Delete file immediately so stale data is never re-shown
        IFileManager::Get().Delete(*NotifyPath);

        TSharedPtr<FJsonObject> Obj;
        TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
        if (!FJsonSerializer::Deserialize(Reader, Obj) || !Obj.IsValid())
        {
            return;
        }

        FString Mode    = Obj->GetStringField(TEXT("mode"));
        FString Message = Obj->GetStringField(TEXT("message"));
        FString Asset   = Obj->GetStringField(TEXT("asset_path"));

        if (Mode == TEXT("notify"))
        {
            ShowSaveBlockedDialog(Asset, Message);
        }
        else
        {
            // silent / error: toast notification
            ShowSaveBlockedNotification(Asset, Message);
        }
    }
}

void UUEAgentSubsystem::HandlePackageSaved(const FString& Filename, UPackage* Package, FObjectPostSaveContext Context)
{
    if (!Package) return;

    const FString PackagePath = Package->GetPathName();

    // 杩囨护鎺夊紩鎿?涓存椂鍖咃紝鍙浆鍙戠敤鎴疯祫婧?
    if (PackagePath.StartsWith(TEXT("/Engine/")) || PackagePath.StartsWith(TEXT("/Temp/")))
    {
        return;
    }

    UE_LOG(LogUEAgent, Verbose, TEXT("Asset post-save: %s"), *PackagePath);

    // 鎵ц post 浜嬩欢宸ュ叿锛堟湰鍦?Python锛屼笉鎷︽埅锛?
    {
        FString AssetName = PackagePath;
        int32 LastSlash;
        if (PackagePath.FindLastChar(TEXT('/'), LastSlash))
        {
            AssetName = PackagePath.Mid(LastSlash + 1);
        }

        FString EscapedPath = PackagePath.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("'"), TEXT("\\'"));
        FString EscapedName = AssetName.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("'"), TEXT("\\'"));

        IPythonScriptPlugin* PythonPlugin = IPythonScriptPlugin::Get();
        if (PythonPlugin)
        {
            PythonPlugin->ExecPythonCommand(*FString::Printf(TEXT(
                "try:\n"
                "    from dcc_event_intercept import handle_post_save\n"
                "    handle_post_save('%s', '%s')\n"
                "except Exception as _e:\n"
                "    try:\n"
                "        import unreal; unreal.log_warning(f'[ArtClaw] post_save error: {_e}')\n"
                "    except Exception: pass\n"
            ), *EscapedPath, *EscapedName));

            // Show native toast/modal if Python wrote a pending notification
            FlushPendingNotify();
        }
    }

    OnAssetPostSave.Broadcast(PackagePath, true);
}

void UUEAgentSubsystem::HandleObjectPreSave(UObject* Object, FObjectPreSaveContext Context)
{
    if (!Object) return;

    UPackage* Package = Object->GetOutermost();
    if (!Package) return;

    const FString PackagePath = Package->GetPathName();

    // 杩囨护寮曟搸鍖?
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

    // 鎵ц post 浜嬩欢宸ュ叿
    {
        FString EscapedPath = AssetPath.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("'"), TEXT("\\'"));
        FString EscapedClass = AssetClass.Replace(TEXT("'"), TEXT("\\'"));
        IPythonScriptPlugin* PythonPlugin = IPythonScriptPlugin::Get();
        if (PythonPlugin)
        {
            PythonPlugin->ExecPythonCommand(*FString::Printf(TEXT(
                "try:\n"
                "    from dcc_event_intercept import handle_post_import\n"
                "    handle_post_import('%s', '%s')\n"
                "except Exception as _e:\n"
                "    try:\n"
                "        import unreal; unreal.log_warning(f'[ArtClaw] post_import error: {_e}')\n"
                "    except Exception: pass\n"
            ), *EscapedPath, *EscapedClass));

            FlushPendingNotify();
        }
    }

    OnAssetImported.Broadcast(AssetPath, AssetClass);
}

void UUEAgentSubsystem::HandleAssetsPreDelete(const TArray<UObject*>& DeletedAssets)
{
    TArray<FString> AssetPaths;

    for (UObject* Asset : DeletedAssets)
    {
        if (!Asset) continue;

        const FString AssetPath = Asset->GetPathName();
        
        // 杩囨护寮曟搸璧勬簮
        if (AssetPath.StartsWith(TEXT("/Engine/")) || AssetPath.StartsWith(TEXT("/Temp/")))
        {
            continue;
        }

        AssetPaths.Add(AssetPath);
        UE_LOG(LogUEAgent, Log, TEXT("Asset pre-delete: %s"), *AssetPath);
        OnAssetPreDelete.Broadcast(AssetPath);
    }

    // 鎵ц pre-delete 妫€鏌ュ伐鍏凤紙娉ㄦ剰锛歎E 鏃犳硶闃绘鍒犻櫎锛屼粎閫氱煡锛?
    if (AssetPaths.Num() > 0)
    {
        // 鏋勫缓 Python 鍒楄〃瀛楃涓?
        FString PathListStr = TEXT("[");
        for (int32 i = 0; i < AssetPaths.Num(); ++i)
        {
            FString Escaped = AssetPaths[i].Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("'"), TEXT("\\'"));
            PathListStr += FString::Printf(TEXT("'%s'"), *Escaped);
            if (i < AssetPaths.Num() - 1) PathListStr += TEXT(", ");
        }
        PathListStr += TEXT("]");

        IPythonScriptPlugin* PythonPlugin = IPythonScriptPlugin::Get();
        if (PythonPlugin)
        {
            // 娉ㄦ剰锛歎E 鏃犳硶鐪熸闃绘鍒犻櫎鎿嶄綔锛圤nAssetsPreDelete 浠呬负閫氱煡浜嬩欢锛屾棤娉曞彇娑堬級
            // 鍥犳姝ゅ鏍规嵁 execution_mode 鍚戠敤鎴峰彂鍑鸿鍛婏紝浣嗗垹闄や粛浼氱户缁墽琛?
            PythonPlugin->ExecPythonCommand(*FString::Printf(TEXT(
                "try:\n"
                "    from dcc_event_intercept import check_pre_delete, _notify_ue\n"
                "    _r = check_pre_delete(%s)\n"
                "    if _r.get('blocked'):\n"
                "        import unreal\n"
                "        _reason = _r.get('reason', 'Delete check failed')\n"
                "        _mode   = _r.get('execution_mode', 'notify')\n"
                "        unreal.log_warning(f'[ArtClaw] Pre-delete blocked (cannot stop): {_reason}')\n"
                "        _notify_ue(_reason, _mode)\n"
                "except Exception as _e:\n"
                "    try:\n"
                "        import unreal\n"
                "        unreal.log_warning(f'[ArtClaw] Pre-delete check error: {_e}')\n"
                "    except Exception:\n"
                "        pass\n"
            ), *PathListStr));

            FlushPendingNotify();
        }
    }
}

void UUEAgentSubsystem::HandleAssetRemoved(const FAssetData& AssetData)
{
    const FString AssetPath = AssetData.GetSoftObjectPath().ToString();
    
    // 杩囨护寮曟搸璧勬簮
    if (AssetPath.StartsWith(TEXT("/Engine/")) || AssetPath.StartsWith(TEXT("/Temp/")))
    {
        return;
    }

    UE_LOG(LogUEAgent, Log, TEXT("Asset post-delete: %s"), *AssetPath);

    // 鎵ц post 浜嬩欢宸ュ叿
    {
        FString EscapedPath = AssetPath.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("'"), TEXT("\\'"));
        FString AssetName = AssetPath;
        int32 LastSlash;
        if (AssetPath.FindLastChar(TEXT('/'), LastSlash))
        {
            AssetName = AssetPath.Mid(LastSlash + 1);
        }
        FString EscapedName = AssetName.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("'"), TEXT("\\'"));
        IPythonScriptPlugin* PythonPlugin = IPythonScriptPlugin::Get();
        if (PythonPlugin)
        {
            PythonPlugin->ExecPythonCommand(*FString::Printf(TEXT(
                "try:\n"
                "    from dcc_event_intercept import handle_post_delete\n"
                "    handle_post_delete('%s', '%s')\n"
                "except Exception as _e:\n"
                "    try:\n"
                "        import unreal; unreal.log_warning(f'[ArtClaw] post_delete error: {_e}')\n"
                "    except Exception: pass\n"
            ), *EscapedPath, *EscapedName));

            FlushPendingNotify();
        }
    }

    OnAssetPostDelete.Broadcast(AssetPath);
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

// 内部辅助：通知 Python 侧 actor 放置事件
static void NotifyActorPlaced(AActor* Actor)
{
    if (!Actor) return;
    IPythonScriptPlugin* PythonPlugin = IPythonScriptPlugin::Get();
    if (!PythonPlugin) return;

    const FString ActorName  = Actor->GetName();
    const FString ActorClass = Actor->GetClass() ? Actor->GetClass()->GetName() : TEXT("Unknown");

    // 尝试从 StaticMeshComponent 获取源资产路径（避免 Python 侧二次查询导致崩溃）
    FString SourceAssetPath;
    if (IsValid(Actor))
    {
        if (AStaticMeshActor* SMActor = Cast<AStaticMeshActor>(Actor))
        {
            UStaticMeshComponent* SMC = SMActor->GetStaticMeshComponent();
            if (IsValid(SMC))
            {
                UStaticMesh* Mesh = SMC->GetStaticMesh();
                if (IsValid(Mesh))
                {
                    // 格式: /Game/Foo/Bar.Bar -> 取第一个 "." 之前的部分
                    SourceAssetPath = Mesh->GetPathName();
                    int32 DotIdx;
                    if (SourceAssetPath.FindChar(TEXT('.'), DotIdx))
                        SourceAssetPath = SourceAssetPath.Left(DotIdx);
                }
            }
        }
    }
    if (SourceAssetPath.IsEmpty())
        SourceAssetPath = Actor->GetPathName();

    // Escape single quotes
    FString SafeAssetPath = SourceAssetPath.Replace(TEXT("'"), TEXT("\\'"));
    FString SafeActorName = ActorName      .Replace(TEXT("'"), TEXT("\\'"));
    FString SafeActorClass= ActorClass     .Replace(TEXT("'"), TEXT("\\'"));

    UE_LOG(LogUEAgent, Log, TEXT("Actor placed in editor: %s (%s) -> %s"), *ActorName, *ActorClass, *SourceAssetPath);

    PythonPlugin->ExecPythonCommand(*FString::Printf(TEXT(
        "try:\n"
        "    from dcc_event_intercept import handle_actor_placed\n"
        "    handle_actor_placed('%s', '%s', '%s')\n"
        "except Exception as _e:\n"
        "    import unreal; unreal.log_warning('[ArtClaw] actor placed event error: ' + str(_e))\n"
    ), *SafeAssetPath, *SafeActorName, *SafeActorClass));

    // Python 执行完后立即刷新 pending 通知（气泡/对话框）
    FlushPendingNotify();
}

void UUEAgentSubsystem::HandleActorsDropped(const TArray<UObject*>& DroppedObjects, const TArray<AActor*>& PlacedActors)
{
    for (AActor* Actor : PlacedActors)
    {
        NotifyActorPlaced(Actor);
    }
}

void UUEAgentSubsystem::HandleActorsPlaced(UObject* InContext, const TArray<AActor*>& PlacedActors)
{
    for (AActor* Actor : PlacedActors)
    {
        NotifyActorPlaced(Actor);
    }
}

// ------------------------------------------------------------------
// 淇濆瓨鎷︽埅閰嶇疆璇诲彇
// ------------------------------------------------------------------

void UUEAgentSubsystem::LoadSaveInterceptConfig()
{
    FString ConfigPath = FPlatformProcess::UserHomeDir();
    ConfigPath = FPaths::Combine(ConfigPath, TEXT(".artclaw"), TEXT("config.json"));
    if (!FPaths::FileExists(ConfigPath))
    {
        return;
    }

    FString JsonContent;
    if (!FFileHelper::LoadFileToString(JsonContent, *ConfigPath))
    {
        return;
    }

    TSharedPtr<FJsonObject> JsonObj;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
    if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
    {
        return;
    }

    JsonObj->TryGetBoolField(TEXT("save_intercept_silent_pass"), bSaveInterceptSilentPass);
    UE_LOG(LogUEAgent, Log, TEXT("Save intercept mode: %s"),
        bSaveInterceptSilentPass ? TEXT("silent pass") : TEXT("default block"));
}

// ------------------------------------------------------------------
// Auto-launch Tool Manager
// ------------------------------------------------------------------

void UUEAgentSubsystem::AutoLaunchToolManager()
{
    // 閫氳繃 Python tool_manager_launcher 妫€娴嬪苟鎷夎捣 Tool Manager
    // 浣跨敤 start_server(open_browser=False) 闈欓粯鍚姩
    IPythonScriptPlugin* PythonPlugin = IPythonScriptPlugin::Get();
    if (!PythonPlugin)
    {
        UE_LOG(LogUEAgent, Warning, TEXT("Python plugin not available, skipping Tool Manager auto-launch"));
        return;
    }

    PythonPlugin->ExecPythonCommand(TEXT(
        "import sys, os\n"
        "try:\n"
        "    import json\n"
        "    _cfg_path = os.path.expanduser('~/.artclaw/config.json')\n"
        "    with open(_cfg_path, 'r', encoding='utf-8') as _f:\n"
        "        _cfg = json.load(_f)\n"
        "    _root = _cfg.get('project_root', '')\n"
        "    if _root:\n"
        "        _core_dir = os.path.join(_root, 'core')\n"
        "        if _core_dir not in sys.path:\n"
        "            sys.path.insert(0, _core_dir)\n"
        "        from tool_manager_launcher import start_server, is_running\n"
        "        if not is_running():\n"
        "            print('[ArtClaw] Tool Manager not running, launching...')\n"
        "            _r = start_server(open_browser=False)\n"
        "            if _r['ok']:\n"
        "                print('[ArtClaw] Tool Manager started successfully')\n"
        "            else:\n"
        "                print(f'[ArtClaw] Tool Manager start failed: {_r.get(\"error\", \"unknown\")}')\n"
        "        else:\n"
        "            print('[ArtClaw] Tool Manager already running')\n"
        "except Exception as _e:\n"
        "    print(f'[ArtClaw] Tool Manager auto-launch error: {_e}')\n"
    ));

    UE_LOG(LogUEAgent, Log, TEXT("Tool Manager auto-launch check completed"));
}

// ------------------------------------------------------------------
// IsPackageOKToSave 淇濆瓨鎷︽埅瀹炵幇
// ------------------------------------------------------------------

void UUEAgentSubsystem::HookIsPackageOKToSave()
{
    if (bIsPackageSaveHooked)
    {
        return;
    }

    // 澶囦唤鐜版湁鐨?delegate锛堝彲鑳芥槸鍏朵粬鎻掍欢缁戝畾鐨勶紝濡?AssetsAuditor锛?
    OkToSaveBackupDelegate = FCoreUObjectDelegates::IsPackageOKToSaveDelegate;
    if (OkToSaveBackupDelegate.IsBoundToObject(this))
    {
        // 闃叉鑷繁澶囦唤鑷繁锛堥噸澶嶈皟鐢ㄧ殑淇濇姢锛?
        OkToSaveBackupDelegate.Unbind();
    }

    // 鎸備笂鎴戜滑鐨勫洖璋?
    FCoreUObjectDelegates::IsPackageOKToSaveDelegate.BindUObject(
        this, &UUEAgentSubsystem::IsPackageOKToSave);

    bIsPackageSaveHooked = true;
    UE_LOG(LogUEAgent, Log, TEXT("IsPackageOKToSave hook installed"));
}

void UUEAgentSubsystem::UnhookIsPackageOKToSave()
{
    if (!bIsPackageSaveHooked)
    {
        return;
    }

    // 杩樺師澶囦唤鐨?delegate
    if (OkToSaveBackupDelegate.IsBound())
    {
        FCoreUObjectDelegates::IsPackageOKToSaveDelegate = OkToSaveBackupDelegate;
        OkToSaveBackupDelegate.Unbind();
    }
    else
    {
        FCoreUObjectDelegates::IsPackageOKToSaveDelegate.Unbind();
    }

    bIsPackageSaveHooked = false;
    UE_LOG(LogUEAgent, Log, TEXT("IsPackageOKToSave hook removed"));
}

bool UUEAgentSubsystem::IsPackageOKToSave(UPackage* PackageToSave, const FString& PackageFileName, FOutputDevice* OutputDevice)
{
    if (!PackageToSave)
    {
        if (OkToSaveBackupDelegate.IsBound())
        {
            return OkToSaveBackupDelegate.Execute(PackageToSave, PackageFileName, OutputDevice);
        }
        return true;
    }

    const FString PackagePath = PackageToSave->GetPathName();

    // 杩囨护寮曟搸/涓存椂鍖?
    if (PackagePath.StartsWith(TEXT("/Engine/")) || PackagePath.StartsWith(TEXT("/Temp/")))
    {
        if (OkToSaveBackupDelegate.IsBound())
        {
            return OkToSaveBackupDelegate.Execute(PackageToSave, PackageFileName, OutputDevice);
        }
        return true;
    }

    // 闈欓粯鏀捐妯″紡锛氳烦杩囨墍鏈夋嫤鎴鏌?
    if (bSaveInterceptSilentPass)
    {
        if (OkToSaveBackupDelegate.IsBound())
        {
            return OkToSaveBackupDelegate.Execute(PackageToSave, PackageFileName, OutputDevice);
        }
        return true;
    }

    // --- 通过 Python 本地执行保存拦截检查 ---
    // 调用 dcc_event_intercept.check_pre_save()，直接在 UE Python 环境内执行
    // 不依赖 Tool Manager HTTP 服务
    {
        FString AssetName = PackagePath;
        int32 LastSlash;
        if (PackagePath.FindLastChar(TEXT('/'), LastSlash))
        {
            AssetName = PackagePath.Mid(LastSlash + 1);
        }

        // 杞箟璺緞涓殑寮曞彿鍜屽弽鏂滄潬
        FString EscapedPath = PackagePath.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("'"), TEXT("\\'"));
        FString EscapedName = AssetName.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("'"), TEXT("\\'"));
        FString EscapedFileName = PackageFileName.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("'"), TEXT("\\'"));

        FString PythonCode = FString::Printf(TEXT(
            "try:\n"
            "    from dcc_event_intercept import check_pre_save\n"
            "    _result = check_pre_save('%s', '%s', '%s')\n"
            "except ImportError:\n"
            "    _result = {'blocked': False, 'reason': ''}\n"
            "except Exception as _e:\n"
            "    _result = {'blocked': False, 'reason': '', 'error': str(_e)}\n"
        ), *EscapedPath, *EscapedName, *EscapedFileName);

        FString ResultJson = FUEAgentManageUtils::RunPythonAndCapture(PythonCode);

        // 瑙ｆ瀽缁撴灉
        TSharedPtr<FJsonObject> ResultObj;
        TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ResultJson);
        if (FJsonSerializer::Deserialize(Reader, ResultObj) && ResultObj.IsValid())
        {
            bool bBlocked = false;
            FString BlockReason;
            ResultObj->TryGetBoolField(TEXT("blocked"), bBlocked);
            ResultObj->TryGetStringField(TEXT("reason"), BlockReason);

            if (bBlocked)
            {
                FString ExecMode;
                ResultObj->TryGetStringField(TEXT("execution_mode"), ExecMode);
                const bool bSilent = ExecMode.Equals(TEXT("silent"), ESearchCase::IgnoreCase);

                // 始终写 Output Log
                UE_LOG(LogUEAgent, Warning, TEXT("Save BLOCKED: %s -- %s (mode=%s)"), *PackagePath, *BlockReason, *ExecMode);

                // 两种模式都真正拦截保存（return false）。
                // UE 引擎在收到 false 时会强制弹出系统级"无法保存"对话框，这是引擎硬编码行为无法绕过。
                // 区别仅在于是否额外弹出 ArtClaw 自己的说明对话框：
                //   silent — 只写 Log + 右下角气泡，不弹额外 Modal（系统对话框依然存在）
                //   notify — 在系统对话框之前额外弹出 ArtClaw Modal，提示详细原因

                if (OutputDevice)
                {
                    OutputDevice->Logf(ELogVerbosity::Warning, TEXT("ArtClaw: Save blocked -- %s"), *BlockReason);
                }

                if (bSilent)
                {
                    // silent 模式：仅气泡通知，不弹 ArtClaw Modal
                    ShowSaveBlockedNotification(PackagePath, BlockReason);
                }
                else
                {
                    // notify 模式：弹出 ArtClaw Modal 对话框，用户确认后引擎系统对话框再出现
                    ShowSaveBlockedDialog(PackagePath, BlockReason);
                }

                // 恢复 dirty 标记（UE 在调用 delegate 前可能已清除）
                PackageToSave->SetDirtyFlag(true);

                return false;
            }
        }
    }

    // 閾惧紡璋冪敤鍘熸湁 delegate锛堝叾浠栨彃浠剁殑淇濆瓨妫€鏌ワ級
    if (OkToSaveBackupDelegate.IsBound())
    {
        return OkToSaveBackupDelegate.Execute(PackageToSave, PackageFileName, OutputDevice);
    }

    return true;
}
