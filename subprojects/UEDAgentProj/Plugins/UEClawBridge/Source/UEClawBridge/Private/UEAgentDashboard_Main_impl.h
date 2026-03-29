// Copyright ArtClaw Project. All Rights Reserved.  主入口文件 - 包含Construct、析构函数等核心方法
// Ref: docs/specs/系统架构设计.md#SlateUI
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

	// 加载快捷输入配置并构建 UI
	LoadQuickInputs();
	RebuildQuickInputPanel();

	// 加载静默模式配置 (阶段 5.7)
	LoadSilentModeFromConfig();

	// ==================================================================
	// 构建 UI 布局
	// ==================================================================
	TSharedPtr<SVerticalBox> MainVBox = SNew(SVerticalBox);

	// --- 状态栏 ---
	MainVBox->AddSlot().AutoHeight()
	[
		SNew(SBorder)
		.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.GroupBorder"))
		.Padding(FMargin(6.0f, 4.0f))
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(SButton)
					.Text_Lambda([this]() { return GetConnectionStatusText(); })
					.OnClicked(this, &SUEAgentDashboard::OnToggleStatusClicked)
					.ButtonColorAndOpacity_Lambda([this]() { return GetConnectionStatusColor(); })
					.ContentPadding(FMargin(6.0f, 2.0f))
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(8.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(STextBlock)
					.Text_Lambda([this]() { return GetVersionText(); })
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
					.ColorAndOpacity(FSlateColor(FLinearColor(0.45f, 0.45f, 0.45f)))
				]
				+ SHorizontalBox::Slot()
				.FillWidth(1.0f)
				[
					SNew(SSpacer)
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(SButton)
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("SettingsBtn")); })
					.OnClicked(this, &SUEAgentDashboard::OnSettingsClicked)
					.ToolTipText(FUEAgentL10n::Get(TEXT("SettingsTip")))
					.ContentPadding(FMargin(6.0f, 2.0f))
				]
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 2.0f, 0.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text_Lambda([this]() { return GetStatusSummaryText(); })
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.55f, 0.55f, 0.55f)))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SAssignNew(StatusDetailWidget, SVerticalBox)
				.Visibility(bStatusExpanded ? EVisibility::Visible : EVisibility::Collapsed)
				+ SVerticalBox::Slot()
				.AutoHeight()
				.Padding(0.0f, 4.0f, 0.0f, 0.0f)
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
					[
						SNew(SButton)
						.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ConnectBtn")); })
						.OnClicked(this, &SUEAgentDashboard::OnConnectClicked)
						.ToolTipText(FUEAgentL10n::Get(TEXT("ConnectTip")))
						.ContentPadding(FMargin(6.0f, 2.0f))
					]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.0f, 0.0f)
					[
						SNew(SButton)
						.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("DisconnectBtn")); })
						.OnClicked(this, &SUEAgentDashboard::OnDisconnectClicked)
						.ToolTipText(FUEAgentL10n::Get(TEXT("DisconnectTip")))
						.ContentPadding(FMargin(6.0f, 2.0f))
					]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.0f, 0.0f)
					[
						SNew(SButton)
						.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("DiagnoseBtn")); })
						.OnClicked(this, &SUEAgentDashboard::OnDiagnoseClicked)
						.ToolTipText(FUEAgentL10n::Get(TEXT("DiagnoseTip")))
						.ContentPadding(FMargin(6.0f, 2.0f))
					]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.0f, 0.0f)
					[
						SNew(SButton)
						.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ViewLogsBtn")); })
						.OnClicked(this, &SUEAgentDashboard::OnViewLogsClicked)
						.ToolTipText(FUEAgentL10n::Get(TEXT("ViewLogsTip")))
						.ContentPadding(FMargin(6.0f, 2.0f))
					]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4.0f, 0.0f)
					[
						SNew(SCheckBox)
						.IsChecked_Lambda([this]() -> ECheckBoxState {
							return bEnterToSend ? ECheckBoxState::Checked : ECheckBoxState::Unchecked;
						})
						.OnCheckStateChanged(this, &SUEAgentDashboard::OnSendModeChanged)
						.ToolTipText(FUEAgentL10n::Get(TEXT("EnterToSendLabel")))
						[
							SNew(STextBlock)
							.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("EnterToSendLabel")); })
							.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
						]
					]
				]
			]
		]
	];

	// --- 分隔线 ---
	MainVBox->AddSlot().AutoHeight()
	[
		SNew(SSeparator)
	];

	// --- 消息列表 ---
	MainVBox->AddSlot()
	.FillHeight(1.0f)
	[
		SAssignNew(MessageScrollBox, SScrollBox)
		+ SScrollBox::Slot()
		[
			SNew(SVerticalBox)
		]
	];

	// --- 分隔线 ---
	MainVBox->AddSlot().AutoHeight()
	[
		SNew(SSeparator)
	];

	// --- 快捷输入栏（可折叠，位于消息列表下方、工具栏上方）---
	MainVBox->AddSlot()
	.AutoHeight()
	.Padding(6.0f, 4.0f)
	[
		SAssignNew(QuickInputExpandableArea, SExpandableArea)
		.HeaderContent()
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QuickInputTitle")); })
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f)))
			]
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			[
				SNew(SSpacer)
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("AddQuickInputBtn")); })
				.OnClicked(this, &SUEAgentDashboard::OnAddQuickInputClicked)
				.ToolTipText(FUEAgentL10n::Get(TEXT("AddQuickInputTip")))
				.ContentPadding(FMargin(6.0f, 2.0f))
			]
		]
		.BodyContent()
		[
			SNew(SBorder)
			.BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
			.Padding(FMargin(0.0f, 4.0f, 0.0f, 0.0f))
			[
				SAssignNew(QuickInputWrapBox, SWrapBox)
			]
		]
		.InitiallyCollapsed(true)
	];

	// --- 分隔线 ---
	{
		MainVBox->AddSlot().AutoHeight()
		[
			SNew(SSeparator)
		];
	}

	// --- 工具栏行 ---
	MainVBox->AddSlot()
	.AutoHeight()
	.Padding(4.0f)
	[
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot()
		.AutoWidth()
		.VAlign(VAlign_Center)
		[
			SAssignNew(SessionMenuAnchor, SMenuAnchor)
			.ToolTipText(FUEAgentL10n::Get(TEXT("SessionMenuTip")))
			[
				SNew(SButton)
				.Text_Lambda([this]() { return GetActiveSessionLabel(); })
				.OnClicked(this, &SUEAgentDashboard::OnSessionMenuClicked)
				.ContentPadding(FMargin(6.0f, 2.0f))
			]
		]
		+ SHorizontalBox::Slot()
		.AutoWidth()
		.VAlign(VAlign_Center)
		.Padding(4.0f, 0.0f)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("NewChatBtn")); })
			.OnClicked(this, &SUEAgentDashboard::OnNewChatClicked)
			.ToolTipText(FUEAgentL10n::Get(TEXT("NewChatTip")))
			.ContentPadding(FMargin(6.0f, 2.0f))
		]
		+ SHorizontalBox::Slot()
		.AutoWidth()
		.VAlign(VAlign_Center)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageBtn")); })
			.OnClicked(this, &SUEAgentDashboard::OnManageClicked)
			.ToolTipText(FUEAgentL10n::Get(TEXT("ManageTip")))
			.ContentPadding(FMargin(6.0f, 2.0f))
		]
		+ SHorizontalBox::Slot()
		.FillWidth(1.0f)
		[
			SNew(SSpacer)
		]
		+ SHorizontalBox::Slot()
		.AutoWidth()
		.VAlign(VAlign_Center)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("StopBtn")); })
			.OnClicked(this, &SUEAgentDashboard::OnStopClicked)
			.ToolTipText(FUEAgentL10n::Get(TEXT("StopTip")))
			.IsEnabled_Lambda([this]() { return bIsWaitingForResponse; })
			.ContentPadding(FMargin(6.0f, 2.0f))
			.ButtonColorAndOpacity(FSlateColor(FLinearColor(0.7f, 0.3f, 0.3f)))
		]
		+ SHorizontalBox::Slot()
		.AutoWidth()
		.VAlign(VAlign_Center)
		[
			SNew(SButton)
			.Text_Lambda([this]() {
				return bIsWaitingForResponse
					? FUEAgentL10n::Get(TEXT("SendBtnWaiting"))
					: FUEAgentL10n::Get(TEXT("SendBtn"));
			})
			.OnClicked(this, &SUEAgentDashboard::OnSendClicked)
			.ToolTipText(FUEAgentL10n::Get(TEXT("SendTip")))
			.ContentPadding(FMargin(10.0f, 2.0f))
			.ButtonColorAndOpacity_Lambda([this]() -> FSlateColor {
				return bIsWaitingForResponse
					? FSlateColor(FLinearColor(0.4f, 0.4f, 0.2f))
					: FSlateColor(FLinearColor(0.15f, 0.45f, 0.75f));
			})
		]
	];

	// --- 输入区域 ---
	// 先创建 InputTextBox
	InputTextBox = SNew(SMultiLineEditableTextBox)
		.AutoWrapText(true)
		.HintText_Lambda([this]() { return GetSendHintText(); })
		.OnTextChanged(this, &SUEAgentDashboard::OnInputTextChanged)
		.OnTextCommitted(this, &SUEAgentDashboard::OnInputTextCommitted);

	// 再创建 SlashMenuAnchor，包裹 InputTextBox
	SlashMenuAnchor = SNew(SMenuAnchor)
		.Placement(MenuPlacement_BelowAnchor)
		[
			SNew(SBox)
			.MinDesiredHeight(32.0f)
			.MaxDesiredHeight(120.0f)
			[
				InputTextBox.ToSharedRef()
			]
		];

	// 添加到主布局
	MainVBox->AddSlot()
	.AutoHeight()
	.Padding(4.0f, 0.0f, 4.0f, 4.0f)
	[
		SlashMenuAnchor.ToSharedRef()
	];

	// --- 手动设置 Slash 命令菜单内容 ---
	if (SlashMenuAnchor.IsValid())
	{
		SlashListView = SNew(SListView<FSlashCommandPtr>)
			.ListItemsSource(&FilteredSlashCommands)
			.OnGenerateRow(this, &SUEAgentDashboard::GenerateSlashCommandRow)
			.OnSelectionChanged(this, &SUEAgentDashboard::OnSlashCommandSelected)
			.SelectionMode(ESelectionMode::Single);

		SlashMenuAnchor->SetMenuContent(
			SNew(SBorder)
			.BorderImage(FCoreStyle::Get().GetBrush("Menu.Background"))
			.Padding(FMargin(4.0f))
			[
				SlashListView.ToSharedRef()
			]
		);
	}

	// 手动设置会话菜单内容
	if (SessionMenuAnchor.IsValid())
	{
		SessionMenuAnchor->SetMenuContent(BuildSessionMenuContent());
	}

	ChildSlot
	[
		MainVBox.ToSharedRef()
	];

	// 欢迎消息
	AddMessage(TEXT("assistant"), FUEAgentL10n::GetStr(TEXT("WelcomeMsg")));

	// 打开面板时自动连接 OpenClaw Bridge
	ConnectOpenClawBridge();

	// Bridge 连接状态持续轮询 — 读取 Python 侧写入的 _bridge_status.json
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

	// 关闭管理面板窗口，防止 Dashboard 销毁后窗口仍引用无效 Widget
	if (ManageWindow.IsValid())
	{
		ManageWindow->RequestDestroyWindow();
		ManageWindow.Reset();
		ManagePanelWidget.Reset();
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
// OpenClaw Gateway 通信 - 响应处理
// ==================================================================

void SUEAgentDashboard::HandlePythonResponse(const FString& Response)
{
	// 1) 移除 "Thinking..." 或流式消息
	for (int32 i = Messages.Num() - 1; i >= 0; --i)
	{
		const FString& S = Messages[i].Sender;
		if (Messages[i].Content == FUEAgentL10n::GetStr(TEXT("Thinking")) && S == TEXT("system"))
		{
			Messages.RemoveAt(i);
			break;
		}
		else if (S == TEXT("thinking") || S == TEXT("streaming"))
		{
			Messages.RemoveAt(i);
		}
	}

	// 2) 重置等待状态
	bIsWaitingForResponse = false;
	bHasStreamingMessage = false;
	StreamLinesRead = 0;

	// 3) --- Plan 模式: 区分 Plan 生成回复 vs Plan 步骤执行回复 ---
	if (bPlanMode)
	{
		// 如果还没有 Plan，尝试解析 Plan
		if (!CurrentPlan.IsSet())
		{
			TryParsePlan(Response);
			if (CurrentPlan.IsSet())
			{
				// Plan 解析成功，添加 Plan 消息卡片
				return;
			}
		}

		// 如果有正在执行的 Plan，更新步骤状态
		if (CurrentPlan.IsSet() && CurrentPlan->bIsExecuting && CurrentPlan->CurrentStepIndex >= 0)
		{
			CurrentPlan->Steps[CurrentPlan->CurrentStepIndex].Status = EPlanStepStatus::Done;
			CurrentPlan->Steps[CurrentPlan->CurrentStepIndex].Result = Response.Left(200);
			CurrentPlan->bIsExecuting = false;

			// 继续执行下一步
			ExecuteNextPlanStep();
			return;
		}
	}

	// 4) 普通 AI 回复
	AddMessage(TEXT("assistant"), Response);
}
