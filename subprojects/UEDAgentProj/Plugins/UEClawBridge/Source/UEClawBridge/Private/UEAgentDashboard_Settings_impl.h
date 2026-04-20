// Copyright ArtClaw Project. All Rights Reserved.
// 设置面板模块 - 语言切换、静默模式、Plan 模式、Skills 管理
// Ref: docs/specs/系统架构设计.md#SettingsPanel
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// 设置面板 - 打开/关闭
// ==================================================================

FReply SUEAgentDashboard::OnSettingsClicked()
{
	// 如果窗口已存在且未销毁，直接激活
	if (SettingsWindow.IsValid() && !SettingsWindow->GetNativeWindow().IsValid() == false)
	{
		SettingsWindow->BringToFront();
		return FReply::Handled();
	}
	// 窗口已被用户关闭（X 按钮），清理悬垂引用
	SettingsWindow.Reset();

	auto Self = SharedThis(this);

	SettingsWindow = SNew(SWindow)
		.Title(FUEAgentL10n::Get(TEXT("SettingsTitle")))
		.ClientSize(FVector2D(380.0f, 480.0f))
		.SupportsMinimize(false)
		.SupportsMaximize(false)
		[
			SNew(SBorder)
			.Padding(16.0f)
			.BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
			[
				SNew(SScrollBox)
				.Orientation(Orient_Vertical)
				+ SScrollBox::Slot()
				[
				SNew(SVerticalBox)

			// --- AI 平台 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FUEAgentL10n::Get(TEXT("SettingsPlatform")))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 4.0f, 0.0f, 0.0f)
			[
				SAssignNew(Self->PlatformListBox, SHorizontalBox)
			]

			// --- 分隔线 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 8.0f)
			[
				SNew(SSeparator)
			]

			// --- 语言切换 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FUEAgentL10n::Get(TEXT("SettingsLanguage")))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 2.0f, 0.0f, 0.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(SButton)
					.Text_Lambda([]() { return FUEAgentL10n::GetLanguageDisplayName(); })
					.ToolTipText(FUEAgentL10n::Get(TEXT("LangToggleTip")))
					.ContentPadding(FMargin(12.0f, 4.0f))
					.OnClicked_Lambda([Self]()
					{
						// 切换语言
						if (FUEAgentL10n::GetLanguage() == EUEAgentLanguage::Chinese)
						{
							FUEAgentL10n::SetLanguage(EUEAgentLanguage::English);
						}
						else
						{
							FUEAgentL10n::SetLanguage(EUEAgentLanguage::Chinese);
						}
						Self->RebuildAfterLanguageChange();
						return FReply::Handled();
					})
				]
			]

			// --- 分隔线 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 12.0f, 0.0f, 8.0f)
			[
				SNew(SSeparator)
			]

			// --- 发送模式 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(SCheckBox)
				.IsChecked_Lambda([Self]() -> ECheckBoxState
				{
					return Self->bEnterToSend ? ECheckBoxState::Checked : ECheckBoxState::Unchecked;
				})
				.OnCheckStateChanged_Lambda([Self](ECheckBoxState NewState)
				{
					Self->bEnterToSend = (NewState == ECheckBoxState::Checked);
				})
				[
					SNew(STextBlock)
					.Text(FUEAgentL10n::Get(TEXT("SettingsSendMode")))
				]
			]

			// --- 分隔线 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 8.0f)
			[
				SNew(SSeparator)
			]

			// --- 上下文窗口大小 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(STextBlock)
				.Text(FUEAgentL10n::Get(TEXT("SettingsContextWindow")))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 4.0f, 0.0f, 0.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(SButton)
					.Text_Lambda([Self]() -> FText
					{
						return FText::FromString(Self->ContextWindowSize == 128000 ? TEXT("[128K]") : TEXT("128K"));
					})
					.OnClicked_Lambda([Self]() { Self->ContextWindowSize = 128000; Self->SaveContextWindowSize(); return FReply::Handled(); })
					.ContentPadding(FMargin(6.0f, 2.0f))
					.ButtonColorAndOpacity_Lambda([Self]() -> FSlateColor
					{
						return Self->ContextWindowSize == 128000
							? FSlateColor(FLinearColor(0.2f, 0.5f, 0.7f))
							: FSlateColor(FLinearColor(0.22f, 0.22f, 0.22f));
					})
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([Self]() -> FText
					{
						return FText::FromString(Self->ContextWindowSize == 200000 ? TEXT("[200K]") : TEXT("200K"));
					})
					.OnClicked_Lambda([Self]() { Self->ContextWindowSize = 200000; Self->SaveContextWindowSize(); return FReply::Handled(); })
					.ContentPadding(FMargin(6.0f, 2.0f))
					.ButtonColorAndOpacity_Lambda([Self]() -> FSlateColor
					{
						return Self->ContextWindowSize == 200000
							? FSlateColor(FLinearColor(0.2f, 0.5f, 0.7f))
							: FSlateColor(FLinearColor(0.22f, 0.22f, 0.22f));
					})
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([Self]() -> FText
					{
						return FText::FromString(Self->ContextWindowSize == 500000 ? TEXT("[500K]") : TEXT("500K"));
					})
					.OnClicked_Lambda([Self]() { Self->ContextWindowSize = 500000; Self->SaveContextWindowSize(); return FReply::Handled(); })
					.ContentPadding(FMargin(6.0f, 2.0f))
					.ButtonColorAndOpacity_Lambda([Self]() -> FSlateColor
					{
						return Self->ContextWindowSize == 500000
							? FSlateColor(FLinearColor(0.2f, 0.5f, 0.7f))
							: FSlateColor(FLinearColor(0.22f, 0.22f, 0.22f));
					})
				]
			]

			// --- 分隔线 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 8.0f)
			[
				SNew(SSeparator)
			]

			// --- Agent 切换 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.FillWidth(1.0f)
				.VAlign(VAlign_Center)
				[
					SNew(STextBlock)
					.Text(FUEAgentL10n::Get(TEXT("SettingsAgent")))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(SButton)
					.Text(FUEAgentL10n::Get(TEXT("AgentRefreshBtn")))
					.OnClicked_Lambda([Self]() { return Self->OnRefreshAgentsClicked(); })
					.ToolTipText(FUEAgentL10n::Get(TEXT("AgentRefreshTip")))
					.ContentPadding(FMargin(6.0f, 2.0f))
				]
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 4.0f, 0.0f, 0.0f)
			[
				SAssignNew(Self->AgentListBox, SVerticalBox)
			]

			// --- 分隔线 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 8.0f)
			[
				SNew(SSeparator)
			]

			// --- 静默模式 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(STextBlock)
				.Text(FUEAgentL10n::Get(TEXT("SettingsSilentMode")))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 2.0f, 0.0f, 0.0f)
			[
				SNew(SHorizontalBox)
				// 中风险静默
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(SButton)
					.Text_Lambda([Self]() -> FText
					{
						return Self->bSilentMedium
							? FUEAgentL10n::Get(TEXT("SilentMediumOn"))
							: FUEAgentL10n::Get(TEXT("SilentMediumOff"));
					})
					.OnClicked_Lambda([Self]()
					{
						Self->bSilentMedium = !Self->bSilentMedium;
						Self->SaveSilentModeToConfig();
						return FReply::Handled();
					})
					.ToolTipText(FUEAgentL10n::Get(TEXT("SilentMediumTip")))
					.ButtonColorAndOpacity_Lambda([Self]() -> FSlateColor
					{
						return Self->bSilentMedium
							? FSlateColor(FLinearColor(0.4f, 0.6f, 0.4f))
							: FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f));
					})
					.ContentPadding(FMargin(8.0f, 4.0f))
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(8.0f, 0.0f)
				[
					// 高风险静默
					SNew(SButton)
					.Text_Lambda([Self]() -> FText
					{
						return Self->bSilentHigh
							? FUEAgentL10n::Get(TEXT("SilentHighOn"))
							: FUEAgentL10n::Get(TEXT("SilentHighOff"));
					})
					.OnClicked_Lambda([Self]()
					{
						Self->bSilentHigh = !Self->bSilentHigh;
						Self->SaveSilentModeToConfig();
						return FReply::Handled();
					})
					.ToolTipText(FUEAgentL10n::Get(TEXT("SilentHighTip")))
					.ButtonColorAndOpacity_Lambda([Self]() -> FSlateColor
					{
						return Self->bSilentHigh
							? FSlateColor(FLinearColor(0.7f, 0.4f, 0.4f))
							: FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f));
					})
					.ContentPadding(FMargin(8.0f, 4.0f))
				]
			]

			// --- 分隔线 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 8.0f)
			[
				SNew(SSeparator)
			]

			// --- Plan 模式 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(SButton)
				.Text_Lambda([Self]() -> FText
				{
					return Self->bPlanMode
						? FUEAgentL10n::Get(TEXT("PlanModeOn"))
						: FUEAgentL10n::Get(TEXT("PlanModeOff"));
				})
				.OnClicked_Lambda([Self]()
				{
					Self->OnTogglePlanModeClicked();
					return FReply::Handled();
				})
				.ToolTipText(FUEAgentL10n::Get(TEXT("PlanModeTip")))
				.ButtonColorAndOpacity_Lambda([Self]() -> FSlateColor
				{
					return Self->bPlanMode
						? FSlateColor(FLinearColor(0.6f, 0.4f, 0.8f))
						: FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f));
				})
				.ContentPadding(FMargin(8.0f, 4.0f))
			]

			// --- 分隔线 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 8.0f)
			[
				SNew(SSeparator)
			]

			// --- Skills 管理 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(SButton)
				.Text(FUEAgentL10n::Get(TEXT("SettingsSkillsManage")))
				.OnClicked(this, &SUEAgentDashboard::OnManageClicked)
				.ToolTipText(FUEAgentL10n::Get(TEXT("ManageTip")))
				.ContentPadding(FMargin(8.0f, 4.0f))
			]

			// --- 底部间距 + 关闭按钮 ---
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 0.0f)
			[
				SNew(SSpacer)
				.Size(FVector2D(0.0f, 4.0f))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.HAlign(HAlign_Right)
			.Padding(0.0f, 8.0f, 0.0f, 0.0f)
			[
				SNew(SButton)
				.Text(FUEAgentL10n::Get(TEXT("SettingsCloseBtn")))
				.OnClicked_Lambda([Self]()
				{
					// 关闭窗口（设置已在操作时即时保存，无需延迟保存）
					if (Self->SettingsWindow.IsValid())
					{
						Self->SettingsWindow->RequestDestroyWindow();
						Self->SettingsWindow.Reset();
					}
					return FReply::Handled();
				})
				.ContentPadding(FMargin(16.0f, 4.0f))
			]
			] // SVerticalBox end
			] // SScrollBox::Slot end
		]; // SBorder end (SWindow content)

	// 显示窗口，作为模态窗口
	SettingsWindow->SetOnWindowClosed(FOnWindowClosed::CreateLambda(
		[Self](const TSharedRef<SWindow>&)
	{
		Self->SettingsWindow.Reset();
	}));

	FUEAgentManageUtils::AddChildWindow(SettingsWindow.ToSharedRef());

	// Agent 列表 UI 构建（必须在 AgentListBox 已赋值之后）
	RebuildAgentListUI();

	// 平台列表 UI 构建
	RebuildPlatformListUI();

	return FReply::Handled();
}

// ==================================================================
// Agent 切换
// ==================================================================

void SUEAgentDashboard::LoadCachedAgents()
{
	// 从 Python 端读取缓存的 Agent 列表
	FString ResultJson = FUEAgentManageUtils::RunPythonAndCapture(TEXT(
		"from openclaw_chat import get_cached_agents, get_agent_id\n"
		"import json\n"
		"_agents = json.loads(get_cached_agents())\n"
		"_agents['current_id'] = get_agent_id()\n"
		"_result = _agents\n"
	));

	CachedAgents.Empty();
	CurrentAgentId.Empty();

	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ResultJson);
	if (FJsonSerializer::Deserialize(Reader, JsonObj) && JsonObj.IsValid())
	{
		CurrentAgentId = JsonObj->GetStringField(TEXT("current_id"));

		const TArray<TSharedPtr<FJsonValue>>* AgentsArray = nullptr;
		if (JsonObj->TryGetArrayField(TEXT("agents"), AgentsArray) && AgentsArray)
		{
			for (const auto& Val : *AgentsArray)
			{
				const TSharedPtr<FJsonObject>* AgentObj = nullptr;
				if (Val->TryGetObject(AgentObj) && AgentObj)
				{
					FAgentEntry Entry;
					Entry.Id = (*AgentObj)->GetStringField(TEXT("id"));
					Entry.Name = (*AgentObj)->GetStringField(TEXT("name"));
					Entry.Emoji = (*AgentObj)->GetStringField(TEXT("emoji"));
					CachedAgents.Add(MoveTemp(Entry));
				}
			}
		}
	}
}

FReply SUEAgentDashboard::OnRefreshAgentsClicked()
{
	// 异步从 Gateway 拉取 Agent 列表
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString ResultFile = TempDir / TEXT("_agents_list.json");
	IFileManager::Get().Delete(*ResultFile, false, false, true);

	PlatformBridge->ListAgents(ResultFile);

	// 轮询结果
	auto Self = SharedThis(this);
	FString CapturedFile = ResultFile;
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedFile](float) -> bool
		{
			if (!FPaths::FileExists(CapturedFile))
			{
				return true; // 继续等待
			}

			TArray<uint8> RawBytes;
			if (!FFileHelper::LoadFileToArray(RawBytes, *CapturedFile))
			{
				IFileManager::Get().Delete(*CapturedFile, false, false, true);
				return false;
			}

			FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
			FString JsonContent(Converter.Length(), Converter.Get());
			IFileManager::Get().Delete(*CapturedFile, false, false, true);

			// 解析
			TSharedPtr<FJsonObject> JsonObj;
			TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
			if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
			{
				Self->AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("AgentRefreshFail")));
				return false;
			}

			// 检查错误
			FString Error;
			if (JsonObj->TryGetStringField(TEXT("error"), Error) && !Error.IsEmpty())
			{
				Self->AddMessage(TEXT("system"),
					FUEAgentL10n::GetStr(TEXT("AgentRefreshFail")) + TEXT(" ") + Error);
				return false;
			}

			// 更新缓存
			Self->CachedAgents.Empty();
			const TArray<TSharedPtr<FJsonValue>>* AgentsArray = nullptr;
			if (JsonObj->TryGetArrayField(TEXT("agents"), AgentsArray) && AgentsArray)
			{
				for (const auto& Val : *AgentsArray)
				{
					const TSharedPtr<FJsonObject>* AgentObj = nullptr;
					if (Val->TryGetObject(AgentObj) && AgentObj)
					{
						FAgentEntry Entry;
						Entry.Id = (*AgentObj)->GetStringField(TEXT("id"));
						Entry.Name = (*AgentObj)->GetStringField(TEXT("name"));
						Entry.Emoji = (*AgentObj)->GetStringField(TEXT("emoji"));
						Self->CachedAgents.Add(MoveTemp(Entry));
					}
				}
			}

			Self->RebuildAgentListUI();
			Self->AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("AgentRefreshDone")));

			return false;
		}),
		0.5f
	);

	return FReply::Handled();
}

void SUEAgentDashboard::OnAgentSelected(const FString& AgentId)
{
	if (AgentId == CurrentAgentId)
	{
		return; // 已经是当前 Agent
	}

	// --- 保存当前 Agent 的会话到缓存 ---
	if (!CurrentAgentId.IsEmpty())
	{
		// 先把当前消息存入活跃 session entry
		if (ActiveSessionIndex >= 0 && SessionEntries.IsValidIndex(ActiveSessionIndex))
		{
			FString CurrentKey = PlatformBridge->GetSessionKey();
			if (!CurrentKey.IsEmpty())
			{
				SessionEntries[ActiveSessionIndex].SessionKey = CurrentKey;
			}
			SessionEntries[ActiveSessionIndex].CachedMessages = Messages;
		}
		AgentSessionCache.Add(CurrentAgentId, SessionEntries);
	}

	// 通过平台桥接切换 Agent
	PlatformBridge->SetAgentId(AgentId);
	FString PreviousAgentId = CurrentAgentId;
	CurrentAgentId = AgentId;

	// --- 恢复目标 Agent 的会话 ---
	TArray<FSessionEntry>* CachedSessions = AgentSessionCache.Find(AgentId);
	if (CachedSessions && CachedSessions->Num() > 0)
	{
		// 恢复缓存的会话列表
		SessionEntries = *CachedSessions;

		// 找到之前活跃的 session（或默认最后一个）
		ActiveSessionIndex = SessionEntries.Num() - 1;
		for (int32 i = 0; i < SessionEntries.Num(); ++i)
		{
			if (SessionEntries[i].bIsActive)
			{
				ActiveSessionIndex = i;
				break;
			}
		}
		SessionEntries[ActiveSessionIndex].bIsActive = true;
		CurrentSessionLabel = SessionEntries[ActiveSessionIndex].Label;

		// 恢复消息
		if (SessionEntries[ActiveSessionIndex].CachedMessages.Num() > 0)
		{
			Messages = SessionEntries[ActiveSessionIndex].CachedMessages;
		}
		else
		{
			Messages.Empty();
		}
		RebuildMessageList();

		// 恢复 Python 端的 session key
		FString RestoredKey = SessionEntries[ActiveSessionIndex].SessionKey;
		if (!RestoredKey.IsEmpty())
		{
			PlatformBridge->SetSessionKey(RestoredKey);
		}
	}
	else
	{
		// 目标 Agent 无缓存 — 创建新会话
		SessionEntries.Empty();
		Messages.Empty();
		RebuildMessageList();
		InitFirstSession();
	}

	// 重置 token usage
	LastTotalTokens = 0;

	// 找到 Agent 名称
	FString AgentDisplay = AgentId;
	for (const auto& A : CachedAgents)
	{
		if (A.Id == AgentId)
		{
			AgentDisplay = A.Emoji.IsEmpty()
				? A.Name
				: FString::Printf(TEXT("%s %s"), *A.Emoji, *A.Name);
			break;
		}
	}

	AddMessage(TEXT("system"),
		FUEAgentL10n::GetStr(TEXT("AgentSwitched")) + AgentDisplay);

	// 刷新 Agent 列表 UI（更新 [当前] 标记）
	RebuildAgentListUI();
}

void SUEAgentDashboard::RebuildAgentListUI()
{
	if (!AgentListBox.IsValid())
	{
		return;
	}

	AgentListBox->ClearChildren();

	if (CachedAgents.Num() == 0)
	{
		AgentListBox->AddSlot()
		.AutoHeight()
		.Padding(4.0f)
		[
			SNew(STextBlock)
			.Text(FUEAgentL10n::Get(TEXT("AgentNone")))
			.Font(FCoreStyle::GetDefaultFontStyle("Italic", 9))
			.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
		];
		return;
	}

	auto Self = SharedThis(this);

	for (const FAgentEntry& Agent : CachedAgents)
	{
		const bool bIsCurrent = (Agent.Id == CurrentAgentId);
		FString CapturedId = Agent.Id;

		// 显示: emoji + name (id) [当前]
		FString DisplayText = Agent.Emoji.IsEmpty()
			? FString::Printf(TEXT("%s (%s)"), *Agent.Name, *Agent.Id)
			: FString::Printf(TEXT("%s %s (%s)"), *Agent.Emoji, *Agent.Name, *Agent.Id);

		if (bIsCurrent)
		{
			DisplayText += TEXT("  ") + FUEAgentL10n::GetStr(TEXT("AgentCurrent"));
		}

		FLinearColor BtnColor = bIsCurrent
			? FLinearColor(0.2f, 0.45f, 0.7f)  // 蓝色高亮
			: FLinearColor(0.22f, 0.22f, 0.22f); // 默认灰

		AgentListBox->AddSlot()
		.AutoHeight()
		.Padding(2.0f, 1.0f)
		[
			SNew(SButton)
			.Text(FText::FromString(DisplayText))
			.OnClicked_Lambda([Self, CapturedId]() -> FReply
			{
				Self->OnAgentSelected(CapturedId);
				return FReply::Handled();
			})
			.ButtonColorAndOpacity(FSlateColor(BtnColor))
			.ContentPadding(FMargin(8.0f, 4.0f))
		];
	}
}

// ==================================================================
// 平台切换
// ==================================================================

void SUEAgentDashboard::LoadAvailablePlatforms()
{
	// 通过 Python bridge_config.get_available_platforms() 获取平台列表
	FString ResultJson = FUEAgentManageUtils::RunPythonAndCapture(TEXT(
		"import json\n"
		"from bridge_config import get_available_platforms, get_platform_type\n"
		"_platforms = get_available_platforms()\n"
		"_result = {'platforms': _platforms, 'current': get_platform_type()}\n"
	));

	AvailablePlatforms.Empty();
	CurrentPlatformType.Empty();

	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ResultJson);
	if (FJsonSerializer::Deserialize(Reader, JsonObj) && JsonObj.IsValid())
	{
		CurrentPlatformType = JsonObj->GetStringField(TEXT("current"));

		const TArray<TSharedPtr<FJsonValue>>* PlatArray = nullptr;
		if (JsonObj->TryGetArrayField(TEXT("platforms"), PlatArray) && PlatArray)
		{
			for (const auto& Val : *PlatArray)
			{
				const TSharedPtr<FJsonObject>* PlatObj = nullptr;
				if (Val->TryGetObject(PlatObj) && PlatObj)
				{
					FPlatformEntry Entry;
					Entry.Type = (*PlatObj)->GetStringField(TEXT("type"));
					Entry.DisplayName = (*PlatObj)->GetStringField(TEXT("display_name"));
					Entry.GatewayUrl = (*PlatObj)->GetStringField(TEXT("gateway_url"));
					(*PlatObj)->TryGetBoolField(TEXT("configured"), Entry.bConfigured);
					AvailablePlatforms.Add(MoveTemp(Entry));
				}
			}
		}
	}
}

void SUEAgentDashboard::OnPlatformSelected(const FString& PlatformType)
{
	if (PlatformType == CurrentPlatformType)
	{
		return;
	}

	// 1. 调用 Python bridge_config.switch_platform() 写入 config
	FString EscapedType = PlatformType;
	EscapedType.ReplaceInline(TEXT("'"), TEXT("\\'"));
	FString SwitchCmd = FString::Printf(
		TEXT("from bridge_config import switch_platform\n")
		TEXT("switch_platform('%s')\n"),
		*EscapedType
	);
	IPythonScriptPlugin::Get()->ExecPythonCommand(*SwitchCmd);

	// 2. 断开旧连接
	PlatformBridge->Disconnect();

	// 3. 重新连接（Python 端会重新读 config，拿到新 gateway url/token）
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString StatusFile = TempDir / TEXT("_connect_status.txt");
	IFileManager::Get().Delete(*StatusFile, false, false, true);
	PlatformBridge->Connect(StatusFile);

	// 4. 更新 UI 状态
	FString PreviousType = CurrentPlatformType;
	CurrentPlatformType = PlatformType;

	// 找到显示名称
	FString DisplayName = PlatformType;
	for (const auto& P : AvailablePlatforms)
	{
		if (P.Type == PlatformType)
		{
			DisplayName = P.DisplayName;
			break;
		}
	}

	// 5. 重置 session（新平台的 agent 列表可能不同）
	PlatformBridge->ResetSession();
	SessionEntries.Empty();
	AgentSessionCache.Empty();
	Messages.Empty();
	RebuildMessageList();
	InitFirstSession();

	// 6. 刷新 Agent 列表并自动切换到第一个可用 Agent
	{
		FString AgentResultFile = TempDir / TEXT("_platform_switch_agents.json");
		IFileManager::Get().Delete(*AgentResultFile, false, false, true);
		PlatformBridge->ListAgents(AgentResultFile);

		auto Self = SharedThis(this);
		FString CapturedAgentFile = AgentResultFile;
		FString CapturedDisplayName = DisplayName;
		FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateLambda([Self, CapturedAgentFile, CapturedDisplayName](float) -> bool
			{
				if (!FPaths::FileExists(CapturedAgentFile))
				{
					return true; // 继续等待
				}

				TArray<uint8> RawBytes;
				if (!FFileHelper::LoadFileToArray(RawBytes, *CapturedAgentFile))
				{
					IFileManager::Get().Delete(*CapturedAgentFile, false, false, true);
					return false;
				}

				FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
				FString JsonContent(Converter.Length(), Converter.Get());
				IFileManager::Get().Delete(*CapturedAgentFile, false, false, true);

				TSharedPtr<FJsonObject> JsonObj;
				TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
				if (FJsonSerializer::Deserialize(Reader, JsonObj) && JsonObj.IsValid())
				{
					Self->CachedAgents.Empty();
					const TArray<TSharedPtr<FJsonValue>>* AgentsArray = nullptr;
					if (JsonObj->TryGetArrayField(TEXT("agents"), AgentsArray) && AgentsArray)
					{
						for (const auto& Val : *AgentsArray)
						{
							const TSharedPtr<FJsonObject>* AgentObj = nullptr;
							if (Val->TryGetObject(AgentObj) && AgentObj)
							{
								FAgentEntry Entry;
								Entry.Id = (*AgentObj)->GetStringField(TEXT("id"));
								Entry.Name = (*AgentObj)->GetStringField(TEXT("name"));
								Entry.Emoji = (*AgentObj)->GetStringField(TEXT("emoji"));
								Self->CachedAgents.Add(MoveTemp(Entry));
							}
						}
					}

					// 自动选第一个 Agent
					if (Self->CachedAgents.Num() > 0)
					{
						const FAgentEntry& First = Self->CachedAgents[0];
						Self->CurrentAgentId = First.Id;
						Self->PlatformBridge->SetAgentId(First.Id);
					}

					Self->RebuildAgentListUI();
				}

				Self->AddMessage(TEXT("system"),
					FString::Printf(TEXT("%s %s"),
						*FUEAgentL10n::GetStr(TEXT("PlatformSwitched")),
						*CapturedDisplayName));

				return false;
			}),
			0.5f
		);
	}

	// 7. 刷新 Skill 安装目录（不同平台 Skills 路径不同）
	{
		FString SkillReloadCmd = TEXT(
			"try:\n"
			"    from skill_hub import get_skill_hub\n"
			"    _hub = get_skill_hub()\n"
			"    if _hub:\n"
			"        _count = _hub.reload_skills_dir()\n"
			"        print(f'Skills reloaded after platform switch: {_count}')\n"
			"except Exception as _e:\n"
			"    print(f'Skill reload failed: {_e}')\n"
		);
		IPythonScriptPlugin::Get()->ExecPythonCommand(*SkillReloadCmd);
	}

	// 8. 刷新平台 UI
	RebuildPlatformListUI();
}

void SUEAgentDashboard::RebuildPlatformListUI()
{
	if (!PlatformListBox.IsValid())
	{
		return;
	}

	// 加载最新平台列表
	LoadAvailablePlatforms();

	PlatformListBox->ClearChildren();

	if (AvailablePlatforms.Num() == 0)
	{
		PlatformListBox->AddSlot()
		.AutoWidth()
		.Padding(4.0f)
		[
			SNew(STextBlock)
			.Text(FText::FromString(TEXT("(No platforms)")))
			.Font(FCoreStyle::GetDefaultFontStyle("Italic", 9))
			.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
		];
		return;
	}

	auto Self = SharedThis(this);

	for (const FPlatformEntry& Plat : AvailablePlatforms)
	{
		const bool bIsCurrent = (Plat.Type == CurrentPlatformType);
		FString CapturedType = Plat.Type;

		// 状态指示: ● (已配置/绿色) 或 ○ (未配置/灰色)
		FString StatusDot = Plat.bConfigured ? TEXT("\u25CF ") : TEXT("\u25CB ");
		FString BtnText = StatusDot + Plat.DisplayName;

		FLinearColor BtnColor = bIsCurrent
			? FLinearColor(0.2f, 0.45f, 0.7f)   // 蓝色高亮
			: FLinearColor(0.22f, 0.22f, 0.22f);  // 默认灰

		PlatformListBox->AddSlot()
		.AutoWidth()
		.Padding(2.0f, 0.0f)
		[
			SNew(SButton)
			.Text(FText::FromString(BtnText))
			.OnClicked_Lambda([Self, CapturedType]() -> FReply
			{
				Self->OnPlatformSelected(CapturedType);
				return FReply::Handled();
			})
			.ButtonColorAndOpacity(FSlateColor(BtnColor))
			.ContentPadding(FMargin(10.0f, 4.0f))
		];
	}
}

// ==================================================================
// Tool Manager 入口
// ==================================================================

FReply SUEAgentDashboard::OnOpenToolManagerClicked()
{
	// 使用 core/tool_manager_launcher.py 统一启动逻辑
	// 先将 core/ 加入 sys.path，然后调用 launch()
	FString BridgeRoot;
	{
		FString RootJson = FUEAgentManageUtils::RunPythonAndCapture(TEXT(
			"import os, json\n"
			"_root = ''\n"
			"try:\n"
			"    _cfg_path = os.path.expanduser('~/.artclaw/config.json')\n"
			"    with open(_cfg_path, 'r', encoding='utf-8') as _f:\n"
			"        _cfg = json.load(_f)\n"
			"    _root = _cfg.get('project_root', '')\n"
			"except Exception:\n"
			"    pass\n"
			"_result = {'root': _root}\n"
		));
		TSharedPtr<FJsonObject> RootObj;
		TSharedRef<TJsonReader<>> RootReader = TJsonReaderFactory<>::Create(RootJson);
		if (FJsonSerializer::Deserialize(RootReader, RootObj) && RootObj.IsValid())
		{
			BridgeRoot = RootObj->GetStringField(TEXT("root"));
		}
	}

	if (BridgeRoot.IsEmpty())
	{
		AddMessage(TEXT("system"), TEXT("[Tool Manager] 无法获取项目根目录，请检查 ~/.artclaw/config.json 中的 project_root 字段"));
		return FReply::Handled();
	}

	FString EscapedRoot = BridgeRoot.Replace(TEXT("\\"), TEXT("\\\\"));
	FString LaunchScript = FString::Printf(
		TEXT(
			"import sys, os, json\n"
			"_core_dir = os.path.join('%s', 'core')\n"
			"if _core_dir not in sys.path:\n"
			"    sys.path.insert(0, _core_dir)\n"
			"try:\n"
			"    from tool_manager_launcher import launch\n"
			"    _r = launch(open_browser=True)\n"
			"    _result = {'ok': _r['ok'], 'already_running': _r.get('already_running', False), 'error': _r.get('error', '')}\n"
			"except Exception as _e:\n"
			"    _result = {'ok': False, 'already_running': False, 'error': str(_e)}\n"
		),
		*EscapedRoot
	);
	FString LaunchJson = FUEAgentManageUtils::RunPythonAndCapture(*LaunchScript);
	TSharedPtr<FJsonObject> LaunchObj;
	TSharedRef<TJsonReader<>> LaunchReader = TJsonReaderFactory<>::Create(LaunchJson);
	if (FJsonSerializer::Deserialize(LaunchReader, LaunchObj) && LaunchObj.IsValid())
	{
		bool bOk = false;
		LaunchObj->TryGetBoolField(TEXT("ok"), bOk);
		if (!bOk)
		{
			FString ErrMsg;
			LaunchObj->TryGetStringField(TEXT("error"), ErrMsg);
			AddMessage(TEXT("system"),
				FString::Printf(TEXT("[Tool Manager] 启动失败: %s"), *ErrMsg));
			return FReply::Handled();
		}

		bool bAlreadyRunning = false;
		LaunchObj->TryGetBoolField(TEXT("already_running"), bAlreadyRunning);
		if (!bAlreadyRunning)
		{
			AddMessage(TEXT("system"), TEXT("[Tool Manager] 正在启动服务，请稍候..."));
		}
	}

	return FReply::Handled();
}