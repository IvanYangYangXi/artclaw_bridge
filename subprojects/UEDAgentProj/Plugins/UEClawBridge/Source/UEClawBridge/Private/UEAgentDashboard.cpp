// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentDashboard.h"
#include "UEAgentSubsystem.h"
#include "UEAgentLocalization.h"
#include "IAgentPlatformBridge.h"
#include "OpenClawPlatformBridge.h"
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

	// 创建平台通信桥接 (当前: OpenClaw)
	PlatformBridge = MakeShared<FOpenClawPlatformBridge>();

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
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("VersionLabel")); })
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
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ServerLabel")); })
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
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ConnectBtn")); })
				.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("ConnectTip")); })
				.OnClicked(this, &SUEAgentDashboard::OnConnectClicked)
				.ContentPadding(FMargin(6.0f, 2.0f))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 3.0f, 0.0f)
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("DisconnectBtn")); })
				.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("DisconnectTip")); })
				.OnClicked(this, &SUEAgentDashboard::OnDisconnectClicked)
				.ContentPadding(FMargin(6.0f, 2.0f))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 3.0f, 0.0f)
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("DiagnoseBtn")); })
				.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("DiagnoseTip")); })
				.OnClicked(this, &SUEAgentDashboard::OnDiagnoseClicked)
				.ContentPadding(FMargin(6.0f, 2.0f))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ViewLogsBtn")); })
				.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("ViewLogsTip")); })
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
			.AreaTitle(FUEAgentL10n::Get(TEXT("StatusAreaTitle")))
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
			.AreaTitle(FUEAgentL10n::Get(TEXT("QuickInputTitle")))
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
							.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("AddQuickInputBtn")); })
							.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("AddQuickInputTip")); })
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
						.HintText_Lambda([this]() { return GetSendHintText(); })
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
						.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("SendBtn")); })
						.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("SendTip")); })
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
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("NewChatBtn")); })
					.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("NewChatTip")); })
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
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("CreateSkillBtn")); })
					.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("CreateSkillTip")); })
					.OnClicked(this, &SUEAgentDashboard::OnCreateSkillClicked)
					.ContentPadding(FMargin(4.0f, 1.0f))
				]

				// 语言切换按钮 (中/En)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([]() {
						return FUEAgentL10n::GetLanguage() == EUEAgentLanguage::Chinese
							? FText::FromString(TEXT("En"))
							: FText::FromString(TEXT("中"));
					})
					.ToolTipText_Lambda([]() {
						return FUEAgentL10n::Get(TEXT("LangToggleTip"));
					})
					.OnClicked(this, &SUEAgentDashboard::OnToggleLanguageClicked)
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
						.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("EnterToSendLabel")); })
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
	AddMessage(TEXT("assistant"), FUEAgentL10n::GetStr(TEXT("WelcomeMsg")));

	// 打开面板时自动连接 OpenClaw Bridge
	ConnectOpenClawBridge();

	// Bridge 连接状态持续轮询 — 读取 Python 侧写入的 _bridge_status.json
	// 统一处理 Bridge 连接状态 + MCP Server 就绪状态，无需额外 socket 探测
	{
		auto Self = SharedThis(this);
		BridgeStatusPollHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateLambda([Self](float) -> bool
			{
				FString StatusFile = FPaths::ProjectSavedDir() / TEXT("UEAgent") / TEXT("_bridge_status.json");
				if (!FPaths::FileExists(StatusFile))
				{
					return true; // 继续轮询
				}

				TArray<uint8> RawBytes;
				if (!FFileHelper::LoadFileToArray(RawBytes, *StatusFile))
				{
					return true;
				}
				FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
				FString JsonStr(Converter.Length(), Converter.Get());

				TSharedPtr<FJsonObject> JsonObj;
				TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
				if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
				{
					return true;
				}

				double Timestamp = JsonObj->GetNumberField(TEXT("timestamp"));
				// 只处理比上次更新的状态
				if (Timestamp <= Self->LastBridgeStatusTimestamp)
				{
					return true;
				}
				Self->LastBridgeStatusTimestamp = Timestamp;

				bool bConnected = false;
				if (!JsonObj->TryGetBoolField(TEXT("connected"), bConnected))
				{
					return true; // connected 字段缺失，跳过本次（文件可能正在被写入）
				}
				bool bMcpReady = false;
				JsonObj->TryGetBoolField(TEXT("mcp_ready"), bMcpReady);

				// 更新 Subsystem 状态（触发图标颜色变化等）
				if (Self->CachedSubsystem.IsValid())
				{
					Self->CachedSubsystem->SetConnectionStatus(bConnected);
				}

				return true; // 持续轮询
			}),
			2.0f // 每 2 秒检查一次
		);
	}
}

SUEAgentDashboard::~SUEAgentDashboard()
{
	// 停止 bridge 状态轮询
	if (BridgeStatusPollHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(BridgeStatusPollHandle);
		BridgeStatusPollHandle.Reset();
	}

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
		? FUEAgentL10n::GetStr(TEXT("McpConnected"))
		: FUEAgentL10n::GetStr(TEXT("McpDisconnected"));
	AddMessage(TEXT("system"), StatusMsg);
}

// ==================================================================
// 状态栏辅助方法
// ==================================================================

FText SUEAgentDashboard::GetConnectionStatusText() const
{
	if (bCachedIsConnected)
	{
		return FUEAgentL10n::Get(TEXT("Connected"));
	}
	return FUEAgentL10n::Get(TEXT("Disconnected"));
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
	return FUEAgentL10n::Get(TEXT("VersionUnknown"));
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
	return FUEAgentL10n::Get(TEXT("ServerNotStarted"));
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

	// 防止重复发送 — 但提供取消手段
	if (bIsWaitingForResponse)
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("StillWaiting")));
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
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("NewChatStarted")));

	// 2) 重置平台桥接的会话
	PlatformBridge->ResetSession();

	// 3) 发送 /new 给 AI（重置远端会话），非静默——显示 AI 的回复
	SendToOpenClaw(TEXT("/new"));

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
		return FUEAgentL10n::Get(TEXT("InputHintEnter"));
	}
	return FUEAgentL10n::Get(TEXT("InputHintCtrlEnter"));
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
		MakeCmd(TEXT("/connect"),    TEXT("连接 OpenClaw 网关"), true),
		MakeCmd(TEXT("/disconnect"), TEXT("断开 OpenClaw 网关连接"), true),
		MakeCmd(TEXT("/diagnose"),   TEXT("运行连接诊断"), true),
		MakeCmd(TEXT("/status"),     TEXT("显示连接状态"), true),
		MakeCmd(TEXT("/clear"),      TEXT("清空聊天记录"), true),
		MakeCmd(TEXT("/cancel"),     TEXT("取消等待 AI 响应"), true),
		MakeCmd(TEXT("/help"),       TEXT("显示所有可用命令"), true),

		// --- AI 命令 (选中后发送给 AI Agent) ---
		MakeCmd(TEXT("/new"),        TEXT("开始新会话"), false),
		MakeCmd(TEXT("/compact"),    TEXT("压缩上下文 (释放 token 空间)"), false),
		MakeCmd(TEXT("/review"),     TEXT("审查选中 Actor / 当前场景"), false),
		MakeCmd(TEXT("/undo"),       TEXT("撤销上一步 AI 操作"), false),
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
	// 命令名颜色: 本地命令白色, AI 命令蓝色
	FLinearColor CmdColor = Item->bIsLocal
		? FLinearColor(0.85f, 0.85f, 0.85f)
		: FLinearColor(0.4f, 0.75f, 1.0f);

	return SNew(STableRow<FSlashCommandPtr>, OwnerTable)
		.Padding(FMargin(6.0f, 3.0f))
		[
			SNew(SHorizontalBox)
			// 命令名
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 12.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Item->Command))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
				.ColorAndOpacity(FSlateColor(CmdColor))
			]
			// 描述
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
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("ChatCleared")));
	}
	else if (Command == TEXT("/cancel"))
	{
		// 取消等待 AI 响应
		if (bIsWaitingForResponse)
		{
			bIsWaitingForResponse = false;
			bHasStreamingMessage = false;
			StreamLinesRead = 0;

			// 停止 poll timer（防止旧的定时器继续轮询文件）
			if (PollTimerHandle.IsValid())
			{
				FTSTicker::GetCoreTicker().RemoveTicker(PollTimerHandle);
				PollTimerHandle.Reset();
			}

			// 通知平台取消当前请求
			PlatformBridge->CancelCurrentRequest();

			// 移除 "Thinking..." 或流式消息
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
		else
		{
			AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("NothingToCancel")));
		}
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
		FString ClientStatus = bCachedIsConnected ? FUEAgentL10n::GetStr(TEXT("Connected")) : FUEAgentL10n::GetStr(TEXT("Disconnected"));
		FString ServerAddr = CachedSubsystem.IsValid() ? CachedSubsystem->GetServerAddress() : TEXT("N/A");
		FString SendMode = bEnterToSend ? FUEAgentL10n::GetStr(TEXT("EnterToSend")) : FUEAgentL10n::GetStr(TEXT("CtrlEnterToSend"));

		TArray<FStringFormatArg> FormatArgs;
		FormatArgs.Add(FStringFormatArg(ClientStatus));
		FormatArgs.Add(FStringFormatArg(ServerAddr));
		FormatArgs.Add(FStringFormatArg(Messages.Num()));
		FormatArgs.Add(FStringFormatArg(SendMode));

		// StatusFormat 用 {0} {1} {2} {3} 占位符
		FString StatusText = FString::Format(*FUEAgentL10n::GetStr(TEXT("StatusFormat")), FormatArgs);
		AddMessage(TEXT("system"), StatusText);

		// 检查 MCP Server + 平台桥接状态
		PlatformBridge->QueryStatus();
	}
	else if (Command == TEXT("/help"))
	{
		FString HelpText = TEXT("可用命令:\n");
		HelpText += TEXT("\n  连接:\n");
		HelpText += TEXT("    /connect     连接 OpenClaw 网关\n");
		HelpText += TEXT("    /disconnect  断开连接\n");
		HelpText += TEXT("    /diagnose    运行连接诊断\n");
		HelpText += TEXT("    /status      显示连接状态\n");
		HelpText += TEXT("\n  会话:\n");
		HelpText += TEXT("    /clear       清空聊天记录\n");
		HelpText += TEXT("    /cancel      取消等待 AI 响应\n");
		HelpText += TEXT("    /help        显示此帮助\n");
		HelpText += TEXT("\n  AI 命令:\n");
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
			SenderLabel = FUEAgentL10n::GetStr(TEXT("SenderYou"));
		}
		else if (Msg.Sender == TEXT("assistant"))
		{
			SenderLabel = FUEAgentL10n::GetStr(TEXT("SenderAI"));
		}
		else
		{
			SenderLabel = FUEAgentL10n::GetStr(TEXT("SenderSystem"));
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
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("Connecting")));

	// 通过平台桥接连接
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString StatusFile = TempDir / TEXT("_connect_status.txt");
	IFileManager::Get().Delete(*StatusFile, false, false, true);

	PlatformBridge->Connect(StatusFile);

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
				// 立即更新 Subsystem 状态（不等 _bridge_status.json 轮询）
				if (Self->CachedSubsystem.IsValid())
				{
					Self->CachedSubsystem->SetConnectionStatus(true);
				}

				Self->AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("ConnectOK")));

				// 连接成功后，发送环境信息给 AI（非静默，显示回复）
				Self->SendEnvironmentContext();
			}
			else
			{
				// 连接失败也要确保状态为 disconnected
				if (Self->CachedSubsystem.IsValid())
				{
					Self->CachedSubsystem->SetConnectionStatus(false);
				}

				Self->AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("ConnectFail")));
			}
			return false;
		}),
		0.5f
	);
}

void SUEAgentDashboard::DisconnectOpenClawBridge()
{
	PlatformBridge->Disconnect();

	// 立即更新 Subsystem 状态（不等 _bridge_status.json 轮询）
	if (CachedSubsystem.IsValid())
	{
		CachedSubsystem->SetConnectionStatus(false);
	}

	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("BridgeDisconnected")));
}

void SUEAgentDashboard::RunDiagnoseConnection()
{
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("RunningHealthCheck")));

	// 诊断结果写入临时文件，然后轮询读取
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString DiagFile = TempDir / TEXT("_diagnose_result.txt");

	// 清除上次结果
	IFileManager::Get().Delete(*DiagFile, false, false, true);

	// 优先使用完整 Health Check，fallback 到平台桥接诊断
	// 强制 reload 确保使用最新代码
	FString PythonCmd = FString::Printf(
		TEXT("import importlib\n"
			 "try:\n"
			 "    import health_check\n"
			 "    importlib.reload(health_check)\n"
			 "    result = health_check.run_health_check()\n"
			 "    with open(r'%s', 'w', encoding='utf-8') as f:\n"
			 "        f.write(result)\n"
			 "except ImportError:\n"
			 "    pass\n"),
		*DiagFile);
	IPythonScriptPlugin::Get()->ExecPythonCommand(*PythonCmd);

	// 如果 health_check 没有生成文件，走平台桥接诊断
	if (!FPaths::FileExists(DiagFile))
	{
		PlatformBridge->RunDiagnostics(DiagFile);
	}

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
// 连接成功后发送环境上下文
// ==================================================================

void SUEAgentDashboard::SendEnvironmentContext()
{
	// 收集静态环境信息并通过 Python 发送给 AI
	// 这些信息在会话期间不会变化，帮助 AI 了解当前工作环境
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString ContextFile = TempDir / TEXT("_env_context.txt");
	IFileManager::Get().Delete(*ContextFile, false, false, true);

	PlatformBridge->CollectEnvironmentContext(ContextFile);

	// 轮询等待 context 文件生成，然后作为消息发送给 AI
	auto Self = SharedThis(this);
	FString CapturedFile = ContextFile;
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedFile](float) -> bool
		{
			if (!FPaths::FileExists(CapturedFile))
			{
				return true; // 继续等待
			}

			FString ContextMsg;
			TArray<uint8> RawBytes;
			if (FFileHelper::LoadFileToArray(RawBytes, *CapturedFile))
			{
				FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
				ContextMsg = FString(Converter.Length(), Converter.Get());
			}
			IFileManager::Get().Delete(*CapturedFile, false, false, true);

			if (!ContextMsg.IsEmpty())
			{
				// 作为系统消息发送给 AI (非静默，AI 的回复会显示在面板)
				Self->SendToOpenClaw(ContextMsg);
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
	// 如果上一个请求还在进行，先取消它（停止旧的轮询定时器）
	if (bIsWaitingForResponse)
	{
		// 停止旧的 poll timer
		if (PollTimerHandle.IsValid())
		{
			FTSTicker::GetCoreTicker().RemoveTicker(PollTimerHandle);
			PollTimerHandle.Reset();
		}
	}

	bIsWaitingForResponse = true;
	StreamLinesRead = 0;
	bHasStreamingMessage = false;
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("Thinking")));

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

	// 通过平台桥接异步发送
	PlatformBridge->SendMessageAsync(EscapedMsg, ResponseFile);

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
		if (Messages.Num() > 0 && Messages.Last().Content == FUEAgentL10n::GetStr(TEXT("Thinking")))
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
	if (!bHasStreamingMessage && Messages.Num() > 0 && Messages.Last().Content == FUEAgentL10n::GetStr(TEXT("Thinking")))
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
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("EmptyResponse")));
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
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("NoQuickInputs")); })
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
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("EditQuickInputBtn")); })
				.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("EditQuickInputTip")); })
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
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("DeleteQuickInputBtn")); })
				.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("DeleteQuickInputTip")); })
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
		.Title(FUEAgentL10n::Get(TEXT("EditQuickInputTitle")))
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
			.Text(FUEAgentL10n::Get(TEXT("QINameLabel")))
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
			.Text(FUEAgentL10n::Get(TEXT("QIContentLabel")))
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
				.Text(FUEAgentL10n::Get(TEXT("QISaveBtn")))
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
				.Text(FUEAgentL10n::Get(TEXT("QICancelBtn")))
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
			FUEAgentL10n::Get(TEXT("ConfirmDeleteQI")),
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
		.Title(FUEAgentL10n::Get(TEXT("EditQuickInputTitle")))
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
			.Text(FUEAgentL10n::Get(TEXT("QINameLabel")))
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
			.Text(FUEAgentL10n::Get(TEXT("QIContentLabel")))
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
				.Text(FUEAgentL10n::Get(TEXT("QISaveBtn")))
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
				.Text(FUEAgentL10n::Get(TEXT("QICancelBtn")))
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
// 阶段 D: Skill 创建集成 (v2 — 对话式，无弹窗)
// ==================================================================

FReply SUEAgentDashboard::OnCreateSkillClicked()
{
	// 检查 AI 连接状态
	if (!bCachedIsConnected)
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PleaseConnectFirst")));
		return FReply::Handled();
	}

	// 在输入框填入引导文本，让用户继续输入描述
	InputTextBox->SetText(FText::FromString(
		FUEAgentL10n::GetStr(TEXT("CreateSkillPrompt"))));
	FSlateApplication::Get().SetKeyboardFocus(InputTextBox.ToSharedRef());
	return FReply::Handled();
}

// ==================================================================
// 语言切换
// ==================================================================

FReply SUEAgentDashboard::OnToggleLanguageClicked()
{
	FUEAgentL10n::ToggleLanguage();
	RebuildAfterLanguageChange();
	return FReply::Handled();
}

void SUEAgentDashboard::RebuildAfterLanguageChange()
{
	// 重建消息列表（更新 sender 标签）
	RebuildMessageList();

	// 重建快捷输入面板
	RebuildQuickInputPanel();

	// 输入框 hint text 会自动通过 lambda/binding 刷新
	// 按钮文本通过 Text_Lambda 自动刷新
	// 对于非动态绑定的文本，Slate 不支持运行时更新静态 .Text()
	// 这些需要在下次打开面板时生效，或通过 Invalidate 触发
}

#undef LOCTEXT_NAMESPACE