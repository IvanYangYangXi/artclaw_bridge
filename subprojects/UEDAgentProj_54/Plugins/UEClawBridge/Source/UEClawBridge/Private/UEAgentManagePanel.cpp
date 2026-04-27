// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentManagePanel.h"
#include "UEAgentMcpTab.h"
#include "UEAgentSkillTab.h"
#include "UEAgentLocalization.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SButton.h"

#define LOCTEXT_NAMESPACE "UEAgentManagePanel"

void SUEAgentManagePanel::Construct(const FArguments& InArgs)
{
	ChildSlot
	[
		SNew(SVerticalBox)

		// === Tab Bar ===
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(4.0f)
		[
			SNew(SHorizontalBox)

			+ SHorizontalBox::Slot().AutoWidth()
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageTabSkill")); })
				.OnClicked(this, &SUEAgentManagePanel::OnSkillTabClicked)
				.ButtonColorAndOpacity(this, &SUEAgentManagePanel::GetTabColor, EManageTab::Skill)
				.ContentPadding(FMargin(8.0f, 4.0f))
			]

			+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0, 0, 0)
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageTabMcp")); })
				.OnClicked(this, &SUEAgentManagePanel::OnMcpTabClicked)
				.ButtonColorAndOpacity(this, &SUEAgentManagePanel::GetTabColor, EManageTab::MCP)
				.ContentPadding(FMargin(8.0f, 4.0f))
			]

			+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]

			+ SHorizontalBox::Slot().AutoWidth()
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageRefreshBtn")); })
				.OnClicked(this, &SUEAgentManagePanel::OnRefreshClicked)
				.ContentPadding(FMargin(6.0f, 4.0f))
			]
		]

		+ SVerticalBox::Slot().AutoHeight()[ SNew(SSeparator) ]

		// === Content Area ===
		+ SVerticalBox::Slot().FillHeight(1.0f)
		[
			SAssignNew(ContentBox, SVerticalBox)
		]
	];

	RebuildContent();
}

FReply SUEAgentManagePanel::OnSkillTabClicked()
{
	ActiveTab = EManageTab::Skill;
	RebuildContent();
	return FReply::Handled();
}

FReply SUEAgentManagePanel::OnMcpTabClicked()
{
	ActiveTab = EManageTab::MCP;
	RebuildContent();
	return FReply::Handled();
}

FReply SUEAgentManagePanel::OnRefreshClicked()
{
	RebuildContent();
	return FReply::Handled();
}

void SUEAgentManagePanel::RebuildContent()
{
	if (!ContentBox.IsValid()) return;
	ContentBox->ClearChildren();

	if (ActiveTab == EManageTab::MCP)
	{
		SAssignNew(McpTab, SUEAgentMcpTab);
		ContentBox->AddSlot().FillHeight(1.0f)[ McpTab.ToSharedRef() ];
	}
	else
	{
		SAssignNew(SkillTab, SUEAgentSkillTab);
		ContentBox->AddSlot().FillHeight(1.0f)[ SkillTab.ToSharedRef() ];
	}
}

FSlateColor SUEAgentManagePanel::GetTabColor(EManageTab Tab) const
{
	if (Tab == ActiveTab)
		return FSlateColor(FLinearColor(0.15f, 0.45f, 0.75f));
	return FSlateColor(FLinearColor(0.25f, 0.25f, 0.25f));
}

#undef LOCTEXT_NAMESPACE
