// Copyright ArtClaw Project. All Rights Reserved.
// Skill Tab — Phase 3/4 操作: 启用/禁用/钉选/详情/安装/卸载/同步/发布
// 所有 include 由 UEAgentSkillTab.cpp 统一管理

#define LOCTEXT_NAMESPACE "UEAgentSkillTab"

// ==================================================================
// Phase 3 Actions
// ==================================================================

void SUEAgentSkillTab::OnEnableChanged(ECheckBoxState NewState, FSkillEntryPtr Item)
{
	Item->bEnabled = (NewState == ECheckBoxState::Checked);
	ExecuteSkillAction(Item->bEnabled ? TEXT("enable") : TEXT("disable"), Item->Name);
}

FReply SUEAgentSkillTab::OnPinClicked(FSkillEntryPtr Item)
{
	Item->bPinned = !Item->bPinned;
	ExecuteSkillAction(Item->bPinned ? TEXT("pin") : TEXT("unpin"), Item->Name);
	RequestRefresh();
	return FReply::Handled();
}

FReply SUEAgentSkillTab::OnDetailClicked(FSkillEntryPtr Item)
{
	FString InstallStr;
	if (Item->InstallStatus == EInstallStatus::Installed)
		InstallStr = FUEAgentL10n::GetStr(TEXT("ManageInstallFull"));
	else
		InstallStr = FUEAgentL10n::GetStr(TEXT("ManageInstallNotInstalled"));

	FString AuthorStr = Item->Author.IsEmpty() ? TEXT("-") : Item->Author;
	FString InstalledStr = Item->InstalledDir.IsEmpty() ? TEXT("-") : Item->InstalledDir;
	FString SourceStr = Item->SourceDir.IsEmpty() ? TEXT("-") : Item->SourceDir;

	// 版本显示：如果有源码版本且不同，显示两个版本号
	FString VersionStr = Item->Version.IsEmpty() ? TEXT("-") : Item->Version;
	if (Item->bUpdatable && !Item->SourceVersion.IsEmpty()
		&& Item->SourceVersion != Item->Version)
	{
		VersionStr = FString::Printf(TEXT("%s  (%s: %s)"),
			*VersionStr,
			*FUEAgentL10n::GetStr(TEXT("ManageDetailSourceVer")),
			*Item->SourceVersion);
	}

	FString DetailText = FString::Printf(
		TEXT("%s\n%s v%s\n\n%s\n\n%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s"),
		*Item->DisplayName, *Item->Name, *VersionStr,
		*Item->Description,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailAuthor")), *AuthorStr,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailLayer")), *Item->Layer,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailSoftware")), *Item->Software,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailCategory")), *Item->Category,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailRisk")), *Item->RiskLevel,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailInstall")), *InstallStr,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailCode")),
			Item->bHasCode ? TEXT("Yes") : TEXT("No"),
		*FUEAgentL10n::GetStr(TEXT("ManageDetailSkillMd")),
			Item->bHasSkillMd ? TEXT("Yes") : TEXT("No"),
		*FUEAgentL10n::GetStr(TEXT("ManageDetailInstalledPath")), *InstalledStr,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailSourcePath")), *SourceStr
	);

	FString CapturedInstDir = Item->InstalledDir;
	FString CapturedSrcDir = Item->SourceDir;
	bool bIsInstalled = (Item->InstallStatus != EInstallStatus::NotInstalled);
	FSkillEntryPtr CapturedItem = Item;

	TSharedRef<SWindow> Win = SNew(SWindow)
		.Title(FText::FromString(Item->DisplayName))
		.ClientSize(FVector2D(480, 420))
		.SupportsMinimize(false).SupportsMaximize(false);

	TWeakPtr<SWindow> WeakWin = Win;

	Win->SetContent(
		SNew(SVerticalBox)
			+ SVerticalBox::Slot()
			.FillHeight(1.0f)
			[
				SNew(SScrollBox) + SScrollBox::Slot().Padding(12)
				[
					SNew(SMultiLineEditableText)
					.Text(FText::FromString(DetailText))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
					.AutoWrapText(true)
					.IsReadOnly(true)
					.AllowContextMenu(true)
				]
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f, 4.0f, 12.0f, 4.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.0f).Padding(0, 0, 4, 0)
				[
					SNew(SButton)
					.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ManageOpenInstalledDir"))))
					.OnClicked_Lambda([CapturedInstDir]() -> FReply
					{
						if (!CapturedInstDir.IsEmpty())
							FPlatformProcess::ExploreFolder(*CapturedInstDir);
						return FReply::Handled();
					})
					.IsEnabled(!CapturedInstDir.IsEmpty())
					.HAlign(HAlign_Center)
				]
				+ SHorizontalBox::Slot().FillWidth(1.0f).Padding(4, 0, 0, 0)
				[
					SNew(SButton)
					.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ManageOpenSourceDir"))))
					.OnClicked_Lambda([CapturedSrcDir]() -> FReply
					{
						if (!CapturedSrcDir.IsEmpty())
							FPlatformProcess::ExploreFolder(*CapturedSrcDir);
						return FReply::Handled();
					})
					.IsEnabled(!CapturedSrcDir.IsEmpty())
					.HAlign(HAlign_Center)
				]
			]
			// 发布按钮行（仅已安装 Skill 可用，即使无修改也能手动发布）
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f, 2.0f, 12.0f, 2.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]
				+ SHorizontalBox::Slot().AutoWidth()
				[
					SNew(SButton)
					.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ManagePublishBtn"))))
					.OnClicked_Lambda([this, CapturedItem, WeakWin = TWeakPtr<SWindow>(Win)]() -> FReply
					{
						if (WeakWin.IsValid())
							WeakWin.Pin()->RequestDestroyWindow();
						OnPublishClicked(CapturedItem);
						return FReply::Handled();
					})
					.IsEnabled(bIsInstalled)
					.ContentPadding(FMargin(8, 3))
					.ToolTipText(FText::FromString(TEXT("将已安装的 Skill 发布到项目源码仓库（版本递增 + git commit）")))
				]
				+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f, 4.0f, 12.0f, 4.0f)
			[
				SNew(SButton)
				.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ManagePublishBtn"))))
				.OnClicked_Lambda([this, CapturedItem, WeakWin]() -> FReply
				{
					if (WeakWin.IsValid())
						WeakWin.Pin()->RequestDestroyWindow();
					OnPublishClicked(CapturedItem);
					return FReply::Handled();
				})
				.IsEnabled(bIsInstalled)
				.HAlign(HAlign_Center)
				.ToolTipText(FText::FromString(TEXT("Publish to source repo (version bump + git commit)")))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f, 0.0f, 12.0f, 8.0f)
			[
				SNew(SSpacer).Size(FVector2D(0, 4))
			]
		);
	FUEAgentManageUtils::AddChildWindow(Win);
	return FReply::Handled();
}

void SUEAgentSkillTab::ExecuteSkillAction(const FString& Action, const FString& SkillName)
{
	FString PyCode = FString::Printf(TEXT(
		"import json, os\n"
		"config_path = os.path.expanduser('~/.artclaw/config.json')\n"
		"cfg = {}\n"
		"if os.path.exists(config_path):\n"
		"    try:\n"
		"        with open(config_path, 'r', encoding='utf-8') as f:\n"
		"            cfg = json.load(f)\n"
		"    except: pass\n"
		"disabled = set(cfg.get('disabled_skills', []))\n"
		"pinned = list(cfg.get('pinned_skills', []))\n"
		"action = '%s'\n"
		"skill_name = '%s'\n"
		"if action == 'enable':\n"
		"    disabled.discard(skill_name)\n"
		"    from skill_hub import get_skill_hub\n"
		"    hub = get_skill_hub()\n"
		"    if hub: hub.enable_skill(skill_name)\n"
		"elif action == 'disable':\n"
		"    disabled.add(skill_name)\n"
		"    if skill_name in pinned: pinned.remove(skill_name)\n"
		"    from skill_hub import get_skill_hub\n"
		"    hub = get_skill_hub()\n"
		"    if hub: hub.disable_skill(skill_name)\n"
		"elif action == 'pin':\n"
		"    if skill_name not in pinned and len(pinned) < 5:\n"
		"        pinned.append(skill_name)\n"
		"    disabled.discard(skill_name)\n"
		"elif action == 'unpin':\n"
		"    if skill_name in pinned: pinned.remove(skill_name)\n"
		"cfg['disabled_skills'] = sorted(disabled)\n"
		"cfg['pinned_skills'] = pinned\n"
		"os.makedirs(os.path.dirname(config_path), exist_ok=True)\n"
		"with open(config_path, 'w', encoding='utf-8') as f:\n"
		"    json.dump(cfg, f, indent=2, ensure_ascii=False)\n"
		"_result = {'action': action, 'skill': skill_name, 'ok': True}\n"
	), *Action, *SkillName);

	FUEAgentManageUtils::RunPythonAndCapture(PyCode);
}

// ==================================================================
// Phase 4 Actions
// ==================================================================

FReply SUEAgentSkillTab::OnInstallClicked(FSkillEntryPtr Item)
{
	FString PyCode = FString::Printf(TEXT(
		"from skill_sync import install_skill\n"
		"_result = install_skill('%s')\n"
	), *Item->Name);
	RunSyncAction(PyCode);
	RequestRefresh();
	return FReply::Handled();
}

FReply SUEAgentSkillTab::OnUninstallClicked(FSkillEntryPtr Item)
{
	FString PyCode = FString::Printf(TEXT(
		"from skill_sync import uninstall_skill\n"
		"_result = uninstall_skill('%s')\n"
	), *Item->Name);
	RunSyncAction(PyCode);
	RequestRefresh();
	return FReply::Handled();
}

FReply SUEAgentSkillTab::OnUpdateClicked(FSkillEntryPtr Item)
{
	FString PyCode = FString::Printf(TEXT(
		"from skill_sync import update_skill\n"
		"_result = update_skill('%s')\n"
	), *Item->Name);
	RunSyncAction(PyCode);
	RequestRefresh();
	return FReply::Handled();
}

FReply SUEAgentSkillTab::OnSyncAllClicked()
{
	FString PyCode = TEXT(
		"from skill_sync import sync_all\n"
		"_result = sync_all()\n"
	);
	RunSyncAction(PyCode);
	RequestRefresh();
	return FReply::Handled();
}

FReply SUEAgentSkillTab::OnPublishClicked(FSkillEntryPtr Item)
{
	TSharedRef<SWindow> Win = SNew(SWindow)
		.Title(FText::Format(
			FUEAgentL10n::Get(TEXT("ManagePublishTitle")),
			FText::FromString(Item->Name)))
		.ClientSize(FVector2D(460, 380))
		.SupportsMinimize(false).SupportsMaximize(false);

	TSharedPtr<SEditableTextBox> ChangelogInput;
	TWeakPtr<SWindow> WeakWin = Win;
	FString SkillName = Item->Name;
	FString CurrentVersion = Item->Version.IsEmpty() ? TEXT("0.0.0") : Item->Version;

	// --- 目标层级选择状态 ---
	TSharedPtr<FString> SelectedLayer = MakeShared<FString>(TEXT("marketplace"));

	// --- DCC 软件目录选择状态 ---
	// 默认值: 从当前 Skill 的 Software 字段推断
	FString DefaultDcc = Item->Software;
	if (DefaultDcc == TEXT("unreal_engine")) DefaultDcc = TEXT("unreal");
	if (DefaultDcc.IsEmpty()) DefaultDcc = TEXT("universal");
	TSharedPtr<FString> SelectedDcc = MakeShared<FString>(DefaultDcc);

	// 可选 DCC 列表（动态加载，与筛选标签一致）
	TArray<FString> DccOptions = {TEXT("universal"), TEXT("unreal"), TEXT("maya"), TEXT("max")};
	// 也加入数据中发现的非标准 DCC（如果有）
	for (const FString& Sw : DiscoveredSoftwareTypes)
	{
		FString Norm = (Sw == TEXT("unreal_engine")) ? TEXT("unreal") : Sw;
		if (!DccOptions.Contains(Norm)) DccOptions.Add(Norm);
	}

	// 构建 DCC 按钮选择行的容器
	TSharedPtr<SHorizontalBox> DccButtonRow;

	// lambda: 重建 DCC 按钮行，高亮选中项
	auto RebuildDccButtons = [&DccButtonRow, &DccOptions, SelectedDcc]()
	{
		if (!DccButtonRow.IsValid()) return;
		DccButtonRow->ClearChildren();
		for (const FString& Dcc : DccOptions)
		{
			bool bActive = (*SelectedDcc == Dcc);
			FString Label = Dcc;
			if (Dcc == TEXT("unreal")) Label = TEXT("UE");
			else if (Dcc == TEXT("maya")) Label = TEXT("Maya");
			else if (Dcc == TEXT("max")) Label = TEXT("Max");
			else if (Dcc == TEXT("universal")) Label = TEXT("Universal");

			DccButtonRow->AddSlot().AutoWidth().Padding(2, 0)
			[
				SNew(SButton)
				.Text(FText::FromString(Label))
				.ButtonColorAndOpacity(bActive
					? FSlateColor(FLinearColor(0.15f, 0.55f, 0.65f))
					: FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f)))
				.ContentPadding(FMargin(6, 2))
				// Note: OnClicked is set below via a different mechanism since we need capture
			];
		}
	};

	Win->SetContent(
		SNew(SVerticalBox)

		+ SVerticalBox::Slot().AutoHeight().Padding(12, 8)
		[
			SNew(STextBlock)
			.Text(FText::Format(
				FUEAgentL10n::Get(TEXT("ManagePublishDesc")),
				FText::FromString(SkillName),
				FText::FromString(CurrentVersion)))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
			.AutoWrapText(true)
		]

		// --- 目标层级选择 ---
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 6)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManagePublishLayerLabel")); })
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0, 2, 0, 0)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
				[
					SNew(SButton)
					.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ManageFilterLayerMarket"))))
					.OnClicked_Lambda([SelectedLayer, WeakWin]() {
						*SelectedLayer = TEXT("marketplace");
						// 刷新弹窗 — 简单方案：直接 Invalidate
						if (WeakWin.IsValid()) WeakWin.Pin()->Invalidate(EInvalidateWidgetReason::Paint);
						return FReply::Handled();
					})
					.ButtonColorAndOpacity_Lambda([SelectedLayer]() {
						return (*SelectedLayer == TEXT("marketplace"))
							? FSlateColor(FLinearColor(0.3f, 0.5f, 0.9f))
							: FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f));
					})
					.ContentPadding(FMargin(6, 2))
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
				[
					SNew(SButton)
					.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ManageFilterLayerOfficial"))))
					.OnClicked_Lambda([SelectedLayer, WeakWin]() {
						*SelectedLayer = TEXT("official");
						if (WeakWin.IsValid()) WeakWin.Pin()->Invalidate(EInvalidateWidgetReason::Paint);
						return FReply::Handled();
					})
					.ButtonColorAndOpacity_Lambda([SelectedLayer]() {
						return (*SelectedLayer == TEXT("official"))
							? FSlateColor(FLinearColor(0.2f, 0.7f, 0.3f))
							: FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f));
					})
					.ContentPadding(FMargin(6, 2))
				]
			]
		]

		// --- DCC 软件目录选择 ---
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 6)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManagePublishDccLabel")); })
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0, 2, 0, 0)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
				[
					SNew(SButton)
					.Text(FText::FromString(TEXT("Universal")))
					.OnClicked_Lambda([SelectedDcc, WeakWin]() {
						*SelectedDcc = TEXT("universal");
						if (WeakWin.IsValid()) WeakWin.Pin()->Invalidate(EInvalidateWidgetReason::Paint);
						return FReply::Handled();
					})
					.ButtonColorAndOpacity_Lambda([SelectedDcc]() {
						return (*SelectedDcc == TEXT("universal"))
							? FSlateColor(FLinearColor(0.15f, 0.55f, 0.65f))
							: FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f));
					})
					.ContentPadding(FMargin(6, 2))
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
				[
					SNew(SButton)
					.Text(FText::FromString(TEXT("UE")))
					.OnClicked_Lambda([SelectedDcc, WeakWin]() {
						*SelectedDcc = TEXT("unreal");
						if (WeakWin.IsValid()) WeakWin.Pin()->Invalidate(EInvalidateWidgetReason::Paint);
						return FReply::Handled();
					})
					.ButtonColorAndOpacity_Lambda([SelectedDcc]() {
						return (*SelectedDcc == TEXT("unreal"))
							? FSlateColor(FLinearColor(0.15f, 0.55f, 0.65f))
							: FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f));
					})
					.ContentPadding(FMargin(6, 2))
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
				[
					SNew(SButton)
					.Text(FText::FromString(TEXT("Maya")))
					.OnClicked_Lambda([SelectedDcc, WeakWin]() {
						*SelectedDcc = TEXT("maya");
						if (WeakWin.IsValid()) WeakWin.Pin()->Invalidate(EInvalidateWidgetReason::Paint);
						return FReply::Handled();
					})
					.ButtonColorAndOpacity_Lambda([SelectedDcc]() {
						return (*SelectedDcc == TEXT("maya"))
							? FSlateColor(FLinearColor(0.15f, 0.55f, 0.65f))
							: FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f));
					})
					.ContentPadding(FMargin(6, 2))
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
				[
					SNew(SButton)
					.Text(FText::FromString(TEXT("Max")))
					.OnClicked_Lambda([SelectedDcc, WeakWin]() {
						*SelectedDcc = TEXT("max");
						if (WeakWin.IsValid()) WeakWin.Pin()->Invalidate(EInvalidateWidgetReason::Paint);
						return FReply::Handled();
					})
					.ButtonColorAndOpacity_Lambda([SelectedDcc]() {
						return (*SelectedDcc == TEXT("max"))
							? FSlateColor(FLinearColor(0.15f, 0.55f, 0.65f))
							: FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f));
					})
					.ContentPadding(FMargin(6, 2))
				]
			]
		]

		// --- Changelog ---
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 6)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManagePublishChangelogLabel")); })
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0, 2, 0, 0)
			[
				SAssignNew(ChangelogInput, SEditableTextBox)
				.HintText(FText::FromString(TEXT("...")))
			]
		]

		+ SVerticalBox::Slot().FillHeight(1.0f)[ SNew(SSpacer) ]

		// --- Patch / Minor / Major / Cancel ---
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 8)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]

			+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
			[
				SNew(SButton)
				.Text(FText::FromString(TEXT("Patch")))
				.OnClicked_Lambda([this, SkillName, ChangelogInput, SelectedLayer, SelectedDcc, WeakWin]() {
					FString CL = ChangelogInput->GetText().ToString();
					FString Py = FString::Printf(TEXT(
						"from skill_sync import publish_skill\n"
						"_result = publish_skill('%s', '%s', 'patch', '%s', '%s')\n"
					), *SkillName, **SelectedLayer,
					   *CL.Replace(TEXT("'"), TEXT("\\'")), **SelectedDcc);
					RunSyncAction(Py);
					if (WeakWin.IsValid()) WeakWin.Pin()->RequestDestroyWindow();
					RequestRefresh();
					return FReply::Handled();
				})
				.ContentPadding(FMargin(6, 3))
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
			[
				SNew(SButton)
				.Text(FText::FromString(TEXT("Minor")))
				.OnClicked_Lambda([this, SkillName, ChangelogInput, SelectedLayer, SelectedDcc, WeakWin]() {
					FString CL = ChangelogInput->GetText().ToString();
					FString Py = FString::Printf(TEXT(
						"from skill_sync import publish_skill\n"
						"_result = publish_skill('%s', '%s', 'minor', '%s', '%s')\n"
					), *SkillName, **SelectedLayer,
					   *CL.Replace(TEXT("'"), TEXT("\\'")), **SelectedDcc);
					RunSyncAction(Py);
					if (WeakWin.IsValid()) WeakWin.Pin()->RequestDestroyWindow();
					RequestRefresh();
					return FReply::Handled();
				})
				.ContentPadding(FMargin(6, 3))
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
			[
				SNew(SButton)
				.Text(FText::FromString(TEXT("Major")))
				.OnClicked_Lambda([this, SkillName, ChangelogInput, SelectedLayer, SelectedDcc, WeakWin]() {
					FString CL = ChangelogInput->GetText().ToString();
					FString Py = FString::Printf(TEXT(
						"from skill_sync import publish_skill\n"
						"_result = publish_skill('%s', '%s', 'major', '%s', '%s')\n"
					), *SkillName, **SelectedLayer,
					   *CL.Replace(TEXT("'"), TEXT("\\'")), **SelectedDcc);
					RunSyncAction(Py);
					if (WeakWin.IsValid()) WeakWin.Pin()->RequestDestroyWindow();
					RequestRefresh();
					return FReply::Handled();
				})
				.ContentPadding(FMargin(6, 3))
			]

			+ SHorizontalBox::Slot().AutoWidth().Padding(8, 0, 0, 0)
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QICancelBtn")); })
				.OnClicked_Lambda([WeakWin]() {
					if (WeakWin.IsValid()) WeakWin.Pin()->RequestDestroyWindow();
					return FReply::Handled();
				})
				.ContentPadding(FMargin(6, 3))
			]
		]
	);

	FUEAgentManageUtils::AddChildWindow(Win);
	return FReply::Handled();
}

#undef LOCTEXT_NAMESPACE
