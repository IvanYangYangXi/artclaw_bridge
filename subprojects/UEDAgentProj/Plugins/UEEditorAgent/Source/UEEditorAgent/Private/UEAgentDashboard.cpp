// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentDashboard.h"
#include "UEAgentSubsystem.h"
#include "Editor.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Layout/SExpandableArea.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Text/SMultiLineEditableText.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SMultiLineEditableTextBox.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SMenuAnchor.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/STableRow.h"
#include "Framework/Application/SlateApplication.h"
#include "Misc/MessageDialog.h"
#include "IPythonScriptPlugin.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Misc/Guid.h"
#include "Misc/FileHelper.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonWriter.h"

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

		// ========== 快捷输入分栏 (可折叠) ==========
		+ SVerticalBox::Slot()
		.AutoHeight()
		[
			SAssignNew(QuickInputExpandableArea, SExpandableArea)
			.InitiallyCollapsed(true)
			.AreaTitle(LOCTEXT("QuickInputTitle", "Quick Inputs"))
			.BodyContent()
			[
				SNew(SBox)
				.Padding(FMargin(8.0f, 4.0f, 8.0f, 4.0f))
				[
					SNew(SVerticalBox)

					// 快捷按钮容器 (WrapBox 自动换行)
					+ SVerticalBox::Slot()
					.AutoHeight()
					[
						SAssignNew(QuickInputWrapBox, SWrapBox)
						.UseAllottedSize(true)
					]

					// 添加按钮 (始终显示在末尾)
					+ SVerticalBox::Slot()
					.AutoHeight()
					.Padding(0.0f, 4.0f, 0.0f, 0.0f)
					[
						SNew(SHorizontalBox)
						+ SHorizontalBox::Slot()
						.AutoWidth()
						[
							SNew(SButton)
							.Text(LOCTEXT("AddQuickInputBtn", "+ Add"))
							.ToolTipText(LOCTEXT("AddQuickInputTip", "Add a new quick input"))
							.OnClicked(this, &SUEAgentDashboard::OnAddQuickInputClicked)
							.ContentPadding(FMargin(6.0f, 2.0f))
						]
					]
				]
			]
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
						.HintText(LOCTEXT("InputHintDefault", "Ask AI anything... (Enter to send, / for commands)"))
						.AutoWrapText(true)
						.OnTextChanged(this, &SUEAgentDashboard::OnInputTextChanged)
						.OnTextCommitted(this, &SUEAgentDashboard::OnInputTextCommitted)
						.OnKeyDownHandler(this, &SUEAgentDashboard::OnInputKeyDown)
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
						.Text(LOCTEXT("SendBtn", "Send"))
						.ToolTipText(LOCTEXT("SendTip", "Send message"))
						.OnClicked(this, &SUEAgentDashboard::OnSendClicked)
						.ContentPadding(FMargin(6.0f, 4.0f))
					]
				]
				.MenuContent(SlashMenuContent)
			]

			// 底部工具栏: /new + Create Skill + 弹性间距 + Enter to Send
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
				]

				// D1: Create Skill 按钮
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text(LOCTEXT("CreateSkillBtn", "\xF0\x9F\x94\xA7 Create Skill"))
					.ToolTipText(LOCTEXT("CreateSkillTip", "Create a new ArtClaw Skill via natural language description"))
					.OnClicked(this, &SUEAgentDashboard::OnCreateSkillClicked)
					.ContentPadding(FMargin(4.0f, 1.0f))
				]

				// 弹性间距
				+ SHorizontalBox::Slot()
				.FillWidth(1.0f)
				[
					SNew(SSpacer)
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

	// 加载快捷输入配置并构建 UI
	LoadQuickInputs();
	RebuildQuickInputPanel();

	// 欢迎消息
	AddMessage(TEXT("assistant"),
		TEXT("Hello! I'm the UE Claw Bridge AI Assistant.\n\n")
		TEXT("Type / to see available commands, or ask me anything.\n")
		TEXT("Commands: /new, /connect, /disconnect, /diagnose, /status, /help"));

	// 打开面板时自动连接 OpenClaw Bridge
	ConnectOpenClawBridge();

	// MCP Server 状态检查延迟到 3 秒后执行，避免在启动阶段误报
	// （MCP Server 通过 Slate tick 异步启动，Dashboard 构造时可能还没就绪）
	{
		auto Self = SharedThis(this);
		FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateLambda([Self](float) -> bool
			{
				FString CheckMcpCmd = TEXT(
					"import socket\n"
					"_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
					"_s.settimeout(0.5)\n"
					"try:\n"
					"    _s.connect(('127.0.0.1', 8080))\n"
					"    _s.close()\n"
					"    print('[LogUEAgent] MCP Server: port 8080 OK')\n"
					"except:\n"
					"    _s.close()\n"
					"    print('[LogUEAgent_Error] MCP Server: port 8080 NOT listening')\n"
				);
				IPythonScriptPlugin::Get()->ExecPythonCommand(*CheckMcpCmd);
				return false; // 只执行一次
			}),
			3.0f // 延迟 3 秒
		);
	}
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
	if (bCachedIsConnected)
	{
		return LOCTEXT("Connected", "Connected");
	}
	return LOCTEXT("Disconnected", "Disconnected");
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

	// D1/D2: 检查是否为 ArtClaw Skill 创建触发
	if (IsArtclawSkillTrigger(InputText))
	{
		FString SkillDesc = ExtractSkillDescription(InputText);
		AddMessage(TEXT("user"), InputText);
		InputTextBox->SetText(FText::GetEmpty());

		if (SkillDesc.IsEmpty())
		{
			// 没有具体描述 → 打开对话框让用户输入
			OpenSkillCreationDialog();
		}
		else
		{
			// 有描述 → 直接触发生成流程
			StartSkillGeneration(SkillDesc, TEXT(""), TEXT("unreal_engine"));
		}
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
	// 1) 本地清屏
	Messages.Empty();
	RebuildMessageList();
	AddMessage(TEXT("system"), TEXT("New conversation started."));

	// 2) 重置 Python Bridge 的 session key
	IPythonScriptPlugin::Get()->ExecPythonCommand(
		TEXT("try:\n")
		TEXT("    from openclaw_bridge import _bridge\n")
		TEXT("    if _bridge: _bridge._session_key = ''\n")
		TEXT("except: pass"));

	// 3) 发送 /new 给 AI（重置远端会话），静默处理不显示 Thinking
	{
		FString EscapedMsg = TEXT("/new");
		FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
		IFileManager::Get().MakeDirectory(*TempDir, true);
		FString ResponseFile = TempDir / TEXT("_openclaw_newchat_response.txt");
		IFileManager::Get().Delete(*ResponseFile, false, false, true);

		FString PythonCmd = FString::Printf(
			TEXT("from openclaw_bridge import send_chat_async_to_file; send_chat_async_to_file('%s', r'%s')"),
			*EscapedMsg, *ResponseFile);
		IPythonScriptPlugin::Get()->ExecPythonCommand(*PythonCmd);

		// 静默丢弃 /new 的响应（只是为了触发 AI 侧重置）
		auto Self = SharedThis(this);
		FString CapturedFile = ResponseFile;
		FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateLambda([Self, CapturedFile](float) -> bool
			{
				if (!FPaths::FileExists(CapturedFile))
				{
					return true;
				}
				// 读取并丢弃响应文件
				IFileManager::Get().Delete(*CapturedFile, false, false, true);
				return false;
			}),
			0.5f
		);
	}

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
			// Shift+Enter: 不拦截，让 SMultiLineEditableTextBox 处理换行
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
			// 普通 Enter: 不拦截，让 SMultiLineEditableTextBox 处理换行
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
		return LOCTEXT("InputHintEnter", "Ask AI anything... (Enter to send, Shift+Enter for newline, / for commands)");
	}
	return LOCTEXT("InputHintCtrlEnter", "Ask AI anything... (Ctrl+Enter to send, Enter for newline, / for commands)");
}

// ==================================================================
// Slash 命令
// ==================================================================

void SUEAgentDashboard::InitSlashCommands()
{
	auto MakeCmd = [](const FString& Cmd, const FString& Desc, bool bLocal) -> FSlashCommandPtr {
		auto Item = MakeShared<FSlashCommand>();
		Item->Command = Cmd;
		Item->Description = Desc;
		Item->bIsLocal = bLocal;
		return Item;
	};

	AllSlashCommands = {
		// --- 本地命令 (不转发，本地执行) ---
		MakeCmd(TEXT("/connect"),    TEXT("[本地] 连接 OpenClaw 网关"), true),
		MakeCmd(TEXT("/disconnect"), TEXT("[本地] 断开 OpenClaw 网关连接"), true),
		MakeCmd(TEXT("/diagnose"),   TEXT("[本地] 运行连接诊断"), true),
		MakeCmd(TEXT("/status"),     TEXT("[本地] 显示连接状态"), true),
		MakeCmd(TEXT("/help"),       TEXT("[本地] 显示所有可用命令"), true),
		MakeCmd(TEXT("/clear"),      TEXT("[本地] 清空聊天记录"), true),

		// --- AI 命令 (选中后发送给 AI Agent) ---
		MakeCmd(TEXT("/new"),        TEXT("[AI] 开始新会话"), false),
		MakeCmd(TEXT("/select"),     TEXT("[AI] 查看选中物体"), false),
		MakeCmd(TEXT("/create"),     TEXT("[AI] 创建物体 (如 /create StaticMesh Cube)"), false),
		MakeCmd(TEXT("/delete"),     TEXT("[AI] 删除选中物体"), false),
		MakeCmd(TEXT("/material"),   TEXT("[AI] 材质操作"), false),
		MakeCmd(TEXT("/camera"),     TEXT("[AI] 相机操作"), false),
		MakeCmd(TEXT("/level"),      TEXT("[AI] 关卡信息"), false),
		MakeCmd(TEXT("/assets"),     TEXT("[AI] 资产搜索"), false),
		MakeCmd(TEXT("/run"),        TEXT("[AI] 执行 Python 代码"), false),
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
	// 根据命令类型选择不同颜色
	FLinearColor TypeColor = Item->bIsLocal
		? FLinearColor(0.4f, 0.9f, 0.4f)  // 本地命令 - 绿色
		: FLinearColor(0.4f, 0.7f, 1.0f); // AI 命令 - 蓝色

	FLinearColor TypeBgColor = Item->bIsLocal
		? FLinearColor(0.1f, 0.3f, 0.1f, 0.3f)  // 本地命令背景 - 深绿色半透明
		: FLinearColor(0.1f, 0.2f, 0.3f, 0.3f); // AI 命令背景 - 深蓝色半透明

	FString TypeLabel = Item->bIsLocal ? TEXT("本地") : TEXT("AI");

	return SNew(STableRow<FSlashCommandPtr>, OwnerTable)
		.Padding(FMargin(6.0f, 3.0f))
		[
			SNew(SHorizontalBox)
			// 类型标签 (本地/AI)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 8.0f, 0.0f)
			.VAlign(VAlign_Center)
			[
				SNew(SBorder)
				.BorderBackgroundColor(FSlateColor(TypeBgColor))
				.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.GroupBorder"))
				.Padding(FMargin(4.0f, 1.0f))
				[
					SNew(STextBlock)
					.Text(FText::FromString(TypeLabel))
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 8))
					.ColorAndOpacity(FSlateColor(TypeColor))
				]
			]
			// 命令名
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 12.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Item->Command))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.9f, 0.9f, 0.9f)))
			]
			// 描述
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

	// 清空输入框并关闭菜单 (必须在 HandleSlashCommand 之前，因为 SendToOpenClaw 会检查输入)
	if (InputTextBox.IsValid())
	{
		InputTextBox->SetText(FText::GetEmpty());
	}
	if (SlashMenuAnchor.IsValid())
	{
		SlashMenuAnchor->SetIsOpen(false);
	}

	// 处理命令
	HandleSlashCommand(Cmd, InputArgs);
}

// ==================================================================
// Slash 命令处理 (集中路由)
// ==================================================================

void SUEAgentDashboard::HandleSlashCommand(const FString& Command, const FString& Args)
{
	// --- 本地命令 (不转发，本地执行) ---
	if (Command == TEXT("/clear"))
	{
		// 纯本地清屏，不发 /new 给 AI
		Messages.Empty();
		RebuildMessageList();
		AddMessage(TEXT("system"), TEXT("Chat cleared."));
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
			TEXT("MCP Client: %s\nMCP Server: %s\nMessages: %d\nSend Mode: %s"),
			bCachedIsConnected ? TEXT("Connected") : TEXT("Disconnected"),
			CachedSubsystem.IsValid() ? *CachedSubsystem->GetServerAddress() : TEXT("N/A"),
			Messages.Num(),
			bEnterToSend ? TEXT("Enter to Send") : TEXT("Ctrl+Enter to Send"));
		AddMessage(TEXT("system"), StatusText);

		// 检查 MCP Server + OpenClaw Bridge 状态
		FString PythonCheck = TEXT(
			"import socket\n"
			"_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
			"_s.settimeout(0.5)\n"
			"mcp_ok = False\n"
			"try:\n"
			"    _s.connect(('127.0.0.1', 8080))\n"
			"    mcp_ok = True\n"
			"except: pass\n"
			"finally: _s.close()\n"
			"from openclaw_bridge import is_connected as _oc_connected\n"
			"oc_ok = _oc_connected()\n"
			"_mcp_s = 'OK' if mcp_ok else 'DOWN'\n"
			"_oc_s = 'Connected' if oc_ok else 'Disconnected'\n"
			"print(f'[LogUEAgent] Status: MCP Server={_mcp_s}, OpenClaw Bridge={_oc_s}')\n"
		);
		IPythonScriptPlugin::Get()->ExecPythonCommand(*PythonCheck);
	}
	else if (Command == TEXT("/help"))
	{
		FString HelpText = TEXT("可用命令列表:\n");
		HelpText += TEXT("\n  [本地命令 - 本地执行]:\n");
		HelpText += TEXT("    /connect     - 连接 OpenClaw 网关\n");
		HelpText += TEXT("    /disconnect  - 断开 OpenClaw 网关连接\n");
		HelpText += TEXT("    /diagnose    - 运行连接诊断\n");
		HelpText += TEXT("    /status      - 显示连接状态\n");
		HelpText += TEXT("    /clear       - 清空聊天记录\n");
		HelpText += TEXT("    /help        - 显示所有可用命令\n");
		HelpText += TEXT("\n  [AI 命令 - 发送给 AI Agent]:\n");
		for (const auto& Cmd : AllSlashCommands)
		{
			// 只显示 AI 命令
			if (Cmd->bIsLocal)
			{
				continue;
			}
			HelpText += FString::Printf(TEXT("    %-12s - %s\n"), *Cmd->Command, *Cmd->Description);
		}
		AddMessage(TEXT("system"), HelpText);
	}
	// --- AI 命令 (选中后将命令文字直接作为消息发送给 AI Agent) ---
	else
	{
		// 将 "/command args" 整合成完整命令发送给 AI
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

			// 消息内容 (可选中/复制)
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f, 0.0f, 0.0f, 4.0f)
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

	MessageScrollBox->ScrollToEnd();
}

// ==================================================================
// OpenClaw Bridge 连接管理
// ==================================================================

void SUEAgentDashboard::ConnectOpenClawBridge()
{
	AddMessage(TEXT("system"), TEXT("Connecting..."));

	// 检测 UE MCP Server 是否就绪（只检查，不重复启动；
	// init_unreal.py 已通过 Slate tick 延迟启动 MCP，这里只需等待）
	FString CheckMcp = TEXT(
		"import socket\n"
		"def _check_mcp_ready():\n"
		"    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
		"    s.settimeout(0.5)\n"
		"    try:\n"
		"        s.connect(('127.0.0.1', 8080))\n"
		"        s.close()\n"
		"        print('[LogUEAgent] MCP Server: OK')\n"
		"    except:\n"
		"        s.close()\n"
		"        print('[LogUEAgent] MCP Server: not ready yet (init_unreal will start it)')\n"
		"_check_mcp_ready()\n"
	);
	IPythonScriptPlugin::Get()->ExecPythonCommand(*CheckMcp);

	// 连接 OpenClaw Bridge (Chat 通道) + 检查结果
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString StatusFile = TempDir / TEXT("_connect_status.txt");
	IFileManager::Get().Delete(*StatusFile, false, false, true);

	FString ConnectBridge = FString::Printf(
		TEXT("import time\n"
			 "from openclaw_bridge import connect, is_connected\n"
			 "connect()\n"
			 "time.sleep(1.5)\n"
			 "status = 'ok' if is_connected() else 'fail'\n"
			 "with open(r'%s', 'w') as f:\n"
			 "    f.write(status)\n"),
		*StatusFile
	);
	IPythonScriptPlugin::Get()->ExecPythonCommand(*ConnectBridge);

	// 轮询连接结果
	auto Self = SharedThis(this);
	FString CapturedFile = StatusFile;
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedFile](float) -> bool
		{
			if (!FPaths::FileExists(CapturedFile))
			{
				return true;
			}

			FString Status;
			FFileHelper::LoadFileToString(Status, *CapturedFile);
			IFileManager::Get().Delete(*CapturedFile, false, false, true);
			Status.TrimStartAndEndInline();

			if (Status == TEXT("ok"))
			{
				Self->AddMessage(TEXT("system"), TEXT("OpenClaw Bridge: Connected."));
			}
			else
			{
				Self->AddMessage(TEXT("system"),
					TEXT("OpenClaw Bridge: Connection failed.\n"
						 "Check: 1) OpenClaw is running  2) Gateway port 18789  3) /diagnose"));
			}
			return false;
		}),
		0.5f
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
	AddMessage(TEXT("system"), TEXT("Running environment health check..."));

	// 诊断结果写入临时文件，然后轮询读取
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString DiagFile = TempDir / TEXT("_diagnose_result.txt");

	// 清除上次结果
	IFileManager::Get().Delete(*DiagFile, false, false, true);

	// 优先使用完整 Health Check，fallback 到 diagnose_connection
	// 强制 reload 确保使用最新代码
	FString PythonCmd = FString::Printf(
		TEXT("import importlib\n"
			 "try:\n"
			 "    import health_check\n"
			 "    importlib.reload(health_check)\n"
			 "    result = health_check.run_health_check()\n"
			 "except ImportError:\n"
			 "    from openclaw_bridge import diagnose_connection\n"
			 "    result = diagnose_connection()\n"
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
			TArray<uint8> DiagBytes;
			if (FFileHelper::LoadFileToArray(DiagBytes, *CapturedFile))
			{
				FUTF8ToTCHAR DiagConverter(reinterpret_cast<const ANSICHAR*>(DiagBytes.GetData()), DiagBytes.Num());
				Content = FString(DiagConverter.Length(), DiagConverter.Get());
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
	StreamLinesRead = 0;
	bHasStreamingMessage = false;
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
	FString StreamFile = TempDir / TEXT("_openclaw_response_stream.jsonl");

	// 清除上次响应文件
	IFileManager::Get().Delete(*ResponseFile, false, false, true);
	IFileManager::Get().Delete(*StreamFile, false, false, true);

	// 通过 Python Bridge 异步发送
	// Python 侧会把结果写入临时文件
	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_bridge import send_chat_async_to_file; send_chat_async_to_file('%s', r'%s')"),
		*EscapedMsg, *ResponseFile);

	IPythonScriptPlugin::Get()->ExecPythonCommand(*PythonCmd);

	// 启动定时器轮询临时文件
	auto Self = SharedThis(this);
	FString CapturedResponseFile = ResponseFile;
	FString CapturedStreamFile = StreamFile;
	PollTimerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedResponseFile, CapturedStreamFile](float DeltaTime) -> bool
		{
			if (!Self->bIsWaitingForResponse)
			{
				return false;
			}

			// --- 流式文件轮询: 读取新增行并实时显示 ---
			if (FPaths::FileExists(CapturedStreamFile))
			{
				// 用 UTF-8 读取流式文件（Python 以 UTF-8 写入）
				FString StreamContent;
				TArray<uint8> RawBytes;
				if (FFileHelper::LoadFileToArray(RawBytes, *CapturedStreamFile))
				{
					// 手动从 UTF-8 转换为 FString
					FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
					StreamContent = FString(Converter.Length(), Converter.Get());
					TArray<FString> Lines;
					StreamContent.ParseIntoArrayLines(Lines);

					// 只处理新增的行
					for (int32 i = Self->StreamLinesRead; i < Lines.Num(); i++)
					{
						const FString& Line = Lines[i];
						if (Line.IsEmpty()) continue;

						// 使用 UE JSON 解析器，比手工字符串操作更可靠
						TSharedPtr<FJsonObject> JsonObj;
						TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Line);
						if (FJsonSerializer::Deserialize(Reader, JsonObj) && JsonObj.IsValid())
						{
							FString EventType = JsonObj->GetStringField(TEXT("type"));
							FString EventText = JsonObj->GetStringField(TEXT("text"));

							if (!EventText.IsEmpty())
							{
								if (EventType == TEXT("thinking"))
								{
									Self->UpdateStreamingMessage(TEXT("thinking"), EventText);
								}
								else if (EventType == TEXT("delta"))
								{
									Self->UpdateStreamingMessage(TEXT("assistant"), EventText);
								}
							}
						}
					}
					Self->StreamLinesRead = Lines.Num();
				}
			}

			// --- 最终响应文件轮询 ---
			if (!FPaths::FileExists(CapturedResponseFile))
			{
				return true; // 继续等待
			}

			// 读取响应（UTF-8）
			FString ResponseContent;
			TArray<uint8> RespBytes;
			if (FFileHelper::LoadFileToArray(RespBytes, *CapturedResponseFile))
			{
				FUTF8ToTCHAR RespConverter(reinterpret_cast<const ANSICHAR*>(RespBytes.GetData()), RespBytes.Num());
				ResponseContent = FString(RespConverter.Length(), RespConverter.Get());

				// 删除临时文件
				IFileManager::Get().Delete(*CapturedResponseFile, false, false, true);
				IFileManager::Get().Delete(*CapturedStreamFile, false, false, true);

				// 处理响应
				Self->HandlePythonResponse(ResponseContent);
			}

			return false; // 停止轮询
		}),
		0.25f // 每 0.25 秒检查一次（流式需要更快）
	);
}

void SUEAgentDashboard::UpdateStreamingMessage(const FString& Sender, const FString& Content)
{
	if (Content.IsEmpty()) return;

	// 流式消息统一用 "streaming" 标识，以区分最终回复的颜色
	FString StreamSender = (Sender == TEXT("thinking")) ? TEXT("thinking") : TEXT("streaming");

	if (!bHasStreamingMessage)
	{
		// 替换 "Thinking..." 消息
		if (Messages.Num() > 0 && Messages.Last().Content == TEXT("Thinking..."))
		{
			Messages.RemoveAt(Messages.Num() - 1);
		}
		// 添加流式消息
		FChatMessage Msg;
		Msg.Sender = StreamSender;
		Msg.Content = Content;
		Msg.Timestamp = FDateTime::Now();
		Messages.Add(MoveTemp(Msg));
		bHasStreamingMessage = true;
	}
	else
	{
		// 更新最后一条消息（如果 sender 类型相同则更新内容，否则追加新消息）
		if (Messages.Num() > 0 && Messages.Last().Sender == StreamSender)
		{
			Messages.Last().Content = Content;
		}
		else
		{
			// Sender 类型变了（例如从 thinking 变成 streaming），追加新消息
			FChatMessage Msg;
			Msg.Sender = StreamSender;
			Msg.Content = Content;
			Msg.Timestamp = FDateTime::Now();
			Messages.Add(MoveTemp(Msg));
		}
	}

	RebuildMessageList();
	// 自动滚动到底部
	if (MessageScrollBox.IsValid())
	{
		MessageScrollBox->ScrollToEnd();
	}
}

void SUEAgentDashboard::HandlePythonResponse(const FString& Response)
{
	bIsWaitingForResponse = false;

	// 移除 "Thinking..." 消息（如果流式显示还没替换掉的话）
	if (!bHasStreamingMessage && Messages.Num() > 0 && Messages.Last().Content == TEXT("Thinking..."))
	{
		Messages.RemoveAt(Messages.Num() - 1);
		RebuildMessageList();
	}

	// 如果有流式消息，移除它们（最终回复会替代）
	// 找到最后的 thinking/流式消息并移除
	if (bHasStreamingMessage)
	{
		// 从末尾往前找，移除所有流式 thinking/streaming 消息
		while (Messages.Num() > 0)
		{
			const FString& LastSender = Messages.Last().Sender;
			if (LastSender == TEXT("thinking") || LastSender == TEXT("streaming"))
			{
				Messages.RemoveAt(Messages.Num() - 1);
			}
			else
			{
				break;
			}
		}
		RebuildMessageList();
	}

	bHasStreamingMessage = false;
	StreamLinesRead = 0;

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
// 快捷输入 (Quick Inputs)
// ==================================================================

FString SUEAgentDashboard::GetQuickInputConfigPath() const
{
	// 优先使用项目 Saved 目录（随项目走）
	FString ConfigDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*ConfigDir, true);
	return ConfigDir / TEXT("quick_inputs.json");
}

void SUEAgentDashboard::LoadQuickInputs()
{
	QuickInputs.Empty();

	FString ConfigPath = GetQuickInputConfigPath();
	if (!FPaths::FileExists(ConfigPath))
	{
		return;
	}

	FString FileContent;
	if (!FFileHelper::LoadFileToString(FileContent, *ConfigPath))
	{
		UE_LOG(LogTemp, Warning, TEXT("[UEAgent] Failed to load quick_inputs.json"));
		return;
	}

	TSharedPtr<FJsonObject> RootObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(FileContent);
	if (!FJsonSerializer::Deserialize(Reader, RootObj) || !RootObj.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("[UEAgent] Failed to parse quick_inputs.json"));
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* ItemsArray = nullptr;
	if (!RootObj->TryGetArrayField(TEXT("quick_inputs"), ItemsArray))
	{
		return;
	}

	for (const auto& ItemVal : *ItemsArray)
	{
		const TSharedPtr<FJsonObject>* ItemObj = nullptr;
		if (!ItemVal->TryGetObject(ItemObj) || !(*ItemObj).IsValid())
		{
			continue;
		}

		FQuickInput QI;
		QI.Id = (*ItemObj)->GetStringField(TEXT("id"));
		QI.Name = (*ItemObj)->GetStringField(TEXT("name"));
		QI.Content = (*ItemObj)->GetStringField(TEXT("content"));

		if (!QI.Id.IsEmpty() && !QI.Name.IsEmpty())
		{
			QuickInputs.Add(MoveTemp(QI));
		}
	}

	UE_LOG(LogTemp, Log, TEXT("[UEAgent] Loaded %d quick inputs"), QuickInputs.Num());
}

void SUEAgentDashboard::SaveQuickInputs()
{
	TSharedRef<FJsonObject> RootObj = MakeShared<FJsonObject>();
	TArray<TSharedPtr<FJsonValue>> ItemsArray;

	for (const FQuickInput& QI : QuickInputs)
	{
		TSharedRef<FJsonObject> ItemObj = MakeShared<FJsonObject>();
		ItemObj->SetStringField(TEXT("id"), QI.Id);
		ItemObj->SetStringField(TEXT("name"), QI.Name);
		ItemObj->SetStringField(TEXT("content"), QI.Content);
		ItemsArray.Add(MakeShared<FJsonValueObject>(ItemObj));
	}

	RootObj->SetArrayField(TEXT("quick_inputs"), ItemsArray);

	FString OutputStr;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputStr);
	FJsonSerializer::Serialize(RootObj, Writer);

	FString ConfigPath = GetQuickInputConfigPath();
	if (FFileHelper::SaveStringToFile(OutputStr, *ConfigPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
	{
		UE_LOG(LogTemp, Log, TEXT("[UEAgent] Saved %d quick inputs to %s"), QuickInputs.Num(), *ConfigPath);
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("[UEAgent] Failed to save quick_inputs.json"));
	}
}

void SUEAgentDashboard::RebuildQuickInputPanel()
{
	if (!QuickInputWrapBox.IsValid())
	{
		return;
	}

	QuickInputWrapBox->ClearChildren();

	if (QuickInputs.Num() == 0)
	{
		// 空状态提示
		QuickInputWrapBox->AddSlot()
		.Padding(2.0f)
		[
			SNew(STextBlock)
			.Text(LOCTEXT("NoQuickInputs", "No quick inputs yet. Click '+ Add' to create one."))
			.Font(FCoreStyle::GetDefaultFontStyle("Italic", 9))
			.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
		];
		return;
	}

	for (int32 i = 0; i < QuickInputs.Num(); i++)
	{
		const FQuickInput& QI = QuickInputs[i];
		const int32 CapturedIndex = i;

		QuickInputWrapBox->AddSlot()
		.Padding(2.0f)
		[
			SNew(SHorizontalBox)

			// 快捷按钮
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(FText::FromString(QI.Name))
				.ToolTipText(FText::FromString(QI.Content))
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply
				{
					return OnQuickInputClicked(CapturedIndex);
				})
				.ContentPadding(FMargin(8.0f, 3.0f))
			]

			// 编辑按钮 (小号铅笔)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			.Padding(1.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("EditQuickInputBtn", "e"))
				.ToolTipText(LOCTEXT("EditQuickInputTip", "Edit this quick input"))
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply
				{
					return OnEditQuickInputClicked(CapturedIndex);
				})
				.ContentPadding(FMargin(3.0f, 1.0f))
			]

			// 删除按钮 (小号 x)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			.Padding(1.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("DeleteQuickInputBtn", "x"))
				.ToolTipText(LOCTEXT("DeleteQuickInputTip", "Delete this quick input"))
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply
				{
					return OnDeleteQuickInputClicked(CapturedIndex);
				})
				.ContentPadding(FMargin(3.0f, 1.0f))
			]
		];
	}
}

FReply SUEAgentDashboard::OnQuickInputClicked(int32 Index)
{
	if (!QuickInputs.IsValidIndex(Index))
	{
		return FReply::Handled();
	}

	const FString& Content = QuickInputs[Index].Content;

	if (InputTextBox.IsValid())
	{
		InputTextBox->SetText(FText::FromString(Content));

		// 设置焦点到输入框
		FSlateApplication::Get().SetKeyboardFocus(InputTextBox.ToSharedRef(), EFocusCause::SetDirectly);
	}

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnAddQuickInputClicked()
{
	FQuickInput NewQI;
	NewQI.Id = FGuid::NewGuid().ToString();
	NewQI.Name = FString::Printf(TEXT("Quick %d"), QuickInputs.Num() + 1);
	NewQI.Content = TEXT("");

	QuickInputs.Add(MoveTemp(NewQI));
	SaveQuickInputs();
	RebuildQuickInputPanel();

	// 弹出内联编辑对话框
	// 用简单的 Message Dialog 让用户输入名称和内容
	// 找到刚添加的项目索引
	int32 NewIndex = QuickInputs.Num() - 1;

	// 使用 SWindow 弹出编辑窗口
	TSharedRef<SWindow> EditWindow =
		SNew(SWindow)
		.Title(LOCTEXT("EditQuickInputTitle", "Edit Quick Input"))
		.ClientSize(FVector2D(400, 180))
		.SupportsMinimize(false)
		.SupportsMaximize(false)
		.SizingRule(ESizingRule::FixedSize);

	TSharedPtr<SEditableTextBox> NameInput;
	TSharedPtr<SEditableTextBox> ContentInput;

	EditWindow->SetContent(
		SNew(SVerticalBox)
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f)
		[
			SNew(STextBlock)
			.Text(LOCTEXT("QINameLabel", "Name (displayed on button):"))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f, 2.0f)
		[
			SAssignNew(NameInput, SEditableTextBox)
			.Text(FText::FromString(QuickInputs[NewIndex].Name))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f, 8.0f, 8.0f, 0.0f)
		[
			SNew(STextBlock)
			.Text(LOCTEXT("QIContentLabel", "Content (filled into chat):"))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f, 2.0f)
		[
			SAssignNew(ContentInput, SEditableTextBox)
			.Text(FText::FromString(QuickInputs[NewIndex].Content))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f, 12.0f)
		.HAlign(HAlign_Right)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 4.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("QISaveBtn", "Save"))
				.ContentPadding(FMargin(12.0f, 4.0f))
				.OnClicked_Lambda([this, NewIndex, NameInput, ContentInput, EditWindow]() -> FReply
				{
					if (QuickInputs.IsValidIndex(NewIndex))
					{
						FString NewName = NameInput.IsValid() ? NameInput->GetText().ToString().TrimStartAndEnd() : TEXT("");
						FString NewContent = ContentInput.IsValid() ? ContentInput->GetText().ToString().TrimStartAndEnd() : TEXT("");

						if (NewName.IsEmpty())
						{
							NewName = FString::Printf(TEXT("Quick %d"), NewIndex + 1);
						}

						QuickInputs[NewIndex].Name = NewName;
						QuickInputs[NewIndex].Content = NewContent;
						SaveQuickInputs();
						RebuildQuickInputPanel();
					}
					EditWindow->RequestDestroyWindow();
					return FReply::Handled();
				})
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(LOCTEXT("QICancelBtn", "Cancel"))
				.ContentPadding(FMargin(12.0f, 4.0f))
				.OnClicked_Lambda([this, NewIndex, EditWindow]() -> FReply
				{
					// 取消时删除刚才添加的空项
					if (QuickInputs.IsValidIndex(NewIndex) && QuickInputs[NewIndex].Content.IsEmpty())
					{
						QuickInputs.RemoveAt(NewIndex);
						SaveQuickInputs();
						RebuildQuickInputPanel();
					}
					EditWindow->RequestDestroyWindow();
					return FReply::Handled();
				})
			]
		]
	);

	FSlateApplication::Get().AddModalWindow(EditWindow, FSlateApplication::Get().GetActiveTopLevelWindow());

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnDeleteQuickInputClicked(int32 Index)
{
	if (!QuickInputs.IsValidIndex(Index))
	{
		return FReply::Handled();
	}

	FString ItemName = QuickInputs[Index].Name;

	// 确认删除
	EAppReturnType::Type Result = FMessageDialog::Open(
		EAppMsgType::YesNo,
		FText::Format(
			LOCTEXT("ConfirmDeleteQI", "Delete quick input \"{0}\"?"),
			FText::FromString(ItemName)));

	if (Result == EAppReturnType::Yes)
	{
		QuickInputs.RemoveAt(Index);
		SaveQuickInputs();
		RebuildQuickInputPanel();
	}

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnEditQuickInputClicked(int32 Index)
{
	if (!QuickInputs.IsValidIndex(Index))
	{
		return FReply::Handled();
	}

	TSharedRef<SWindow> EditWindow =
		SNew(SWindow)
		.Title(LOCTEXT("EditQuickInputTitle2", "Edit Quick Input"))
		.ClientSize(FVector2D(400, 180))
		.SupportsMinimize(false)
		.SupportsMaximize(false)
		.SizingRule(ESizingRule::FixedSize);

	TSharedPtr<SEditableTextBox> NameInput;
	TSharedPtr<SEditableTextBox> ContentInput;

	EditWindow->SetContent(
		SNew(SVerticalBox)
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f)
		[
			SNew(STextBlock)
			.Text(LOCTEXT("QINameLabel2", "Name (displayed on button):"))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f, 2.0f)
		[
			SAssignNew(NameInput, SEditableTextBox)
			.Text(FText::FromString(QuickInputs[Index].Name))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f, 8.0f, 8.0f, 0.0f)
		[
			SNew(STextBlock)
			.Text(LOCTEXT("QIContentLabel2", "Content (filled into chat):"))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f, 2.0f)
		[
			SAssignNew(ContentInput, SEditableTextBox)
			.Text(FText::FromString(QuickInputs[Index].Content))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f, 12.0f)
		.HAlign(HAlign_Right)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 4.0f, 0.0f)
			[
				SNew(SButton)
				.Text(LOCTEXT("QISaveBtn2", "Save"))
				.ContentPadding(FMargin(12.0f, 4.0f))
				.OnClicked_Lambda([this, Index, NameInput, ContentInput, EditWindow]() -> FReply
				{
					if (QuickInputs.IsValidIndex(Index))
					{
						FString NewName = NameInput.IsValid() ? NameInput->GetText().ToString().TrimStartAndEnd() : TEXT("");
						FString NewContent = ContentInput.IsValid() ? ContentInput->GetText().ToString().TrimStartAndEnd() : TEXT("");

						if (!NewName.IsEmpty())
						{
							QuickInputs[Index].Name = NewName;
						}
						QuickInputs[Index].Content = NewContent;
						SaveQuickInputs();
						RebuildQuickInputPanel();
					}
					EditWindow->RequestDestroyWindow();
					return FReply::Handled();
				})
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(LOCTEXT("QICancelBtn2", "Cancel"))
				.ContentPadding(FMargin(12.0f, 4.0f))
				.OnClicked_Lambda([EditWindow]() -> FReply
				{
					EditWindow->RequestDestroyWindow();
					return FReply::Handled();
				})
			]
		]
	);

	FSlateApplication::Get().AddModalWindow(EditWindow, FSlateApplication::Get().GetActiveTopLevelWindow());

	return FReply::Handled();
}

void SUEAgentDashboard::OnQuickInputNameCommitted(const FText& NewText, ETextCommit::Type CommitType, int32 Index)
{
	if (QuickInputs.IsValidIndex(Index))
	{
		QuickInputs[Index].Name = NewText.ToString().TrimStartAndEnd();
		SaveQuickInputs();
		RebuildQuickInputPanel();
	}
}

void SUEAgentDashboard::OnQuickInputContentCommitted(const FText& NewText, ETextCommit::Type CommitType, int32 Index)
{
	if (QuickInputs.IsValidIndex(Index))
	{
		QuickInputs[Index].Content = NewText.ToString().TrimStartAndEnd();
		SaveQuickInputs();
	}
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
	else if (Sender == TEXT("streaming"))
	{
		// 流式消息：较灰的绿色，区分最终回复
		return FSlateColor(FLinearColor(0.45f, 0.6f, 0.45f));
	}
	else if (Sender == TEXT("thinking"))
	{
		// 淡紫色，区分 thinking 过程
		return FSlateColor(FLinearColor(0.7f, 0.5f, 0.9f));
	}
	else
	{
		return FSlateColor(FLinearColor(0.7f, 0.7f, 0.7f));
	}
}

// ==================================================================
// 阶段 D: Skill 创建集成
// ==================================================================

FReply SUEAgentDashboard::OnCreateSkillClicked()
{
	OpenSkillCreationDialog();
	return FReply::Handled();
}

void SUEAgentDashboard::OpenSkillCreationDialog()
{
	// D2: 模态输入对话框
	TSharedRef<SWindow> DialogWindow = SNew(SWindow)
		.Title(FText::FromString(TEXT("ArtClaw - Create New Skill")))
		.ClientSize(FVector2D(520, 340))
		.SupportsMinimize(false)
		.SupportsMaximize(false);

	// 对话框内容变量
	TSharedPtr<SEditableTextBox> DescInput;
	TSharedPtr<SEditableTextBox> CategoryInput;
	TSharedPtr<SEditableTextBox> SoftwareInput;

	// 捕获 this 和窗口引用
	TWeakPtr<SWindow> WeakWindow = DialogWindow;
	SUEAgentDashboard* Self = this;

	DialogWindow->SetContent(
		SNew(SVerticalBox)
		// 标题提示
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 12.0f, 12.0f, 4.0f)
		[
			SNew(STextBlock)
			.Text(FText::FromString(TEXT("Describe the skill you want to create:")))
			.Font(FCoreStyle::GetDefaultFontStyle("Bold", 11))
		]
		// 描述输入
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 4.0f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 2.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(TEXT("Description (natural language):")))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SAssignNew(DescInput, SEditableTextBox)
				.HintText(FText::FromString(TEXT("e.g. Batch rename actors in the scene with a prefix")))
			]
		]
		// 分类输入
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 4.0f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 2.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(TEXT("Category (optional):")))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SAssignNew(CategoryInput, SEditableTextBox)
				.HintText(FText::FromString(TEXT("scene / asset / material / lighting / render / utils ...")))
			]
		]
		// 软件输入
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 4.0f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 2.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(TEXT("Software (optional, default: unreal_engine):")))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SAssignNew(SoftwareInput, SEditableTextBox)
				.HintText(FText::FromString(TEXT("unreal_engine / maya / 3ds_max / universal")))
			]
		]
		// 弹性间距
		+ SVerticalBox::Slot()
		.FillHeight(1.0f)
		[
			SNew(SSpacer)
		]
		// 按钮行
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 8.0f, 12.0f, 12.0f)
		.HAlign(HAlign_Right)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 8.0f, 0.0f)
			[
				SNew(SButton)
				.Text(FText::FromString(TEXT("Cancel")))
				.OnClicked_Lambda([WeakWindow]() -> FReply {
					if (TSharedPtr<SWindow> Win = WeakWindow.Pin())
					{
						Win->RequestDestroyWindow();
					}
					return FReply::Handled();
				})
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(FText::FromString(TEXT("Create")))
				.OnClicked_Lambda([Self, DescInput, CategoryInput, SoftwareInput, WeakWindow]() -> FReply {
					FString Desc = DescInput->GetText().ToString().TrimStartAndEnd();
					FString Cat = CategoryInput->GetText().ToString().TrimStartAndEnd();
					FString Sw = SoftwareInput->GetText().ToString().TrimStartAndEnd();

					if (Desc.IsEmpty())
					{
						// 不能为空
						return FReply::Handled();
					}

					if (Sw.IsEmpty())
					{
						Sw = TEXT("unreal_engine");
					}

					if (TSharedPtr<SWindow> Win = WeakWindow.Pin())
					{
						Win->RequestDestroyWindow();
					}

					Self->StartSkillGeneration(Desc, Cat, Sw);
					return FReply::Handled();
				})
			]
		]
	);

	FSlateApplication::Get().AddModalWindow(DialogWindow, SharedThis(this));
}

void SUEAgentDashboard::StartSkillGeneration(const FString& Description, const FString& Category, const FString& Software)
{
	if (bIsGeneratingSkill)
	{
		AddMessage(TEXT("system"), TEXT("A skill is already being generated. Please wait..."));
		return;
	}

	bIsGeneratingSkill = true;

	// D3: 显示生成进度
	AddMessage(TEXT("system"), FString::Printf(TEXT("Creating skill: \"%s\" ..."), *Description));

	// 准备 Python 命令，调用 skill_mcp_tools 的 skill_generate
	FString EscapedDesc = Description.Replace(TEXT("\""), TEXT("\\\"")).Replace(TEXT("'"), TEXT("\\'"));
	FString EscapedCat = Category.Replace(TEXT("\""), TEXT("\\\""));
	FString EscapedSw = Software.Replace(TEXT("\""), TEXT("\\\""));

	FString PythonCode = FString::Printf(
		TEXT("import json\n")
		TEXT("from skill_mcp_tools import _handle_skill_generate\n")
		TEXT("_args = {\"description\": \"%s\", \"category\": \"%s\", \"software\": \"%s\", \"target_layer\": \"user\"}\n")
		TEXT("_result = _handle_skill_generate(None, _args)\n")
		TEXT("import os\n")
		TEXT("_path = os.path.join(str(__import__('unreal').Paths.project_saved_dir()), 'UEAgent', '_skill_gen_result.json')\n")
		TEXT("os.makedirs(os.path.dirname(_path), exist_ok=True)\n")
		TEXT("with open(_path, 'w', encoding='utf-8') as _f:\n")
		TEXT("    _f.write(_result)\n")
		TEXT("__import__('unreal').log('[ArtClaw] Skill generation result written')\n"),
		*EscapedDesc, *EscapedCat, *EscapedSw
	);

	// 设置结果文件路径
	FString SavedDir = FPaths::ProjectSavedDir();
	SkillResultFile = FPaths::Combine(SavedDir, TEXT("UEAgent"), TEXT("_skill_gen_result.json"));

	// 删除旧结果文件
	if (FPaths::FileExists(SkillResultFile))
	{
		IFileManager::Get().Delete(*SkillResultFile);
	}

	// 执行 Python
	IPythonScriptPlugin* PythonPlugin = IPythonScriptPlugin::Get();
	if (PythonPlugin)
	{
		PythonPlugin->ExecPythonCommand(*PythonCode);
	}
	else
	{
		AddMessage(TEXT("system"), TEXT("Error: Python plugin not available"));
		bIsGeneratingSkill = false;
		return;
	}

	// 启动轮询等待结果
	PollSkillGenerationProgress();
}

void SUEAgentDashboard::PollSkillGenerationProgress()
{
	// D3: 轮询结果文件
	SkillPollHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([this](float DeltaTime) -> bool
		{
			if (!bIsGeneratingSkill)
			{
				return false; // 停止轮询
			}

			if (FPaths::FileExists(SkillResultFile))
			{
				// 读取结果
				FString ResultJson;
				if (FFileHelper::LoadFileToString(ResultJson, *SkillResultFile))
				{
					bIsGeneratingSkill = false;

					// 删除临时文件
					IFileManager::Get().Delete(*SkillResultFile);

					// 解析结果
					TSharedPtr<FJsonObject> JsonObj;
					TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ResultJson);
					if (FJsonSerializer::Deserialize(Reader, JsonObj) && JsonObj.IsValid())
					{
						bool bSuccess = JsonObj->GetBoolField(TEXT("success"));
						if (bSuccess)
						{
							FString SkillName = JsonObj->GetStringField(TEXT("skill_name"));
							FString Message = JsonObj->GetStringField(TEXT("message"));
							AddMessage(TEXT("system"), FString::Printf(TEXT("✅ %s"), *Message));

							// D4: 如果有生成的文件内容，可以展示预览
							OpenSkillPreviewDialog(ResultJson);
						}
						else
						{
							FString Error = JsonObj->GetStringField(TEXT("error"));
							AddMessage(TEXT("system"), FString::Printf(TEXT("❌ Skill creation failed: %s"), *Error));
						}
					}
					else
					{
						AddMessage(TEXT("system"), TEXT("❌ Failed to parse skill generation result"));
					}

					return false; // 停止轮询
				}
			}

			return true; // 继续轮询
		}),
		0.5f // 每 0.5 秒轮询一次
	);
}

void SUEAgentDashboard::OpenSkillPreviewDialog(const FString& PreviewJson)
{
	// D4: 展示生成结果预览
	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PreviewJson);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
	{
		return;
	}

	FString SkillName = JsonObj->GetStringField(TEXT("skill_name"));
	FString Category = JsonObj->GetStringField(TEXT("inferred_category"));

	// 获取生成的文件内容
	const TSharedPtr<FJsonObject>* FilesObj = nullptr;
	FString InitCode;
	if (JsonObj->TryGetObjectField(TEXT("generated_files"), FilesObj))
	{
		InitCode = (*FilesObj)->GetStringField(TEXT("__init__.py"));
	}

	// 获取下一步提示
	FString NextSteps;
	const TArray<TSharedPtr<FJsonValue>>* StepsArr = nullptr;
	if (JsonObj->TryGetArrayField(TEXT("next_steps"), StepsArr))
	{
		for (const auto& Step : *StepsArr)
		{
			NextSteps += TEXT("  • ") + Step->AsString() + TEXT("\n");
		}
	}

	// 在聊天窗口显示预览
	AddMessage(TEXT("system"), FString::Printf(
		TEXT("📦 Skill \"%s\" scaffold generated:\n"
			 "   Category: %s\n"
			 "   Next steps:\n%s"),
		*SkillName, *Category, *NextSteps
	));

	// 如果有代码，显示代码片段（截取前 20 行）
	if (!InitCode.IsEmpty())
	{
		TArray<FString> Lines;
		InitCode.ParseIntoArrayLines(Lines);
		int32 ShowLines = FMath::Min(Lines.Num(), 20);
		FString Preview;
		for (int32 i = 0; i < ShowLines; i++)
		{
			Preview += Lines[i] + TEXT("\n");
		}
		if (Lines.Num() > 20)
		{
			Preview += FString::Printf(TEXT("... (%d more lines)"), Lines.Num() - 20);
		}
		AddMessage(TEXT("system"), FString::Printf(TEXT("Generated __init__.py:\n%s"), *Preview), true);
	}
}

bool SUEAgentDashboard::IsArtclawSkillTrigger(const FString& InputText) const
{
	FString Lower = InputText.ToLower();

	// 必须同时包含 "artclaw" 和明确的创建/生成意图词
	// 仅提及 "artclaw" + "skill" 不触发（如 "列出 artclaw 的 skill"）
	// 符合 skill-management-system.md §8.1 的触发方式区分
	if (!Lower.Contains(TEXT("artclaw")))
	{
		return false;
	}

	// 必须包含创建/生成动作词
	bool bHasCreateIntent =
		Lower.Contains(TEXT("创建")) ||
		Lower.Contains(TEXT("create")) ||
		Lower.Contains(TEXT("生成")) ||
		Lower.Contains(TEXT("generate")) ||
		Lower.Contains(TEXT("新建")) ||
		Lower.Contains(TEXT("开发"));

	if (!bHasCreateIntent)
	{
		return false;
	}

	// 还需要包含 skill/技能 关键词，确认是创建 Skill（而非创建其他东西）
	bool bHasSkillKeyword =
		Lower.Contains(TEXT("skill")) ||
		Lower.Contains(TEXT("技能"));

	return bHasSkillKeyword;
}

FString SUEAgentDashboard::ExtractSkillDescription(const FString& InputText) const
{
	FString Text = InputText;

	// 移除常见触发词前缀
	TArray<FString> Prefixes = {
		TEXT("用 artclaw 创建一个技能"),
		TEXT("用artclaw创建一个技能"),
		TEXT("用 artclaw 创建技能"),
		TEXT("用artclaw创建技能"),
		TEXT("artclaw 创建技能"),
		TEXT("artclaw创建技能"),
		TEXT("artclaw skill create"),
		TEXT("artclaw create skill"),
		TEXT("artclaw generate"),
		TEXT("artclaw skill"),
		TEXT("artclaw"),
	};

	FString Lower = Text.ToLower();
	for (const FString& Prefix : Prefixes)
	{
		if (Lower.StartsWith(Prefix))
		{
			Text = Text.Mid(Prefix.Len()).TrimStartAndEnd();
			// 移除开头的标点/冒号
			while (Text.Len() > 0 &&
				(Text[0] == TEXT(':') || Text[0] == TEXT(',') ||
				 Text[0] == TEXT(' ') || Text[0] == 0xFF1A))  // 全角冒号
			{
				Text = Text.Mid(1);
			}
			return Text.TrimStartAndEnd();
		}
	}

	return FString();
}

bool SUEAgentDashboard::ShowCppRequirementDialog(const FString& SkillName, const TArray<FString>& CppRequirements)
{
	// D4 子流程: C++ 需求确认弹窗
	// 按 skill-management-system.md §2.5 的弹窗规范

	FString RequirementList;
	for (const FString& Req : CppRequirements)
	{
		RequirementList += TEXT("  • ") + Req + TEXT("\n");
	}

	FString Message = FString::Printf(
		TEXT("ArtClaw Skill \"%s\" requires C++ support:\n\n%s\n"
			 "Adding C++ interfaces requires recompilation.\n\n"
			 "Choose:\n"
			 "  [Yes] - Add C++ interfaces and rebuild\n"
			 "  [No]  - Skip, run with Python-only features"),
		*SkillName, *RequirementList
	);

	EAppReturnType::Type Result = FMessageDialog::Open(
		EAppMsgType::YesNo,
		FText::FromString(Message),
		FText::FromString(TEXT("ArtClaw - C++ Interface Required"))
	);

	return Result == EAppReturnType::Yes;
}

#undef LOCTEXT_NAMESPACE