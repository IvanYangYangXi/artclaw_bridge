// Copyright ArtClaw Project. All Rights Reserved.
// 设置面板模块 - 语言切换、静默模式、Plan 模式、Skills 管理
// Ref: docs/specs/系统架构设计.md#SettingsPanel

#include "UEAgentDashboard.h"
#include "UEAgentLocalization.h"
#include "UEAgentManagePanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SSeparator.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/SWindow.h"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"

// ==================================================================
// 设置面板 - 打开/关闭
// ==================================================================

FReply SUEAgentDashboard::OnSettingsClicked()
{
	// 如果窗口已存在，直接激活
	if (SettingsWindow.IsValid())
	{
		SettingsWindow->BringToFront();
		return FReply::Handled();
	}

	// 记录当前状态（用于取消时恢复）
	const bool OrigSilentMedium = bSilentMedium;
	const bool OrigSilentHigh = bSilentHigh;
	const bool OrigPlanMode = bPlanMode;
	const bool OrigEnterToSend = bEnterToSend;

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
				.OnClicked_Lambda([]()
				{
					FGlobalTabmanager::Get()->TryInvokeTab(FName("UEAgentManagePanel"));
					return FReply::Handled();
				})
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
				.OnClicked_Lambda([Self, OrigSilentMedium, OrigSilentHigh, OrigPlanMode, OrigEnterToSend]()
				{
					// 保存静默模式配置（仅在变更时）
					if (Self->bSilentMedium != OrigSilentMedium || Self->bSilentHigh != OrigSilentHigh)
					{
						Self->SaveSilentModeToConfig();
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
	FSlateApplication::Get().AddWindow(SettingsWindow.ToSharedRef());

	return FReply::Handled();
}
