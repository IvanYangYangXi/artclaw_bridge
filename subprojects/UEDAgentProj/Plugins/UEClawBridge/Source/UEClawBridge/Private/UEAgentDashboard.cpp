// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentDashboard.h"
#include "UEAgentSubsystem.h"
#include "UEAgentLocalization.h"
#include "UEAgentManagePanel.h"
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
#include "Widgets/Input/SComboBox.h"
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
#include "HAL/PlatformProcess.h"

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

	// 初始化会话名称标签 (任务 5.4) + 首个会话条目 (任务 5.8)
	InitFirstSession();

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

					// 发送 / 停止 切换按钮 (底部对齐)
					// bIsWaitingForResponse 时变为红色停止按钮
					+ SHorizontalBox::Slot()
					.AutoWidth()
					.VAlign(VAlign_Bottom)
					.Padding(0.0f, 0.0f, 0.0f, 1.0f)
					[
						SNew(SButton)
						.Text_Lambda([this]() -> FText {
							if (bIsWaitingForResponse)
							{
								return FUEAgentL10n::Get(TEXT("StopBtn"));
							}
							return FUEAgentL10n::Get(TEXT("SendBtn"));
						})
						.ToolTipText_Lambda([this]() -> FText {
							if (bIsWaitingForResponse)
							{
								return FUEAgentL10n::Get(TEXT("StopTip"));
							}
							return FUEAgentL10n::Get(TEXT("SendTip"));
						})
						.OnClicked_Lambda([this]() -> FReply {
							if (bIsWaitingForResponse)
							{
								return OnStopClicked();
							}
							return OnSendClicked();
						})
						.ButtonColorAndOpacity(TAttribute<FLinearColor>::CreateLambda([this]() -> FLinearColor {
							if (bIsWaitingForResponse)
							{
								return FLinearColor(0.8f, 0.2f, 0.2f); // 红色停止
							}
							return FLinearColor(1.0f, 1.0f, 1.0f); // 默认白色
						}))
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

				// 会话选择下拉菜单 (任务 5.8)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SAssignNew(SessionMenuAnchor, SMenuAnchor)
					.Placement(MenuPlacement_AboveAnchor)
					.OnGetMenuContent_Lambda([this]() -> TSharedRef<SWidget>
					{
						return BuildSessionMenuContent();
					})
					[
						SNew(SButton)
						.Text_Lambda([this]() -> FText { return GetActiveSessionLabel(); })
						.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("SessionMenuTip")); })
						.OnClicked_Lambda([this]() -> FReply { return OnSessionMenuClicked(); })
						.ContentPadding(FMargin(4.0f, 1.0f))
					]
				]

				// /new 按钮 (小号紧凑)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
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

				// Skill/MCP 管理按钮
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageBtn")); })
					.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageTip")); })
					.OnClicked(this, &SUEAgentDashboard::OnManageClicked)
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

				// 静默模式切换按钮 (阶段 5.7)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([this]() {
						return bSilentMode
							? FUEAgentL10n::Get(TEXT("SilentModeOn"))
							: FUEAgentL10n::Get(TEXT("SilentModeOff"));
					})
					.ToolTipText_Lambda([]() {
						return FUEAgentL10n::Get(TEXT("SilentModeTip"));
					})
					.OnClicked(this, &SUEAgentDashboard::OnToggleSilentModeClicked)
					.ContentPadding(FMargin(4.0f, 1.0f))
					.ButtonColorAndOpacity(TAttribute<FLinearColor>::CreateLambda([this]() -> FLinearColor {
						return bSilentMode
							? FLinearColor(0.2f, 0.6f, 0.2f) // 绿色 = 开
							: FLinearColor(1.0f, 1.0f, 1.0f); // 默认
					}))
				]

				// Plan 模式切换按钮 (任务 5.9)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([this]() {
						return GetPlanModeButtonText();
					})
					.ToolTipText_Lambda([]() {
						return FUEAgentL10n::Get(TEXT("PlanModeTip"));
					})
					.OnClicked(this, &SUEAgentDashboard::OnTogglePlanModeClicked)
					.ContentPadding(FMargin(4.0f, 1.0f))
					.ButtonColorAndOpacity(TAttribute<FLinearColor>::CreateLambda([this]() -> FLinearColor {
						return bPlanMode
							? FLinearColor(0.3f, 0.5f, 0.9f) // 蓝色 = Plan 开
							: FLinearColor(1.0f, 1.0f, 1.0f); // 默认
					}))
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

	// 加载静默模式配置 (阶段 5.7)
	LoadSilentModeFromConfig();

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

				// Connect 成功后的宽限期内，忽略 connected=false（防止旧值覆盖）
				if (!bConnected && Self->ConnectGraceUntil > 0.0
					&& FPlatformTime::Seconds() < Self->ConnectGraceUntil)
				{
					return true;
				}
				// 宽限期过后或读到 connected=true 时，清除宽限期
				Self->ConnectGraceUntil = 0.0;

				// 更新 Subsystem 状态（触发图标颜色变化等）
				if (Self->CachedSubsystem.IsValid())
				{
					Self->CachedSubsystem->SetConnectionStatus(bConnected);
				}

				// 当 Bridge 已连接 + MCP Server 就绪 + 环境上下文待发送 → 发送环境信息给 AI
				if (bConnected && bMcpReady && Self->bEnvContextPending)
				{
					Self->bEnvContextPending = false;
					Self->SendEnvironmentContext();
				}

				return true; // 持续轮询
			}),
			2.0f // 每 2 秒检查一次
		);
	}

	// 阶段 5.6: 文件操作确认请求轮询 — 独立于 AI 响应轮询
	// Python 侧在 MCP tool 执行线程中写入 _confirm_request.json 并等待响应
	// C++ 侧在 Game Thread 定时检测并弹窗
	{
		auto Self = SharedThis(this);
		ConfirmPollHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateLambda([Self](float) -> bool
			{
				Self->PollConfirmationRequests();
				return true; // 持续轮询
			}),
			0.2f // 每 0.2 秒检查一次 (Python 侧 sleep(0.1) 精度)
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

	// 停止确认弹窗轮询 (阶段 5.6)
	if (ConfirmPollHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(ConfirmPollHandle);
		ConfirmPollHandle.Reset();
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
	FString FormatStr = FUEAgentL10n::GetStr(TEXT("StatsFormat"));
	FStringFormatOrderedArguments Args;
	Args.Add(Connections);
	Args.Add(Messages.Num());
	return FText::FromString(FString::Format(*FormatStr, Args));
}

FText SUEAgentDashboard::GetStatusSummaryText() const
{
	FString Summary = bCachedIsConnected
		? FUEAgentL10n::GetStr(TEXT("ConnectedDot"))
		: FUEAgentL10n::GetStr(TEXT("DisconnectedDot"));

	// 显示上下文使用百分比 (任务 5.5)
	if (LastTotalTokens > 0 && ContextWindowSize > 0)
	{
		int32 Pct = FMath::RoundToInt32(100.0f * LastTotalTokens / ContextWindowSize);
		Pct = FMath::Clamp(Pct, 0, 100);

		// 格式化 token 数为 K 单位
		auto FormatK = [](int32 Tokens) -> FString
		{
			if (Tokens >= 1000)
			{
				return FString::Printf(TEXT("%dK"), FMath::RoundToInt32(Tokens / 1000.0f));
			}
			return FString::Printf(TEXT("%d"), Tokens);
		};

		Summary += FString::Printf(TEXT("  |  %s: %d%% (%s/%s)"),
			*FUEAgentL10n::GetStr(TEXT("ContextUsage")),
			Pct,
			*FormatK(LastTotalTokens),
			*FormatK(ContextWindowSize));
	}

	// 显示当前会话名称 (任务 5.4)
	if (!CurrentSessionLabel.IsEmpty())
	{
		Summary += FString::Printf(TEXT("  |  %s"), *CurrentSessionLabel);
	}

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
	SendToOpenClaw(InputText);

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnNewChatClicked()
{
	// 0) 取消正在执行的 Plan (任务 5.9)
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
		FString SilentFlagFile = FPaths::ProjectSavedDir() / TEXT("UEAgent/_silent_session.flag");
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
		// SessionKey 会在首次发送消息后由 bridge 自动生成

		SessionEntries.Add(MoveTemp(NewEntry));
		ActiveSessionIndex = SessionEntries.Num() - 1;
	}

	// 6) 发送 /new 给 AI（重置远端会话），非静默——显示 AI 的回复
	SendToOpenClaw(TEXT("/new"));

	return FReply::Handled();
}

// ==================================================================
// 停止 AI 回答 (任务 5.2)
// ==================================================================

FReply SUEAgentDashboard::OnStopClicked()
{
	if (!bIsWaitingForResponse)
	{
		return FReply::Handled();
	}

	// 1) 停止 poll timer
	if (PollTimerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(PollTimerHandle);
		PollTimerHandle.Reset();
	}

	// 2) 调用平台桥接取消请求
	PlatformBridge->CancelRequest();

	// 3) 重置等待状态
	bIsWaitingForResponse = false;
	bHasStreamingMessage = false;
	StreamLinesRead = 0;

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
	auto MakeCmd = [](const FString& Cmd, const FString& L10nKey, bool bLocal) -> FSlashCommandPtr {
		auto Item = MakeShared<FSlashCommand>();
		Item->Command = Cmd;
		Item->Description = FUEAgentL10n::GetStr(L10nKey);
		Item->bIsLocal = bLocal;
		return Item;
	};

	AllSlashCommands = {
		// --- 本地命令 (不转发，本地执行) ---
		MakeCmd(TEXT("/connect"),    TEXT("SlashConnect"), true),
		MakeCmd(TEXT("/disconnect"), TEXT("SlashDisconnect"), true),
		MakeCmd(TEXT("/diagnose"),   TEXT("SlashDiagnose"), true),
		MakeCmd(TEXT("/status"),     TEXT("SlashStatus"), true),
		MakeCmd(TEXT("/clear"),      TEXT("SlashClear"), true),
		MakeCmd(TEXT("/cancel"),     TEXT("SlashCancel"), true),
		MakeCmd(TEXT("/help"),       TEXT("SlashHelp"), true),
		MakeCmd(TEXT("/plan"),       TEXT("SlashPlan"), true),

		// --- AI 命令 (选中后发送给 AI Agent) ---
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
		FString HelpText = FUEAgentL10n::GetStr(TEXT("HelpTitle")) + TEXT("\n");
		HelpText += FUEAgentL10n::GetStr(TEXT("HelpSectionConnect")) + TEXT("\n");
		HelpText += FString::Printf(TEXT("    /connect     %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashConnect")));
		HelpText += FString::Printf(TEXT("    /disconnect  %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashDisconnect")));
		HelpText += FString::Printf(TEXT("    /diagnose    %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashDiagnose")));
		HelpText += FString::Printf(TEXT("    /status      %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashStatus")));
		HelpText += FUEAgentL10n::GetStr(TEXT("HelpSectionChat")) + TEXT("\n");
		HelpText += FString::Printf(TEXT("    /clear       %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashClear")));
		HelpText += FString::Printf(TEXT("    /cancel      %s\n"), *FUEAgentL10n::GetStr(TEXT("SlashCancel")));
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
			// /plan (无参数) → 切换 Plan 模式开关
			bPlanMode = !bPlanMode;
			if (!bPlanMode)
			{
				// 关闭 Plan 模式时，如果有活跃 Plan 则取消
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
			// /plan <任务描述> → 开启 Plan 模式并直接发送
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

	// 生成摘要作为 Content
	Msg.Content = FString::Printf(TEXT("[%s] %s"), *ToolName, *ToolId);

	Messages.Add(MoveTemp(Msg));
	RebuildMessageList();
}

void SUEAgentDashboard::AddToolResultMessage(const FString& ToolName, const FString& ToolId, const FString& ResultContent, bool bIsError)
{
	// 尝试找到对应的 tool_call 消息并更新它（而非追加新消息）
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

	// 没找到对应 call，作为独立 result 消息添加
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

void SUEAgentDashboard::RebuildMessageList()
{
	if (!MessageScrollBox.IsValid())
	{
		return;
	}

	MessageScrollBox->ClearChildren();

	for (int32 MsgIdx = 0; MsgIdx < Messages.Num(); ++MsgIdx)
	{
		const FChatMessage& Msg = Messages[MsgIdx];
		FString TimeStr = Msg.Timestamp.ToString(TEXT("%H:%M"));

		// --- 工具调用/结果消息 ---
		if (Msg.Sender == TEXT("tool_call") || Msg.Sender == TEXT("tool_result") || Msg.Sender == TEXT("tool_error"))
		{
			bool bIsError = Msg.bToolError;
			bool bHasResult = !Msg.ToolResult.IsEmpty();
			FString StatusIcon = bHasResult ? (bIsError ? TEXT("X") : TEXT("ok")) : TEXT("...");
			FString ToggleLabel = Msg.bToolCollapsed ? TEXT("+") : TEXT("-");

			// 工具调用卡片
			MessageScrollBox->AddSlot()
			.Padding(6.0f, 1.0f)
			[
				SNew(SVerticalBox)

				// 工具标题行: [toggle] tool_icon ToolName  时间  状态
				+ SVerticalBox::Slot()
				.AutoHeight()
				[
					SNew(SHorizontalBox)

					// 展开/折叠按钮
					+ SHorizontalBox::Slot()
					.AutoWidth()
					.Padding(0.0f, 0.0f, 4.0f, 0.0f)
					[
						SNew(SButton)
						.ButtonStyle(FCoreStyle::Get(), "NoBorder")
						.ContentPadding(FMargin(2.0f, 0.0f))
						.OnClicked_Lambda([this, MsgIdx]() { return OnToggleToolCollapse(MsgIdx); })
						[
							SNew(STextBlock)
							.Text(FText::FromString(ToggleLabel))
							.Font(FCoreStyle::GetDefaultFontStyle("Mono", 9))
							.ColorAndOpacity(FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f)))
						]
					]

					// 工具名称
					+ SHorizontalBox::Slot()
					.AutoWidth()
					[
						SNew(STextBlock)
						.Text(FText::FromString(Msg.ToolName))
						.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
						.ColorAndOpacity(GetSenderColor(Msg.Sender))
					]

					// 时间
					+ SHorizontalBox::Slot()
					.AutoWidth()
					.Padding(8.0f, 0.0f, 0.0f, 0.0f)
					[
						SNew(STextBlock)
						.Text(FText::FromString(TimeStr))
						.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
						.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
					]

					// 状态
					+ SHorizontalBox::Slot()
					.AutoWidth()
					.Padding(8.0f, 0.0f, 0.0f, 0.0f)
					[
						SNew(STextBlock)
						.Text(FText::FromString(FString::Printf(TEXT("[%s]"), *StatusIcon)))
						.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
						.ColorAndOpacity(bIsError
							? FSlateColor(FLinearColor(0.9f, 0.3f, 0.3f))
							: FSlateColor(FLinearColor(0.5f, 0.7f, 0.5f)))
					]
				]

				// 展开的详情
				+ SVerticalBox::Slot()
				.AutoHeight()
				[
					SNew(SBox)
					.Visibility(Msg.bToolCollapsed ? EVisibility::Collapsed : EVisibility::Visible)
					[
						SNew(SVerticalBox)

						// 参数
						+ SVerticalBox::Slot()
						.AutoHeight()
						.Padding(20.0f, 2.0f, 0.0f, 2.0f)
						[
							SNew(SMultiLineEditableText)
							.Text(FText::FromString(
								Msg.ToolArguments.IsEmpty()
									? TEXT("(no arguments)")
									: Msg.ToolArguments))
							.Font(FCoreStyle::GetDefaultFontStyle("Mono", 8))
							.AutoWrapText(true)
							.IsReadOnly(true)
							.AllowContextMenu(true)
							.ColorAndOpacity(FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f)))
						]

						// 结果
						+ SVerticalBox::Slot()
						.AutoHeight()
						.Padding(20.0f, 2.0f, 0.0f, 4.0f)
						[
							SNew(SBox)
							.Visibility(bHasResult ? EVisibility::Visible : EVisibility::Collapsed)
							[
								SNew(SMultiLineEditableText)
								.Text(FText::FromString(Msg.ToolResult.Left(1000)))
								.Font(FCoreStyle::GetDefaultFontStyle("Mono", 8))
								.AutoWrapText(true)
								.IsReadOnly(true)
								.AllowContextMenu(true)
								.ColorAndOpacity(bIsError
									? FSlateColor(FLinearColor(0.9f, 0.4f, 0.4f))
									: FSlateColor(FLinearColor(0.5f, 0.7f, 0.5f)))
							]
						]
					]
				]
			];

			continue;
		}

		// --- Plan 卡片消息 (任务 5.9) ---
		if (Msg.Sender == TEXT("plan") && CurrentPlan.IsSet())
		{
			// 计算完成数
			int32 DoneCount = 0;
			int32 TotalCount = CurrentPlan->Steps.Num();
			for (const auto& Step : CurrentPlan->Steps)
			{
				if (Step.Status == EPlanStepStatus::Done)
				{
					DoneCount++;
				}
			}

			// 进度文本
			FString ProgressStr = FString::Printf(TEXT("%s (%d/%d %s)"),
				*FUEAgentL10n::GetStr(TEXT("PlanTitle")),
				DoneCount, TotalCount,
				*FUEAgentL10n::GetStr(TEXT("PlanProgressFmt")));

			// 构建步骤列表
			TSharedRef<SVerticalBox> StepsBox = SNew(SVerticalBox);

			// 标题行
			StepsBox->AddSlot()
			.AutoHeight()
			.Padding(4.0f, 4.0f, 4.0f, 6.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(ProgressStr))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.85f, 0.85f, 0.85f)))
			];

			// 步骤列表
			for (int32 Si = 0; Si < CurrentPlan->Steps.Num(); Si++)
			{
				const FPlanStep& Step = CurrentPlan->Steps[Si];
				const int32 CapturedStepIndex = Si;

				// 状态标签和颜色
				FString StatusLabel;
				FLinearColor StatusColor;
				switch (Step.Status)
				{
				case EPlanStepStatus::Pending:
					StatusLabel = FString::Printf(TEXT("[%s]"), *FUEAgentL10n::GetStr(TEXT("PlanStepPending")));
					StatusColor = FLinearColor(0.5f, 0.5f, 0.5f);
					break;
				case EPlanStepStatus::Running:
					StatusLabel = FString::Printf(TEXT("[%s]"), *FUEAgentL10n::GetStr(TEXT("PlanStepRunning")));
					StatusColor = FLinearColor(0.3f, 0.6f, 1.0f);
					break;
				case EPlanStepStatus::Done:
					StatusLabel = FString::Printf(TEXT("[%s]"), *FUEAgentL10n::GetStr(TEXT("PlanStepDone")));
					StatusColor = FLinearColor(0.3f, 0.85f, 0.3f);
					break;
				case EPlanStepStatus::Failed:
					StatusLabel = FString::Printf(TEXT("[%s]"), *FUEAgentL10n::GetStr(TEXT("PlanStepFailed")));
					StatusColor = FLinearColor(0.9f, 0.3f, 0.3f);
					break;
				case EPlanStepStatus::Skipped:
					StatusLabel = FString::Printf(TEXT("[%s]"), *FUEAgentL10n::GetStr(TEXT("PlanStepSkipped")));
					StatusColor = FLinearColor(0.45f, 0.45f, 0.45f);
					break;
				}

				FString StepText = FString::Printf(TEXT("%s %d. %s"), *StatusLabel, Step.Index, *Step.Title);

				TSharedRef<SHorizontalBox> StepRow = SNew(SHorizontalBox)

					// 状态 + 步骤标题
					+ SHorizontalBox::Slot()
					.FillWidth(1.0f)
					.VAlign(VAlign_Center)
					[
						SNew(STextBlock)
						.Text(FText::FromString(StepText))
						.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
						.ColorAndOpacity(FSlateColor(StatusColor))
						.AutoWrapText(true)
					];

				// 删除按钮 (仅 Pending 状态显示)
				if (Step.Status == EPlanStepStatus::Pending)
				{
					StepRow->AddSlot()
					.AutoWidth()
					.VAlign(VAlign_Center)
					.Padding(4.0f, 0.0f, 0.0f, 0.0f)
					[
						SNew(SButton)
						.Text(FUEAgentL10n::Get(TEXT("PlanDeleteStep")))
						.OnClicked_Lambda([this, CapturedStepIndex]() -> FReply
						{
							return OnDeletePlanStep(CapturedStepIndex);
						})
						.ContentPadding(FMargin(3.0f, 1.0f))
						.ButtonColorAndOpacity(FLinearColor(0.7f, 0.3f, 0.3f))
					];
				}

				StepsBox->AddSlot()
				.AutoHeight()
				.Padding(8.0f, 1.0f, 4.0f, 1.0f)
				[
					StepRow
				];
			}

			// 底部操作按钮
			TSharedRef<SHorizontalBox> ActionRow = SNew(SHorizontalBox);

			if (!CurrentPlan->bIsExecuting)
			{
				// "执行全部" 按钮 (Plan 未开始执行或已暂停时显示)
				if (CurrentPlan->bIsPaused)
				{
					ActionRow->AddSlot()
					.AutoWidth()
					.Padding(0.0f, 0.0f, 4.0f, 0.0f)
					[
						SNew(SButton)
						.Text(FUEAgentL10n::Get(TEXT("PlanResume")))
						.OnClicked(this, &SUEAgentDashboard::OnResumePlanClicked)
						.ContentPadding(FMargin(8.0f, 3.0f))
						.ButtonColorAndOpacity(FLinearColor(0.3f, 0.7f, 0.3f))
					];
				}
				else
				{
					ActionRow->AddSlot()
					.AutoWidth()
					.Padding(0.0f, 0.0f, 4.0f, 0.0f)
					[
						SNew(SButton)
						.Text(FUEAgentL10n::Get(TEXT("PlanExecuteAll")))
						.OnClicked(this, &SUEAgentDashboard::OnExecutePlanClicked)
						.ContentPadding(FMargin(8.0f, 3.0f))
						.ButtonColorAndOpacity(FLinearColor(0.3f, 0.7f, 0.3f))
					];
				}
			}
			else
			{
				// "暂停" 按钮 (执行中时显示)
				ActionRow->AddSlot()
				.AutoWidth()
				.Padding(0.0f, 0.0f, 4.0f, 0.0f)
				[
					SNew(SButton)
					.Text(FUEAgentL10n::Get(TEXT("PlanPause")))
					.OnClicked(this, &SUEAgentDashboard::OnPausePlanClicked)
					.ContentPadding(FMargin(8.0f, 3.0f))
					.ButtonColorAndOpacity(FLinearColor(0.8f, 0.6f, 0.2f))
				];
			}

			// "取消计划" 按钮
			ActionRow->AddSlot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(FUEAgentL10n::Get(TEXT("PlanCancel")))
				.OnClicked(this, &SUEAgentDashboard::OnCancelPlanClicked)
				.ContentPadding(FMargin(8.0f, 3.0f))
				.ButtonColorAndOpacity(FLinearColor(0.7f, 0.3f, 0.3f))
			];

			StepsBox->AddSlot()
			.AutoHeight()
			.Padding(8.0f, 8.0f, 4.0f, 4.0f)
			[
				ActionRow
			];

			// 整个 Plan 卡片
			MessageScrollBox->AddSlot()
			.Padding(6.0f, 4.0f)
			[
				SNew(SBorder)
				.BorderImage(FAppStyle::GetBrush("ToolPanel.GroupBorder"))
				.Padding(FMargin(4.0f))
				[
					StepsBox
				]
			];

			continue;
		}

		// --- 常规消息 ---
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

	// 任务 5.3: 延迟一帧再次滚动，确保 Layout 计算完成后滚到底
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([WeakThis = TWeakPtr<SUEAgentDashboard>(SharedThis(this))](float) -> bool
		{
			if (auto Pinned = WeakThis.Pin())
			{
				if (Pinned->MessageScrollBox.IsValid())
				{
					Pinned->MessageScrollBox->ScrollToEnd();
				}
			}
			return false; // 只执行一次
		}),
		0.0f // 下一帧立即执行
	);
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

				// 防止旧的 _bridge_status.json 轮询覆盖刚设置的 connected 状态：
				// 设置宽限期，在此期间轮询跳过状态更新
				Self->ConnectGraceUntil = FPlatformTime::Seconds() + 5.0;

				Self->AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("ConnectOK")));

				// 环境上下文延迟到 mcp_ready=true 时发送（见 BridgeStatusPoll）
				Self->bEnvContextPending = true;
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

	bEnvContextPending = false;
	ConnectGraceUntil = 0.0;

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

							if (EventType == TEXT("thinking"))
							{
								FString EventText = JsonObj->GetStringField(TEXT("text"));
								if (!EventText.IsEmpty())
								{
									Self->UpdateStreamingMessage(TEXT("thinking"), EventText);
								}
							}
							else if (EventType == TEXT("delta"))
							{
								FString EventText = JsonObj->GetStringField(TEXT("text"));
								if (!EventText.IsEmpty())
								{
									Self->UpdateStreamingMessage(TEXT("assistant"), EventText);
								}
							}
							else if (EventType == TEXT("tool_call"))
							{
								FString ToolName = JsonObj->GetStringField(TEXT("tool_name"));
								FString ToolId = JsonObj->GetStringField(TEXT("tool_id"));

								// 序列化 arguments 对象为字符串
								FString ArgsStr;
								const TSharedPtr<FJsonObject>* ArgsObj = nullptr;
								if (JsonObj->TryGetObjectField(TEXT("arguments"), ArgsObj) && ArgsObj)
								{
									TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&ArgsStr);
									FJsonSerializer::Serialize(ArgsObj->ToSharedRef(), Writer);
								}

								if (!ToolName.IsEmpty())
								{
									Self->AddToolCallMessage(ToolName, ToolId, ArgsStr);
								}
							}
							else if (EventType == TEXT("tool_result"))
							{
								FString ToolName = JsonObj->GetStringField(TEXT("tool_name"));
								FString ToolId = JsonObj->GetStringField(TEXT("tool_id"));
								FString Content = JsonObj->GetStringField(TEXT("content"));
								bool bIsError = JsonObj->GetBoolField(TEXT("is_error"));

								if (!ToolName.IsEmpty())
								{
									Self->AddToolResultMessage(ToolName, ToolId, Content, bIsError);
								}
							}
							else if (EventType == TEXT("usage"))
							{
								// 解析 token usage 信息 (任务 5.5)
								const TSharedPtr<FJsonObject>* UsageObj = nullptr;
								if (JsonObj->TryGetObjectField(TEXT("usage"), UsageObj) && UsageObj)
								{
									int32 TotalTokens = 0;
									if ((*UsageObj)->TryGetNumberField(TEXT("totalTokens"), TotalTokens) && TotalTokens > 0)
									{
										Self->LastTotalTokens = TotalTokens;
									}
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
		// 替换 "Thinking..." 消息 — 从末尾往前查找（跳过 tool 消息）
		for (int32 i = Messages.Num() - 1; i >= 0; --i)
		{
			if (Messages[i].Content == FUEAgentL10n::GetStr(TEXT("Thinking"))
				&& Messages[i].Sender == TEXT("system"))
			{
				Messages.RemoveAt(i);
				break;
			}
			// 只跳过 tool 消息，遇到其他类型就停止
			if (Messages[i].Sender != TEXT("tool_call")
				&& Messages[i].Sender != TEXT("tool_result")
				&& Messages[i].Sender != TEXT("tool_error"))
			{
				break;
			}
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
		// 从末尾往前找最后一条 streaming/thinking 消息（跳过 tool 消息）
		int32 LastStreamIdx = INDEX_NONE;
		for (int32 i = Messages.Num() - 1; i >= 0; --i)
		{
			if (Messages[i].Sender == StreamSender)
			{
				LastStreamIdx = i;
				break;
			}
			// 只跳过 tool 消息
			if (Messages[i].Sender != TEXT("tool_call")
				&& Messages[i].Sender != TEXT("tool_result")
				&& Messages[i].Sender != TEXT("tool_error"))
			{
				break;
			}
		}

		if (LastStreamIdx != INDEX_NONE)
		{
			Messages[LastStreamIdx].Content = Content;
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
	if (!bHasStreamingMessage && Messages.Num() > 0)
	{
		for (int32 i = Messages.Num() - 1; i >= 0; --i)
		{
			if (Messages[i].Content == FUEAgentL10n::GetStr(TEXT("Thinking"))
				&& Messages[i].Sender == TEXT("system"))
			{
				Messages.RemoveAt(i);
				RebuildMessageList();
				break;
			}
			// 跳过 tool 消息
			if (Messages[i].Sender != TEXT("tool_call")
				&& Messages[i].Sender != TEXT("tool_result")
				&& Messages[i].Sender != TEXT("tool_error"))
			{
				break;
			}
		}
	}

	// 如果有流式消息，移除 thinking/streaming 消息（最终回复会替代）
	// 保留 tool 消息
	if (bHasStreamingMessage)
	{
		for (int32 i = Messages.Num() - 1; i >= 0; --i)
		{
			const FString& S = Messages[i].Sender;
			if (S == TEXT("thinking") || S == TEXT("streaming"))
			{
				Messages.RemoveAt(i);
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

	// --- Plan 模式: 区分 Plan 生成回复 vs Plan 步骤执行回复 ---
	if (bPlanMode)
	{
		// 状态1: 正在生成 Plan (bPlanMode=true, !CurrentPlan.IsSet())
		if (!CurrentPlan.IsSet())
		{
			TryParsePlan(Response);
			return;
		}

		// 状态2: 正在执行 Plan 步骤
		if (CurrentPlan.IsSet() && CurrentPlan->bIsExecuting)
		{
			int32 StepIdx = CurrentPlan->CurrentStepIndex;
			if (StepIdx >= 0 && StepIdx < CurrentPlan->Steps.Num())
			{
				// 显示 AI 回复
				AddMessage(TEXT("assistant"), Response);

				// 简单错误检测 — 只匹配明确的错误标记
				if (Response.Contains(TEXT("[Error]")) || Response.Contains(TEXT("[ERROR]")))
				{
					CurrentPlan->Steps[StepIdx].Status = EPlanStepStatus::Failed;
					CurrentPlan->Steps[StepIdx].Result = Response.Left(200);
					CurrentPlan->bIsPaused = true;
					CurrentPlan->bIsExecuting = false;
					AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanStepFailedMsg")));
					AddPlanMessage();
				}
				else
				{
					// 当前步骤完成
					CurrentPlan->Steps[StepIdx].Status = EPlanStepStatus::Done;
					CurrentPlan->Steps[StepIdx].Result = Response.Left(200);

					// 继续下一步 (ExecuteNextPlanStep 会调用 AddPlanMessage)
					ExecuteNextPlanStep();
				}
			}
			return;
		}
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
	else if (Sender == TEXT("tool_call"))
	{
		// 橙色，工具调用
		return FSlateColor(FLinearColor(1.0f, 0.6f, 0.2f));
	}
	else if (Sender == TEXT("tool_result"))
	{
		// 暗绿，工具结果
		return FSlateColor(FLinearColor(0.3f, 0.6f, 0.3f));
	}
	else if (Sender == TEXT("tool_error"))
	{
		// 红色，工具执行报错
		return FSlateColor(FLinearColor(0.9f, 0.3f, 0.3f));
	}
	else if (Sender == TEXT("plan"))
	{
		// 蓝色，Plan 卡片
		return FSlateColor(FLinearColor(0.4f, 0.6f, 1.0f));
	}
	else
	{
		return FSlateColor(FLinearColor(0.7f, 0.7f, 0.7f));
	}
}

// ==================================================================
// 多会话管理 (任务 5.8)
// ==================================================================

void SUEAgentDashboard::InitFirstSession()
{
	FDateTime Now = FDateTime::Now();
	CurrentSessionLabel = FString::Printf(TEXT("%s %02d-%02d %02d:%02d"),
		*FUEAgentL10n::GetStr(TEXT("SessionLabel")),
		Now.GetMonth(), Now.GetDay(), Now.GetHour(), Now.GetMinute());

	FSessionEntry FirstEntry;
	FirstEntry.Label = CurrentSessionLabel;
	FirstEntry.CreatedAt = Now;
	FirstEntry.bIsActive = true;

	SessionEntries.Add(MoveTemp(FirstEntry));
	ActiveSessionIndex = 0;
}

FReply SUEAgentDashboard::OnSessionMenuClicked()
{
	if (SessionMenuAnchor.IsValid())
	{
		SessionMenuAnchor->SetIsOpen(!SessionMenuAnchor->IsOpen());
	}
	return FReply::Handled();
}

TSharedRef<SWidget> SUEAgentDashboard::BuildSessionMenuContent()
{
	// 在打开菜单前，更新当前活跃会话的 session key
	if (ActiveSessionIndex >= 0 && SessionEntries.IsValidIndex(ActiveSessionIndex))
	{
		FString CurrentKey = PlatformBridge->GetSessionKey();
		if (!CurrentKey.IsEmpty())
		{
			SessionEntries[ActiveSessionIndex].SessionKey = CurrentKey;
		}
	}

	TSharedRef<SVerticalBox> MenuBox = SNew(SVerticalBox);

	for (int32 i = SessionEntries.Num() - 1; i >= 0; --i)
	{
		const FSessionEntry& Entry = SessionEntries[i];
		const int32 CapturedIndex = i;
		bool bActive = (i == ActiveSessionIndex);

		MenuBox->AddSlot()
		.AutoHeight()
		.Padding(2.0f, 1.0f)
		[
			SNew(SHorizontalBox)

			// 会话标签
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			.VAlign(VAlign_Center)
			[
				SNew(SButton)
				.ButtonStyle(FCoreStyle::Get(), "NoBorder")
				.ContentPadding(FMargin(6.0f, 3.0f))
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply
				{
					OnSessionSelected(CapturedIndex);
					if (SessionMenuAnchor.IsValid())
					{
						SessionMenuAnchor->SetIsOpen(false);
					}
					return FReply::Handled();
				})
				[
					SNew(STextBlock)
					.Text(FText::FromString(Entry.Label))
					.Font(bActive
						? FCoreStyle::GetDefaultFontStyle("Bold", 10)
						: FCoreStyle::GetDefaultFontStyle("Regular", 10))
					.ColorAndOpacity(bActive
						? FSlateColor(FLinearColor(0.3f, 0.8f, 1.0f))
						: FSlateColor(FLinearColor(0.8f, 0.8f, 0.8f)))
				]
			]

			// 删除按钮 (小 X，不对当前活跃的唯一会话显示)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			.Padding(4.0f, 0.0f, 2.0f, 0.0f)
			[
				SNew(SButton)
				.Visibility(SessionEntries.Num() > 1 ? EVisibility::Visible : EVisibility::Collapsed)
				.ButtonStyle(FCoreStyle::Get(), "NoBorder")
				.ContentPadding(FMargin(3.0f, 1.0f))
				.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("SessionDeleteTip")); })
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply
				{
					OnDeleteSession(CapturedIndex);
					if (SessionMenuAnchor.IsValid())
					{
						SessionMenuAnchor->SetIsOpen(false);
					}
					return FReply::Handled();
				})
				[
					SNew(STextBlock)
					.Text(FText::FromString(TEXT("x")))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
					.ColorAndOpacity(FSlateColor(FLinearColor(0.6f, 0.4f, 0.4f)))
				]
			]
		];
	}

	return SNew(SBorder)
		.BorderImage(FAppStyle::GetBrush("Menu.Background"))
		.Padding(4.0f)
		[
			SNew(SBox)
			.MaxDesiredHeight(300.0f)
			.MinDesiredWidth(200.0f)
			[
				MenuBox
			]
		];
}

void SUEAgentDashboard::OnSessionSelected(int32 Index)
{
	if (!SessionEntries.IsValidIndex(Index))
	{
		return;
	}

	// 已经是当前会话，无需切换
	if (Index == ActiveSessionIndex)
	{
		return;
	}

	// 1) 保存当前活跃会话的 session key
	if (ActiveSessionIndex >= 0 && SessionEntries.IsValidIndex(ActiveSessionIndex))
	{
		FString CurrentKey = PlatformBridge->GetSessionKey();
		if (!CurrentKey.IsEmpty())
		{
			SessionEntries[ActiveSessionIndex].SessionKey = CurrentKey;
		}
		SessionEntries[ActiveSessionIndex].bIsActive = false;
	}

	// 2) 设置新活跃会话
	ActiveSessionIndex = Index;
	SessionEntries[Index].bIsActive = true;
	CurrentSessionLabel = SessionEntries[Index].Label;

	// 3) 清空当前消息列表
	Messages.Empty();
	RebuildMessageList();

	// 4) 如果目标会话有 session key，加载历史并切换 bridge
	if (!SessionEntries[Index].SessionKey.IsEmpty())
	{
		// 切换 bridge 的 session key
		PlatformBridge->SetSessionKey(SessionEntries[Index].SessionKey);

		// 加载历史消息
		LoadSessionHistory(SessionEntries[Index].SessionKey);
	}
	else
	{
		// 新建的但未发过消息的会话，重置 bridge session
		PlatformBridge->ResetSession();
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("NewChatStarted")));
	}

	// 5) 重置 token usage
	LastTotalTokens = 0;

	AddMessage(TEXT("system"),
		FString::Printf(TEXT("%s"),
			*FString::Format(
				*FUEAgentL10n::GetStr(TEXT("SessionSwitched")),
				{ FStringFormatArg(CurrentSessionLabel) })));
}

void SUEAgentDashboard::OnDeleteSession(int32 Index)
{
	if (!SessionEntries.IsValidIndex(Index))
	{
		return;
	}

	// 确认删除
	EAppReturnType::Type Result = FMessageDialog::Open(
		EAppMsgType::YesNo,
		FUEAgentL10n::Get(TEXT("SessionDeleteConfirm")));

	if (Result != EAppReturnType::Yes)
	{
		return;
	}

	bool bDeletingActive = (Index == ActiveSessionIndex);

	SessionEntries.RemoveAt(Index);

	// 修正 ActiveSessionIndex
	if (bDeletingActive)
	{
		// 删的是当前活跃会话
		if (SessionEntries.Num() == 0)
		{
			// 没有会话了，创建一个新的
			InitFirstSession();
			Messages.Empty();
			RebuildMessageList();
			PlatformBridge->ResetSession();
			AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("NewChatStarted")));
		}
		else
		{
			// 切到最新的会话
			int32 NewIndex = SessionEntries.Num() - 1;
			ActiveSessionIndex = -1; // 临时设为 -1，OnSessionSelected 会设置
			OnSessionSelected(NewIndex);
		}
	}
	else
	{
		// 删的不是当前会话，只需修正索引
		if (Index < ActiveSessionIndex)
		{
			ActiveSessionIndex--;
		}
	}

	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("SessionDeleted")));
}

void SUEAgentDashboard::LoadSessionHistory(const FString& SessionKey)
{
	// 转义 session key 中的特殊字符（先转义反斜杠，再转义引号）
	FString EscapedKey = SessionKey;
	EscapedKey.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
	EscapedKey.ReplaceInline(TEXT("'"), TEXT("\\'"));

	// 调用 Python 函数加载历史，结果写入临时文件
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString HistoryFile = TempDir / TEXT("_session_history.json");
	IFileManager::Get().Delete(*HistoryFile, false, false, true);

	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_bridge import load_session_history\n")
		TEXT("_hist = load_session_history('%s')\n")
		TEXT("with open(r'%s', 'w', encoding='utf-8') as f:\n")
		TEXT("    f.write(_hist)\n"),
		*EscapedKey, *HistoryFile
	);
	IPythonScriptPlugin::Get()->ExecPythonCommand(*PythonCmd);

	// 读取历史文件并解析 JSON
	FString HistoryContent;
	TArray<uint8> RawBytes;
	if (!FFileHelper::LoadFileToArray(RawBytes, *HistoryFile))
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("SessionEmpty")));
		return;
	}

	FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
	HistoryContent = FString(Converter.Length(), Converter.Get());
	IFileManager::Get().Delete(*HistoryFile, false, false, true);

	// 解析 JSON 数组
	TArray<TSharedPtr<FJsonValue>> JsonArray;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(HistoryContent);
	if (!FJsonSerializer::Deserialize(Reader, JsonArray))
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("SessionEmpty")));
		return;
	}

	if (JsonArray.Num() == 0)
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("SessionEmpty")));
		return;
	}

	// 将历史消息添加到 Messages
	for (const auto& Item : JsonArray)
	{
		const TSharedPtr<FJsonObject>* MsgObj = nullptr;
		if (!Item->TryGetObject(MsgObj) || !(*MsgObj).IsValid())
		{
			continue;
		}

		FString Sender = (*MsgObj)->GetStringField(TEXT("sender"));
		FString Content = (*MsgObj)->GetStringField(TEXT("content"));
		FString TimestampStr = (*MsgObj)->GetStringField(TEXT("timestamp"));

		if (Content.IsEmpty())
		{
			continue;
		}

		// 转换 sender: "user" / "assistant"
		FChatMessage Msg;
		Msg.Sender = Sender;
		Msg.Content = Content;
		Msg.Timestamp = FDateTime::Now(); // 简化处理，不解析 ISO 时间戳

		// 尝试解析 ISO 8601 时间戳
		if (!TimestampStr.IsEmpty())
		{
			FDateTime ParsedTime;
			if (FDateTime::ParseIso8601(*TimestampStr, ParsedTime))
			{
				Msg.Timestamp = ParsedTime;
			}
		}

		Messages.Add(MoveTemp(Msg));
	}

	RebuildMessageList();

	// 显示加载结果
	FString LoadedMsg = FString::Format(
		*FUEAgentL10n::GetStr(TEXT("SessionHistoryLoaded")),
		{ FStringFormatArg(JsonArray.Num()) });
	AddMessage(TEXT("system"), LoadedMsg);
}

FText SUEAgentDashboard::GetActiveSessionLabel() const
{
	if (ActiveSessionIndex >= 0 && SessionEntries.IsValidIndex(ActiveSessionIndex))
	{
		return FText::FromString(
			FString::Printf(TEXT("\u25BC %s"), *SessionEntries[ActiveSessionIndex].Label));
	}
	return FText::FromString(TEXT("\u25BC ---"));
}

// ==================================================================
// Plan 模式 (任务 5.9)
// ==================================================================

FReply SUEAgentDashboard::OnTogglePlanModeClicked()
{
	bPlanMode = !bPlanMode;
	if (!bPlanMode)
	{
		// 关闭 Plan 模式时，如果有活跃 Plan 则取消
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
	return FReply::Handled();
}

FText SUEAgentDashboard::GetPlanModeButtonText() const
{
	return bPlanMode
		? FUEAgentL10n::Get(TEXT("PlanModeOn"))
		: FUEAgentL10n::Get(TEXT("PlanModeOff"));
}

void SUEAgentDashboard::TryParsePlan(const FString& Response)
{
	FString JsonStr;

	// 策略1: 匹配 ```json ... ``` code block
	int32 CodeStart = Response.Find(TEXT("```json"));
	if (CodeStart != INDEX_NONE)
	{
		int32 ContentStart = CodeStart + 7; // skip ```json
		int32 CodeEnd = Response.Find(TEXT("```"), ESearchCase::IgnoreCase, ESearchDir::FromStart, ContentStart);
		if (CodeEnd != INDEX_NONE)
		{
			JsonStr = Response.Mid(ContentStart, CodeEnd - ContentStart).TrimStartAndEnd();
		}
	}

	// 策略2: 匹配 {"plan" ...}
	if (JsonStr.IsEmpty())
	{
		int32 JsonStart = Response.Find(TEXT("{\"plan\""));
		if (JsonStart != INDEX_NONE)
		{
			// 从 {"plan" 开始找到最后一个 }
			int32 JsonEnd = Response.Find(TEXT("}"), ESearchCase::IgnoreCase, ESearchDir::FromEnd);
			if (JsonEnd != INDEX_NONE)
			{
				JsonStr = Response.Mid(JsonStart, JsonEnd - JsonStart + 1);
			}
		}
	}

	// 策略3: 解析失败，回退为普通回复
	if (JsonStr.IsEmpty())
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanParseFailed")));
		AddMessage(TEXT("assistant"), Response);
		return;
	}

	// 解析 JSON
	TSharedPtr<FJsonObject> RootObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
	if (!FJsonSerializer::Deserialize(Reader, RootObj) || !RootObj.IsValid())
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanParseFailed")));
		AddMessage(TEXT("assistant"), Response);
		return;
	}

	const TSharedPtr<FJsonObject>* PlanObj = nullptr;
	if (!RootObj->TryGetObjectField(TEXT("plan"), PlanObj) || !PlanObj)
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanParseFailed")));
		AddMessage(TEXT("assistant"), Response);
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* StepsArray = nullptr;
	if (!(*PlanObj)->TryGetArrayField(TEXT("steps"), StepsArray) || !StepsArray)
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanParseFailed")));
		AddMessage(TEXT("assistant"), Response);
		return;
	}

	// 构建 Plan
	FPlan NewPlan;
	NewPlan.PlanId = FGuid::NewGuid().ToString();
	NewPlan.UserRequest = LastPlanRequest;

	for (const auto& StepVal : *StepsArray)
	{
		const TSharedPtr<FJsonObject>* StepObj = nullptr;
		if (StepVal->TryGetObject(StepObj) && StepObj)
		{
			FPlanStep Step;
			Step.Index = (*StepObj)->GetIntegerField(TEXT("index"));
			Step.Title = (*StepObj)->GetStringField(TEXT("title"));
			Step.Description = (*StepObj)->GetStringField(TEXT("description"));
			NewPlan.Steps.Add(MoveTemp(Step));
		}
	}

	if (NewPlan.Steps.Num() == 0)
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanParseFailed")));
		AddMessage(TEXT("assistant"), Response);
		return;
	}

	CurrentPlan = MoveTemp(NewPlan);
	AddPlanMessage();
}

void SUEAgentDashboard::AddPlanMessage()
{
	if (!CurrentPlan.IsSet())
	{
		return;
	}

	// 移除之前的 plan 消息 (如果有) — 每次状态变化后重新渲染
	for (int32 i = Messages.Num() - 1; i >= 0; --i)
	{
		if (Messages[i].Sender == TEXT("plan"))
		{
			Messages.RemoveAt(i);
		}
	}

	FChatMessage PlanMsg;
	PlanMsg.Sender = TEXT("plan");
	PlanMsg.Content = TEXT("plan_display");
	PlanMsg.Timestamp = FDateTime::Now();
	Messages.Add(MoveTemp(PlanMsg));
	RebuildMessageList();
}

void SUEAgentDashboard::ExecuteNextPlanStep()
{
	if (!CurrentPlan.IsSet() || CurrentPlan->bIsPaused)
	{
		return;
	}

	// 找下一个 Pending 步骤
	int32 NextIndex = -1;
	for (int32 i = 0; i < CurrentPlan->Steps.Num(); i++)
	{
		if (CurrentPlan->Steps[i].Status == EPlanStepStatus::Pending)
		{
			NextIndex = i;
			break;
		}
	}

	if (NextIndex == -1)
	{
		// 所有步骤完成
		CurrentPlan->bIsExecuting = false;
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanCompleted")));
		RebuildMessageList();
		return;
	}

	CurrentPlan->CurrentStepIndex = NextIndex;
	CurrentPlan->Steps[NextIndex].Status = EPlanStepStatus::Running;

	// 更新 Plan UI 卡片
	AddPlanMessage();

	// 发送步骤给 AI
	FString StepPrompt = FString::Printf(
		TEXT("Please execute the following step (step %d of %d):\n\n"
			 "Step %d: %s\n%s"),
		NextIndex + 1,
		CurrentPlan->Steps.Num(),
		CurrentPlan->Steps[NextIndex].Index,
		*CurrentPlan->Steps[NextIndex].Title,
		*CurrentPlan->Steps[NextIndex].Description);

	SendToOpenClaw(StepPrompt);
}

FReply SUEAgentDashboard::OnExecutePlanClicked()
{
	if (!CurrentPlan.IsSet() || CurrentPlan->bIsExecuting)
	{
		return FReply::Handled();
	}

	CurrentPlan->bIsExecuting = true;
	CurrentPlan->bIsPaused = false;
	ExecuteNextPlanStep();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnPausePlanClicked()
{
	if (!CurrentPlan.IsSet() || !CurrentPlan->bIsExecuting)
	{
		return FReply::Handled();
	}

	CurrentPlan->bIsPaused = true;
	CurrentPlan->bIsExecuting = false;

	// 停止当前 AI 请求
	if (bIsWaitingForResponse)
	{
		OnStopClicked();
	}

	// 当前运行中的步骤标记回 Pending（可重试）
	if (CurrentPlan->CurrentStepIndex >= 0 &&
		CurrentPlan->CurrentStepIndex < CurrentPlan->Steps.Num() &&
		CurrentPlan->Steps[CurrentPlan->CurrentStepIndex].Status == EPlanStepStatus::Running)
	{
		CurrentPlan->Steps[CurrentPlan->CurrentStepIndex].Status = EPlanStepStatus::Pending;
	}

	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanPaused")));
	AddPlanMessage();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnResumePlanClicked()
{
	if (!CurrentPlan.IsSet() || !CurrentPlan->bIsPaused)
	{
		return FReply::Handled();
	}

	CurrentPlan->bIsPaused = false;
	CurrentPlan->bIsExecuting = true;
	ExecuteNextPlanStep();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnCancelPlanClicked()
{
	if (!CurrentPlan.IsSet())
	{
		return FReply::Handled();
	}

	if (CurrentPlan->bIsExecuting && bIsWaitingForResponse)
	{
		OnStopClicked();
	}

	CurrentPlan.Reset();
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("PlanCancelled")));
	RebuildMessageList();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnDeletePlanStep(int32 StepIndex)
{
	if (!CurrentPlan.IsSet())
	{
		return FReply::Handled();
	}

	if (StepIndex < 0 || StepIndex >= CurrentPlan->Steps.Num())
	{
		return FReply::Handled();
	}

	// 只能删除 Pending 状态的步骤
	if (CurrentPlan->Steps[StepIndex].Status != EPlanStepStatus::Pending)
	{
		return FReply::Handled();
	}

	CurrentPlan->Steps[StepIndex].Status = EPlanStepStatus::Skipped;
	AddPlanMessage();
	return FReply::Handled();
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
// Skill/MCP 管理面板
// ==================================================================

FReply SUEAgentDashboard::OnManageClicked()
{
	// 打开管理面板为独立窗口
	TSharedRef<SWindow> ManageWindow = SNew(SWindow)
		.Title(FUEAgentL10n::Get(TEXT("ManageWindowTitle")))
		.ClientSize(FVector2D(520.0f, 480.0f))
		.SupportsMinimize(false)
		.SupportsMaximize(false)
		[
			SNew(SUEAgentManagePanel)
		];

	FSlateApplication::Get().AddWindow(ManageWindow);
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
	// 重新初始化 Slash 命令（更新描述文本）
	InitSlashCommands();

	// 重建消息列表（更新 sender 标签）
	RebuildMessageList();

	// 重建快捷输入面板
	RebuildQuickInputPanel();

	// 输入框 hint text 会自动通过 lambda/binding 刷新
	// 按钮文本通过 Text_Lambda 自动刷新
}

// ==================================================================
// 文件操作确认弹窗 (阶段 5.6)
// ==================================================================

void SUEAgentDashboard::PollConfirmationRequests()
{
	FString ConfirmRequestFile = FPaths::ProjectSavedDir() / TEXT("UEAgent/_confirm_request.json");
	if (!FPaths::FileExists(ConfirmRequestFile))
	{
		return;
	}

	// 读取请求 JSON (UTF-8)
	FString RequestJson;
	TArray<uint8> RawBytes;
	if (!FFileHelper::LoadFileToArray(RawBytes, *ConfirmRequestFile))
	{
		return;
	}
	FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
	RequestJson = FString(Converter.Length(), Converter.Get());

	// 解析 JSON
	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RequestJson);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
	{
		return;
	}

	FString RiskLevel = JsonObj->GetStringField(TEXT("risk"));
	FString CodePreview = JsonObj->GetStringField(TEXT("code_preview"));
	const TArray<TSharedPtr<FJsonValue>>* OperationsArray = nullptr;
	JsonObj->TryGetArrayField(TEXT("operations"), OperationsArray);

	TArray<TSharedPtr<FJsonValue>> Operations;
	if (OperationsArray)
	{
		Operations = *OperationsArray;
	}

	// 显示确认弹窗
	ShowConfirmationDialog(RiskLevel, Operations, CodePreview);
}

void SUEAgentDashboard::ShowConfirmationDialog(
	const FString& RiskLevel,
	const TArray<TSharedPtr<FJsonValue>>& Operations,
	const FString& CodePreview)
{
	bool bIsHighRisk = (RiskLevel == TEXT("high"));

	// 构建操作列表文本
	FString OpsText;
	bool bHasBatch = false;
	for (const auto& OpVal : Operations)
	{
		const TSharedPtr<FJsonObject>* OpObj = nullptr;
		if (OpVal->TryGetObject(OpObj) && (*OpObj).IsValid())
		{
			FString OpName = (*OpObj)->GetStringField(TEXT("op"));
			FString CallName = (*OpObj)->GetStringField(TEXT("call"));
			int32 Line = (*OpObj)->GetIntegerField(TEXT("line"));
			bool bInLoop = false;
			(*OpObj)->TryGetBoolField(TEXT("in_loop"), bInLoop);

			OpsText += FString::Printf(TEXT("  • L%d: %s  (%s)"), Line, *CallName, *OpName);
			if (bInLoop)
			{
				OpsText += TEXT("  [LOOP]");
				bHasBatch = true;
			}
			OpsText += TEXT("\n");
		}
	}

	// 构建自定义弹窗 (SWindow + SVerticalBox)
	// 支持复选框 "本次会话不再提示中风险操作"
	TSharedRef<SWindow> ConfirmWindow = SNew(SWindow)
		.Title(FUEAgentL10n::Get(TEXT("ConfirmTitle")))
		.ClientSize(FVector2D(480, 360))
		.SupportsMinimize(false)
		.SupportsMaximize(false)
		.SizingRule(ESizingRule::FixedSize)
		.IsTopmostWindow(true);

	TSharedPtr<SCheckBox> SessionSilentCheckBox;
	bool bUserApproved = false;

	ConfirmWindow->SetContent(
		SNew(SVerticalBox)

		// 风险等级标题
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 12.0f, 12.0f, 4.0f)
		[
			SNew(STextBlock)
			.Text(bIsHighRisk
				? FUEAgentL10n::Get(TEXT("ConfirmRiskHigh"))
				: FUEAgentL10n::Get(TEXT("ConfirmRiskMedium")))
			.Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
			.ColorAndOpacity(bIsHighRisk
				? FSlateColor(FLinearColor(0.9f, 0.2f, 0.2f))
				: FSlateColor(FLinearColor(0.9f, 0.7f, 0.2f)))
		]

		// 批量操作警告
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 2.0f, 12.0f, 4.0f)
		[
			SNew(STextBlock)
			.Text(FUEAgentL10n::Get(TEXT("ConfirmBatchWarning")))
			.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
			.ColorAndOpacity(FSlateColor(FLinearColor(0.9f, 0.3f, 0.3f)))
			.Visibility(bHasBatch ? EVisibility::Visible : EVisibility::Collapsed)
		]

		// "将执行以下操作:"
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 4.0f, 12.0f, 2.0f)
		[
			SNew(STextBlock)
			.Text(FUEAgentL10n::Get(TEXT("ConfirmOperations")))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]

		// 操作列表
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 0.0f, 12.0f, 8.0f)
		[
			SNew(SMultiLineEditableText)
			.Text(FText::FromString(OpsText))
			.Font(FCoreStyle::GetDefaultFontStyle("Mono", 9))
			.AutoWrapText(true)
			.IsReadOnly(true)
			.AllowContextMenu(true)
		]

		// "代码预览:"
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 0.0f, 12.0f, 2.0f)
		[
			SNew(STextBlock)
			.Text(FUEAgentL10n::Get(TEXT("ConfirmCodePreview")))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]

		// 代码预览内容
		+ SVerticalBox::Slot()
		.FillHeight(1.0f)
		.Padding(12.0f, 0.0f, 12.0f, 8.0f)
		[
			SNew(SScrollBox)
			+ SScrollBox::Slot()
			[
				SNew(SMultiLineEditableText)
				.Text(FText::FromString(CodePreview.Left(500)))
				.Font(FCoreStyle::GetDefaultFontStyle("Mono", 8))
				.AutoWrapText(true)
				.IsReadOnly(true)
				.AllowContextMenu(true)
				.ColorAndOpacity(FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f)))
			]
		]

		// 复选框: 本次会话不再提示 (仅非高风险时显示)
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 0.0f, 12.0f, 8.0f)
		[
			SNew(SHorizontalBox)
			.Visibility(!bIsHighRisk ? EVisibility::Visible : EVisibility::Collapsed)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			.Padding(0.0f, 0.0f, 4.0f, 0.0f)
			[
				SAssignNew(SessionSilentCheckBox, SCheckBox)
			]
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			.VAlign(VAlign_Center)
			[
				SNew(STextBlock)
				.Text(FUEAgentL10n::Get(TEXT("ConfirmSessionSilent")))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
			]
		]

		// 按钮行
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(12.0f, 0.0f, 12.0f, 12.0f)
		.HAlign(HAlign_Right)
		[
			SNew(SHorizontalBox)

			// 允许 按钮
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(0.0f, 0.0f, 8.0f, 0.0f)
			[
				SNew(SButton)
				.Text(FUEAgentL10n::Get(TEXT("ConfirmApprove")))
				.ContentPadding(FMargin(16.0f, 6.0f))
				.OnClicked_Lambda([&bUserApproved, ConfirmWindow]() -> FReply
				{
					bUserApproved = true;
					ConfirmWindow->RequestDestroyWindow();
					return FReply::Handled();
				})
			]

			// 拒绝 按钮
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(FUEAgentL10n::Get(TEXT("ConfirmDeny")))
				.ContentPadding(FMargin(16.0f, 6.0f))
				.ButtonColorAndOpacity(FLinearColor(0.8f, 0.2f, 0.2f))
				.OnClicked_Lambda([&bUserApproved, ConfirmWindow]() -> FReply
				{
					bUserApproved = false;
					ConfirmWindow->RequestDestroyWindow();
					return FReply::Handled();
				})
			]
		]
	);

	// 模态弹窗 — 阻塞直到用户选择
	FSlateApplication::Get().AddModalWindow(ConfirmWindow, FSlateApplication::Get().GetActiveTopLevelWindow());

	// 检查复选框状态 (会话静默)
	bool bSessionSilent = false;
	if (SessionSilentCheckBox.IsValid() && SessionSilentCheckBox->IsChecked())
	{
		bSessionSilent = true;
		// 写入会话静默标记文件 (Python 侧读取)
		FString SilentFlagFile = FPaths::ProjectSavedDir() / TEXT("UEAgent/_silent_session.flag");
		FFileHelper::SaveStringToFile(TEXT("1"), *SilentFlagFile);
	}

	// 写入确认结果
	FString ResponseFile = FPaths::ProjectSavedDir() / TEXT("UEAgent/_confirm_response.json");
	FString ResponseJson;
	if (bSessionSilent)
	{
		ResponseJson = bUserApproved
			? TEXT("{\"approved\":true,\"session_silent\":true}")
			: TEXT("{\"approved\":false,\"session_silent\":false}");
	}
	else
	{
		ResponseJson = bUserApproved
			? TEXT("{\"approved\":true}")
			: TEXT("{\"approved\":false}");
	}
	FFileHelper::SaveStringToFile(ResponseJson, *ResponseFile,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

// ==================================================================
// 静默模式 (阶段 5.7)
// ==================================================================

void SUEAgentDashboard::LoadSilentModeFromConfig()
{
	FString Home = FPlatformProcess::UserHomeDir();
	FString ConfigPath = Home / TEXT(".artclaw/config.json");
	if (!FPaths::FileExists(ConfigPath))
	{
		bSilentMode = false;
		return;
	}

	FString Content;
	if (!FFileHelper::LoadFileToString(Content, *ConfigPath))
	{
		bSilentMode = false;
		return;
	}

	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Content);
	if (FJsonSerializer::Deserialize(Reader, JsonObj) && JsonObj.IsValid())
	{
		JsonObj->TryGetBoolField(TEXT("silent_mode"), bSilentMode);
	}
}

void SUEAgentDashboard::SaveSilentModeToConfig(bool bNewSilentMode)
{
	FString Home = FPlatformProcess::UserHomeDir();
	FString ConfigPath = Home / TEXT(".artclaw/config.json");

	// 读取现有配置
	TSharedPtr<FJsonObject> JsonObj;
	if (FPaths::FileExists(ConfigPath))
	{
		FString Content;
		if (FFileHelper::LoadFileToString(Content, *ConfigPath))
		{
			TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Content);
			FJsonSerializer::Deserialize(Reader, JsonObj);
		}
	}

	if (!JsonObj.IsValid())
	{
		JsonObj = MakeShared<FJsonObject>();
	}

	// 更新 silent_mode 字段
	JsonObj->SetBoolField(TEXT("silent_mode"), bNewSilentMode);

	// 确保 silent_mode_level 存在
	if (!JsonObj->HasField(TEXT("silent_mode_level")))
	{
		JsonObj->SetStringField(TEXT("silent_mode_level"), TEXT("medium"));
	}

	// 写回文件
	FString OutputStr;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputStr);
	FJsonSerializer::Serialize(JsonObj.ToSharedRef(), Writer);

	// 确保目录存在
	FString Dir = FPaths::GetPath(ConfigPath);
	IFileManager::Get().MakeDirectory(*Dir, true);

	FFileHelper::SaveStringToFile(OutputStr, *ConfigPath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

FReply SUEAgentDashboard::OnToggleSilentModeClicked()
{
	bSilentMode = !bSilentMode;
	SaveSilentModeToConfig(bSilentMode);

	// 如果关闭静默模式，同时清除会话静默标记
	if (!bSilentMode)
	{
		FString SilentFlagFile = FPaths::ProjectSavedDir() / TEXT("UEAgent/_silent_session.flag");
		IFileManager::Get().Delete(*SilentFlagFile, false, false, true);
	}

	return FReply::Handled();
}

#undef LOCTEXT_NAMESPACE