// Copyright ArtClaw Project. All Rights Reserved.
// 会话管理模块 - 多会话切换、 历史记录加载、会话恢复
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// 会话持久化 — 重启恢复
// ==================================================================

FString SUEAgentDashboard::GetLastSessionFilePath() const
{
	return FPaths::ProjectSavedDir() / TEXT("UEAgent") / TEXT("_last_session.json");
}

void SUEAgentDashboard::SaveLastSession()
{
	// 获取当前 session key（如果 Python 端还活着的话）
	FString SessionKey;
	if (PlatformBridge.IsValid())
	{
		SessionKey = PlatformBridge->GetSessionKey();
	}

	// 如果没有 session key，也保存（恢复时会创建新会话）
	TSharedRef<FJsonObject> JsonObj = MakeShared<FJsonObject>();
	JsonObj->SetStringField(TEXT("session_key"), SessionKey);
	JsonObj->SetStringField(TEXT("agent_id"), CurrentAgentId);
	JsonObj->SetStringField(TEXT("session_label"), CurrentSessionLabel);

	FString OutputStr;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputStr);
	FJsonSerializer::Serialize(JsonObj, Writer);

	FString FilePath = GetLastSessionFilePath();
	FString Dir = FPaths::GetPath(FilePath);
	IFileManager::Get().MakeDirectory(*Dir, true);
	FFileHelper::SaveStringToFile(OutputStr, *FilePath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

void SUEAgentDashboard::RestoreOrInitSession()
{
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
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
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