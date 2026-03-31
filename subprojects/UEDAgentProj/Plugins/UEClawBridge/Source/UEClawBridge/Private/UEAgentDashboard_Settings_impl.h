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

	// 记录当前状态（用于取消时恢复）
	const bool OrigSilentMedium = bSilentMedium;
	const bool OrigSilentHigh = bSilentHigh;
	const bool OrigPlanMode = bPlanMode;
	const bool OrigEnterToSend = bEnterToSend;
	const int32 OrigContextWindowSize = ContextWindowSize;

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
				SNew(SVerticalBox)

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
					.OnClicked_Lambda([Self]() { Self->ContextWindowSize = 128000; return FReply::Handled(); })
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
					.OnClicked_Lambda([Self]() { Self->ContextWindowSize = 200000; return FReply::Handled(); })
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
					.OnClicked_Lambda([Self]() { Self->ContextWindowSize = 500000; return FReply::Handled(); })
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
			.FillHeight(1.0f)
			[
				SNew(SSpacer)
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.HAlign(HAlign_Right)
			.Padding(0.0f, 8.0f, 0.0f, 0.0f)
			[
				SNew(SButton)
				.Text(FUEAgentL10n::Get(TEXT("SettingsCloseBtn")))
				.OnClicked_Lambda([Self, OrigSilentMedium, OrigSilentHigh, OrigPlanMode, OrigEnterToSend, OrigContextWindowSize]()
				{
					// 保存静默模式配置（仅在变更时）
					if (Self->bSilentMedium != OrigSilentMedium || Self->bSilentHigh != OrigSilentHigh)
					{
						Self->SaveSilentModeToConfig();
					}

					// 保存上下文窗口大小（仅在变更时）
					if (Self->ContextWindowSize != OrigContextWindowSize)
					{
						Self->SaveContextWindowSize();
					}

					// 关闭窗口
					if (Self->SettingsWindow.IsValid())
					{
						Self->SettingsWindow->RequestDestroyWindow();
						Self->SettingsWindow.Reset();
					}
					return FReply::Handled();
				})
				.ContentPadding(FMargin(16.0f, 4.0f))
			]
			]
		];

	// 显示窗口，作为模态窗口
	SettingsWindow->SetOnWindowClosed(FOnWindowClosed::CreateLambda([Self](const TSharedRef<SWindow>&)
	{
		Self->SettingsWindow.Reset();
	}));

	FUEAgentManageUtils::AddChildWindow(SettingsWindow.ToSharedRef());

	// Agent 列表 UI 构建（必须在 AgentListBox 已赋值之后）
	RebuildAgentListUI();

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
