// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentDashboard.h"
#include "UEAgentSubsystem.h"
#include "Editor.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Layout/SExpandableArea.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Input/SMenuAnchor.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/STableRow.h"
#include "IPythonScriptPlugin.h"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"

// ==================================================================
// Construct
// ==================================================================

void SUEAgentDashboard::Construct(const FArguments& InArgs)
{
	// 获取 Subsystem 单例
	if (GEditor)
	{
		CachedSubsystem = GEditor->GetEditorSubsystem<UUEAgentSubsystem>();
	}

	if (CachedSubsystem.IsValid())
	{
		bCachedIsConnected = CachedSubsystem->GetConnectionStatus();
		CachedSubsystem->OnConnectionStatusChangedNative.AddSP(
			this, &SUEAgentDashboard::HandleConnectionStatusChanged);
	}

	// 初始化 Slash 快捷命令
	InitSlashCommands();

	// --- 构建状态详情 Widget (折叠区域内容) ---
	TSharedRef<SWidget> StatusDetailContent =
		SNew(SVerticalBox)

		// 版本号
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0.0f, 2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth()
			[
				SNew(STextBlock)
				.Text(LOCTEXT("VersionLabel", "Version: "))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			]
			+ SHorizontalBox::Slot().AutoWidth()
			[
				SNew(STextBlock)
				.Text(this, &SUEAgentDashboard::GetVersionText)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			]
		]

		// 服务器地址
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0.0f, 2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth()
			[
				SNew(STextBlock)
				.Text(LOCTEXT("ServerLabel", "Server: "))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			]
			+ SHorizontalBox::Slot().AutoWidth()
			[
				SNew(STextBlock)
				.Text(this, &SUEAgentDashboard::GetServerAddressText)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			]
		]

		// 统计
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0.0f, 2.0f)
		[
			SNew(STextBlock)
			.Text(this, &SUEAgentDashboard::GetStatsText)
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			.AutoWrapText(true)
		]

		// 操作按钮 (紧凑排列)
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0.0f, 4.0f, 0.0f, 0.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 3.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("ConnectBtn", "Connect"))
				.ToolTipText(LOCTEXT("ConnectTip", "Connect to OpenClaw Gateway"))
				.OnClicked(this, &SUEAgentDashboard::OnConnectClicked)
				.ContentPadding(FMargin(6.0f, 2.0f))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 3.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("DisconnectBtn", "Disconnect"))
				.ToolTipText(LOCTEXT("DisconnectTip", "Disconnect from OpenClaw Gateway"))
				.OnClicked(this, &SUEAgentDashboard::OnDisconnectClicked)
				.ContentPadding(FMargin(6.0f, 2.0f))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 3.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("DiagnoseBtn", "Diagnose"))
				.ToolTipText(LOCTEXT("DiagnoseTip", "Run 6-step connection diagnostics"))
				.OnClicked(this, &SUEAgentDashboard::OnDiagnoseClicked)
				.ContentPadding(FMargin(6.0f, 2.0f))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(LOCTEXT("ViewLogsBtn", "Logs"))
				.ToolTipText(LOCTEXT("ViewLogsTip", "Open Output Log"))
				.OnClicked(this, &SUEAgentDashboard::OnViewLogsClicked)
				.ContentPadding(FMargin(6.0f, 2.0f))
			]
		];

	// --- Slash 命令下拉列表 ---
	TSharedRef<SWidget> SlashMenuContent =
		SNew(SBorder)
		.BorderImage(FAppStyle::GetBrush("Menu.Background"))
		.Padding(2.0f)
		[
			SNew(SBox)
			.MaxDesiredHeight(200.0f)
			.MinDesiredWidth(300.0f)
			[
				SAssignNew(SlashListView, SListView<FSlashCommandPtr>)
				.ListItemsSource(&FilteredSlashCommands)
				.OnGenerateRow(this, &SUEAgentDashboard::GenerateSlashCommandRow)
				.OnSelectionChanged(this, &SUEAgentDashboard::OnSlashCommandSelected)
				.SelectionMode(ESelectionMode::Single)
			]
		];

	// --- 主布局 ---
	ChildSlot
	[
		SNew(SVerticalBox)

		// ========== 状态栏 (可折叠) ==========
		+ SVerticalBox::Slot()
		.AutoHeight()
		[
			SNew(SExpandableArea)
			.InitiallyCollapsed(true)
			.AreaTitle(LOCTEXT("StatusAreaTitle", "Agent Status"))
			.HeaderContent()
			[
				// 单行摘要: 状态指示 + 连接信息
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(8.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(STextBlock)
					.Text(this, &SUEAgentDashboard::GetStatusSummaryText)
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
					.ColorAndOpacity(this, &SUEAgentDashboard::GetConnectionStatusColor)
				]
			]
			.BodyContent()
			[
				SNew(SBox)
				.Padding(FMargin(12.0f, 4.0f, 12.0f, 8.0f))
				[
					StatusDetailContent
				]
			]
		]

		// ========== 消息区域 ==========
		+ SVerticalBox::Slot()
		.FillHeight(1.0f)
		.Padding(4.0f, 2.0f)
		[
			SAssignNew(MessageScrollBox, SScrollBox)
		]

		// ========== 分隔线 ==========
		+ SVerticalBox::Slot()
		.AutoHeight()
		[
			SNew(SSeparator)
		]

		// ========== 输入区域 ==========
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(4.0f, 2.0f, 4.0f, 4.0f)
		[
			SNew(SVerticalBox)

			// Slash 命令菜单锚点
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SAssignNew(SlashMenuAnchor, SMenuAnchor)
				.Placement(MenuPlacement_AboveAnchor)
				.Method(EPopupMethod::UseCurrentWindow)
				[
					// 输入框 + 发送按钮 (横向排列)
					SNew(SHorizontalBox)

					// 多行输入框 (设置最小高度)
					+ SHorizontalBox::Slot()
					.FillWidth(1.0f)
					.Padding(0.0f, 0.0f, 4.0f, 0.0f)
					[
						SNew(SBox)
						.MinDesiredHeight(52.0f)
						.MaxDesiredHeight(120.0f)
						[
							SAssignNew(InputTextBox, SMultiLineEditableTextBox)
							.HintText(this, &SUEAgentDashboard::GetSendHintText)
							.AutoWrapText(true)
							.OnTextChanged(this, &SUEAgentDashboard::OnInputTextChanged)
							.OnTextCommitted(this, &SUEAgentDashboard::OnInputTextCommitted)
							.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
						]
					]

					// 发送按钮 (底部对齐)
					+ SHorizontalBox::Slot()
					.AutoWidth()
					.VAlign(VAlign_Bottom)
					.Padding(0.0f, 0.0f, 0.0f, 1.0f)
					[
						SNew(SButton)
						.Text(LOCTEXT("SendBtn", "\u25B6"))  // ▶ 符号
						.ToolTipText(LOCTEXT("SendTip", "Send message"))
						.OnClicked(this, &SUEAgentDashboard::OnSendClicked)
						.ContentPadding(FMargin(8.0f, 6.0f))
					]
				]
				.MenuContent(SlashMenuContent)
			]

			// 底部工具栏: /new + 弹性间距 + Enter to Send
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 2.0f, 0.0f, 0.0f)
			[
				SNew(SHorizontalBox)

				// /new 按钮 (小号紧凑)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(SButton)
					.Text(LOCTEXT("NewChatBtn", "+ New Chat"))
					.ToolTipText(LOCTEXT("NewChatTip", "Start a new conversation (/new)"))
					.OnClicked(this, &SUEAgentDashboard::OnNewChatClicked)
					.ContentPadding(FMargin(4.0f, 1.0f))
					.ButtonStyle(&FAppStyle::Get().GetWidgetStyle<FButtonStyle>("SimpleButton"))
				]

				// 弹性间距
				+ SHorizontalBox::Slot()
				.FillWidth(1.0f)
				[
					SNullWidget::NullWidget
				]

				// 发送模式: [☑] Enter to Send
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot()
					.AutoWidth()
					.VAlign(VAlign_Center)
					.Padding(0.0f, 0.0f, 2.0f, 0.0f)
					[
						SAssignNew(SendModeCheckBox, SCheckBox)
						.IsChecked(bEnterToSend ? ECheckBoxState::Checked : ECheckBoxState::Unchecked)
						.OnCheckStateChanged(this, &SUEAgentDashboard::OnSendModeChanged)
					]
					+ SHorizontalBox::Slot()
					.AutoWidth()
					.VAlign(VAlign_Center)
					[
						SNew(STextBlock)
						.Text(LOCTEXT("EnterToSendLabel", "Enter to Send"))
						.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
						.ColorAndOpacity(FSlateColor(FLinearColor(0.45f, 0.45f, 0.45f)))
					]
				]
			]
		]
	];

	// 欢迎消息
	AddMessage(TEXT("assistant"),
		TEXT("Hello! I'm the UE Editor Agent.\n\n")
		TEXT("Type / to see available commands, or ask me anything.\n")
		TEXT("Commands: /new, /connect, /disconnect, /diagnose, /status, /help"));

	// 打开面板时自动连接 OpenClaw Bridge
	ConnectOpenClawBridge();
}

SUEAgentDashboard::~SUEAgentDashboard()
{
	if (CachedSubsystem.IsValid())
	{
		CachedSubsystem->OnConnectionStatusChangedNative.RemoveAll(this);
	}
}

// ==================================================================
// 委托回调
// ==================================================================

void SUEAgentDashboard::HandleConnectionStatusChanged(bool bNewStatus)
{
	bCachedIsConnected = bNewStatus;

	FString StatusMsg = bNewStatus
		? TEXT("MCP client connected.")
		: TEXT("MCP client disconnected.");
	AddMessage(TEXT("system"), StatusMsg);
}

// ==================================================================
// 状态栏辅助方法
// ==================================================================

FText SUEAgentDashboard::GetConnectionStatusText() const
{
	return bCachedIsConnected
		? LOCTEXT("Connected", "Connected")
		: LOCTEXT("Disconnected", "Disconnected");
}

FSlateColor SUEAgentDashboard::GetConnectionStatusColor() const
{
	return bCachedIsConnected
		? FSlateColor(FLinearColor(0.2f, 0.8f, 0.2f))
		: FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f));
}

FText SUEAgentDashboard::GetVersionText() const
{
	if (CachedSubsystem.IsValid())
	{
		return FText::FromString(CachedSubsystem->GetPluginVersion());
	}
	return LOCTEXT("VersionUnknown", "Unknown");
}

FText SUEAgentDashboard::GetServerAddressText() const
{
	if (CachedSubsystem.IsValid())
	{
		FString Address = CachedSubsystem->GetServerAddress();
		if (!Address.IsEmpty())
		{
			return FText::FromString(Address);
		}
	}
	return LOCTEXT("ServerNotStarted", "Not started");
}

FText SUEAgentDashboard::GetStatsText() const
{
	int32 Connections = 0;
	if (CachedSubsystem.IsValid())
	{
		Connections = CachedSubsystem->GetClientCount();
	}
	return FText::FromString(FString::Printf(
		TEXT("Active Connections: %d  |  Messages: %d"),
		Connections, Messages.Num()));
}

FText SUEAgentDashboard::GetStatusSummaryText() const
{
	FString Summary = bCachedIsConnected
		? TEXT("● Connected")
		: TEXT("○ Disconnected");

	if (CachedSubsystem.IsValid())
	{
		FString Addr = CachedSubsystem->GetServerAddress();
		if (!Addr.IsEmpty())
		{
			Summary += FString::Printf(TEXT("  |  %s"), *Addr);
		}
	}
	return FText::FromString(Summary);
}

// ==================================================================
// 按钮回调
// ==================================================================

FReply SUEAgentDashboard::OnToggleStatusClicked()
{
	bStatusExpanded = !bStatusExpanded;
	if (StatusDetailWidget.IsValid())
	{
		StatusDetailWidget->SetVisibility(
			bStatusExpanded ? EVisibility::Visible : EVisibility::Collapsed);
	}
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnConnectClicked()
{
	ConnectOpenClawBridge();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnDisconnectClicked()
{
	DisconnectOpenClawBridge();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnDiagnoseClicked()
{
	RunDiagnoseConnection();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnViewLogsClicked()
{
	FGlobalTabmanager::Get()->TryInvokeTab(FName("OutputLog"));
	return FReply::Handled();
}

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

	// 检查是否为 Slash 命令
	if (InputText.StartsWith(TEXT("/")))
	{
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

	// 防止重复发送
	if (bIsWaitingForResponse)
	{
		AddMessage(TEXT("system"), TEXT("Waiting for AI response..."));
		return FReply::Handled();
	}

	// 添加用户消息
	AddMessage(TEXT("user"), InputText);

	// 通过 OpenClaw Python Bridge 转发给 AI
	SendToOpenClaw(InputText);

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnNewChatClicked()
{
	Messages.Empty();
	RebuildMessageList();
	AddMessage(TEXT("system"), TEXT("New conversation started."));
	// 可选: 通知 Python Bridge 重置 session
	IPythonScriptPlugin::Get()->ExecPythonCommand(
		TEXT("try:\n")
		TEXT("    from openclaw_bridge import _bridge\n")
		TEXT("    if _bridge: _bridge._session_key = ''\n")
		TEXT("except: pass"));
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
	if (CommitType == ETextCommit::OnEnter)
	{
		if (bEnterToSend)
		{
			// Enter 直接发送模式
			OnSendClicked();
		}
		// 否则 Enter 换行 (SMultiLineEditableTextBox 默认行为)
		// Ctrl+Enter 在 SMultiLineEditableTextBox 中也触发 OnEnter，
		// 所以在非 Enter 直发模式下也能发送
	}
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
		return LOCTEXT("InputHintEnter", "Ask AI anything... (Enter to send, Shift+Enter for newline, / for commands)");
	}
	return LOCTEXT("InputHintCtrlEnter", "Ask AI anything... (Ctrl+Enter to send, Enter for newline, / for commands)");
}

// ==================================================================
// Slash 命令
// ==================================================================

void SUEAgentDashboard::InitSlashCommands()
{
	auto MakeCmd = [](const FString& Cmd, const FString& Desc) -> FSlashCommandPtr {
		auto Item = MakeShared<FSlashCommand>();
		Item->Command = Cmd;
		Item->Description = Desc;
		return Item;
	};

	AllSlashCommands = {
		// --- 会话管理 ---
		MakeCmd(TEXT("/new"),        TEXT("Start a new conversation")),
		MakeCmd(TEXT("/clear"),      TEXT("Clear chat history (alias for /new)")),

		// --- 连接管理 ---
		MakeCmd(TEXT("/connect"),    TEXT("Connect to OpenClaw Gateway")),
		MakeCmd(TEXT("/disconnect"), TEXT("Disconnect from OpenClaw Gateway")),
		MakeCmd(TEXT("/diagnose"),   TEXT("Run connection diagnostics")),
		MakeCmd(TEXT("/status"),     TEXT("Show agent connection status")),

		// --- AI 工具 ---
		MakeCmd(TEXT("/select"),     TEXT("Show currently selected actors")),
		MakeCmd(TEXT("/create"),     TEXT("Create an actor (e.g. /create StaticMesh Cube)")),
		MakeCmd(TEXT("/delete"),     TEXT("Delete selected actors")),
		MakeCmd(TEXT("/material"),   TEXT("Inspect or modify materials")),
		MakeCmd(TEXT("/camera"),     TEXT("Get or set viewport camera")),
		MakeCmd(TEXT("/level"),      TEXT("Show level information")),
		MakeCmd(TEXT("/assets"),     TEXT("Search or list assets")),
		MakeCmd(TEXT("/run"),        TEXT("Execute Python code directly")),

		// --- 帮助 ---
		MakeCmd(TEXT("/help"),       TEXT("Show all available commands")),
	};
}

void SUEAgentDashboard::UpdateSlashSuggestions(const FString& InputText)
{
	if (!SlashMenuAnchor.IsValid())
	{
		return;
	}

	// 只在输入以 "/" 开头时显示
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
	return SNew(STableRow<FSlashCommandPtr>, OwnerTable)
		.Padding(FMargin(6.0f, 3.0f))
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 12.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Item->Command))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.4f, 0.8f, 1.0f)))
			]
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Item->Description))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f)))
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

	// 从命令中解析参数部分 (如果输入框有额外内容)
	FString InputArgs;
	if (InputTextBox.IsValid())
	{
		FString FullInput = InputTextBox->GetText().ToString();
		if (FullInput.StartsWith(Cmd))
		{
			InputArgs = FullInput.Mid(Cmd.Len()).TrimStartAndEnd();
		}
	}

	// 处理命令
	HandleSlashCommand(Cmd, InputArgs);

	// 清空输入框并关闭菜单
	if (InputTextBox.IsValid())
	{
		InputTextBox->SetText(FText::GetEmpty());
	}
	if (SlashMenuAnchor.IsValid())
	{
		SlashMenuAnchor->SetIsOpen(false);
	}
}

// ==================================================================
// Slash 命令处理 (集中路由)
// ==================================================================

void SUEAgentDashboard::HandleSlashCommand(const FString& Command, const FString& Args)
{
	if (Command == TEXT("/new") || Command == TEXT("/clear"))
	{
		OnNewChatClicked();
	}
	else if (Command == TEXT("/connect"))
	{
		ConnectOpenClawBridge();
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
		FString StatusText = FString::Printf(
			TEXT("Connection: %s\nServer: %s\nMessages: %d"),
			bCachedIsConnected ? TEXT("Connected") : TEXT("Disconnected"),
			CachedSubsystem.IsValid() ? *CachedSubsystem->GetServerAddress() : TEXT("N/A"),
			Messages.Num());
		AddMessage(TEXT("system"), StatusText);
	}
	else if (Command == TEXT("/help"))
	{
		FString HelpText = TEXT("Available commands:\n");
		HelpText += TEXT("\n  Session:\n");
		HelpText += TEXT("    /new         - Start a new conversation\n");
		HelpText += TEXT("    /clear       - Alias for /new\n");
		HelpText += TEXT("\n  Connection:\n");
		HelpText += TEXT("    /connect     - Connect to OpenClaw Gateway\n");
		HelpText += TEXT("    /disconnect  - Disconnect from Gateway\n");
		HelpText += TEXT("    /diagnose    - Run connection diagnostics\n");
		HelpText += TEXT("    /status      - Show connection status\n");
		HelpText += TEXT("\n  AI Tools:\n");
		for (const auto& Cmd : AllSlashCommands)
		{
			// 跳过已列出的命令
			if (Cmd->Command == TEXT("/new") || Cmd->Command == TEXT("/clear") ||
				Cmd->Command == TEXT("/connect") || Cmd->Command == TEXT("/disconnect") ||
				Cmd->Command == TEXT("/diagnose") || Cmd->Command == TEXT("/status") ||
				Cmd->Command == TEXT("/help"))
			{
				continue;
			}
			HelpText += FString::Printf(TEXT("    %-12s - %s\n"), *Cmd->Command, *Cmd->Description);
		}
		AddMessage(TEXT("system"), HelpText);
	}
	else
	{
		// AI 工具命令: 将 "/command args" 整合成自然语言发送给 AI
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

void SUEAgentDashboard::RebuildMessageList()
{
	if (!MessageScrollBox.IsValid())
	{
		return;
	}

	MessageScrollBox->ClearChildren();

	for (const FChatMessage& Msg : Messages)
	{
		FString TimeStr = Msg.Timestamp.ToString(TEXT("%H:%M"));

		FString SenderLabel;
		if (Msg.Sender == TEXT("user"))
		{
			SenderLabel = TEXT("You");
		}
		else if (Msg.Sender == TEXT("assistant"))
		{
			SenderLabel = TEXT("AI Agent");
		}
		else
		{
			SenderLabel = TEXT("System");
		}

		MessageScrollBox->AddSlot()
		.Padding(6.0f, 2.0f)
		[
			SNew(SVerticalBox)

			// 发送者 + 时间
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 1.0f)
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

			// 消息内容
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f, 0.0f, 0.0f, 4.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Msg.Content))
				.Font(Msg.bIsCode
					? FCoreStyle::GetDefaultFontStyle("Mono", 9)
					: FCoreStyle::GetDefaultFontStyle("Regular", 10))
				.AutoWrapText(true)
			]
		];
	}

	MessageScrollBox->ScrollToEnd();
}

// ==================================================================
// OpenClaw Bridge 连接管理
// ==================================================================

void SUEAgentDashboard::ConnectOpenClawBridge()
{
	AddMessage(TEXT("system"), TEXT("Connecting to OpenClaw Gateway..."));

	FString PythonCmd = TEXT(
		"from openclaw_bridge import connect\n"
		"connect()\n"
		"import time; time.sleep(1.5)\n"
		"from openclaw_bridge import is_connected\n"
		"if is_connected():\n"
		"    print('[LogUEAgent] OpenClaw Bridge connected successfully')\n"
		"else:\n"
		"    print('[LogUEAgent] OpenClaw Bridge connection pending...')\n"
	);
	IPythonScriptPlugin::Get()->ExecPythonCommand(*PythonCmd);

	// 延迟检查连接状态
	auto Self = SharedThis(this);
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self](float) -> bool
		{
			FString CheckCmd = TEXT(
				"from openclaw_bridge import is_connected\n"
				"_ue_bridge_connected = is_connected()\n"
			);
			IPythonScriptPlugin::Get()->ExecPythonCommand(*CheckCmd);
			// 由于无法直接返回 Python 值，通过文件或日志间接确认
			Self->AddMessage(TEXT("system"), TEXT("OpenClaw Bridge connect requested. Check status with /status."));
			return false;
		}),
		2.0f
	);
}

void SUEAgentDashboard::DisconnectOpenClawBridge()
{
	FString PythonCmd = TEXT(
		"from openclaw_bridge import shutdown\n"
		"shutdown()\n"
		"print('[LogUEAgent] OpenClaw Bridge disconnected')\n"
	);
	IPythonScriptPlugin::Get()->ExecPythonCommand(*PythonCmd);
	AddMessage(TEXT("system"), TEXT("OpenClaw Bridge disconnected."));
}

void SUEAgentDashboard::RunDiagnoseConnection()
{
	AddMessage(TEXT("system"), TEXT("Running connection diagnostics..."));

	// 诊断结果写入临时文件，然后轮询读取
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString DiagFile = TempDir / TEXT("_diagnose_result.txt");

	// 清除上次结果
	IFileManager::Get().Delete(*DiagFile, false, false, true);

	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_bridge import diagnose_connection\n"
			 "result = diagnose_connection()\n"
			 "with open(r'%s', 'w', encoding='utf-8') as f:\n"
			 "    f.write(result)\n"),
		*DiagFile);
	IPythonScriptPlugin::Get()->ExecPythonCommand(*PythonCmd);

	// 轮询诊断结果文件
	auto Self = SharedThis(this);
	FString CapturedFile = DiagFile;
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedFile](float) -> bool
		{
			if (!FPaths::FileExists(CapturedFile))
			{
				return true; // 继续等待
			}

			FString Content;
			if (FFileHelper::LoadFileToString(Content, *CapturedFile))
			{
				IFileManager::Get().Delete(*CapturedFile, false, false, true);
				Self->AddMessage(TEXT("system"), Content);
			}
			return false;
		}),
		0.5f
	);
}

// ==================================================================
// OpenClaw Gateway 通信 (阶段 3) — 通过 Python Bridge
// ==================================================================

void SUEAgentDashboard::SendToOpenClaw(const FString& UserMessage)
{
	bIsWaitingForResponse = true;
	AddMessage(TEXT("system"), TEXT("Thinking..."));

	// 转义消息中的引号和特殊字符，安全嵌入 Python 字符串
	FString EscapedMsg = UserMessage;
	EscapedMsg.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
	EscapedMsg.ReplaceInline(TEXT("'"), TEXT("\\'"));
	EscapedMsg.ReplaceInline(TEXT("\n"), TEXT("\\n"));
	EscapedMsg.ReplaceInline(TEXT("\r"), TEXT(""));

	// 临时文件路径 — Python 写入响应，C++ 读取
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString ResponseFile = TempDir / TEXT("_openclaw_response.txt");

	// 清除上次响应文件
	IFileManager::Get().Delete(*ResponseFile, false, false, true);

	// 通过 Python Bridge 异步发送
	// Python 侧会把结果写入临时文件
	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_bridge import send_chat_async_to_file; send_chat_async_to_file('%s', r'%s')"),
		*EscapedMsg, *ResponseFile);

	IPythonScriptPlugin::Get()->ExecPythonCommand(*PythonCmd);

	// 启动定时器轮询临时文件
	auto Self = SharedThis(this);
	FString CapturedResponseFile = ResponseFile;
	PollTimerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedResponseFile](float DeltaTime) -> bool
		{
			if (!Self->bIsWaitingForResponse)
			{
				return false;
			}

			// 检查响应文件是否存在
			if (!FPaths::FileExists(CapturedResponseFile))
			{
				return true; // 继续等待
			}

			// 读取响应
			FString ResponseContent;
			if (FFileHelper::LoadFileToString(ResponseContent, *CapturedResponseFile))
			{
				// 删除临时文件
				IFileManager::Get().Delete(*CapturedResponseFile, false, false, true);

				// 处理响应
				Self->HandlePythonResponse(ResponseContent);
			}

			return false; // 停止轮询
		}),
		0.5f // 每 0.5 秒检查一次
	);
}

void SUEAgentDashboard::HandlePythonResponse(const FString& Response)
{
	bIsWaitingForResponse = false;

	// 移除 "Thinking..." 消息
	if (Messages.Num() > 0 && Messages.Last().Content == TEXT("Thinking..."))
	{
		Messages.RemoveAt(Messages.Num() - 1);
		RebuildMessageList();
	}

	if (Response.IsEmpty())
	{
		AddMessage(TEXT("system"), TEXT("Empty response from AI."));
		return;
	}

	// 检查是否是错误
	if (Response.StartsWith(TEXT("[Error]")))
	{
		AddMessage(TEXT("system"), Response);
		return;
	}

	// 显示 AI 回复
	AddMessage(TEXT("assistant"), Response);
}


// ==================================================================
// 消息发送者颜色
// ==================================================================

FSlateColor SUEAgentDashboard::GetSenderColor(const FString& Sender) const
{
	if (Sender == TEXT("user"))
	{
		return FSlateColor(FLinearColor(0.3f, 0.7f, 1.0f));
	}
	else if (Sender == TEXT("assistant"))
	{
		return FSlateColor(FLinearColor(0.4f, 0.9f, 0.4f));
	}
	else
	{
		return FSlateColor(FLinearColor(0.7f, 0.7f, 0.7f));
	}
}

#undef LOCTEXT_NAMESPACE