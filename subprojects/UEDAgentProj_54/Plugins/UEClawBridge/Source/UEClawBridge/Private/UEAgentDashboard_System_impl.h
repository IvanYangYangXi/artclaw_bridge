// Copyright ArtClaw Project. All Rights Reserved. 
// 系统功能模块 - 技能创建、语言切换、确认对话框、静默模式
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// 阶段 D: Skill 创建集成 (v2 — 对话式，无弹窗)
// ==================================================================

FReply SUEAgentDashboard::OnCreateSkillClicked()
{
	// 在输入框填充引导文本
	if (InputTextBox.IsValid())
	{
		FString GuideText = TEXT("I want to create a new skill that can help me with UE editor tasks. Please guide me through the process.");
		InputTextBox->SetText(FText::FromString(GuideText));
		FSlateApplication::Get().SetKeyboardFocus(InputTextBox);
	}
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnManageClicked()
{
	// 打开 Skill/MCP 管理独立窗口
	if (ManageWindow.IsValid())
	{
		ManageWindow->BringToFront();
		return FReply::Handled();
	}

	auto Self = SharedThis(this);
	ManageWindow = SNew(SWindow)
		.Title(FUEAgentL10n::Get(TEXT("ManageWindowTitle")))
		.ClientSize(FVector2D(600.0f, 500.0f))
		.SupportsMinimize(false)
		.SupportsMaximize(false)
		[
			SNew(SBorder)
			.BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
			.Padding(0.0f)
			[
				SAssignNew(ManagePanelWidget, SUEAgentManagePanel)
			]
		];

	ManageWindow->SetOnWindowClosed(FOnWindowClosed::CreateLambda([Self](const TSharedRef<SWindow>&)
	{
		Self->ManageWindow.Reset();
		Self->ManagePanelWidget.Reset();
		// 刷新 Chat Panel 的钉选 Skill 标签（用户可能在管理面板中钉选/取消了）
		Self->LoadPinnedSkills();
		Self->RebuildPinnedSkillsUI();
	}));

	FUEAgentManageUtils::AddChildWindow(ManageWindow.ToSharedRef());
	return FReply::Handled();
}

// ==================================================================
// 语言切换
// ==================================================================

FReply SUEAgentDashboard::OnToggleLanguageClicked()
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

	// 重建整个 UI
	RebuildAfterLanguageChange();

	return FReply::Handled();
}

void SUEAgentDashboard::RebuildAfterLanguageChange()
{
	// 重建整个 UI（刷新所有文本）
	// 由于 Construct 方法包含大量 Slate 声明，这里简化处理
	// 实际项目中可能需要将 UI 构建逻辑提取为单独方法
	Messages.Empty();
	RebuildMessageList();
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("LanguageChanged")));
}

// ==================================================================
// 文件操作确认弹窗 (阶段 5.6)
// ==================================================================

void SUEAgentDashboard::PollConfirmationRequests()
{
	FString ConfirmFile = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge/_confirm_request.json");
	if (!FPaths::FileExists(ConfirmFile))
	{
		return;
	}

	FString JsonContent;
	TArray<uint8> RawBytes;
	if (!FFileHelper::LoadFileToArray(RawBytes, *ConfirmFile))
	{
		return;
	}

	FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
	JsonContent = FString(Converter.Length(), Converter.Get());

	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
	{
		IFileManager::Get().Delete(*ConfirmFile, false, false, true);
		return;
	}

	FString RiskLevel = JsonObj->GetStringField(TEXT("riskLevel"));
	FString CodePreview = JsonObj->GetStringField(TEXT("codePreview"));

	// 删除请求文件（无论是否弹窗）
	IFileManager::Get().Delete(*ConfirmFile, false, false, true);

	// 静默模式检查：按风险级别自动批准
	bool bAutoApprove = false;
	if (RiskLevel == TEXT("medium") && bSilentMedium)
	{
		bAutoApprove = true;
	}
	else if (RiskLevel == TEXT("high") && bSilentHigh)
	{
		bAutoApprove = true;
	}

	if (bAutoApprove)
	{
		// 静默模式：直接写入批准响应，不弹窗
		FString ResponseFile = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge/_confirm_response.json");
		FFileHelper::SaveStringToFile(TEXT("yes"), *ResponseFile);
		AddMessage(TEXT("system"),
			FString::Printf(TEXT("[%s] %s"),
				*RiskLevel,
				*FUEAgentL10n::GetStr(TEXT("ConfirmSessionSilent"))));
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* OperationsArray = nullptr;
	JsonObj->TryGetArrayField(TEXT("operations"), OperationsArray);

	TArray<TSharedPtr<FJsonValue>> Operations;
	if (OperationsArray)
	{
		Operations = *OperationsArray;
	}

	// 显示确认对话框
	ShowConfirmationDialog(RiskLevel, Operations, CodePreview);
}

void SUEAgentDashboard::ShowConfirmationDialog(const FString& RiskLevel,
	const TArray<TSharedPtr<FJsonValue>>& Operations,
	const FString& CodePreview)
{
	auto Self = SharedThis(this);
	FString CapturedRiskLevel = RiskLevel;

	// 构建操作列表文本
	FString OpsText;
	for (const auto& OpVal : Operations)
	{
		const TSharedPtr<FJsonObject>* OpObj = nullptr;
		if (OpVal->TryGetObject(OpObj) && OpObj)
		{
			FString OpType = (*OpObj)->GetStringField(TEXT("type"));
			FString OpPath = (*OpObj)->GetStringField(TEXT("path"));
			OpsText += FString::Printf(TEXT("  %s: %s\n"), *OpType, *OpPath);
		}
	}

	// 风险级别颜色和标签
	FLinearColor RiskColor = RiskLevel == TEXT("high")
		? FLinearColor(0.9f, 0.2f, 0.2f)
		: FLinearColor(0.9f, 0.7f, 0.2f);
	FString RiskLabel = RiskLevel == TEXT("high")
		? FUEAgentL10n::GetStr(TEXT("RiskHigh"))
		: FUEAgentL10n::GetStr(TEXT("RiskMedium"));

	// "Don't ask again" 状态
	TSharedPtr<bool> bDontAskAgain = MakeShared<bool>(false);

	// 构建自定义确认窗口
	TSharedRef<SWindow> ConfirmWindowRef = SNew(SWindow)
		.Title(FText::FromString(FUEAgentL10n::GetStr(TEXT("ConfirmTitle"))))
		.ClientSize(FVector2D(450.0f, 340.0f))
		.SupportsMinimize(false)
		.SupportsMaximize(false)
		.IsTopmostWindow(true);

	// 用 TWeakPtr 避免循环引用
	TWeakPtr<SWindow> WeakConfirmWindow = ConfirmWindowRef;

	ConfirmWindowRef->SetContent(
		SNew(SBorder)
		.Padding(16.0f)
		.BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
		[
			SNew(SVerticalBox)

			// 风险级别标签
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(STextBlock)
				.Text(FText::FromString(RiskLabel))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
				.ColorAndOpacity(FSlateColor(RiskColor))
			]

			// 说明文本
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ConfirmMessage"))))
				.AutoWrapText(true)
			]

			// 操作列表
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(OpsText.IsEmpty() ? TEXT("") : OpsText))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.7f, 0.7f, 0.7f)))
			]

			// 代码预览
			+ SVerticalBox::Slot()
			.FillHeight(1.0f)
			.Padding(0.0f, 4.0f, 0.0f, 0.0f)
			[
				SNew(SBorder)
				.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.GroupBorder"))
				.Padding(6.0f)
				.Visibility(CodePreview.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible)
				[
					SNew(SScrollBox)
					+ SScrollBox::Slot()
					[
						SNew(STextBlock)
						.Text(FText::FromString(CodePreview.Left(800)))
						.Font(FCoreStyle::GetDefaultFontStyle("Mono", 8))
						.AutoWrapText(true)
					]
				]
			]

			// 分隔线
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f)
			[
				SNew(SSeparator)
			]

			// "不再提示此风险级别" 复选框
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 8.0f)
			[
				SNew(SCheckBox)
				.OnCheckStateChanged_Lambda([bDontAskAgain](ECheckBoxState NewState)
				{
					*bDontAskAgain = (NewState == ECheckBoxState::Checked);
				})
				[
					SNew(STextBlock)
					.Text(FText::FromString(
						FUEAgentL10n::GetStr(TEXT("ConfirmDontAsk")) + TEXT(" (") + RiskLabel + TEXT(")")
					))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
				]
			]

			// 按钮行
			+ SVerticalBox::Slot()
			.AutoHeight()
			.HAlign(HAlign_Right)
			[
				SNew(SHorizontalBox)
				// 拒绝按钮
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(0.0f, 0.0f, 8.0f, 0.0f)
				[
					SNew(SButton)
					.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ConfirmDeny"))))
					.ContentPadding(FMargin(16.0f, 4.0f))
					.ButtonColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.25f, 0.25f)))
					.OnClicked_Lambda([WeakConfirmWindow]()
					{
						FString ResponseFile = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge/_confirm_response.json");
						FFileHelper::SaveStringToFile(TEXT("no"), *ResponseFile);
						if (TSharedPtr<SWindow> Win = WeakConfirmWindow.Pin())
						{
							Win->RequestDestroyWindow();
						}
						return FReply::Handled();
					})
				]
				// 批准按钮
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(SButton)
					.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ConfirmAllow"))))
					.ContentPadding(FMargin(16.0f, 4.0f))
					.ButtonColorAndOpacity(FSlateColor(FLinearColor(0.2f, 0.5f, 0.3f)))
					.OnClicked_Lambda([Self, CapturedRiskLevel, bDontAskAgain, WeakConfirmWindow]()
					{
						FString ResponseFile = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge/_confirm_response.json");
						FFileHelper::SaveStringToFile(TEXT("yes"), *ResponseFile);

						if (*bDontAskAgain)
						{
							if (CapturedRiskLevel == TEXT("medium"))
							{
								Self->bSilentMedium = true;
							}
							else if (CapturedRiskLevel == TEXT("high"))
							{
								Self->bSilentHigh = true;
							}
							Self->SaveSilentModeToConfig();
							Self->AddMessage(TEXT("system"),
								FUEAgentL10n::GetStr(TEXT("ConfirmSilentEnabled")));
						}

						if (TSharedPtr<SWindow> Win = WeakConfirmWindow.Pin())
						{
							Win->RequestDestroyWindow();
						}
						return FReply::Handled();
					})
				]
			]
		]
	);

	FUEAgentManageUtils::AddChildWindow(ConfirmWindowRef);
}

// ==================================================================
// 静默模式 (阶段 5.7)
// ==================================================================

void SUEAgentDashboard::LoadSilentModeFromConfig()
{
	// 读取 ~/.artclaw/config.json（与 SaveContextWindowSize 同一配置文件）
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

	JsonObj->TryGetBoolField(TEXT("silent_mode_medium"), bSilentMedium);
	JsonObj->TryGetBoolField(TEXT("silent_mode_high"), bSilentHigh);
}

void SUEAgentDashboard::SaveSilentModeToConfig()
{
	// 读取 → 合并 → 写回（不覆盖其他字段）
	FString ConfigPath = FPlatformProcess::UserHomeDir();
	ConfigPath = FPaths::Combine(ConfigPath, TEXT(".artclaw"), TEXT("config.json"));

	TSharedPtr<FJsonObject> JsonObj = MakeShared<FJsonObject>();

	// 先读取现有内容
	FString JsonContent;
	if (FFileHelper::LoadFileToString(JsonContent, *ConfigPath))
	{
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
		TSharedPtr<FJsonObject> ExistingObj;
		if (FJsonSerializer::Deserialize(Reader, ExistingObj) && ExistingObj.IsValid())
		{
			JsonObj = ExistingObj;
		}
	}

	// 合并静默模式字段
	JsonObj->SetBoolField(TEXT("silent_mode_medium"), bSilentMedium);
	JsonObj->SetBoolField(TEXT("silent_mode_high"), bSilentHigh);

	// 写回
	FString Dir = FPaths::GetPath(ConfigPath);
	IFileManager::Get().MakeDirectory(*Dir, true);

	FString OutputStr;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputStr);
	FJsonSerializer::Serialize(JsonObj.ToSharedRef(), Writer);

	FFileHelper::SaveStringToFile(OutputStr, *ConfigPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

FReply SUEAgentDashboard::OnToggleSilentMediumClicked()
{
	bSilentMedium = !bSilentMedium;
	SaveSilentModeToConfig();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnToggleSilentHighClicked()
{
	bSilentHigh = !bSilentHigh;
	SaveSilentModeToConfig();
	return FReply::Handled();
}

// ==================================================================
// 保存拦截配置 Load/Save
// ==================================================================

void SUEAgentDashboard::LoadSaveInterceptFromConfig()
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

	// 同步到 Subsystem
	if (CachedSubsystem.IsValid())
	{
		CachedSubsystem->SetSaveInterceptSilentPass(bSaveInterceptSilentPass);
	}
}

void SUEAgentDashboard::SaveSaveInterceptToConfig()
{
	FString ConfigPath = FPlatformProcess::UserHomeDir();
	ConfigPath = FPaths::Combine(ConfigPath, TEXT(".artclaw"), TEXT("config.json"));

	TSharedPtr<FJsonObject> JsonObj = MakeShared<FJsonObject>();

	FString JsonContent;
	if (FFileHelper::LoadFileToString(JsonContent, *ConfigPath))
	{
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
		TSharedPtr<FJsonObject> ExistingObj;
		if (FJsonSerializer::Deserialize(Reader, ExistingObj) && ExistingObj.IsValid())
		{
			JsonObj = ExistingObj;
		}
	}

	JsonObj->SetBoolField(TEXT("save_intercept_silent_pass"), bSaveInterceptSilentPass);

	FString Dir = FPaths::GetPath(ConfigPath);
	IFileManager::Get().MakeDirectory(*Dir, true);

	FString OutputStr;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputStr);
	FJsonSerializer::Serialize(JsonObj.ToSharedRef(), Writer);

	FFileHelper::SaveStringToFile(OutputStr, *ConfigPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}