// Copyright ArtClaw Project. All Rights Reserved.
// 消息列表渲染模块 - RebuildMessageList 及相关辅助方法

#include "UEAgentDashboard.h"
#include "UEAgentLocalization.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Text/SMultiLineEditableText.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"

// ==================================================================
// 消息列表渲染
// ==================================================================

void SUEAgentDashboard::RebuildMessageList()
{
	if (!MessageScrollBox.IsValid())
	{
		return;
	}

	MessageScrollBox->ClearChildren();

	for (int32 i = 0; i < Messages.Num(); ++i)
	{
		const FChatMessage& Msg = Messages[i];

		// --- Plan 消息卡片 ---
		if (Msg.Sender == TEXT("plan") && CurrentPlan.IsSet())
		{
			MessageScrollBox->AddSlot()
			.Padding(4.0f, 2.0f)
			[
				SNew(SBorder)
				.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.GroupBorder"))
				.Padding(8.0f)
				[
					SNew(SVerticalBox)
					+ SVerticalBox::Slot()
					.AutoHeight()
					[
						SNew(STextBlock)
						.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("PlanTitle"))))
						.Font(FCoreStyle::GetDefaultFontStyle("Bold", 11))
					]
					+ SVerticalBox::Slot()
					.AutoHeight()
					.Padding(0.0f, 4.0f, 0.0f, 0.0f)
					[
						SNew(STextBlock)
						.Text(FText::FromString(CurrentPlan->UserRequest))
						.Font(FCoreStyle::GetDefaultFontStyle("Italic", 9))
						.ColorAndOpacity(FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f)))
					]
				]
			];

			// Plan 步骤
			for (int32 s = 0; s < CurrentPlan->Steps.Num(); ++s)
			{
				const FPlanStep& Step = CurrentPlan->Steps[s];
				if (Step.Status == EPlanStepStatus::Skipped) continue;

				FString StatusIcon;
				FLinearColor StatusColor;
				switch (Step.Status)
				{
				case EPlanStepStatus::Done:
					StatusIcon = TEXT("[OK]"); StatusColor = FLinearColor(0.2f, 0.8f, 0.2f); break;
				case EPlanStepStatus::Running:
					StatusIcon = TEXT("[>>]"); StatusColor = FLinearColor(1.0f, 0.7f, 0.2f); break;
				case EPlanStepStatus::Failed:
					StatusIcon = TEXT("[!!]"); StatusColor = FLinearColor(0.9f, 0.3f, 0.3f); break;
				default:
					StatusIcon = TEXT("[  ]"); StatusColor = FLinearColor(0.6f, 0.6f, 0.6f); break;
				}

				MessageScrollBox->AddSlot()
				.Padding(16.0f, 1.0f, 4.0f, 1.0f)
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot()
					.AutoWidth()
					[
						SNew(STextBlock)
						.Text(FText::FromString(StatusIcon))
						.Font(FCoreStyle::GetDefaultFontStyle("Mono", 10))
						.ColorAndOpacity(FSlateColor(StatusColor))
					]
					+ SHorizontalBox::Slot()
					.FillWidth(1.0f)
					.Padding(4.0f, 0.0f, 0.0f, 0.0f)
					[
						SNew(STextBlock)
						.Text(FText::FromString(FString::Printf(TEXT("%d. %s"), Step.Index, *Step.Title)))
						.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
						.ColorAndOpacity(FSlateColor(StatusColor))
					]
					+ SHorizontalBox::Slot()
					.AutoWidth()
					[
						SNew(SButton)
						.Text(FText::FromString(TEXT("X")))
						.OnClicked(this, &SUEAgentDashboard::OnDeletePlanStep, s)
						.ButtonStyle(FCoreStyle::Get(), "NoBorder")
						.ForegroundColor(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
					]
				];
			}

			// Plan 操作按钮
			MessageScrollBox->AddSlot()
			.Padding(4.0f, 2.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(SButton)
					.Text(FText::FromString(TEXT("Execute All")))
					.OnClicked(this, &SUEAgentDashboard::OnExecutePlanClicked)
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text(FText::FromString(TEXT("Cancel")))
					.OnClicked(this, &SUEAgentDashboard::OnCancelPlanClicked)
				]
			];

			continue;
		}

		// --- Tool call / tool result 消息 ---
		if (Msg.Sender == TEXT("tool_call") || Msg.Sender == TEXT("tool_result") || Msg.Sender == TEXT("tool_error"))
		{
			FString ToolLabel = Msg.Sender == TEXT("tool_call")
				? FString::Printf(TEXT("Tool: %s"), *Msg.ToolName)
				: FString::Printf(TEXT("Result: %s"), *Msg.ToolName);

			MessageScrollBox->AddSlot()
			.Padding(4.0f, 2.0f)
			[
				SNew(SBorder)
				.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.DarkGroupBorder"))
				.Padding(6.0f)
				[
					SNew(SVerticalBox)
					// Header (clickable to collapse/expand)
					+ SVerticalBox::Slot()
					.AutoHeight()
					[
						SNew(SButton)
						.Text(FText::FromString(Msg.bToolCollapsed ? ToolLabel : (ToolLabel + TEXT(" (expanded)"))))
						.OnClicked_Lambda([this, i]() -> FReply { return OnToggleToolCollapse(i); })
						.ButtonStyle(FCoreStyle::Get(), "NoBorder")
						.ForegroundColor(GetSenderColor(Msg.Sender))
						.HAlign(HAlign_Left)
					]
					// Tool call arguments or result (collapsible)
					+ SVerticalBox::Slot()
					.AutoHeight()
					[
						SNew(SBox)
						.Visibility(Msg.bToolCollapsed ? EVisibility::Collapsed : EVisibility::Visible)
						[
							SNew(SMultiLineEditableText)
							.Text(FText::FromString(
								Msg.Sender == TEXT("tool_call") ? Msg.ToolArguments : Msg.ToolResult))
							.Font(FCoreStyle::GetDefaultFontStyle("Mono", 9))
							.AutoWrapText(true)
							.IsReadOnly(true)
							.AllowContextMenu(true)
						]
					]
				]
			];

			continue;
		}

		// --- 普通消息 (user / assistant / system / thinking / streaming) ---
		FString TimeStr = Msg.Timestamp.ToString(TEXT("%H:%M"));

		FString SenderLabel;
		if (Msg.Sender == TEXT("user"))
		{
			SenderLabel = FUEAgentL10n::GetStr(TEXT("SenderYou"));
		}
		else if (Msg.Sender == TEXT("assistant"))
		{
			SenderLabel = FUEAgentL10n::GetStr(TEXT("SenderAI"));
		}
		else if (Msg.Sender == TEXT("thinking"))
		{
			SenderLabel = FUEAgentL10n::GetStr(TEXT("Thinking"));
		}
		else if (Msg.Sender == TEXT("streaming"))
		{
			SenderLabel = FUEAgentL10n::GetStr(TEXT("SenderAI"));
		}
		else
		{
			SenderLabel = FUEAgentL10n::GetStr(TEXT("SenderSystem"));
		}

		MessageScrollBox->AddSlot()
		.Padding(4.0f, 2.0f)
		[
			SNew(SVerticalBox)

			// Sender + time
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 2.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(STextBlock)
					.Text(FText::FromString(SenderLabel))
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
					.ColorAndOpacity(GetSenderColor(Msg.Sender))
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(8.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(STextBlock)
					.Text(FText::FromString(TimeStr))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
					.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
				]
			]

			// Content
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(8.0f, 0.0f, 0.0f, 4.0f)
			[
				SNew(SMultiLineEditableText)
				.Text(FText::FromString(Msg.Content))
				.Font(Msg.bIsCode
					? FCoreStyle::GetDefaultFontStyle("Mono", 9)
					: FCoreStyle::GetDefaultFontStyle("Regular", 10))
				.AutoWrapText(true)
				.IsReadOnly(true)
				.AllowContextMenu(true)
			]
		];
	}

	// 延迟一帧再滚到底部，确保 Slate layout pass 完成后尺寸已知
	TWeakPtr<SScrollBox> WeakScroll = MessageScrollBox;
	RegisterActiveTimer(0.0f, FWidgetActiveTimerDelegate::CreateLambda(
		[WeakScroll](double, float) -> EActiveTimerReturnType
		{
			if (TSharedPtr<SScrollBox> Scroll = WeakScroll.Pin())
			{
				Scroll->ScrollToEnd();
			}
			return EActiveTimerReturnType::Stop;
		}
	));
}

FSlateColor SUEAgentDashboard::GetSenderColor(const FString& Sender) const
{
	if (Sender == TEXT("user"))
	{
		return FSlateColor(FLinearColor(0.85f, 0.85f, 0.85f)); // 白色
	}
	if (Sender == TEXT("assistant"))
	{
		return FSlateColor(FLinearColor(0.4f, 0.75f, 1.0f)); // 蓝色
	}
	if (Sender == TEXT("system"))
	{
		return FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f)); // 灰色
	}
	if (Sender == TEXT("tool_call"))
	{
		return FSlateColor(FLinearColor(0.9f, 0.8f, 0.4f)); // 黄色
	}
	if (Sender == TEXT("tool_result") || Sender == TEXT("tool_error"))
	{
		return FSlateColor(FLinearColor(0.5f, 0.8f, 0.5f)); // 绿色
	}
	if (Sender == TEXT("thinking") || Sender == TEXT("streaming"))
	{
		return FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f)); // 灰色
	}
	return FSlateColor(FLinearColor::White);
}
