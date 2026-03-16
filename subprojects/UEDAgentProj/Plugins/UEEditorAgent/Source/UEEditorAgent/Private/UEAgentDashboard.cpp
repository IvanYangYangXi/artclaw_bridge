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

		// 操作按钮
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0.0f, 4.0f, 0.0f, 0.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 6.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("TestConnectionBtn", "Test Connection"))
				.OnClicked(this, &SUEAgentDashboard::OnTestConnectionClicked)
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(LOCTEXT("ViewLogsBtn", "View Logs"))
				.OnClicked(this, &SUEAgentDashboard::OnViewLogsClicked)
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
		.MaxHeight(160.0f)
		.Padding(6.0f, 4.0f, 6.0f, 6.0f)
		[
			SNew(SVerticalBox)

			// Slash 命令菜单锚点 (浮在输入框上方)
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SAssignNew(SlashMenuAnchor, SMenuAnchor)
				.Placement(MenuPlacement_AboveAnchor)
				.Method(EPopupMethod::UseCurrentWindow)
				[
					// 输入行: 多行输入 + 按钮
					SNew(SHorizontalBox)

					// 多行输入框
					+ SHorizontalBox::Slot()
					.FillWidth(1.0f)
					.Padding(0.0f, 0.0f, 4.0f, 0.0f)
					[
						SAssignNew(InputTextBox, SMultiLineEditableTextBox)
						.HintText(LOCTEXT("InputHint", "Ask AI anything... (type / for commands)"))
						.AutoWrapText(true)
						.OnTextChanged(this, &SUEAgentDashboard::OnInputTextChanged)
						.OnTextCommitted(this, &SUEAgentDashboard::OnInputTextCommitted)
					]

					// 按钮列
					+ SHorizontalBox::Slot()
					.AutoWidth()
					.VAlign(VAlign_Bottom)
					[
						SNew(SVerticalBox)
						+ SVerticalBox::Slot()
						.AutoHeight()
						.Padding(0.0f, 0.0f, 0.0f, 2.0f)
						[
							SNew(SButton)
							.Text(LOCTEXT("SendBtn", "Send"))
							.ToolTipText(LOCTEXT("SendTip", "Send message (Ctrl+Enter)"))
							.OnClicked(this, &SUEAgentDashboard::OnSendClicked)
						]
						+ SVerticalBox::Slot()
						.AutoHeight()
						[
							SNew(SButton)
							.Text(LOCTEXT("ClearBtn", "Clear"))
							.ToolTipText(LOCTEXT("ClearTip", "Clear chat history"))
							.OnClicked(this, &SUEAgentDashboard::OnClearClicked)
						]
					]
				]
				.MenuContent(SlashMenuContent)
			]
		]
	];

	// 欢迎消息
	AddMessage(TEXT("assistant"),
		TEXT("Hello! I'm the UE Editor Agent.\n\n")
		TEXT("Type / to see available commands, or ask me anything.\n")
		TEXT("Connect an MCP client to enable AI responses."));
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

FReply SUEAgentDashboard::OnTestConnectionClicked()
{
	if (CachedSubsystem.IsValid())
	{
		CachedSubsystem->SetConnectionStatus(!CachedSubsystem->GetConnectionStatus());
	}
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

	// 防止重复发送
	if (bIsWaitingForResponse)
	{
		AddMessage(TEXT("system"), TEXT("Waiting for AI response..."));
		return FReply::Handled();
	}

	// 关闭 Slash 菜单
	if (SlashMenuAnchor.IsValid())
	{
		SlashMenuAnchor->SetIsOpen(false);
	}

	// 添加用户消息
	AddMessage(TEXT("user"), InputText);

	// 清空输入框
	InputTextBox->SetText(FText::GetEmpty());

	// 通过 OpenClaw Gateway HTTP API 转发给 AI
	SendToOpenClaw(InputText);

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnClearClicked()
{
	Messages.Empty();
	RebuildMessageList();
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
	// Ctrl+Enter 发送 (SMultiLineEditableTextBox 的 OnEnter 默认换行)
	if (CommitType == ETextCommit::OnEnter)
	{
		OnSendClicked();
	}
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
		MakeCmd(TEXT("/select"),    TEXT("Show currently selected actors")),
		MakeCmd(TEXT("/create"),    TEXT("Create an actor (e.g. /create StaticMesh Cube)")),
		MakeCmd(TEXT("/delete"),    TEXT("Delete selected actors")),
		MakeCmd(TEXT("/material"),  TEXT("Inspect or modify materials")),
		MakeCmd(TEXT("/camera"),    TEXT("Get or set viewport camera")),
		MakeCmd(TEXT("/level"),     TEXT("Show level information")),
		MakeCmd(TEXT("/assets"),    TEXT("Search or list assets")),
		MakeCmd(TEXT("/run"),       TEXT("Execute Python code directly")),
		MakeCmd(TEXT("/status"),    TEXT("Show agent connection status")),
		MakeCmd(TEXT("/clear"),     TEXT("Clear chat history")),
		MakeCmd(TEXT("/help"),      TEXT("Show all available commands")),
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

	// 处理内置命令
	if (Item->Command == TEXT("/clear"))
	{
		OnClearClicked();
		if (InputTextBox.IsValid())
		{
			InputTextBox->SetText(FText::GetEmpty());
		}
	}
	else if (Item->Command == TEXT("/help"))
	{
		FString HelpText = TEXT("Available commands:\n");
		for (const auto& Cmd : AllSlashCommands)
		{
			HelpText += FString::Printf(TEXT("  %s - %s\n"), *Cmd->Command, *Cmd->Description);
		}
		AddMessage(TEXT("system"), HelpText);
		if (InputTextBox.IsValid())
		{
			InputTextBox->SetText(FText::GetEmpty());
		}
	}
	else if (Item->Command == TEXT("/status"))
	{
		FString StatusText = FString::Printf(TEXT("Connection: %s\nServer: %s"),
			bCachedIsConnected ? TEXT("Connected") : TEXT("Disconnected"),
			CachedSubsystem.IsValid() ? *CachedSubsystem->GetServerAddress() : TEXT("N/A"));
		AddMessage(TEXT("system"), StatusText);
		if (InputTextBox.IsValid())
		{
			InputTextBox->SetText(FText::GetEmpty());
		}
	}
	else
	{
		// 将命令填入输入框并追加空格，等待用户补充参数
		if (InputTextBox.IsValid())
		{
			InputTextBox->SetText(FText::FromString(Item->Command + TEXT(" ")));
		}
	}

	// 关闭菜单
	if (SlashMenuAnchor.IsValid())
	{
		SlashMenuAnchor->SetIsOpen(false);
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