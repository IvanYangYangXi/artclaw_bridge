// Copyright ArtClaw Project. All Rights Reserved.
// 聊天功能模块 - 消息发送/接收、输入处理、Slash命令、工具调用展示
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// 按钮回调 - 聊天相关
// ==================================================================

FReply SUEAgentDashboard::OnSendClicked()
{
	if (!InputTextBox.IsValid())
	{
		return FReply::Handled();
	}

	FString InputText = InputTextBox->GetText().ToString().TrimStartAndEnd();
	if (InputText.IsEmpty())
	{
		return FReply::Handled();
	}

	// 关闭 Slash 菜单
	if (SlashMenuAnchor.IsValid())
	{
		SlashMenuAnchor->SetIsOpen(false);
	}

	// 清空输入框
	InputTextBox->SetText(FText::GetEmpty());

	// --- 附件路径注入: 将待发送附件的文件路径前缀到消息 ---
	FString AttachmentPrefix;
	if (PendingAttachments.Num() > 0)
	{
		AttachmentPrefix = TEXT("[Attachments - 用户附件文件，请直接读取以下路径]\n");
		for (const auto& Att : PendingAttachments)
		{
			// 始终发送完整路径 + MIME 类型，AI 通过 read 工具读取文件
			AttachmentPrefix += FString::Printf(TEXT("- %s (%s): %s\n"),
				*Att.DisplayName, *Att.MimeType, *Att.FilePath);
		}
		AttachmentPrefix += TEXT("[/Attachments]\n\n");
	}

	// 检查是否为 Slash 命令
	if (InputText.StartsWith(TEXT("/")))
	{
		// Slash 命令不携带附件
		ClearAttachments();

		// 解析命令和参数
		FString Command, Args;
		if (!InputText.Split(TEXT(" "), &Command, &Args))
		{
			Command = InputText;
			Args = TEXT("");
		}
		HandleSlashCommand(Command.ToLower(), Args.TrimStartAndEnd());
		return FReply::Handled();
	}

	// 防止重复发送 — 但提供取消手段
	if (bIsWaitingForResponse)
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("StillWaiting")));
		return FReply::Handled();
	}

	// 添加用户消息（含附件标识 — 显示完整路径便于超链接检测）
	FString DisplayMessage = InputText;
	if (PendingAttachments.Num() > 0)
	{
		FString AttachInfo;
		for (const auto& Att : PendingAttachments)
		{
			if (!AttachInfo.IsEmpty()) AttachInfo += TEXT("\n");
			AttachInfo += FString::Printf(TEXT("[%s] %s"),
				Att.bIsImage ? TEXT("IMG") : TEXT("FILE"), *Att.FilePath);
		}
		DisplayMessage = AttachInfo + TEXT("\n") + InputText;
	}
	AddMessage(TEXT("user"), DisplayMessage);

	// --- Plan 模式: 拦截用户输入，先生成 Plan ---
	if (bPlanMode && !CurrentPlan.IsSet())
	{
		LastPlanRequest = InputText;
		FString PlanPrompt = FString::Printf(
			TEXT("Please create a step-by-step plan for the following task.\n\n"
				 "Output ONLY the plan in this exact JSON format, do not execute anything, do not add any other text:\n"
				 "```json\n"
				 "{\"plan\":{\"steps\":[{\"index\":1,\"title\":\"Step title\",\"description\":\"Step description\"}]}}\n"
				 "```\n\n"
				 "Task: %s"),
			*InputText);
		SendToOpenClaw(PlanPrompt);
		return FReply::Handled();
	}

	// 通过 OpenClaw Python Bridge 转发给 AI
	FString FinalMessage = AttachmentPrefix + InputText;
	SendToOpenClaw(FinalMessage);

	// 清空附件 (不删除临时文件 — AI 可能还需要读取)
	PendingAttachments.Empty();
	RebuildAttachmentPreview();

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnNewChatClicked()
{
	// 0) 清空待发送附件
	ClearAttachments();

	// 0b) 取消正在执行的 Plan (任务 5.9)
	if (CurrentPlan.IsSet())
	{
		if (CurrentPlan->bIsExecuting && bIsWaitingForResponse)
		{
			OnStopClicked();
		}
		CurrentPlan.Reset();
	}

	// 1) 保存当前活跃会话的 session key (任务 5.8)
	if (ActiveSessionIndex >= 0 && SessionEntries.IsValidIndex(ActiveSessionIndex))
	{
		FString CurrentKey = PlatformBridge->GetSessionKey();
		if (!CurrentKey.IsEmpty())
		{
			SessionEntries[ActiveSessionIndex].SessionKey = CurrentKey;
		}
		SessionEntries[ActiveSessionIndex].bIsActive = false;
	}

	// 2) 本地清屏
	Messages.Empty();
	RebuildMessageList();
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("NewChatStarted")));

	// 3) 重置 token usage (任务 5.5)
	LastTotalTokens = 0;

	// 4) 重置平台桥接的会话
	PlatformBridge->ResetSession();

	// 4b) 清除会话静默标记 (阶段 5.7)
	{
		FString SilentFlagFile = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge/_silent_session.flag");
		IFileManager::Get().Delete(*SilentFlagFile, false, false, true);
	}

	// 5) 创建新会话条目 (任务 5.8)
	{
		FDateTime Now = FDateTime::Now();
		CurrentSessionLabel = FString::Printf(TEXT("%s %02d-%02d %02d:%02d"),
			*FUEAgentL10n::GetStr(TEXT("SessionLabel")),
			Now.GetMonth(), Now.GetDay(), Now.GetHour(), Now.GetMinute());

		FSessionEntry NewEntry;
		NewEntry.Label = CurrentSessionLabel;
		NewEntry.CreatedAt = Now;
		NewEntry.bIsActive = true;
		// SessionKey 会在首次发送消息后由 stream.jsonl 的 session_key 事件回填

		SessionEntries.Add(MoveTemp(NewEntry));
		ActiveSessionIndex = SessionEntries.Num() - 1;
	}

	// 6) 不再发 /new 给 AI — reset_session() 已清空 _session_key，
	//    下次用户发消息时 _chat_worker 自动生成新 key → 新 session 自动创建

	return FReply::Handled();
}

// ==================================================================
// 停止 AI 回答 (任务 5.2)
// ==================================================================

FReply SUEAgentDashboard::OnStopClicked()
{
	// 始终可用: UE 崩溃重启后 bIsWaitingForResponse=false，
	// 但 Gateway 上的 AI 可能仍在运行，需要能发送 abort。

	// 1) 停止 poll timer
	if (PollTimerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(PollTimerHandle);
		PollTimerHandle.Reset();
	}

	// 2) 调用平台桥接取消请求 (发送 chat.abort RPC)
	PlatformBridge->CancelRequest();

	// 3) 重置等待状态
	bIsWaitingForResponse = false;
	bHasStreamingMessage = false;
	StreamLinesRead = 0;
	StreamingTextWidget.Reset();
	StreamingMessageIndex = INDEX_NONE;

	// 4) 移除 "Thinking..." 或流式消息
	for (int32 i = Messages.Num() - 1; i >= 0; --i)
	{
		const FString& S = Messages[i].Sender;
		if (Messages[i].Content == FUEAgentL10n::GetStr(TEXT("Thinking")) && S == TEXT("system"))
		{
			Messages.RemoveAt(i);
		}
		else if (S == TEXT("thinking") || S == TEXT("streaming"))
		{
			Messages.RemoveAt(i);
		}
	}

	// 5) 添加系统消息并重建
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("AIStopped")));

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnResumeClicked()
{
	ResumeReceiving();
	return FReply::Handled();
}

// ==================================================================
// 聊天输入回调
// ==================================================================

void SUEAgentDashboard::OnInputTextChanged(const FText& NewText)
{
	FString Text = NewText.ToString();
	UpdateSlashSuggestions(Text);
}

void SUEAgentDashboard::OnInputTextCommitted(const FText& NewText, ETextCommit::Type CommitType)
{
	// SMultiLineEditableTextBox 在按 Enter 时不触发 OnTextCommitted,
	// 键盘发送逻辑已移至 OnInputKeyDown。
	// 此回调仅在失去焦点时触发 (CommitType == OnUserMovedFocus)
}

FReply SUEAgentDashboard::OnInputKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent)
{
	const FKey Key = InKeyEvent.GetKey();

	// --- Ctrl+V: 优先尝试粘贴剪贴板图片/文件 ---
	if (Key == EKeys::V && InKeyEvent.IsControlDown() && !InKeyEvent.IsShiftDown() && !InKeyEvent.IsAltDown())
	{
		if (TryPasteFromClipboard())
		{
			return FReply::Handled(); // 已处理为附件，不再粘贴文本
		}
		// 普通文本 → 不拦截，让 SMultiLineEditableTextBox 正常粘贴
	}

	if (Key == EKeys::Enter)
	{
		const bool bCtrl = InKeyEvent.IsControlDown();
		const bool bShift = InKeyEvent.IsShiftDown();

		if (bEnterToSend)
		{
			// Enter to Send 模式:
			//   Enter = 发送
			//   Shift+Enter = 换行
			if (!bShift && !bCtrl)
			{
				OnSendClicked();
				return FReply::Handled();
			}
			// Shift+Enter: 不拦截，let SMultiLineEditableTextBox handle newline
		}
		else
		{
			// Ctrl+Enter to Send 模式:
			//   Ctrl+Enter = 发送
			//   Enter = 换行
			if (bCtrl)
			{
				OnSendClicked();
				return FReply::Handled();
			}
			// Normal Enter: don't intercept, let SMultiLineEditableTextBox handle newline
		}
	}

	return FReply::Unhandled();
}

// ==================================================================
// 发送模式
// ==================================================================

void SUEAgentDashboard::OnSendModeChanged(ECheckBoxState NewState)
{
	bEnterToSend = (NewState == ECheckBoxState::Checked);
}

bool SUEAgentDashboard::ShouldSendOnEnter() const
{
	return bEnterToSend;
}

FText SUEAgentDashboard::GetSendHintText() const
{
	if (bEnterToSend)
	{
		return FUEAgentL10n::Get(TEXT("InputHintEnter"));
	}
	return FUEAgentL10n::Get(TEXT("InputHintCtrlEnter"));
}

// ==================================================================
// Slash 命令
// ==================================================================

void SUEAgentDashboard::InitSlashCommands()
{
	auto MakeCmd = [](const FString& Cmd, const FString& L10nKey, bool bLocal) -> FSlashCommandPtr {
		auto Item = MakeShared<FSlashCommand>();
		Item->Command = Cmd;
		Item->Description = FUEAgentL10n::GetStr(L10nKey);
		Item->bIsLocal = bLocal;
		return Item;
	};

	AllSlashCommands = {
		// --- Local commands (don't forward, execute locally) ---
		MakeCmd(TEXT("/connect"),    TEXT("SlashConnect"), true),
		MakeCmd(TEXT("/disconnect"), TEXT("SlashDisconnect"), true),
		MakeCmd(TEXT("/diagnose"),   TEXT("SlashDiagnose"), true),
		MakeCmd(TEXT("/status"),     TEXT("SlashStatus"), true),
		MakeCmd(TEXT("/clear"),      TEXT("SlashClear"), true),
		MakeCmd(TEXT("/cancel"),     TEXT("SlashCancel"), true),
		MakeCmd(TEXT("/resume"),     TEXT("SlashResume"), true),
		MakeCmd(TEXT("/help"),       TEXT("SlashHelp"), true),
		MakeCmd(TEXT("/plan"),       TEXT("SlashPlan"), true),

		// --- AI commands (after selection, send to AI Agent) ---
		MakeCmd(TEXT("/new"),        TEXT("SlashNew"), false),
		MakeCmd(TEXT("/compact"),    TEXT("SlashCompact"), false),
		MakeCmd(TEXT("/review"),     TEXT("SlashReview"), false),
		MakeCmd(TEXT("/undo"),       TEXT("SlashUndo"), false),
	};
}

void SUEAgentDashboard::UpdateSlashSuggestions(const FString& InputText)
{
	if (!SlashMenuAnchor.IsValid())
	{
		return;
	}

	// Only show when input starts with "/"
	if (!InputText.StartsWith(TEXT("/")))
	{
		SlashMenuAnchor->SetIsOpen(false);
		return;
	}

	FString Filter = InputText.ToLower();
	FilteredSlashCommands.Empty();

	for (const auto& Cmd : AllSlashCommands)
	{
		if (Cmd->Command.ToLower().Contains(Filter) || Filter == TEXT("/"))
		{
			FilteredSlashCommands.Add(Cmd);
		}
	}

	if (FilteredSlashCommands.Num() > 0)
	{
		if (SlashListView.IsValid())
		{
			SlashListView->RequestListRefresh();
		}
		SlashMenuAnchor->SetIsOpen(true);
	}
	else
	{
		SlashMenuAnchor->SetIsOpen(false);
	}
}

TSharedRef<ITableRow> SUEAgentDashboard::GenerateSlashCommandRow(
	FSlashCommandPtr Item, const TSharedRef<STableViewBase>& OwnerTable)
{
	// Command color: local command white, AI command blue
	FLinearColor CmdColor = Item->bIsLocal
		? FLinearColor(0.85f, 0.85f, 0.85f)
		: FLinearColor(0.4f, 0.75f, 1.0f);

	return SNew(STableRow<FSlashCommandPtr>, OwnerTable)
		.Padding(FMargin(6.0f, 3.0f))
		[
			SNew(SHorizontalBox)
			// Command name
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 12.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Item->Command))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
				.ColorAndOpacity(FSlateColor(CmdColor))
			]
			// Description
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Item->Description))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.55f, 0.55f, 0.55f)))
			]
		];
}

void SUEAgentDashboard::OnSlashCommandSelected(FSlashCommandPtr Item, ESelectInfo::Type SelectInfo)
{
	if (!Item.IsValid() || SelectInfo == ESelectInfo::Direct)
	{
		return;
	}

	const FString& Cmd = Item->Command;

	// Parse argument part from command (if input box has extra content)
	FString InputArgs;
	if (InputTextBox.IsValid())
	{
		FString FullInput = InputTextBox->GetText().ToString();
		if (FullInput.StartsWith(Cmd))
		{
			InputArgs = FullInput.Mid(Cmd.Len()).TrimStartAndEnd();
		}
	}

	// Clear input box and close menu (must be before HandleSlashCommand, because SendToOpenClaw checks input)
	if (InputTextBox.IsValid())
	{
		InputTextBox->SetText(FText::GetEmpty());
	}
	if (SlashMenuAnchor.IsValid())
	{
		SlashMenuAnchor->SetIsOpen(false);
	}

	// Handle command
	HandleSlashCommand(Cmd, InputArgs);
}

// ==================================================================
// Slash 命令处理 (集中路由)
// ==================================================================

void SUEAgentDashboard::HandleSlashCommand(const FString& Command, const FString& Args)
{
	// --- Local commands (don't forward, execute locally) ---
	if (Command == TEXT("/clear"))
	{
		// Pure local clear, don't send /new to AI
		Messages.Empty();
		RebuildMessageList();
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("ChatCleared")));
	}
	else if (Command == TEXT("/cancel"))
	{
		// Cancel: 始终发送 abort（UE 崩溃重启后也能停止 Gateway 上运行的 AI）
		{
			bIsWaitingForResponse = false;
			bHasStreamingMessage = false;
			StreamLinesRead = 0;
			StreamingTextWidget.Reset();
			StreamingMessageIndex = INDEX_NONE;

			// Stop poll timer (prevent old timer from continuing to poll file)
			if (PollTimerHandle.IsValid())
			{
				FTSTicker::GetCoreTicker().RemoveTicker(PollTimerHandle);
				PollTimerHandle.Reset();
			}

			// Notify platform to cancel current request
			PlatformBridge->CancelCurrentRequest();

			// Remove "Thinking..." or streaming message
			while (Messages.Num() > 0)
			{
				const FString& LastSender = Messages.Last().Sender;
				if (Messages.Last().Content == FUEAgentL10n::GetStr(TEXT("Thinking"))
					|| LastSender == TEXT("thinking")
					|| LastSender == TEXT("streaming"))
				{
					Messages.RemoveAt(Messages.Num() - 1);
				}
				else
				{
					break;
				}
			}
			RebuildMessageList();
			AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("RequestCancelled")));
		}
	}
	else if (Command == TEXT("/connect"))
	{
		ConnectOpenClawBridge();
	}
	else if (Command == TEXT("/resume"))
	{
		ResumeReceiving();
	}
	else if (Command == TEXT("/disconnect"))
	{
		DisconnectOpenClawBridge();
	}
	else if (Command == TEXT("/diagnose"))
	{
		RunDiagnoseConnection();
	}
	else if (Command == TEXT("/status"))
	{
		FString ClientStatus = bCachedIsConnected ? FUEAgentL10n::GetStr(TEXT("Connected")) : FUEAgentL10n::GetStr(TEXT("Disconnected"));
		FString ServerAddr = CachedSubsystem.IsValid() ? CachedSubsystem->GetServerAddress() : TEXT("N/A");
		FString SendMode = bEnterToSend ? FUEAgentL10n::GetStr(TEXT("EnterToSend")) : FUEAgentL10n::GetStr(TEXT("CtrlEnterToSend"));

		TArray<FStringFormatArg> FormatArgs;
		FormatArgs.Add(FStringFormatArg(ClientStatus));
		FormatArgs.Add(FStringFormatArg(ServerAddr));
		FormatArgs.Add(FStringFormatArg(Messages.Num()));
		FormatArgs.Add(FStringFormatArg(SendMode));

		// StatusFormat uses {0} {1} {2} {3} placeholders
		FString StatusText = FString::Format(*FUEAgentL10n::GetStr(TEXT("StatusFormat")), FormatArgs);
		AddMessage(TEXT("system"), StatusText);

		// Check MCP Server + platform bridge status
		PlatformBridge->QueryStatus();
	}
	else if (Command == TEXT("/help"))
	{
		FString HelpText = FUEAgentL10n::GetStr(TEXT("HelpTitle")) + TEXT("\n");
		HelpText += FUEAgentL10n::GetStr(TEXT("HelpSectionConnect")) + TEXT("\n");
		HelpText += FString::Printf(TEXT("    /connect     %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashConnect")));
		HelpText += FString::Printf(TEXT("    /disconnect  %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashDisconnect")));
		HelpText += FString::Printf(TEXT("    /diagnose    %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashDiagnose")));
		HelpText += FString::Printf(TEXT("    /status      %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashStatus")));
		HelpText += FUEAgentL10n::GetStr(TEXT("HelpSectionChat")) + TEXT("\n");
		HelpText += FString::Printf(TEXT("    /clear       %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashClear")));
		HelpText += FString::Printf(TEXT("    /cancel      %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashCancel")));
		HelpText += FString::Printf(TEXT("    /resume      %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashResume")));
		HelpText += FString::Printf(TEXT("    /help        %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashHelp")));
		HelpText += FString::Printf(TEXT("    /plan        %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashPlan")));
		HelpText += FUEAgentL10n::GetStr(TEXT("HelpSectionAI")) + TEXT("\n");
		for (const auto& Cmd : AllSlashCommands)
		{
			if (Cmd->bIsLocal)
			{
				continue;
			}
			HelpText += FString::Printf(TEXT("    %-12s %s\n"), *Cmd->Command, *Cmd->Description);
		}
		AddMessage(TEXT("system"), HelpText);
	}
	else if (Command == TEXT("/plan"))
	{
		if (Args.IsEmpty())
		{
			// /plan (no args) → toggle Plan mode switch
			bPlanMode = !bPlanMode;
			if (!bPlanMode)
			{
				// When turning off Plan mode, cancel if there's an active Plan
				if (CurrentPlan.IsSet())
				{
					if (CurrentPlan->bIsExecuting && bIsWaitingForResponse)
					{
						OnStopClicked();
					}
					CurrentPlan.Reset();
				}
			}
			AddMessage(TEXT("system"),
				bPlanMode
					? FUEAgentL10n::GetStr(TEXT("PlanModeEnabled"))
					: FUEAgentL10n::GetStr(TEXT("PlanModeDisabled")));
		}
		else
		{
			// /plan <task description> → enable Plan mode and send directly
			bPlanMode = true;
			LastPlanRequest = Args;
			AddMessage(TEXT("user"), Args);
			FString PlanPrompt = FString::Printf(
				TEXT("Please create a step-by-step plan for the following task.\n\n"
					 "Output ONLY the plan in this exact JSON format, do not execute anything, do not add any other text:\n"
					 "```json\n"
					 "{\"plan\":{\"steps\":[{\"index\":1,\"title\":\"Step title\",\"description\":\"Step description\"}]}}\n"
					 "```\n\n"
					 "Task: %s"),
				*Args);
			SendToOpenClaw(PlanPrompt);
		}
	}
	// --- AI commands (after selection, send command text directly to AI Agent) ---
	else
	{
		// Combine "/command args" into complete command and send to AI
		FString FullMessage = Command;
		if (!Args.IsEmpty())
		{
			FullMessage += TEXT(" ") + Args;
		}
		AddMessage(TEXT("user"), FullMessage);
		SendToOpenClaw(FullMessage);
	}
}

// ==================================================================
// 聊天辅助方法
// ==================================================================

void SUEAgentDashboard::AddMessage(const FString& Sender, const FString& Content, bool bIsCode)
{
	if (Messages.Num() >= MaxMessages)
	{
		Messages.RemoveAt(0, Messages.Num() - MaxMessages + 1);
	}

	FChatMessage Msg;
	Msg.Sender = Sender;
	Msg.Content = Content;
	Msg.Timestamp = FDateTime::Now();
	Msg.bIsCode = bIsCode;
	Messages.Add(MoveTemp(Msg));

	RebuildMessageList();
}

void SUEAgentDashboard::AddToolCallMessage(const FString& ToolName, const FString& ToolId, const FString& Arguments)
{
	if (Messages.Num() >= MaxMessages)
	{
		Messages.RemoveAt(0, Messages.Num() - MaxMessages + 1);
	}

	FChatMessage Msg;
	Msg.Sender = TEXT("tool_call");
	Msg.ToolName = ToolName;
	Msg.ToolId = ToolId;
	Msg.ToolArguments = Arguments;
	Msg.Timestamp = FDateTime::Now();
	Msg.bToolCollapsed = true;

	// Generate summary as Content
	Msg.Content = FString::Printf(TEXT("[%s] %s"), *ToolName, *ToolId);

	Messages.Add(MoveTemp(Msg));
	RebuildMessageList();
}

void SUEAgentDashboard::AddToolResultMessage(const FString& ToolName, const FString& ToolId, const FString& ResultContent, bool bIsError)
{
	// Try to find corresponding tool_call message and update it (instead of appending new message)
	for (int32 i = Messages.Num() - 1; i >= 0; --i)
	{
		if (Messages[i].Sender == TEXT("tool_call") && Messages[i].ToolId == ToolId)
		{
			Messages[i].ToolResult = ResultContent;
			Messages[i].bToolError = bIsError;
			if (bIsError)
			{
				Messages[i].Sender = TEXT("tool_error");
			}
			RebuildMessageList();
			return;
		}
	}

	// Didn't find corresponding call, add as independent result message
	if (Messages.Num() >= MaxMessages)
	{
		Messages.RemoveAt(0, Messages.Num() - MaxMessages + 1);
	}

	FChatMessage Msg;
	Msg.Sender = bIsError ? TEXT("tool_error") : TEXT("tool_result");
	Msg.ToolName = ToolName;
	Msg.ToolId = ToolId;
	Msg.ToolResult = ResultContent;
	Msg.bToolError = bIsError;
	Msg.Timestamp = FDateTime::Now();
	Msg.bToolCollapsed = true;
	Msg.Content = FString::Printf(TEXT("[%s] %s"), *ToolName, *ToolId);

	Messages.Add(MoveTemp(Msg));
	RebuildMessageList();
}

FReply SUEAgentDashboard::OnToggleToolCollapse(int32 MessageIndex)
{
	if (Messages.IsValidIndex(MessageIndex))
	{
		Messages[MessageIndex].bToolCollapsed = !Messages[MessageIndex].bToolCollapsed;
		RebuildMessageList();
	}
	return FReply::Handled();
}