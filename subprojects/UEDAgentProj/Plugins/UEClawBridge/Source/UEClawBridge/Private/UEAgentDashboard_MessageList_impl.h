// Copyright ArtClaw Project. All Rights Reserved.
// 消息列表渲染模块 - RebuildMessageList 及相关辅助方法
// 所有 include 由 UEAgentDashboard.cpp 统一管理

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
			// 折叠标题: 显示工具名 + 状态
			FString ToolStatus;
			if (Msg.Sender == TEXT("tool_error"))
			{
				ToolStatus = TEXT("[error]");
			}
			else if (!Msg.ToolResult.IsEmpty())
			{
				ToolStatus = TEXT("[done]");
			}
			else if (Msg.Sender == TEXT("tool_call"))
			{
				ToolStatus = TEXT("[running]");
			}

			FString ToolLabel = FString::Printf(TEXT("Tool: %s %s"), *Msg.ToolName, *ToolStatus);

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
						.Text(FText::FromString(Msg.bToolCollapsed ? ToolLabel : (ToolLabel + TEXT(" <<"))))
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
							SNew(SVerticalBox)
							+ SVerticalBox::Slot()
							.AutoHeight()
							[
								SNew(SMultiLineEditableText)
								.Text(FText::FromString(Msg.ToolArguments))
								.Font(FCoreStyle::GetDefaultFontStyle("Mono", 9))
								.AutoWrapText(true)
								.IsReadOnly(true)
								.AllowContextMenu(true)
								.Visibility(Msg.ToolArguments.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible)
							]
							+ SVerticalBox::Slot()
							.AutoHeight()
							.Padding(0.0f, 2.0f, 0.0f, 0.0f)
							[
								SNew(SMultiLineEditableText)
								.Text(FText::FromString(Msg.ToolResult))
								.Font(FCoreStyle::GetDefaultFontStyle("Mono", 9))
								.AutoWrapText(true)
								.IsReadOnly(true)
								.AllowContextMenu(true)
								.Visibility(Msg.ToolResult.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible)
							]
						]
					]
				]
			];

			continue;
		}

		// --- Tool 状态消息（紧凑单行，无标签头） ---
		if (Msg.Sender == TEXT("tool_status"))
		{
			MessageScrollBox->AddSlot()
			.Padding(12.0f, 0.0f, 4.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Msg.Content))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.65f, 0.55f, 0.35f))) // 暗橙
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

		// 消息内容文字颜色: 用户绿白、AI 白色、系统灰色、思考紫灰
		FLinearColor ContentColor = FLinearColor(0.88f, 0.88f, 0.88f); // 默认近白
		if (Msg.Sender == TEXT("user"))
		{
			ContentColor = FLinearColor(0.85f, 0.95f, 0.87f); // 淡绿白
		}
		else if (Msg.Sender == TEXT("system"))
		{
			ContentColor = FLinearColor(0.6f, 0.6f, 0.6f); // 灰色
		}
		else if (Msg.Sender == TEXT("thinking"))
		{
			ContentColor = FLinearColor(0.65f, 0.6f, 0.75f); // 淡紫灰
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
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
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
				SNew(SBorder)
				.BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
				.ForegroundColor(FSlateColor(ContentColor))
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
			]
		];
	}

	// 延迟一帧再滚到底部，确保 Slate layout pass 完成后尺寸已知
	TWeakPtr<SScrollBox> WeakScroll = MessageScrollBox;
	RegisterActiveTimer(0.0f, FWidgetActiveTimerDelegate::CreateLambda(
		[WeakScroll](double, float) -> EActiveTimerReturnType
		{
			// 关引擎时 Slate 可能已 shutdown，必须先检查
			if (!FSlateApplication::IsInitialized())
			{
				return EActiveTimerReturnType::Stop;
			}
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
		return FSlateColor(FLinearColor(0.3f, 0.85f, 0.55f)); // 绿色 — 用户消息醒目
	}
	if (Sender == TEXT("assistant"))
	{
		return FSlateColor(FLinearColor(0.4f, 0.75f, 1.0f)); // 蓝色 — AI 助手
	}
	if (Sender == TEXT("system"))
	{
		return FSlateColor(FLinearColor(0.55f, 0.55f, 0.55f)); // 灰色 — 系统提示
	}
	if (Sender == TEXT("tool_call"))
	{
		return FSlateColor(FLinearColor(0.85f, 0.65f, 0.3f)); // 橙色 — Tool 调用中
	}
	if (Sender == TEXT("tool_result"))
	{
		return FSlateColor(FLinearColor(0.4f, 0.75f, 0.5f)); // 暗绿 — Tool 完成
	}
	if (Sender == TEXT("tool_error"))
	{
		return FSlateColor(FLinearColor(0.9f, 0.35f, 0.35f)); // 红色 — Tool 出错
	}
	if (Sender == TEXT("tool_status"))
	{
		return FSlateColor(FLinearColor(0.65f, 0.55f, 0.35f)); // 暗橙 — Tool 状态
	}
	if (Sender == TEXT("thinking"))
	{
		return FSlateColor(FLinearColor(0.65f, 0.55f, 0.85f)); // 紫色 — AI 思考
	}
	if (Sender == TEXT("streaming"))
	{
		return FSlateColor(FLinearColor(0.5f, 0.7f, 0.9f)); // 浅蓝 — 流式输出中
	}
	return FSlateColor(FLinearColor::White);
}
