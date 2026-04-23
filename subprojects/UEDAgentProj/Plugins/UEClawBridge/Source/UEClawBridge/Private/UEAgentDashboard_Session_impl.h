// Copyright ArtClaw Project. All Rights Reserved.
// 会话管理模块 - 多会话切换、 历史记录加载、会话恢复
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// 会话持久化 — 重启恢复
// ==================================================================

FString SUEAgentDashboard::GetLastSessionFilePath() const
{
	return FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge") / TEXT("_last_session.json");
}

void SUEAgentDashboard::SaveLastSession()
{
	// 安全检查：UE 关闭序列中 FPaths/IFileManager 依赖的 LazySingleton 可能已销毁
	if (!FSlateApplication::IsInitialized() || !GEngine)
	{
		return;
	}

	// 从 C++ 缓存获取 session key（不调 Python，避免析构时 Python 已卸载）
	FString SessionKey;
	if (ActiveSessionIndex >= 0 && SessionEntries.IsValidIndex(ActiveSessionIndex))
	{
		SessionKey = SessionEntries[ActiveSessionIndex].SessionKey;
	}

	// 手拼 JSON 字符串，不使用 TJsonWriter/TMemoryWriterBase
	// 原因：TJsonStringWriter 构造依赖 LazySingleton，在 UE 关闭序列中
	// 调用会触发 "Assertion failed: Ptr [LazySingleton.h:109]" 断点
	auto EscapeJson = [](const FString& S) -> FString
	{
		FString Out = S;
		Out.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
		Out.ReplaceInline(TEXT("\""), TEXT("\\\""));
		Out.ReplaceInline(TEXT("\n"), TEXT("\\n"));
		Out.ReplaceInline(TEXT("\r"), TEXT("\\r"));
		Out.ReplaceInline(TEXT("\t"), TEXT("\\t"));
		return Out;
	};

	FString OutputStr = FString::Printf(
		TEXT("{\"session_key\":\"%s\",\"agent_id\":\"%s\",\"session_label\":\"%s\"}"),
		*EscapeJson(SessionKey),
		*EscapeJson(CurrentAgentId),
		*EscapeJson(CurrentSessionLabel)
	);

	FString FilePath = GetLastSessionFilePath();
	FString Dir = FPaths::GetPath(FilePath);
	IFileManager::Get().MakeDirectory(*Dir, true);
	FFileHelper::SaveStringToFile(OutputStr, *FilePath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

void SUEAgentDashboard::RestoreOrInitSession()
{
	// --- 0) 清理上次 UE 崩溃遗留的临时文件 ---
	// 在恢复会话之前清理，避免 SendToOpenClaw 的 poll 定时器误读旧文件
	{
		FString TempDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge");
		IFileManager::Get().Delete(*(TempDir / TEXT("_openclaw_response.txt")), false, false, true);
		IFileManager::Get().Delete(*(TempDir / TEXT("_openclaw_response_stream.jsonl")), false, false, true);
		IFileManager::Get().Delete(*(TempDir / TEXT("_openclaw_msg_input.txt")), false, false, true);
	}

	FString FilePath = GetLastSessionFilePath();
	FString JsonContent;

	if (!FPaths::FileExists(FilePath) || !FFileHelper::LoadFileToString(JsonContent, *FilePath))
	{
		// 没有上次会话记录，走正常初始化
		InitFirstSession();
		return;
	}

	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
	{
		InitFirstSession();
		return;
	}

	FString SavedKey   = JsonObj->GetStringField(TEXT("session_key"));
	FString SavedAgent = JsonObj->GetStringField(TEXT("agent_id"));
	FString SavedLabel = JsonObj->GetStringField(TEXT("session_label"));

	if (SavedKey.IsEmpty())
	{
		// 没有有效 session key，走正常初始化
		InitFirstSession();
		return;
	}

	// 恢复 Agent ID
	if (!SavedAgent.IsEmpty())
	{
		CurrentAgentId = SavedAgent;
		PlatformBridge->SetAgentId(SavedAgent);
	}

	// 恢复 session key
	PlatformBridge->SetSessionKey(SavedKey);

	// 恢复 session label
	CurrentSessionLabel = SavedLabel.IsEmpty()
		? FUEAgentL10n::GetStr(TEXT("SessionLabel")) + TEXT(" (restored)")
		: SavedLabel;

	// 创建 session entry
	FSessionEntry RestoredEntry;
	RestoredEntry.SessionKey = SavedKey;
	RestoredEntry.Label = CurrentSessionLabel;
	RestoredEntry.CreatedAt = FDateTime::Now();
	RestoredEntry.bIsActive = true;

	SessionEntries.Add(MoveTemp(RestoredEntry));
	ActiveSessionIndex = 0;

	// --- 会话恢复: 中止 Gateway 上残留的 AI 运行 ---
	// UE 崩溃后 agent 可能仍在 Gateway 上运行，需要中止以避免:
	// 1. 新消息发送后收到旧运行的事件干扰
	// 2. 无法停止旧的 AI 运行
	// 3. 旧运行占用 session 导致新请求失败
	{
		FString TempDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge");
		IFileManager::Get().MakeDirectory(*TempDir, true);
		FString RecoverFile = TempDir / TEXT("_recover_status.txt");
		IFileManager::Get().Delete(*RecoverFile, false, false, true);

		PlatformBridge->RecoverSession(RecoverFile);

		// 轮询恢复结果（非阻塞，在后台完成）
		auto Self = SharedThis(this);
		FString CapturedFile = RecoverFile;
		FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateLambda([Self, CapturedFile](float) -> bool
			{
				if (!FPaths::FileExists(CapturedFile))
				{
					return true; // 继续等待
				}

				FString Status;
				FFileHelper::LoadFileToString(Status, *CapturedFile);
				IFileManager::Get().Delete(*CapturedFile, false, false, true);
				Status.TrimStartAndEndInline();

				if (Status == TEXT("aborted"))
				{
					Self->AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("SessionRecoveredAborted")));
				}
				else if (Status.StartsWith(TEXT("error:")))
				{
					UE_LOG(LogTemp, Warning, TEXT("[UEAgent] Session recovery error: %s"), *Status);
				}
				// "ok" = 无需恢复，静默通过

				return false;
			}),
			0.5f
		);
	}
}

// ==================================================================
// 多会话管理 (任务 5.8)
// ==================================================================

void SUEAgentDashboard::InitFirstSession()
{
	FDateTime Now = FDateTime::Now();
	CurrentSessionLabel = FString::Printf(TEXT("%s %02d-%02d %02d:%02d"),
		*FUEAgentL10n::GetStr(TEXT("SessionLabel")),
		Now.GetMonth(), Now.GetDay(), Now.GetHour(), Now.GetMinute());

	FSessionEntry FirstEntry;
	FirstEntry.Label = CurrentSessionLabel;
	FirstEntry.CreatedAt = Now;
	FirstEntry.bIsActive = true;

	SessionEntries.Add(MoveTemp(FirstEntry));
	ActiveSessionIndex = 0;
}

FReply SUEAgentDashboard::OnSessionMenuClicked()
{
	if (SessionMenuAnchor.IsValid())
	{
		// 每次打开菜单前重建内容（SessionEntries 可能已变化）
		SessionMenuAnchor->SetMenuContent(BuildSessionMenuContent());
		SessionMenuAnchor->SetIsOpen(!SessionMenuAnchor->IsOpen());
	}
	return FReply::Handled();
}

TSharedRef<SWidget> SUEAgentDashboard::BuildSessionMenuContent()
{
	TSharedRef<SVerticalBox> MenuContent = SNew(SVerticalBox);

	// 会话列表（不含新建按钮，新建通过工具栏的 "+ 新会话" 按钮）
	for (int32 i = 0; i < SessionEntries.Num(); ++i)
	{
		const FSessionEntry& Entry = SessionEntries[i];
		const int32 CapturedIndex = i;

		MenuContent->AddSlot()
		.AutoHeight()
		.Padding(4.0f, 2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			[
				SNew(SButton)
				.Text(FText::FromString(Entry.Label))
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply { OnSessionSelected(CapturedIndex); return FReply::Handled(); })
				.ContentPadding(FMargin(8.0f, 4.0f))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(FUEAgentL10n::Get(TEXT("DeleteSession")))
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply { OnDeleteSession(CapturedIndex); return FReply::Handled(); })
				.ContentPadding(FMargin(4.0f, 4.0f))
				.ButtonColorAndOpacity(FLinearColor(0.8f, 0.3f, 0.3f))
			]
		];
	}

	return MenuContent;
}

void SUEAgentDashboard::OnSessionSelected(int32 Index)
{
	if (!SessionEntries.IsValidIndex(Index) || Index == ActiveSessionIndex)
	{
		return;
	}

	// 保存当前会话的消息到 CachedMessages
	if (ActiveSessionIndex >= 0 && SessionEntries.IsValidIndex(ActiveSessionIndex))
	{
		FString CurrentKey = PlatformBridge->GetSessionKey();
		if (!CurrentKey.IsEmpty())
		{
			SessionEntries[ActiveSessionIndex].SessionKey = CurrentKey;
		}
		SessionEntries[ActiveSessionIndex].CachedMessages = Messages;
		SessionEntries[ActiveSessionIndex].bIsActive = false;
	}

	// 切换到新会话
	ActiveSessionIndex = Index;
	SessionEntries[Index].bIsActive = true;
	CurrentSessionLabel = SessionEntries[Index].Label;

	FString SessionKey = SessionEntries[Index].SessionKey;

	// 恢复消息: 优先本地缓存，fallback 到 Gateway 历史
	if (SessionEntries[Index].CachedMessages.Num() > 0)
	{
		// 本地缓存命中 — 直接恢复，零延迟
		Messages = SessionEntries[Index].CachedMessages;
		RebuildMessageList();
	}
	else if (!SessionKey.IsEmpty())
	{
		// 从 Gateway 拉取历史
		Messages.Empty();
		RebuildMessageList();
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("LoadingHistory")));
		LoadSessionHistory(SessionKey);
	}
	else
	{
		// 新空会话
		Messages.Empty();
		RebuildMessageList();
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("NewChatStarted")));
	}

	// 切换 Python 端的活跃 session key
	if (!SessionKey.IsEmpty())
	{
		PlatformBridge->SetSessionKey(SessionKey);
	}
	else
	{
		PlatformBridge->ResetSession();
	}

	// 关闭菜单
	if (SessionMenuAnchor.IsValid())
	{
		SessionMenuAnchor->SetIsOpen(false);
	}
}

void SUEAgentDashboard::OnDeleteSession(int32 Index)
{
	if (!SessionEntries.IsValidIndex(Index))
	{
		return;
	}

	// 如果删除的是当前活跃会话，切换到其他会话
	if (Index == ActiveSessionIndex)
	{
		if (SessionEntries.Num() > 1)
		{
			int32 NewIndex = (Index == 0) ? 1 : 0;
			OnSessionSelected(NewIndex);
		}
		else
		{
			// 只有一个会话，清空但不删除
			Messages.Empty();
			RebuildMessageList();
			InitFirstSession();
		}
	}

	SessionEntries.RemoveAt(Index);
}

void SUEAgentDashboard::LoadSessionHistory(const FString& SessionKey)
{
	// 从 Gateway 异步拉取会话历史
	FString TempDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge");
	IFileManager::Get().MakeDirectory(*TempDir, true);

	// 用 session key 的 hash 作为临时文件名，避免冲突
	FString SafeKey = SessionKey;
	SafeKey.ReplaceInline(TEXT("/"), TEXT("_"));
	SafeKey.ReplaceInline(TEXT(":"), TEXT("_"));
	FString HistoryFile = TempDir / FString::Printf(TEXT("_history_%s.json"), *SafeKey);
	IFileManager::Get().Delete(*HistoryFile, false, false, true);

	// 调用平台桥接异步拉取
	PlatformBridge->FetchSessionHistory(SessionKey, HistoryFile);

	// 轮询历史文件
	auto Self = SharedThis(this);
	FString CapturedFile = HistoryFile;
	int32 CapturedIndex = ActiveSessionIndex;
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedFile, CapturedIndex](float) -> bool
		{
			if (!FPaths::FileExists(CapturedFile))
			{
				return true; // 继续等待
			}

			// 读取 JSON
			TArray<uint8> RawBytes;
			if (!FFileHelper::LoadFileToArray(RawBytes, *CapturedFile))
			{
				IFileManager::Get().Delete(*CapturedFile, false, false, true);
				return false;
			}

			FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
			FString JsonContent(Converter.Length(), Converter.Get());
			IFileManager::Get().Delete(*CapturedFile, false, false, true);

			TSharedPtr<FJsonObject> JsonObj;
			TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
			if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
			{
				return false;
			}

			// 解析消息数组
			const TArray<TSharedPtr<FJsonValue>>* MessagesArray = nullptr;
			if (!JsonObj->TryGetArrayField(TEXT("messages"), MessagesArray) || !MessagesArray)
			{
				return false;
			}

			// 只有当用户仍停留在同一个 session 时才更新 UI
			if (Self->ActiveSessionIndex != CapturedIndex)
			{
				return false;
			}

			// 移除 "加载中..." 消息
			for (int32 i = Self->Messages.Num() - 1; i >= 0; --i)
			{
				if (Self->Messages[i].Sender == TEXT("system")
					&& Self->Messages[i].Content == FUEAgentL10n::GetStr(TEXT("LoadingHistory")))
				{
					Self->Messages.RemoveAt(i);
					break;
				}
			}

			for (const auto& MsgVal : *MessagesArray)
			{
				const TSharedPtr<FJsonObject>* MsgObj = nullptr;
				if (!MsgVal->TryGetObject(MsgObj) || !MsgObj)
				{
					continue;
				}

				FChatMessage Msg;
				Msg.Sender = (*MsgObj)->GetStringField(TEXT("sender"));
				Msg.Content = (*MsgObj)->GetStringField(TEXT("content"));
				(*MsgObj)->TryGetBoolField(TEXT("isCode"), Msg.bIsCode);
				Self->Messages.Add(MoveTemp(Msg));
			}

			Self->RebuildMessageList();

			// 缓存到 SessionEntry，下次切换直接用
			if (Self->SessionEntries.IsValidIndex(CapturedIndex))
			{
				Self->SessionEntries[CapturedIndex].CachedMessages = Self->Messages;
			}

			return false;
		}),
		0.5f
	);
}

FText SUEAgentDashboard::GetActiveSessionLabel() const
{
	return FText::FromString(CurrentSessionLabel);
}