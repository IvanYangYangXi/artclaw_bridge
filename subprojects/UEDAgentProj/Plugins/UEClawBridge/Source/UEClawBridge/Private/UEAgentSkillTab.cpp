// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentSkillTab.h"
#include "UEAgentManageUtils.h"
#include "UEAgentLocalization.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Text/SMultiLineEditableText.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/STableRow.h"
#include "Framework/Application/SlateApplication.h"

// 模块化拆分 - 数据刷新与解析
#include "UEAgentSkillTab_Data_impl.h"

#define LOCTEXT_NAMESPACE "UEAgentSkillTab"

// ==================================================================
// Construct / Refresh
// ==================================================================

void SUEAgentSkillTab::Construct(const FArguments& InArgs)
{
	ChildSlot[ SAssignNew(ContentBox, SVerticalBox) ];
	Refresh();
}

void SUEAgentSkillTab::Refresh()
{
	bPendingRefresh = false;
	RefreshData();
	if (!ContentBox.IsValid()) return;
	ContentBox->ClearChildren();
	ContentBox->AddSlot().FillHeight(1.0f)[ BuildContent() ];
}

void SUEAgentSkillTab::RequestRefresh()
{
	if (bPendingRefresh) return;
	bPendingRefresh = true;
	RegisterActiveTimer(0.0f, FWidgetActiveTimerDelegate::CreateLambda(
		[this](double, float) -> EActiveTimerReturnType
		{
			Refresh();
			return EActiveTimerReturnType::Stop;
		}
	));
}

FString SUEAgentSkillTab::RunSyncAction(const FString& PyCode)
{
	return FUEAgentManageUtils::RunPythonAndCapture(PyCode);
}

// ==================================================================
// Build UI
// ==================================================================

TSharedRef<SWidget> SUEAgentSkillTab::BuildContent()
{
	int32 FullCount = 0, NotInstalledCount = 0, UpdatableCount = 0;
	for (const auto& S : AllSkills)
	{
		if (S->InstallStatus == EInstallStatus::Installed) FullCount++;
		else NotInstalledCount++;
		if (S->bUpdatable) UpdatableCount++;
	}

	auto MakeFilterBtn = [this](const FString& Label, const FString& Key,
		const FString& Field, FLinearColor Active) -> TSharedRef<SWidget>
	{
		bool bActive = false;
		if (Field == TEXT("layer")) bActive = (LayerFilter == Key);
		else if (Field == TEXT("install")) bActive = (InstallFilter == Key);
		else if (Field == TEXT("dcc")) bActive = (DccFilter == Key);

		return SNew(SButton)
			.Text(FText::FromString(Label))
			.OnClicked_Lambda([this, Key, Field]() {
				if (Field == TEXT("layer")) LayerFilter = Key;
				else if (Field == TEXT("install"))
					InstallFilter = (InstallFilter == Key) ? TEXT("all") : Key;
				else if (Field == TEXT("dcc")) DccFilter = Key;
				RequestRefresh();
				return FReply::Handled();
			})
			.ButtonColorAndOpacity(bActive
				? FSlateColor(Active) : FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f)))
			.ContentPadding(FMargin(4, 1));
	};

	// Layer 显示名与颜色映射
	auto GetLayerDisplayName = [](const FString& Key) -> FString
	{
		if (Key == TEXT("official"))    return FUEAgentL10n::GetStr(TEXT("ManageFilterLayerOfficial"));
		if (Key == TEXT("marketplace")) return FUEAgentL10n::GetStr(TEXT("ManageFilterLayerMarket"));
		if (Key == TEXT("user"))        return FUEAgentL10n::GetStr(TEXT("ManageFilterLayerUser"));
		if (Key == TEXT("platform"))    return FUEAgentL10n::GetStr(TEXT("ManageFilterLayerPlatform"));
		return Key;  // 未知 layer 直接用原名
	};
	auto GetLayerColor = [](const FString& Key) -> FLinearColor
	{
		if (Key == TEXT("official"))    return FLinearColor(0.2f, 0.7f, 0.3f);
		if (Key == TEXT("marketplace")) return FLinearColor(0.3f, 0.5f, 0.9f);
		if (Key == TEXT("user"))        return FLinearColor(0.8f, 0.6f, 0.2f);
		if (Key == TEXT("platform"))    return FLinearColor(0.5f, 0.4f, 0.7f);
		return FLinearColor(0.5f, 0.5f, 0.5f);
	};

	// DCC 显示名映射
	auto GetDccDisplayName = [](const FString& Key) -> FString
	{
		if (Key == TEXT("unreal") || Key == TEXT("unreal_engine")) return TEXT("UE");
		if (Key == TEXT("maya")) return TEXT("Maya");
		if (Key == TEXT("max"))  return TEXT("Max");
		if (Key == TEXT("universal")) return FUEAgentL10n::GetStr(TEXT("ManageFilterDccUniversal"));
		// 未知 DCC：首字母大写
		if (Key.Len() > 0) return Key.Left(1).ToUpper() + Key.Mid(1);
		return Key;
	};

	// --- 动态构建 Layer 筛选行 ---
	TSharedRef<SHorizontalBox> LayerRow = SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
		[
			SNew(STextBlock)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageFilterLayer")); })
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
			.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
		]
		+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
		[ MakeFilterBtn(FUEAgentL10n::GetStr(TEXT("ManageFilterLayerAll")),
			TEXT("all"), TEXT("layer"), FLinearColor(0.15f, 0.45f, 0.75f)) ];

	for (const FString& L : DiscoveredLayers)
	{
		LayerRow->AddSlot().AutoWidth().Padding(2, 0)
		[
			MakeFilterBtn(GetLayerDisplayName(L), L, TEXT("layer"), GetLayerColor(L))
		];
	}

	// Separator + Not-installed toggle
	LayerRow->AddSlot().AutoWidth().Padding(8, 0, 4, 0).VAlign(VAlign_Center)
	[
		SNew(STextBlock).Text(FText::FromString(TEXT("|")))
		.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
		.ColorAndOpacity(FSlateColor(FLinearColor(0.35f, 0.35f, 0.35f)))
	];
	LayerRow->AddSlot().AutoWidth().Padding(2, 0)
	[
		MakeFilterBtn(FUEAgentL10n::GetStr(TEXT("ManageFilterNotInstalled")),
			TEXT("notinstalled"), TEXT("install"), FLinearColor(0.85f, 0.5f, 0.2f))
	];

	// --- 动态构建 DCC 筛选行 ---
	TSharedRef<SHorizontalBox> DccRow = SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
		[
			SNew(STextBlock)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageFilterDcc")); })
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
			.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
		]
		+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
		[ MakeFilterBtn(FUEAgentL10n::GetStr(TEXT("ManageFilterDccAll")),
			TEXT("all"), TEXT("dcc"), FLinearColor(0.15f, 0.55f, 0.65f)) ];

	// DCC 排序：把 unreal_engine/unreal 合并显示
	TSet<FString> DccSeen;
	for (const FString& Sw : DiscoveredSoftwareTypes)
	{
		// unreal_engine 和 unreal 视为同一分类
		FString FilterKey = (Sw == TEXT("unreal_engine")) ? TEXT("unreal") : Sw;
		if (DccSeen.Contains(FilterKey)) continue;
		DccSeen.Add(FilterKey);

		DccRow->AddSlot().AutoWidth().Padding(2, 0)
		[
			MakeFilterBtn(GetDccDisplayName(FilterKey),
				FilterKey, TEXT("dcc"), FLinearColor(0.15f, 0.55f, 0.65f))
		];
	}

	return SNew(SVerticalBox)

	// Layer filter + Not-installed toggle (动态)
	+ SVerticalBox::Slot().AutoHeight().Padding(8, 4)
	[ LayerRow ]

	// DCC/Software filter (动态)
	+ SVerticalBox::Slot().AutoHeight().Padding(8, 2)
	[ DccRow ]

	// 搜索框 + 同步按钮
	+ SVerticalBox::Slot().AutoHeight().Padding(8, 2, 8, 4)
	[
		SNew(SHorizontalBox)

		// 搜索框
		+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
		[
			SAssignNew(SearchBox, SEditableTextBox)
			.HintText_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageSearchHint")); })
			.Text(FText::FromString(SearchKeyword))
			.OnTextChanged_Lambda([this](const FText& NewText)
			{
				SearchKeyword = NewText.ToString();
				ApplyFilters();
				if (SkillListView.IsValid()) SkillListView->RequestListRefresh();
			})
		]

		+ SHorizontalBox::Slot().AutoWidth().Padding(6, 0, 0, 0).VAlign(VAlign_Center)
		[
			SNew(STextBlock)
			.Text(FText::Format(
				FUEAgentL10n::Get(TEXT("ManageSkillCount")),
				FText::AsNumber(FilteredSkills.Num()),
				FText::AsNumber(AllSkills.Num())))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
		]

		+ SHorizontalBox::Slot().FillWidth(0.05f)[ SNew(SSpacer) ]

		// 一键同步 (Phase 4)
		+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
		[
			SNew(SButton)
			.Text_Lambda([UpdatableCount, NotInstalledCount]() {
				return FText::Format(
					FUEAgentL10n::Get(TEXT("ManageSyncBtn")),
					FText::AsNumber(NotInstalledCount + UpdatableCount));
			})
			.OnClicked(this, &SUEAgentSkillTab::OnSyncAllClicked)
			.IsEnabled(NotInstalledCount + UpdatableCount > 0)
			.ContentPadding(FMargin(6, 2))
		]
	]

	+ SVerticalBox::Slot().AutoHeight()[ SNew(SSeparator) ]

	// Skill list
	+ SVerticalBox::Slot().FillHeight(1.0f).Padding(4)
	[
		SNew(SScrollBox)
		+ SScrollBox::Slot()
		[
			SAssignNew(SkillListView, SListView<FSkillEntryPtr>)
			.ListItemsSource(&FilteredSkills)
			.OnGenerateRow(this, &SUEAgentSkillTab::GenerateRow)
			.SelectionMode(ESelectionMode::None)
		]
	];
}

TSharedRef<ITableRow> SUEAgentSkillTab::GenerateRow(
	FSkillEntryPtr Item, const TSharedRef<STableViewBase>& OwnerTable)
{
	// 层级颜色
	FLinearColor LC(0.5f, 0.5f, 0.5f);
	if (Item->Layer == TEXT("official")) LC = FLinearColor(0.2f, 0.7f, 0.3f);
	else if (Item->Layer == TEXT("marketplace")) LC = FLinearColor(0.3f, 0.5f, 0.9f);
	else if (Item->Layer == TEXT("user")) LC = FLinearColor(0.8f, 0.6f, 0.2f);
	else if (Item->Layer == TEXT("custom")) LC = FLinearColor(0.6f, 0.4f, 0.6f);
	else if (Item->Layer == TEXT("openclaw") || Item->Layer == TEXT("platform")) LC = FLinearColor(0.5f, 0.4f, 0.7f);

	// 安装状态（已简化：只区分 Installed / NotInstalled）
	FLinearColor IC; FString IL;
	if (Item->InstallStatus == EInstallStatus::Installed)
	{
		IC = FLinearColor(0.2f, 0.65f, 0.5f);
		IL = FUEAgentL10n::GetStr(TEXT("ManageInstallFull"));
	}
	else // NotInstalled
	{
		IC = FLinearColor(0.6f, 0.4f, 0.3f);
		IL = FUEAgentL10n::GetStr(TEXT("ManageInstallNotInstalled"));
	}

	float Op = (Item->bEnabled && Item->InstallStatus != EInstallStatus::NotInstalled) ? 1.0f : 0.45f;
	bool bIsInstalled = (Item->InstallStatus != EInstallStatus::NotInstalled);

	return SNew(STableRow<FSkillEntryPtr>, OwnerTable)
	[
		SNew(SHorizontalBox)

		// Pin (only for installed)
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0, 2, 0, 2)
		[
			SNew(SButton)
			.Text(FText::FromString(Item->bPinned ? TEXT("\u2605") : TEXT("\u2606")))  // ★ pinned / ☆ unpinned
			.OnClicked(FOnClicked::CreateSP(this, &SUEAgentSkillTab::OnPinClicked, Item))
			.ButtonStyle(FCoreStyle::Get(), "NoBorder")
			.ContentPadding(FMargin(4, 2))
			.ForegroundColor(Item->bPinned
				? FSlateColor(FLinearColor(0.95f, 0.75f, 0.1f))   // 金色 (pinned)
				: FSlateColor(FLinearColor(0.45f, 0.45f, 0.45f)))  // 灰色 (unpinned)
			.IsEnabled(bIsInstalled)
			.ToolTipText_Lambda([Item]() {
				return Item->bPinned
					? FUEAgentL10n::Get(TEXT("ManageUnpinTip"))
					: FUEAgentL10n::Get(TEXT("ManagePinTip"));
			})
		]

		// Enable (only for installed)
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2)
		[
			SNew(SCheckBox)
			.IsChecked(Item->bEnabled ? ECheckBoxState::Checked : ECheckBoxState::Unchecked)
			.OnCheckStateChanged(FOnCheckStateChanged::CreateSP(
				this, &SUEAgentSkillTab::OnEnableChanged, Item))
			.IsEnabled(bIsInstalled)
		]

		// Name + version + author
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4, 2)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth()
				[
					SNew(STextBlock)
					.Text(FText::FromString(Item->DisplayName))
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
					.ColorAndOpacity(FSlateColor(FLinearColor(0.9f*Op, 0.9f*Op, 0.9f*Op)))
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(6, 0, 0, 0)
				[
					SNew(STextBlock)
					.Text(FText::FromString(Item->Version))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
					.ColorAndOpacity(FSlateColor(FLinearColor(0.45f, 0.45f, 0.45f)))
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(6, 0, 0, 0)
				[
					SNew(STextBlock)
					.Text(FText::FromString(Item->Author.IsEmpty() ? TEXT("") : (TEXT("  ") + Item->Author)))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
					.ColorAndOpacity(FSlateColor(FLinearColor(0.5f*Op, 0.5f*Op, 0.35f*Op)))
					.Visibility(Item->Author.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible)
				]
			]
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(STextBlock)
				.Text(FText::FromString(Item->Name))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.4f*Op, 0.4f*Op, 0.4f*Op)))
			]
		]

		// Layer badge
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4, 0)
		[
			SNew(SBorder)
			.BorderBackgroundColor(FSlateColor(LC * 0.3f))
			.Padding(FMargin(4, 1))
			[
				SNew(STextBlock)
				.Text(FText::FromString(Item->Layer))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(LC))
			]
		]

		// Install status badge
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2, 0)
		[
			SNew(SBorder)
			.BorderBackgroundColor(FSlateColor(IC * 0.25f))
			.Padding(FMargin(3, 1))
			[
				SNew(STextBlock)
				.Text(FText::FromString(IL))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
				.ColorAndOpacity(FSlateColor(IC))
			]
		]

		+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]

		// Phase 4: 操作按钮（根据状态显示不同按钮）
		// 未安装 → [安装]
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageInstallBtn")); })
			.OnClicked(FOnClicked::CreateSP(this, &SUEAgentSkillTab::OnInstallClicked, Item))
			.Visibility(Item->InstallStatus == EInstallStatus::NotInstalled
				? EVisibility::Visible : EVisibility::Collapsed)
			.ContentPadding(FMargin(4, 1))
		]

		// 可更新 → [更新]
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageUpdateBtn")); })
			.OnClicked(FOnClicked::CreateSP(this, &SUEAgentSkillTab::OnUpdateClicked, Item))
			.Visibility(Item->bUpdatable ? EVisibility::Visible : EVisibility::Collapsed)
			.ContentPadding(FMargin(4, 1))
		]

		// 已安装 (user/custom 层) → [卸载]
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageUninstallBtn")); })
			.OnClicked(FOnClicked::CreateSP(this, &SUEAgentSkillTab::OnUninstallClicked, Item))
			.Visibility(bIsInstalled && (Item->Layer == TEXT("user") || Item->Layer == TEXT("custom")
				|| Item->Layer == TEXT("marketplace"))
				? EVisibility::Visible : EVisibility::Collapsed)
			.ContentPadding(FMargin(4, 1))
		]

		// 已安装 → [发布]（所有已安装 Skill 都可发布）
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManagePublishBtn")); })
			.OnClicked(FOnClicked::CreateSP(this, &SUEAgentSkillTab::OnPublishClicked, Item))
			.Visibility(bIsInstalled ? EVisibility::Visible : EVisibility::Collapsed)
			.ContentPadding(FMargin(4, 1))
		]

		// Detail
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2)
		[
			SNew(SButton)
			.Text(FText::FromString(TEXT("...")))
			.OnClicked(FOnClicked::CreateSP(this, &SUEAgentSkillTab::OnDetailClicked, Item))
			.ContentPadding(FMargin(4, 1))
			.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageDetailTip")); })
		]
	];
}

// 模块化拆分 - Phase 3/4 操作方法
#include "UEAgentSkillTab_Actions_impl.h"
