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
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/STableRow.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

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
	RefreshData();
	if (!ContentBox.IsValid()) return;
	ContentBox->ClearChildren();
	ContentBox->AddSlot().FillHeight(1.0f)[ BuildContent() ];
}

FString SUEAgentSkillTab::RunSyncAction(const FString& PyCode)
{
	return FUEAgentManageUtils::RunPythonAndCapture(PyCode);
}

// ==================================================================
// Data — 合并 Phase 3 (已安装) + Phase 4 (未安装/可更新)
// ==================================================================

void SUEAgentSkillTab::RefreshData()
{
	AllSkills.Empty();
	FilteredSkills.Empty();

	FString PyCode = TEXT(
		"from skill_hub import get_skill_hub\n"
		"import json, os, sys\n"
		"\n"
		"# 确保 skill_sync 可导入\n"
		"py_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else ''\n"
		"# skill_sync.py 在 Content/Python/ 下\n"
		"\n"
		"hub = get_skill_hub()\n"
		"skills = []\n"
		"seen_names = set()\n"
		"\n"
		"# 1) skill_hub 代码包\n"
		"if hub:\n"
		"    for m in hub._all_manifests:\n"
		"        if m.name in seen_names: continue\n"
		"        seen_names.add(m.name)\n"
		"        src_dir = getattr(m, 'source_dir', '')\n"
		"        skills.append({\n"
		"            'name': m.name,\n"
		"            'display_name': getattr(m, 'display_name', m.name),\n"
		"            'description': getattr(m, 'description', ''),\n"
		"            'version': getattr(m, 'version', ''),\n"
		"            'layer': getattr(m, 'source_layer', 'custom'),\n"
		"            'software': getattr(m, 'software', 'universal'),\n"
		"            'category': getattr(m, 'category', 'general'),\n"
		"            'risk_level': getattr(m, 'risk_level', 'low'),\n"
		"            'has_code': os.path.exists(os.path.join(str(src_dir), '__init__.py')) if src_dir else False,\n"
		"            'has_skill_md': os.path.exists(os.path.join(str(src_dir), 'SKILL.md')) if src_dir else False,\n"
		"            'install_status': 'full',\n"
		"            'source_dir': str(src_dir) if src_dir else '',\n"
		"        })\n"
		"\n"
		"# 2) ~/.openclaw/skills/ 仅文档\n"
		"oc_dir = os.path.expanduser('~/.openclaw/skills')\n"
		"if os.path.isdir(oc_dir):\n"
		"    for name in sorted(os.listdir(oc_dir)):\n"
		"        if name in seen_names: continue\n"
		"        sd = os.path.join(oc_dir, name)\n"
		"        sm = os.path.join(sd, 'SKILL.md')\n"
		"        if not os.path.isdir(sd) or not os.path.isfile(sm): continue\n"
		"        seen_names.add(name)\n"
		"        desc = ''\n"
		"        try:\n"
		"            with open(sm, 'r', encoding='utf-8') as f:\n"
		"                for line in f:\n"
		"                    line = line.strip()\n"
		"                    if line and not line.startswith('#'):\n"
		"                        desc = line[:120]; break\n"
		"        except: pass\n"
		"        skills.append({\n"
		"            'name': name, 'display_name': name, 'description': desc,\n"
		"            'version': '', 'layer': 'openclaw', 'software': 'universal',\n"
		"            'category': 'general', 'risk_level': 'low',\n"
		"            'has_code': False, 'has_skill_md': True,\n"
		"            'install_status': 'doc_only', 'source_dir': sd,\n"
		"        })\n"
		"\n"
		"# 3) Phase 4: 未安装的 Skill (源码有但运行时没有)\n"
		"try:\n"
		"    from skill_sync import compare_source_vs_runtime\n"
		"    diff = compare_source_vs_runtime()\n"
		"    if not diff.get('error'):\n"
		"        for info in diff.get('available', []):\n"
		"            n = info['name']\n"
		"            if n in seen_names: continue\n"
		"            seen_names.add(n)\n"
		"            skills.append({\n"
		"                'name': n, 'display_name': n,\n"
		"                'description': '',\n"
		"                'version': info.get('version', ''),\n"
		"                'layer': info.get('layer', 'marketplace'),\n"
		"                'software': info.get('dcc', 'universal'),\n"
		"                'category': 'general', 'risk_level': 'low',\n"
		"                'has_code': info.get('has_code', False),\n"
		"                'has_skill_md': info.get('has_skill_md', False),\n"
		"                'install_status': 'not_installed',\n"
		"                'source_dir': info.get('path', ''),\n"
		"            })\n"
		"        # 标记可更新\n"
		"        updatable_names = {i['name'] for i in diff.get('updatable', [])}\n"
		"        for s in skills:\n"
		"            if s['name'] in updatable_names:\n"
		"                s['updatable'] = True\n"
		"                # 找到对应的源码版本\n"
		"                for u in diff.get('updatable', []):\n"
		"                    if u['name'] == s['name']:\n"
		"                        s['source_version'] = u.get('version', '')\n"
		"                        break\n"
		"except Exception as e:\n"
		"    pass  # skill_sync 不可用时降级\n"
		"\n"
		"# 4) 启用/禁用/钉选\n"
		"config_path = os.path.expanduser('~/.artclaw/config.json')\n"
		"pinned = []; disabled = []\n"
		"if os.path.exists(config_path):\n"
		"    try:\n"
		"        with open(config_path, 'r', encoding='utf-8') as f:\n"
		"            cfg = json.load(f)\n"
		"        pinned = cfg.get('pinned_skills', [])\n"
		"        disabled = cfg.get('disabled_skills', [])\n"
		"    except: pass\n"
		"for s in skills:\n"
		"    s['enabled'] = s['name'] not in disabled\n"
		"    s['pinned'] = s['name'] in pinned\n"
		"\n"
		"_result = {'skills': skills, 'count': len(skills)}\n"
	);

	FString JsonStr = FUEAgentManageUtils::RunPythonAndCapture(PyCode);
	ParseSkillList(JsonStr);
}

void SUEAgentSkillTab::ParseSkillList(const FString& JsonStr)
{
	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid()) return;

	const TArray<TSharedPtr<FJsonValue>>* Arr;
	if (!JsonObj->TryGetArrayField(TEXT("skills"), Arr)) return;

	for (const auto& Val : *Arr)
	{
		TSharedPtr<FJsonObject> Obj = Val->AsObject();
		if (!Obj.IsValid()) continue;

		FSkillEntryPtr E = MakeShared<FSkillEntry>();
		E->Name = Obj->GetStringField(TEXT("name"));
		E->DisplayName = Obj->GetStringField(TEXT("display_name"));
		E->Description = Obj->GetStringField(TEXT("description"));
		E->Version = Obj->GetStringField(TEXT("version"));
		E->Layer = Obj->GetStringField(TEXT("layer"));
		E->Software = Obj->GetStringField(TEXT("software"));
		E->Category = Obj->GetStringField(TEXT("category"));
		E->RiskLevel = Obj->GetStringField(TEXT("risk_level"));
		Obj->TryGetBoolField(TEXT("enabled"), E->bEnabled);
		Obj->TryGetBoolField(TEXT("pinned"), E->bPinned);
		Obj->TryGetBoolField(TEXT("has_code"), E->bHasCode);
		Obj->TryGetBoolField(TEXT("has_skill_md"), E->bHasSkillMd);
		Obj->TryGetBoolField(TEXT("updatable"), E->bUpdatable);
		E->SourceDir = Obj->GetStringField(TEXT("source_dir"));

		FString InstallStr = Obj->GetStringField(TEXT("install_status"));
		if (InstallStr == TEXT("doc_only"))
			E->InstallStatus = EInstallStatus::DocOnly;
		else if (InstallStr == TEXT("not_installed"))
			E->InstallStatus = EInstallStatus::NotInstalled;
		else
			E->InstallStatus = EInstallStatus::Full;

		// 源码版本（可更新时有值）- 使用 TryGetStringField 避免字段不存在时崩溃
		Obj->TryGetStringField(TEXT("source_version"), E->SourcePath);

		AllSkills.Add(E);
	}

	ApplyFilters();
}

void SUEAgentSkillTab::ApplyFilters()
{
	FilteredSkills.Empty();
	for (const auto& S : AllSkills)
	{
		if (LayerFilter != TEXT("all") && S->Layer != LayerFilter) continue;

		if (DccFilter != TEXT("all"))
		{
			if (DccFilter == TEXT("unreal"))
			{
				if (S->Software != TEXT("unreal_engine") && S->Software != TEXT("universal")
					&& S->Software != TEXT("unreal"))
					continue;
			}
			else if (S->Software != DccFilter)
				continue;
		}

		if (InstallFilter != TEXT("all"))
		{
			if (InstallFilter == TEXT("full") && S->InstallStatus != EInstallStatus::Full) continue;
			if (InstallFilter == TEXT("doc_only") && S->InstallStatus != EInstallStatus::DocOnly) continue;
			if (InstallFilter == TEXT("not_installed") && S->InstallStatus != EInstallStatus::NotInstalled) continue;
		}

		FilteredSkills.Add(S);
	}
}

// ==================================================================
// Build UI
// ==================================================================

TSharedRef<SWidget> SUEAgentSkillTab::BuildContent()
{
	int32 FullCount = 0, DocCount = 0, NotInstalledCount = 0, UpdatableCount = 0;
	for (const auto& S : AllSkills)
	{
		if (S->InstallStatus == EInstallStatus::Full) FullCount++;
		else if (S->InstallStatus == EInstallStatus::DocOnly) DocCount++;
		else NotInstalledCount++;
		if (S->bUpdatable) UpdatableCount++;
	}

	auto MakeFilterBtn = [this](const FString& Label, const FString& Key,
		const FString& Field, FLinearColor Active) -> TSharedRef<SWidget>
	{
		bool bActive = (Field == TEXT("layer")) ? (LayerFilter == Key)
			: (Field == TEXT("install")) ? (InstallFilter == Key) : false;

		return SNew(SButton)
			.Text(FText::FromString(Label))
			.OnClicked_Lambda([this, Key, Field]() {
				if (Field == TEXT("layer")) LayerFilter = Key;
				else if (Field == TEXT("install")) InstallFilter = Key;
				Refresh();
				return FReply::Handled();
			})
			.ButtonColorAndOpacity(bActive
				? FSlateColor(Active) : FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f)))
			.ContentPadding(FMargin(4, 1));
	};

	return SNew(SVerticalBox)

	// Layer filter
	+ SVerticalBox::Slot().AutoHeight().Padding(8, 4)
	[
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
		[
			SNew(STextBlock)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageFilterLayer")); })
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
			.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
		]
		+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
		[ MakeFilterBtn(FUEAgentL10n::GetStr(TEXT("ManageFilterLayerAll")),
			TEXT("all"), TEXT("layer"), FLinearColor(0.15f, 0.45f, 0.75f)) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
		[ MakeFilterBtn(FUEAgentL10n::GetStr(TEXT("ManageFilterLayerOfficial")),
			TEXT("official"), TEXT("layer"), FLinearColor(0.2f, 0.7f, 0.3f)) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
		[ MakeFilterBtn(FUEAgentL10n::GetStr(TEXT("ManageFilterLayerMarket")),
			TEXT("marketplace"), TEXT("layer"), FLinearColor(0.3f, 0.5f, 0.9f)) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
		[ MakeFilterBtn(FUEAgentL10n::GetStr(TEXT("ManageFilterLayerUser")),
			TEXT("user"), TEXT("layer"), FLinearColor(0.8f, 0.6f, 0.2f)) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
		[ MakeFilterBtn(FUEAgentL10n::GetStr(TEXT("ManageFilterLayerOpenClaw")),
			TEXT("openclaw"), TEXT("layer"), FLinearColor(0.6f, 0.4f, 0.8f)) ]
	]

	// Install status filter + sync button
	+ SVerticalBox::Slot().AutoHeight().Padding(8, 2, 8, 4)
	[
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
		[
			SNew(STextBlock)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageFilterInstall")); })
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
			.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
		]
		+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
		[
			MakeFilterBtn(
				FString::Printf(TEXT("%s (%d)"),
					*FUEAgentL10n::GetStr(TEXT("ManageInstallFilterAll")), AllSkills.Num()),
				TEXT("all"), TEXT("install"), FLinearColor(0.15f, 0.45f, 0.75f))
		]
		+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
		[
			MakeFilterBtn(
				FString::Printf(TEXT("%s (%d)"),
					*FUEAgentL10n::GetStr(TEXT("ManageInstallFull")), FullCount),
				TEXT("full"), TEXT("install"), FLinearColor(0.2f, 0.65f, 0.5f))
		]
		+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
		[
			MakeFilterBtn(
				FString::Printf(TEXT("%s (%d)"),
					*FUEAgentL10n::GetStr(TEXT("ManageInstallDoc")), DocCount),
				TEXT("doc_only"), TEXT("install"), FLinearColor(0.55f, 0.55f, 0.7f))
		]
		+ SHorizontalBox::Slot().AutoWidth().Padding(2, 0)
		[
			MakeFilterBtn(
				FString::Printf(TEXT("%s (%d)"),
					*FUEAgentL10n::GetStr(TEXT("ManageInstallNotInstalled")), NotInstalledCount),
				TEXT("not_installed"), TEXT("install"), FLinearColor(0.6f, 0.4f, 0.3f))
		]

		+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]

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

		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(8, 0, 0, 0)
		[
			SNew(STextBlock)
			.Text(FText::Format(
				FUEAgentL10n::Get(TEXT("ManageSkillCount")),
				FText::AsNumber(FilteredSkills.Num()),
				FText::AsNumber(AllSkills.Num())))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
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
	else if (Item->Layer == TEXT("openclaw")) LC = FLinearColor(0.6f, 0.4f, 0.8f);

	// 安装状态
	FLinearColor IC; FString IL;
	if (Item->InstallStatus == EInstallStatus::Full)
	{
		IC = FLinearColor(0.2f, 0.65f, 0.5f);
		IL = FUEAgentL10n::GetStr(TEXT("ManageInstallFull"));
	}
	else if (Item->InstallStatus == EInstallStatus::DocOnly)
	{
		IC = FLinearColor(0.55f, 0.55f, 0.7f);
		IL = FUEAgentL10n::GetStr(TEXT("ManageInstallDoc"));
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
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2, 2, 0, 2)
		[
			SNew(SButton)
			.Text(FText::FromString(Item->bPinned ? TEXT("*") : TEXT(" ")))
			.OnClicked(FOnClicked::CreateSP(this, &SUEAgentSkillTab::OnPinClicked, Item))
			.ContentPadding(FMargin(2, 0))
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

		// Name + version
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

		// user/custom 层已安装 → [发布]
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManagePublishBtn")); })
			.OnClicked(FOnClicked::CreateSP(this, &SUEAgentSkillTab::OnPublishClicked, Item))
			.Visibility(bIsInstalled && (Item->Layer == TEXT("user") || Item->Layer == TEXT("custom"))
				? EVisibility::Visible : EVisibility::Collapsed)
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
	Refresh();
	return FReply::Handled();
}

FReply SUEAgentSkillTab::OnDetailClicked(FSkillEntryPtr Item)
{
	FString InstallStr;
	if (Item->InstallStatus == EInstallStatus::Full)
		InstallStr = FUEAgentL10n::GetStr(TEXT("ManageInstallFull"));
	else if (Item->InstallStatus == EInstallStatus::DocOnly)
		InstallStr = FUEAgentL10n::GetStr(TEXT("ManageInstallDoc"));
	else
		InstallStr = FUEAgentL10n::GetStr(TEXT("ManageInstallNotInstalled"));

	FString DetailText = FString::Printf(
		TEXT("%s\n%s v%s\n\n%s\n\n%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s"),
		*Item->DisplayName, *Item->Name, *Item->Version,
		*Item->Description,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailLayer")), *Item->Layer,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailSoftware")), *Item->Software,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailCategory")), *Item->Category,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailRisk")), *Item->RiskLevel,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailInstall")), *InstallStr,
		*FUEAgentL10n::GetStr(TEXT("ManageDetailCode")),
			Item->bHasCode ? TEXT("Yes") : TEXT("No"),
		*FUEAgentL10n::GetStr(TEXT("ManageDetailSkillMd")),
			Item->bHasSkillMd ? TEXT("Yes") : TEXT("No"),
		*FUEAgentL10n::GetStr(TEXT("ManageDetailPath")),
			Item->SourceDir.IsEmpty() ? TEXT("-") : *Item->SourceDir
	);

	TSharedRef<SWindow> Win = SNew(SWindow)
		.Title(FText::FromString(Item->DisplayName))
		.ClientSize(FVector2D(420, 340))
		.SupportsMinimize(false).SupportsMaximize(false)
		[
			SNew(SScrollBox) + SScrollBox::Slot().Padding(12)
			[
				SNew(STextBlock)
				.Text(FText::FromString(DetailText))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
				.AutoWrapText(true)
			]
		];
	FSlateApplication::Get().AddWindow(Win);
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
	Refresh();
	return FReply::Handled();
}

FReply SUEAgentSkillTab::OnUninstallClicked(FSkillEntryPtr Item)
{
	FString PyCode = FString::Printf(TEXT(
		"from skill_sync import uninstall_skill\n"
		"_result = uninstall_skill('%s')\n"
	), *Item->Name);
	RunSyncAction(PyCode);
	Refresh();
	return FReply::Handled();
}

FReply SUEAgentSkillTab::OnUpdateClicked(FSkillEntryPtr Item)
{
	FString PyCode = FString::Printf(TEXT(
		"from skill_sync import update_skill\n"
		"_result = update_skill('%s')\n"
	), *Item->Name);
	RunSyncAction(PyCode);
	Refresh();
	return FReply::Handled();
}

FReply SUEAgentSkillTab::OnSyncAllClicked()
{
	FString PyCode = TEXT(
		"from skill_sync import sync_all\n"
		"_result = sync_all()\n"
	);
	RunSyncAction(PyCode);
	Refresh();
	return FReply::Handled();
}

FReply SUEAgentSkillTab::OnPublishClicked(FSkillEntryPtr Item)
{
	// 发布弹窗
	TSharedRef<SWindow> Win = SNew(SWindow)
		.Title(FText::Format(
			FUEAgentL10n::Get(TEXT("ManagePublishTitle")),
			FText::FromString(Item->Name)))
		.ClientSize(FVector2D(420, 280))
		.SupportsMinimize(false).SupportsMaximize(false);

	TSharedPtr<SEditableTextBox> ChangelogInput;
	TWeakPtr<SWindow> WeakWin = Win;
	FString SkillName = Item->Name;
	FString CurrentVersion = Item->Version.IsEmpty() ? TEXT("0.0.0") : Item->Version;

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

		// 变更说明
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 8)
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

		// Buttons: patch / minor / major / cancel
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 8)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]

			+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
			[
				SNew(SButton)
				.Text(FText::FromString(TEXT("Patch")))
				.OnClicked_Lambda([this, SkillName, ChangelogInput, WeakWin]() {
					FString CL = ChangelogInput->GetText().ToString();
					FString Py = FString::Printf(TEXT(
						"from skill_sync import publish_skill\n"
						"_result = publish_skill('%s', 'marketplace', 'patch', '%s')\n"
					), *SkillName, *CL.Replace(TEXT("'"), TEXT("\\'")));
					RunSyncAction(Py);
					if (WeakWin.IsValid()) WeakWin.Pin()->RequestDestroyWindow();
					Refresh();
					return FReply::Handled();
				})
				.ContentPadding(FMargin(6, 3))
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
			[
				SNew(SButton)
				.Text(FText::FromString(TEXT("Minor")))
				.OnClicked_Lambda([this, SkillName, ChangelogInput, WeakWin]() {
					FString CL = ChangelogInput->GetText().ToString();
					FString Py = FString::Printf(TEXT(
						"from skill_sync import publish_skill\n"
						"_result = publish_skill('%s', 'marketplace', 'minor', '%s')\n"
					), *SkillName, *CL.Replace(TEXT("'"), TEXT("\\'")));
					RunSyncAction(Py);
					if (WeakWin.IsValid()) WeakWin.Pin()->RequestDestroyWindow();
					Refresh();
					return FReply::Handled();
				})
				.ContentPadding(FMargin(6, 3))
			]
			+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
			[
				SNew(SButton)
				.Text(FText::FromString(TEXT("Major")))
				.OnClicked_Lambda([this, SkillName, ChangelogInput, WeakWin]() {
					FString CL = ChangelogInput->GetText().ToString();
					FString Py = FString::Printf(TEXT(
						"from skill_sync import publish_skill\n"
						"_result = publish_skill('%s', 'marketplace', 'major', '%s')\n"
					), *SkillName, *CL.Replace(TEXT("'"), TEXT("\\'")));
					RunSyncAction(Py);
					if (WeakWin.IsValid()) WeakWin.Pin()->RequestDestroyWindow();
					Refresh();
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

	FSlateApplication::Get().AddWindow(Win);
	return FReply::Handled();
}

#undef LOCTEXT_NAMESPACE
