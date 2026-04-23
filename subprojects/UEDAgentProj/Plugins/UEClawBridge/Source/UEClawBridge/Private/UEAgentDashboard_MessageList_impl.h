// Copyright ArtClaw Project. All Rights Reserved.
// 消息列表渲染模块 - RebuildMessageList 及相关辅助方法
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// Markdown 表格解析辅助
// ==================================================================

/** 检查一行是否为 markdown 表格分隔符 (|---|:---:|---:|) */
static bool IsTableSeparator(const FString& Line)
{
	FString Trimmed = Line.TrimStartAndEnd();
	// 至少包含一个 | 和 一个 ---
	if (!Trimmed.Contains(TEXT("|")) || !Trimmed.Contains(TEXT("-")))
	{
		return false;
	}
	// 去掉首尾 |，按 | 分割，每段必须匹配 :?-+:?
	FString Inner = Trimmed;
	if (Inner.StartsWith(TEXT("|"))) Inner.RemoveFromStart(TEXT("|"));
	if (Inner.EndsWith(TEXT("|"))) Inner.RemoveFromEnd(TEXT("|"));

	TArray<FString> Cells;
	Inner.ParseIntoArray(Cells, TEXT("|"));
	if (Cells.Num() == 0) return false;

	for (const FString& Cell : Cells)
	{
		FString C = Cell.TrimStartAndEnd();
		C.ReplaceInline(TEXT(":"), TEXT(""));
		C.ReplaceInline(TEXT("-"), TEXT(""));
		if (C.Len() > 0) return false; // 含有非 -/: 字符
	}
	return true;
}

/** 解析表格行为列数组 */
static TArray<FString> ParseTableRow(const FString& Line)
{
	FString Inner = Line.TrimStartAndEnd();
	if (Inner.StartsWith(TEXT("|"))) Inner.RemoveFromStart(TEXT("|"));
	if (Inner.EndsWith(TEXT("|"))) Inner.RemoveFromEnd(TEXT("|"));
	TArray<FString> Cells;
	Inner.ParseIntoArray(Cells, TEXT("|"));
	for (FString& C : Cells) C = C.TrimStartAndEnd();
	return Cells;
}

/**
 * 将消息内容拆分为「文本段」和「表格段」，分别用不同 Slate Widget 渲染。
 * 文本段 → SMultiLineEditableText（保持原有效果）
 * 表格段 → SGridPanel（Slate 原生网格，自动列宽，支持中英文混排）
 *
 * 返回 SVerticalBox，内含所有段落的 widget。
 */
static TSharedRef<SVerticalBox> BuildRichContentWidget(
	const FString& Content,
	const FSlateFontInfo& TextFont,
	const FLinearColor& ContentColor)
{
	TSharedRef<SVerticalBox> VBox = SNew(SVerticalBox);

	TArray<FString> Lines;
	Content.ParseIntoArrayLines(Lines);

	int32 i = 0;

	// 累积连续的非表格行，合并后一次性创建文本 widget
	auto FlushTextLines = [&](const TArray<FString>& TextLines)
	{
		if (TextLines.Num() == 0) return;
		FString Joined = FString::Join(TextLines, TEXT("\n"));
		VBox->AddSlot()
		.AutoHeight()
		[
			SNew(SBorder)
			.BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
			.ForegroundColor(FSlateColor(ContentColor))
			[
				SNew(SMultiLineEditableText)
				.Text(FText::FromString(Joined))
				.Font(TextFont)
				.AutoWrapText(true)
				.IsReadOnly(true)
				.AllowContextMenu(true)
			]
		];
	};

	TArray<FString> PendingText;

	while (i < Lines.Num())
	{
		// 检测表格起始
		if (i + 1 < Lines.Num() && Lines[i].Contains(TEXT("|")) && IsTableSeparator(Lines[i + 1]))
		{
			// 先 flush 之前累积的文本
			FlushTextLines(PendingText);
			PendingText.Empty();

			// 收集表格行
			TArray<TArray<FString>> TableRows;
			TableRows.Add(ParseTableRow(Lines[i])); // header

			// 解析对齐
			TArray<FString> SepCells = ParseTableRow(Lines[i + 1]);
			TArray<EHorizontalAlignment> Aligns;
			for (const FString& S : SepCells)
			{
				FString Trimmed = S.TrimStartAndEnd();
				if (Trimmed.StartsWith(TEXT(":")) && Trimmed.EndsWith(TEXT(":")))
					Aligns.Add(HAlign_Center);
				else if (Trimmed.EndsWith(TEXT(":")))
					Aligns.Add(HAlign_Right);
				else
					Aligns.Add(HAlign_Left);
			}

			i += 2; // skip header + separator
			while (i < Lines.Num() && Lines[i].Contains(TEXT("|")) && Lines[i].TrimStartAndEnd().Len() > 0)
			{
				TableRows.Add(ParseTableRow(Lines[i]));
				i++;
			}

			int32 NumCols = 0;
			for (const auto& Row : TableRows) NumCols = FMath::Max(NumCols, Row.Num());
			if (NumCols == 0) continue;

			// 判断每列是否为"长列"（需要自动换行吃剩余空间）
			constexpr int32 LONG_COL_THRESHOLD = 20;
			TArray<int32> ColMaxLen;
			ColMaxLen.SetNumZeroed(NumCols);
			for (const auto& Row : TableRows)
			{
				for (int32 ColIdx = 0; ColIdx < Row.Num(); ++ColIdx)
				{
					ColMaxLen[ColIdx] = FMath::Max(ColMaxLen[ColIdx], Row[ColIdx].Len());
				}
			}
			// 标记长列；没有长列则最后一列兜底
			TArray<bool> IsLongCol;
			IsLongCol.SetNumZeroed(NumCols);
			bool bHasLong = false;
			for (int32 c = 0; c < NumCols; ++c)
			{
				if (ColMaxLen[c] > LONG_COL_THRESHOLD)
				{
					IsLongCol[c] = true;
					bHasLong = true;
				}
			}
			if (!bHasLong)
			{
				IsLongCol[NumCols - 1] = true;
			}

			// 用 Slate 字体测量精确计算每个短列的最大像素宽度
			const FSlateFontInfo HeaderFont = FCoreStyle::GetDefaultFontStyle("Bold", 9);
			const FSlateFontInfo BodyFont = FCoreStyle::GetDefaultFontStyle("Regular", 9);
			constexpr float CELL_H_PADDING = 16.0f; // 左右各 8px

			// 估算文本像素宽度: ASCII ~7px, 非ASCII(中文等) ~13px, 9pt字体
			auto EstimateTextWidth = [](const FString& Text) -> float
			{
				float W = 0.0f;
				for (TCHAR Ch : Text)
				{
					W += (Ch < 128) ? 7.0f : 13.0f;
				}
				return W;
			};

			TArray<float> ColFixedWidth;
			ColFixedWidth.SetNumZeroed(NumCols);
			for (int32 ColIdx = 0; ColIdx < NumCols; ++ColIdx)
			{
				if (IsLongCol[ColIdx]) continue;
				float MaxW = 0.0f;
				for (const auto& Row : TableRows)
				{
					const FString& CellText = (ColIdx < Row.Num()) ? Row[ColIdx] : FString();
					MaxW = FMath::Max(MaxW, EstimateTextWidth(CellText));
				}
				ColFixedWidth[ColIdx] = MaxW + CELL_H_PADDING;
			}

			// 构建表格
			TSharedRef<SVerticalBox> TableVBox = SNew(SVerticalBox);

			for (int32 RowIdx = 0; RowIdx < TableRows.Num(); ++RowIdx)
			{
				const auto& Row = TableRows[RowIdx];
				bool bIsHeader = (RowIdx == 0);

				TSharedRef<SHorizontalBox> RowHBox = SNew(SHorizontalBox);

				for (int32 ColIdx = 0; ColIdx < NumCols; ++ColIdx)
				{
					FString CellText = (ColIdx < Row.Num()) ? Row[ColIdx] : TEXT("");
					EHorizontalAlignment CellAlign = (ColIdx < Aligns.Num()) ? Aligns[ColIdx] : HAlign_Left;
					FLinearColor CellBg = bIsHeader
						? FLinearColor(0.18f, 0.18f, 0.20f)
						: ((RowIdx % 2 == 0) ? FLinearColor(0.12f, 0.12f, 0.13f) : FLinearColor(0.14f, 0.14f, 0.15f));

					TSharedRef<SWidget> CellContent =
						SNew(SBorder)
						.BorderBackgroundColor(FSlateColor(CellBg))
						.ForegroundColor(FSlateColor(bIsHeader
							? FLinearColor(0.85f, 0.85f, 0.85f)
							: ContentColor))
						.Padding(FMargin(8.0f, 3.0f))
						.HAlign(CellAlign)
						[
							SNew(SMultiLineEditableText)
							.Text(FText::FromString(CellText))
							.Font(bIsHeader ? HeaderFont : BodyFont)
							.AutoWrapText(IsLongCol[ColIdx])
							.IsReadOnly(true)
							.AllowContextMenu(true)
						];

					if (IsLongCol[ColIdx])
					{
						RowHBox->AddSlot()
						.FillWidth(1.0f)
						[
							CellContent
						];
					}
					else
					{
						RowHBox->AddSlot()
						.AutoWidth()
						[
							SNew(SBox)
							.WidthOverride(ColFixedWidth[ColIdx])
							[
								CellContent
							]
						];
					}
				}

				TableVBox->AddSlot()
				.AutoHeight()
				[
					RowHBox
				];
			}

			VBox->AddSlot()
			.AutoHeight()
			.Padding(0.0f, 4.0f)
			[
				SNew(SBorder)
				.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.DarkGroupBorder"))
				.Padding(2.0f)
				[
					TableVBox
				]
			];
			continue;
		}

		PendingText.Add(Lines[i]);
		i++;
	}

	// Flush remaining text
	FlushTextLines(PendingText);

	return VBox;
}

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

		// --- Tool call / tool result 消息 (对齐 DCC ToolCallWidget 风格) ---
		if (Msg.Sender == TEXT("tool_call") || Msg.Sender == TEXT("tool_result") || Msg.Sender == TEXT("tool_error"))
		{
			// --- 检测连续 tool 消息数量，决定是否分组 ---
			int32 RunEnd = i;
			while (RunEnd + 1 < Messages.Num()
				&& (Messages[RunEnd + 1].Sender == TEXT("tool_call")
					|| Messages[RunEnd + 1].Sender == TEXT("tool_result")
					|| Messages[RunEnd + 1].Sender == TEXT("tool_error")))
			{
				RunEnd++;
			}
			int32 RunLength = RunEnd - i + 1;

			// 3+ 连续 tool 消息 → 折叠分组
			if (RunLength >= 3)
			{
				// 统计摘要
				int32 DoneCount = 0, ErrorCount = 0, RunningCount = 0;
				for (int32 ti = i; ti <= RunEnd; ++ti)
				{
					if (Messages[ti].Sender == TEXT("tool_error") || Messages[ti].bToolError)
						ErrorCount++;
					else if (!Messages[ti].ToolResult.IsEmpty())
						DoneCount++;
					else
						RunningCount++;
				}
				FString Summary = FString::Printf(TEXT("%d %s"),
					RunLength, *FUEAgentL10n::GetStr(TEXT("ToolCallsCount")));
				FString SubSummary;
				if (DoneCount > 0) SubSummary += FString::Printf(TEXT("%d %s"), DoneCount, *FUEAgentL10n::GetStr(TEXT("ToolDone")));
				if (ErrorCount > 0)
				{
					if (!SubSummary.IsEmpty()) SubSummary += TEXT(", ");
					SubSummary += FString::Printf(TEXT("%d %s"), ErrorCount, *FUEAgentL10n::GetStr(TEXT("ToolErrorShort")));
				}
				if (RunningCount > 0)
				{
					if (!SubSummary.IsEmpty()) SubSummary += TEXT(", ");
					SubSummary += FString::Printf(TEXT("%d %s"), RunningCount, *FUEAgentL10n::GetStr(TEXT("ToolRunning")));
				}

				// 构建内部 tool 卡片列表（每个 tool 可独立展开查看参数/结果）
				TSharedPtr<SVerticalBox> ToolGroupInner = SNew(SVerticalBox);
				for (int32 ti = i; ti <= RunEnd; ++ti)
				{
					const FChatMessage& TMsg = Messages[ti];
					bool bHasRes = !TMsg.ToolResult.IsEmpty();
					bool bErr = (TMsg.Sender == TEXT("tool_error") || TMsg.bToolError);
					FString TStatus = bErr ? TEXT("[error]") : (bHasRes ? TEXT("[done]") : TEXT("[running]"));
					FLinearColor TStatusColor = bErr
						? FLinearColor(0.9f, 0.35f, 0.35f)
						: (bHasRes ? FLinearColor(0.4f, 0.75f, 0.5f) : FLinearColor(0.85f, 0.65f, 0.3f));

					// 构建 tool 详情内容（参数 + 结果）
					TSharedPtr<SVerticalBox> ToolDetail = SNew(SVerticalBox);

					// 参数
					FString TPrettyArgs;
					if (!TMsg.ToolArguments.IsEmpty())
					{
						TSharedPtr<FJsonObject> TArgsObj;
						TSharedRef<TJsonReader<>> TArgsReader = TJsonReaderFactory<>::Create(TMsg.ToolArguments);
						if (FJsonSerializer::Deserialize(TArgsReader, TArgsObj) && TArgsObj.IsValid())
						{
							TSharedRef<TJsonWriter<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>> TW =
								TJsonWriterFactory<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>::Create(&TPrettyArgs);
							FJsonSerializer::Serialize(TArgsObj.ToSharedRef(), TW);
						}
						else
						{
							TPrettyArgs = TMsg.ToolArguments;
						}
					}
					if (!TPrettyArgs.IsEmpty())
					{
						ToolDetail->AddSlot().AutoHeight().Padding(0, 0, 0, 2)
						[
							SNew(STextBlock)
							.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ToolParams"))))
							.Font(FCoreStyle::GetDefaultFontStyle("Bold", 8))
							.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
						];
						// 截断过长参数
						if (TPrettyArgs.Len() > 800)
						{
							TPrettyArgs = TPrettyArgs.Left(800) + TEXT("\n...(truncated)");
						}
						ToolDetail->AddSlot().AutoHeight().Padding(0, 0, 0, 4)
						[
							SNew(SBorder)
							.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.DarkGroupBorder"))
							.Padding(4.0f)
							[
								SNew(SMultiLineEditableText)
								.Text(FText::FromString(TPrettyArgs))
								.Font(FCoreStyle::GetDefaultFontStyle("Mono", 8))
								.AutoWrapText(true)
								.IsReadOnly(true)
							]
						];
					}

					// 结果
					FString TDisplayResult = TMsg.ToolResult;
					if (TDisplayResult.Len() > 1000)
					{
						TDisplayResult = TDisplayResult.Left(1000) + TEXT("\n...(truncated)");
					}
					if (!TDisplayResult.IsEmpty())
					{
						ToolDetail->AddSlot().AutoHeight().Padding(0, 2, 0, 2)
						[
							SNew(STextBlock)
							.Text(FText::FromString(bErr
								? FUEAgentL10n::GetStr(TEXT("ToolError"))
								: FUEAgentL10n::GetStr(TEXT("ToolResult"))))
							.Font(FCoreStyle::GetDefaultFontStyle("Bold", 8))
							.ColorAndOpacity(FSlateColor(bErr
								? FLinearColor(0.9f, 0.35f, 0.35f)
								: FLinearColor(0.4f, 0.75f, 0.5f)))
						];
						ToolDetail->AddSlot().AutoHeight()
						[
							SNew(SBorder)
							.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.DarkGroupBorder"))
							.Padding(4.0f)
							[
								SNew(SMultiLineEditableText)
								.Text(FText::FromString(TDisplayResult))
								.Font(FCoreStyle::GetDefaultFontStyle("Mono", 8))
								.AutoWrapText(true)
								.IsReadOnly(true)
							]
						];
					}

					// 每个 tool 用 SExpandableArea 独立展开
					FString ToolTitle = FString::Printf(TEXT("\u2699 %s  %s"), *TMsg.ToolName, *TStatus);
					ToolGroupInner->AddSlot()
					.AutoHeight()
					.Padding(2.0f, 1.0f)
					[
						SNew(SExpandableArea)
						.AreaTitle(FText::FromString(ToolTitle))
						.AreaTitleFont(FCoreStyle::GetDefaultFontStyle("Regular", 9))
						.InitiallyCollapsed(true)
						.HeaderPadding(FMargin(4.0f, 2.0f))
						.Padding(FMargin(8.0f, 2.0f, 4.0f, 2.0f))
						.BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
						.BodyContent()
						[
							ToolDetail.ToSharedRef()
						]
					];
				}

				// 分组折叠容器
				MessageScrollBox->AddSlot()
				.Padding(4.0f, 1.0f)
				[
					SNew(SBorder)
					.BorderBackgroundColor(FSlateColor(FLinearColor(0.23f, 0.20f, 0.10f)))
					.Padding(0.0f)
					[
						SNew(SExpandableArea)
						.AreaTitle(FText::FromString(FString::Printf(TEXT("\u2699 %s  (%s)"), *Summary, *SubSummary)))
						.InitiallyCollapsed(true)
						.HeaderPadding(FMargin(6.0f, 3.0f))
						.Padding(FMargin(2.0f, 0.0f, 2.0f, 4.0f))
						.BodyContent()
						[
							SNew(SBox)
							.MaxDesiredHeight(500.0f)
							[
								SNew(SScrollBox)
								+ SScrollBox::Slot()
								[
									ToolGroupInner.ToSharedRef()
								]
							]
						]
					]
				];

				// Skip all grouped messages
				i = RunEnd;
				continue;
			}

			// --- 1-2 个 tool 消息 → 原来的单独卡片显示 ---
			// 状态判定
			bool bHasResult = !Msg.ToolResult.IsEmpty();
			bool bIsError = (Msg.Sender == TEXT("tool_error") || Msg.bToolError);
			FString StatusText;
			FLinearColor StatusColor;
			FLinearColor BorderColor;
			FLinearColor BgColor;

			if (bIsError)
			{
				StatusText = TEXT("[error]");
				StatusColor = FLinearColor(0.9f, 0.35f, 0.35f);
				BorderColor = FLinearColor(0.23f, 0.13f, 0.13f);
				BgColor     = FLinearColor(0.12f, 0.09f, 0.09f);
			}
			else if (bHasResult)
			{
				StatusText = TEXT("[done]");
				StatusColor = FLinearColor(0.4f, 0.75f, 0.5f);
				BorderColor = FLinearColor(0.13f, 0.23f, 0.14f);
				BgColor     = FLinearColor(0.09f, 0.12f, 0.09f);
			}
			else
			{
				StatusText = TEXT("[running]");
				StatusColor = FLinearColor(0.85f, 0.65f, 0.3f);
				BorderColor = FLinearColor(0.23f, 0.20f, 0.10f);
				BgColor     = FLinearColor(0.12f, 0.11f, 0.09f);
			}

			FString ArrowStr = Msg.bToolCollapsed ? TEXT("\u25B6") : TEXT("\u25BC");

			// Pretty print arguments JSON
			FString PrettyArgs = Msg.ToolArguments;
			if (!PrettyArgs.IsEmpty())
			{
				TSharedPtr<FJsonObject> ArgsJsonObj;
				TSharedRef<TJsonReader<>> ArgsReader = TJsonReaderFactory<>::Create(PrettyArgs);
				if (FJsonSerializer::Deserialize(ArgsReader, ArgsJsonObj) && ArgsJsonObj.IsValid())
				{
					FString Formatted;
					TSharedRef<TJsonWriter<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>> PrettyWriter =
						TJsonWriterFactory<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>::Create(&Formatted);
					FJsonSerializer::Serialize(ArgsJsonObj.ToSharedRef(), PrettyWriter);
					PrettyArgs = Formatted;
				}
				if (PrettyArgs.Len() > 1500)
				{
					PrettyArgs = PrettyArgs.Left(1500) + TEXT("\n... (truncated)");
				}
			}

			FString DisplayResult = Msg.ToolResult;
			if (DisplayResult.Len() > 2000)
			{
				DisplayResult = DisplayResult.Left(2000) + TEXT("\n... (truncated)");
			}

			MessageScrollBox->AddSlot()
			.Padding(4.0f, 1.0f)
			[
				SNew(SBorder)
				.BorderBackgroundColor(FSlateColor(BorderColor))
				.ColorAndOpacity(FLinearColor::White)
				.Padding(0.0f)
				[
					SNew(SBorder)
					.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.DarkGroupBorder"))
					.Padding(0.0f)
					.ColorAndOpacity(FLinearColor::White)
					[
						SNew(SVerticalBox)

						// --- Header: ▶ ⚙ 工具名 [状态] ---
						+ SVerticalBox::Slot()
						.AutoHeight()
						[
							SNew(SButton)
							.OnClicked_Lambda([this, i]() -> FReply { return OnToggleToolCollapse(i); })
							.ButtonStyle(FCoreStyle::Get(), "NoBorder")
							.HAlign(HAlign_Fill)
							[
								SNew(SHorizontalBox)
								+ SHorizontalBox::Slot()
								.AutoWidth()
								.VAlign(VAlign_Center)
								.Padding(6.0f, 2.0f, 2.0f, 2.0f)
								[
									SNew(STextBlock)
									.Text(FText::FromString(ArrowStr))
									.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
									.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
								]
								+ SHorizontalBox::Slot()
								.AutoWidth()
								.VAlign(VAlign_Center)
								.Padding(0.0f, 2.0f, 3.0f, 2.0f)
								[
									SNew(STextBlock)
									.Text(FText::FromString(TEXT("\u2699")))
									.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
									.ColorAndOpacity(FSlateColor(FLinearColor(0.85f, 0.65f, 0.3f)))
								]
								+ SHorizontalBox::Slot()
								.AutoWidth()
								.VAlign(VAlign_Center)
								.Padding(0.0f, 2.0f, 4.0f, 2.0f)
								[
									SNew(STextBlock)
									.Text(FText::FromString(Msg.ToolName))
									.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
									.ColorAndOpacity(FSlateColor(FLinearColor(0.85f, 0.65f, 0.3f)))
								]
								+ SHorizontalBox::Slot()
								.AutoWidth()
								.VAlign(VAlign_Center)
								.Padding(0.0f, 2.0f, 4.0f, 2.0f)
								[
									SNew(STextBlock)
									.Text(FText::FromString(StatusText))
									.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
									.ColorAndOpacity(FSlateColor(StatusColor))
								]
							]
						]

						// --- Body: 参数 + 结果 (折叠区) ---
						+ SVerticalBox::Slot()
						.AutoHeight()
						[
							SNew(SBox)
							.Visibility(Msg.bToolCollapsed ? EVisibility::Collapsed : EVisibility::Visible)
							.Padding(FMargin(10.0f, 0.0f, 8.0f, 6.0f))
							[
								SNew(SVerticalBox)

								// "参数:" 标签
								+ SVerticalBox::Slot()
								.AutoHeight()
								.Padding(0.0f, 0.0f, 0.0f, 2.0f)
								[
									SNew(STextBlock)
									.Text(FText::FromString(FUEAgentL10n::GetStr(TEXT("ToolParams"))))
									.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
									.ColorAndOpacity(FSlateColor(FLinearColor(0.55f, 0.55f, 0.55f)))
									.Visibility(PrettyArgs.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible)
								]
								// 参数内容
								+ SVerticalBox::Slot()
								.AutoHeight()
								.Padding(0.0f, 0.0f, 0.0f, 4.0f)
								[
									SNew(SBorder)
									.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.DarkGroupBorder"))
									.Padding(4.0f)
									.Visibility(PrettyArgs.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible)
									[
										SNew(SMultiLineEditableText)
										.Text(FText::FromString(PrettyArgs))
										.Font(FCoreStyle::GetDefaultFontStyle("Mono", 9))
										.AutoWrapText(true)
										.IsReadOnly(true)
										.AllowContextMenu(true)
									]
								]
								// "结果:" / "错误:" 标签
								+ SVerticalBox::Slot()
								.AutoHeight()
								.Padding(0.0f, 2.0f, 0.0f, 2.0f)
								[
									SNew(STextBlock)
									.Text(FText::FromString(bIsError
										? FUEAgentL10n::GetStr(TEXT("ToolError"))
										: FUEAgentL10n::GetStr(TEXT("ToolResult"))))
									.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
									.ColorAndOpacity(FSlateColor(bIsError
										? FLinearColor(0.9f, 0.35f, 0.35f)
										: FLinearColor(0.4f, 0.75f, 0.5f)))
									.Visibility(DisplayResult.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible)
								]
								// 结果内容
								+ SVerticalBox::Slot()
								.AutoHeight()
								[
									SNew(SBorder)
									.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.DarkGroupBorder"))
									.Padding(4.0f)
									.Visibility(DisplayResult.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible)
									[
										SNew(SMultiLineEditableText)
										.Text(FText::FromString(DisplayResult))
										.Font(FCoreStyle::GetDefaultFontStyle("Mono", 9))
										.AutoWrapText(true)
										.IsReadOnly(true)
										.AllowContextMenu(true)
									]
								]
							]
						]
					]
				]
			];

			continue;
		}

		// --- Tool 状态消息 — 已有结构化 tool_call 卡片，跳过旧文本摘要 ---
		if (Msg.Sender == TEXT("tool_status"))
		{
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

		// Determine font
		FSlateFontInfo MsgFont = Msg.bIsCode
			? FCoreStyle::GetDefaultFontStyle("Mono", 9)
			: FCoreStyle::GetDefaultFontStyle("Regular", 10);

		// Content — assistant/system use rich renderer (tables etc.), others plain text
		TSharedRef<SWidget> ContentWidget =
			(Msg.Sender == TEXT("assistant") || Msg.Sender == TEXT("system"))
			? StaticCastSharedRef<SWidget>(BuildRichContentWidget(Msg.Content, MsgFont, ContentColor))
			: StaticCastSharedRef<SWidget>(
				SNew(SBorder)
				.BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
				.ForegroundColor(FSlateColor(ContentColor))
				[
					SNew(SMultiLineEditableText)
					.Text(FText::FromString(Msg.Content))
					.Font(MsgFont)
					.AutoWrapText(true)
					.IsReadOnly(true)
					.AllowContextMenu(true)
				]
			);

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
			.Padding(8.0f, 0.0f, 0.0f, 0.0f)
			[
				ContentWidget
			]
		];

		// --- 文件路径超链接 (Content 中检测到的路径) ---
		{
			TArray<FString> FilePaths = ExtractFilePaths(Msg.Content);
			if (FilePaths.Num() > 0)
			{
				TSharedPtr<SVerticalBox> LinksBox = SNew(SVerticalBox);

				for (const FString& Path : FilePaths)
				{
					FString DisplayName = FPaths::GetCleanFilename(Path);
					FString DisplayText = FString::Printf(TEXT("  %s"), *DisplayName);
					FString CapturedPath = Path;

					LinksBox->AddSlot()
					.AutoHeight()
					.Padding(0.0f, 1.0f)
					[
						SNew(SButton)
						.ButtonStyle(&FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("NoBorder"))
						.ContentPadding(FMargin(0.0f))
						.OnClicked_Lambda([CapturedPath]() -> FReply
						{
							FPlatformProcess::LaunchFileInDefaultExternalApplication(*CapturedPath);
							return FReply::Handled();
						})
						.ToolTipText(FText::FromString(Path))
						.Cursor(EMouseCursor::Hand)
						[
							SNew(STextBlock)
							.Text(FText::FromString(DisplayText))
							.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
							.ColorAndOpacity(FSlateColor(FLinearColor(0.4f, 0.7f, 1.0f)))
						]
					];
				}

				MessageScrollBox->AddSlot()
				.Padding(8.0f, 0.0f, 4.0f, 4.0f)
				[
					LinksBox.ToSharedRef()
				];
			}
		}
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

// ==================================================================
// 文件路径提取
// ==================================================================

TArray<FString> SUEAgentDashboard::ExtractFilePaths(const FString& Text)
{
	TArray<FString> Paths;
	TSet<FString> Seen;

	// 按行扫描，匹配 Windows 绝对路径 (X:\...) 和 UNC 路径 (\\server\...)
	// 也匹配被引号包裹的路径
	TArray<FString> Lines;
	Text.ParseIntoArrayLines(Lines);

	for (const FString& Line : Lines)
	{
		FString Working = Line.TrimStartAndEnd();

		// 跳过太短的行
		if (Working.Len() < 4) continue;

		// 检查是否包含盘符模式 (X:\ or X:/)
		int32 SearchStart = 0;
		while (SearchStart < Working.Len() - 2)
		{
			// 查找盘符 "X:\" 或 "X:/"
			int32 ColonPos = INDEX_NONE;
			for (int32 j = SearchStart; j < Working.Len(); ++j)
			{
				if (Working[j] == TEXT(':') && j > 0
					&& FChar::IsAlpha(Working[j - 1])
					&& j + 1 < Working.Len()
					&& (Working[j + 1] == TEXT('\\') || Working[j + 1] == TEXT('/')))
				{
					ColonPos = j;
					break;
				}
			}

			if (ColonPos == INDEX_NONE) break;

			// 路径起始: 盘符前一个字符
			int32 PathStart = ColonPos - 1;

			// 跳过前面的引号/空格
			if (PathStart > 0 && (Working[PathStart - 1] == TEXT('"') || Working[PathStart - 1] == TEXT('\'')))
			{
				// 路径被引号包裹，不调整 PathStart
			}

			// 路径结束: 找到空格、引号、或行末
			int32 PathEnd = ColonPos + 2;
			while (PathEnd < Working.Len())
			{
				TCHAR Ch = Working[PathEnd];
				if (Ch == TEXT('"') || Ch == TEXT('\'') || Ch == TEXT('\n') || Ch == TEXT('\r'))
				{
					break;
				}
				// 空格在路径中可能合法 (如 "Program Files")，但在尾部终止
				// 简单策略: 遇到空格+非路径字符时终止
				if (Ch == TEXT(' '))
				{
					// 向前看: 如果空格后面紧跟非路径起始字符，则终止
					if (PathEnd + 1 >= Working.Len()) break;
					TCHAR Next = Working[PathEnd + 1];
					if (Next == TEXT('-') || Next == TEXT('(') || Next == TEXT('[')
						|| Next == TEXT('\n') || Next == TEXT('\r'))
					{
						break;
					}
				}
				PathEnd++;
			}

			FString Candidate = Working.Mid(PathStart, PathEnd - PathStart).TrimEnd();

			// 去掉尾部的标点符号 (, ; : ) ] 等)
			while (Candidate.Len() > 3)
			{
				TCHAR Last = Candidate[Candidate.Len() - 1];
				if (Last == TEXT(',') || Last == TEXT(';') || Last == TEXT(')')
					|| Last == TEXT(']') || Last == TEXT('>'))
				{
					Candidate.LeftChopInline(1);
				}
				else
				{
					break;
				}
			}

			// 验证: 必须存在且不重复
			if (Candidate.Len() > 3 && !Seen.Contains(Candidate))
			{
				if (FPaths::FileExists(Candidate) || FPaths::DirectoryExists(Candidate))
				{
					Seen.Add(Candidate);
					Paths.Add(Candidate);
				}
			}

			SearchStart = PathEnd;
		}
	}

	return Paths;
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
