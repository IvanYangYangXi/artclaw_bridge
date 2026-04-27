// Copyright ArtClaw Project. All Rights Reserved.  主入口文件 - 包含Construct、析构函数等核心方法
// Ref: docs/specs/系统架构设计.md#SlateUI
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// Pinned Skills — static 存储 (避免修改 .h 成员布局，Live Coding 兼容)
// ==================================================================

struct FPinnedSkillsState
{
	TArray<FString> Names;
	TSharedPtr<SWrapBox> WrapBox;
	TSharedPtr<SBorder> Border;
};
static TMap<const SUEAgentDashboard*, FPinnedSkillsState> GPinnedSkillsMap;

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

	// 恢复上次会话或创建新会话
	RestoreOrInitSession();

	// 加载缓存的 Agent 列表 (Agent 切换)
	LoadCachedAgents();

	// 初始化 Slash 快捷命令
	InitSlashCommands();

	// 加载静默模式配置 (阶段 5.7)
	LoadSilentModeFromConfig();

	// 加载上下文窗口大小配置
	LoadContextWindowSize();

	// 加载保存拦截配置
	LoadSaveInterceptFromConfig();

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
			// 第一行: 连接状态 + Agent + Session + 上下文 + 设置
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(SHorizontalBox)
				// 连接状态按钮 — 最左
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(SButton)
					.Text_Lambda([this]() { return GetConnectionStatusText(); })
					.OnClicked(this, &SUEAgentDashboard::OnToggleStatusClicked)
					.ButtonColorAndOpacity_Lambda([this]() { return GetConnectionStatusColor(); })
					.ContentPadding(FMargin(4.0f, 1.0f))
				]
				// Agent 标签 — 点击打开设置面板
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([this]() -> FText
					{
						for (const auto& A : CachedAgents)
						{
							if (A.Id == CurrentAgentId)
							{
								FString Display = A.Emoji.IsEmpty() ? A.Name : FString::Printf(TEXT("%s %s"), *A.Emoji, *A.Name);
								return FText::FromString(Display);
							}
						}
						return FText::FromString(CurrentAgentId);
					})
					.OnClicked(this, &SUEAgentDashboard::OnSettingsClicked)
					.ContentPadding(FMargin(4.0f, 1.0f))
					.ButtonColorAndOpacity(FSlateColor(FLinearColor(0.18f, 0.35f, 0.55f)))
				]
				// Session 下拉
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SAssignNew(SessionMenuAnchor, SMenuAnchor)
					.ToolTipText(FUEAgentL10n::Get(TEXT("SessionMenuTip")))
					[
						SNew(SButton)
						.Text_Lambda([this]() { return GetActiveSessionLabel(); })
						.OnClicked(this, &SUEAgentDashboard::OnSessionMenuClicked)
						.ContentPadding(FMargin(4.0f, 1.0f))
					]
				]
				+ SHorizontalBox::Slot()
				.FillWidth(1.0f)
				[
					SNew(SSpacer)
				]
				// 上下文使用百分比 — 带标签
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(STextBlock)
					.Text_Lambda([this]() { return GetContextUsageText(); })
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
					.ColorAndOpacity_Lambda([this]() -> FSlateColor
					{
						if (ContextWindowSize > 0 && LastTotalTokens > 0)
						{
							float Pct = (float)LastTotalTokens / (float)ContextWindowSize;
							if (Pct >= 0.8f)
								return FSlateColor(FLinearColor(0.9f, 0.2f, 0.2f));
							if (Pct >= 0.6f)
								return FSlateColor(FLinearColor(0.9f, 0.7f, 0.2f));
						}
						return FSlateColor(FLinearColor(0.55f, 0.55f, 0.55f));
					})
				]
				// Tool Manager 按钮
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ToolManagerBtn")); })
					.OnClicked(this, &SUEAgentDashboard::OnOpenToolManagerClicked)
					.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("ToolManagerTip")); })
					.ContentPadding(FMargin(4.0f, 1.0f))
				]
				// 设置按钮
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(4.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("SettingsBtn")); })
					.OnClicked(this, &SUEAgentDashboard::OnSettingsClicked)
					.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("SettingsTip")); })
					.ContentPadding(FMargin(4.0f, 1.0f))
				]
			]
			// 第二行: 状态摘要 (连接+MCP+服务器地址)
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 2.0f, 0.0f, 0.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth()
				[
					SNew(STextBlock)
					.Text_Lambda([this]() { return GetStatusSummaryText(); })
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
					.ColorAndOpacity(FSlateColor(FLinearColor(0.55f, 0.55f, 0.55f)))
				]
			]
			// 可折叠详情: 连接/断开/诊断/日志按钮
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
	.Padding(6.0f, 1.0f)
	[
		SAssignNew(QuickInputExpandableArea, SExpandableArea)
		.HeaderPadding(FMargin(2.0f, 1.0f))
		.HeaderContent()
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QuickInputTitle")); })
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
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
				.ContentPadding(FMargin(4.0f, 1.0f))
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

	// --- 工具栏行 (常用按钮) ---
	MainVBox->AddSlot()
	.AutoHeight()
	.Padding(4.0f)
	[
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot()
		.AutoWidth()
		.VAlign(VAlign_Center)
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
		.Padding(4.0f, 0.0f, 0.0f, 0.0f)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageBtn")); })
			.OnClicked(this, &SUEAgentDashboard::OnManageClicked)
			.ToolTipText(FUEAgentL10n::Get(TEXT("ManageTip")))
			.ContentPadding(FMargin(6.0f, 2.0f))
		]
		// 附件按钮 — 靠左，紧跟管理按钮
		+ SHorizontalBox::Slot()
		.AutoWidth()
		.VAlign(VAlign_Center)
		.Padding(4.0f, 0.0f, 0.0f, 0.0f)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("AttachBtn")); })
			.OnClicked(this, &SUEAgentDashboard::OnAttachFileClicked)
			.ToolTipText(FUEAgentL10n::Get(TEXT("AttachTip")))
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
			.ContentPadding(FMargin(6.0f, 2.0f))
			.ButtonColorAndOpacity(FSlateColor(FLinearColor(0.7f, 0.3f, 0.3f)))
		]
		// 恢复接收按钮 — 非等待状态时显示（与停止按钮互斥）
		+ SHorizontalBox::Slot()
		.AutoWidth()
		.VAlign(VAlign_Center)
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ResumeBtn")); })
			.OnClicked(this, &SUEAgentDashboard::OnResumeClicked)
			.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("ResumeTip")); })
			.IsEnabled_Lambda([this]() { return !bIsWaitingForResponse; })
			.ContentPadding(FMargin(6.0f, 2.0f))
			.ButtonColorAndOpacity(FSlateColor(FLinearColor(0.3f, 0.6f, 0.3f)))
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

	// --- 附件预览栏 (默认隐藏，有附件时显示) ---
	MainVBox->AddSlot()
	.AutoHeight()
	.Padding(4.0f, 0.0f)
	[
		SAssignNew(AttachmentPreviewBorder, SBorder)
		.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.GroupBorder"))
		.Padding(FMargin(4.0f, 2.0f))
		.Visibility(EVisibility::Collapsed)
		[
			SNew(SScrollBox)
			.Orientation(Orient_Horizontal)
			+ SScrollBox::Slot()
			[
				SAssignNew(AttachmentPreviewBox, SHorizontalBox)
			]
		]
	];

	// --- 钉选 Skill 标签栏 (输入框上方，有钉选时显示) ---
	LoadPinnedSkills();
	auto& PinState = GPinnedSkillsMap.FindOrAdd(this);
	MainVBox->AddSlot()
	.AutoHeight()
	.Padding(4.0f, 2.0f, 4.0f, 0.0f)
	[
		SAssignNew(PinState.Border, SBorder)
		.BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
		.Padding(FMargin(0.0f))
		.Visibility_Lambda([this]() {
			auto* S = GPinnedSkillsMap.Find(this);
			return (S && S->Names.Num() > 0) ? EVisibility::Visible : EVisibility::Collapsed;
		})
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			.Padding(0.0f, 0.0f, 4.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(TEXT("\u2605")))  // ★
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.95f, 0.75f, 0.1f)))
			]
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			[
				SAssignNew(PinState.WrapBox, SWrapBox)
				.UseAllottedSize(true)
			]
		]
	];
	RebuildPinnedSkillsUI();

	// --- 输入区域 ---
	// 先创建 InputTextBox
	InputTextBox = SNew(SMultiLineEditableTextBox)
		.AutoWrapText(true)
		.HintText_Lambda([this]() { return GetSendHintText(); })
		.OnTextChanged(this, &SUEAgentDashboard::OnInputTextChanged)
		.OnTextCommitted(this, &SUEAgentDashboard::OnInputTextCommitted)
		.OnKeyDownHandler(this, &SUEAgentDashboard::OnInputKeyDown);

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

	// 加载快捷输入配置并构建 UI（必须在 QuickInputWrapBox 赋值之后）
	LoadQuickInputs();
	RebuildQuickInputPanel();

	// 欢迎消息
	AddMessage(TEXT("assistant"), FUEAgentL10n::GetStr(TEXT("WelcomeMsg")));

	// 打开面板时自动连接 OpenClaw Bridge
	ConnectOpenClawBridge();

	// Bridge + MCP 状态持续轮询 — 纯 Python 查询，不依赖中间文件
	{
		auto Self = SharedThis(this);
		BridgeStatusPollHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateLambda([Self](float) -> bool
			{
				// 引擎关闭或 Widget 正在析构时跳过 — 防止访问已销毁的 Python/Slate 子系统
				if (Self->bIsBeingDestroyed || IsEngineExitRequested() || !FSlateApplication::IsInitialized())
				{
					return false; // 停止轮询
				}

				// MCP 状态: 直接查询 Python MCP Server 运行状态（纯内存查询）
				{
					FString McpCheck = FUEAgentManageUtils::RunPythonAndCapture(TEXT(
						"try:\n"
						"    from ue_mcp_server import get_mcp_server\n"
						"    s = get_mcp_server()\n"
						"    _result = {'mcp_ready': bool(s and s.is_running)}\n"
						"except:\n"
						"    _result = {'mcp_ready': False}\n"
					));
					TSharedPtr<FJsonObject> McpObj;
					TSharedRef<TJsonReader<>> McpReader = TJsonReaderFactory<>::Create(McpCheck);
					if (FJsonSerializer::Deserialize(McpReader, McpObj) && McpObj.IsValid())
					{
						bool bMcpReady = false;
						McpObj->TryGetBoolField(TEXT("mcp_ready"), bMcpReady);
						Self->bCachedMcpReady = bMcpReady;
					}
				}

				// Gateway 连接状态: 轻量 socket 探测（不经过 openclaw_chat，避免日志刷屏）
				// 端口通过 bridge_config.get_gateway_config() 读取（配置驱动，跨平台通用）
				// 读取链路: ~/.artclaw/config.json platform.gateway_url > 平台配置文件 > _PLATFORM_DEFAULTS
				{
					FString GwCheck = FUEAgentManageUtils::RunPythonAndCapture(TEXT(
						"import socket\n"
						"from bridge_config import get_gateway_config\n"
						"_gw = get_gateway_config()\n"
						"_port = _gw.get('port', 0)\n"
						"if not _port:\n"
						"    _url = _gw.get('url', '')\n"
						"    if ':' in _url.rsplit('/', 1)[-1]:\n"
						"        try: _port = int(_url.rsplit(':', 1)[-1])\n"
						"        except: _port = 18789\n"
						"    else: _port = 18789\n"
						"_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
						"_s.settimeout(0.3)\n"
						"try:\n"
						"    _s.connect(('127.0.0.1', _port))\n"
						"    _result = {'connected': True}\n"
						"except:\n"
						"    _result = {'connected': False}\n"
						"finally:\n"
						"    _s.close()\n"
					));
					TSharedPtr<FJsonObject> GwObj;
					TSharedRef<TJsonReader<>> GwReader = TJsonReaderFactory<>::Create(GwCheck);
					if (FJsonSerializer::Deserialize(GwReader, GwObj) && GwObj.IsValid())
					{
						bool bConnected = false;
						GwObj->TryGetBoolField(TEXT("connected"), bConnected);

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
					}
				}

				// Session token 用量: 读取 _session_usage.json（Python chat 完成后写入）
				// Python 子线程无法 import unreal，会写到 ~/.artclaw/ 而非 ProjectSavedDir
				{
					FString UsagePath;
					FString Path1 = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge") / TEXT("_session_usage.json");
					FString Path2 = FPaths::Combine(FPlatformProcess::UserHomeDir(), TEXT(".artclaw"), TEXT("_session_usage.json"));
					if (FPaths::FileExists(Path1))
					{
						UsagePath = Path1;
					}
					else if (FPaths::FileExists(Path2))
					{
						UsagePath = Path2;
					}

					if (!UsagePath.IsEmpty())
					{
						FString UsageContent;
						if (FFileHelper::LoadFileToString(UsageContent, *UsagePath))
						{
							TSharedPtr<FJsonObject> UsageObj;
							TSharedRef<TJsonReader<>> UsageReader = TJsonReaderFactory<>::Create(UsageContent);
							if (FJsonSerializer::Deserialize(UsageReader, UsageObj) && UsageObj.IsValid())
							{
								// 校验 sessionKey 匹配当前会话（避免显示旧会话的 usage）
								FString FileSessionKey;
								UsageObj->TryGetStringField(TEXT("sessionKey"), FileSessionKey);
								FString CurrentKey = Self->PlatformBridge->GetSessionKey();
								if (!FileSessionKey.IsEmpty() && !CurrentKey.IsEmpty() && FileSessionKey != CurrentKey)
								{
									// sessionKey 不匹配，跳过（等待 Python 查询完成后写入正确的值）
								}
								else
								{
									// totalTokens = 最后一次 API 调用的 input token（当前上下文大小）
									// inputTokens = 累积总量，不可直接用于上下文百分比
									int32 Tokens = 0;
									UsageObj->TryGetNumberField(TEXT("totalTokens"), Tokens);
									if (Tokens > 0)
									{
										Self->LastTotalTokens = Tokens;
									}
								}
							}
						}
					}
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
				if (Self->bIsBeingDestroyed || IsEngineExitRequested())
				{
					return false;
				}
				Self->PollConfirmationRequests();
				return true; // 持续轮询
			}),
			0.2f // 每 0.2 秒检查一次 (Python 侧 sleep(0.1) 精度)
		);
	}
}

SUEAgentDashboard::~SUEAgentDashboard()
{
	// 设置析构标记 — ticker lambda 检查此标记避免在析构过程中执行
	bIsBeingDestroyed = true;

	// 【最先】停止所有 Ticker 轮询 — 防止析构过程中 lambda 仍触发
	// 特别是 BridgeStatusPoll 会调 RunPythonAndCapture + SetConnectionStatus，
	// 后者 Broadcast 会触发 HandleConnectionStatusChanged → AddMessage → RebuildMessageList，
	// 如果 Slate/Python 子系统已销毁则崩溃
	if (BridgeStatusPollHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(BridgeStatusPollHandle);
		BridgeStatusPollHandle.Reset();
	}
	if (PollTimerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(PollTimerHandle);
		PollTimerHandle.Reset();
	}
	if (ConfirmPollHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(ConfirmPollHandle);
		ConfirmPollHandle.Reset();
	}
	bIsWaitingForResponse = false;

	// 断开委托 — 防止 Subsystem 在我们析构后仍回调
	if (CachedSubsystem.IsValid())
	{
		CachedSubsystem->OnConnectionStatusChangedNative.RemoveAll(this);
	}
	CachedSubsystem.Reset();

	// 保存当前会话状态 — 仅在 Slate/路径子系统仍然可用时执行
	// FPaths::ProjectSavedDir() 依赖 LazySingleton，引擎关闭序列中已失效
	if (FSlateApplication::IsInitialized())
	{
		SaveLastSession();
	}

	// 主动清空消息列表 Widget — 必须在 Slate 还活着时执行，否则 STextBlock /
	// SButton 子 Widget 在析构链中会访问已关闭的 Slate 字体/渲染服务导致崩溃
	if (MessageScrollBox.IsValid() && FSlateApplication::IsInitialized())
	{
		MessageScrollBox->ClearChildren();
	}
	MessageScrollBox.Reset();

	// 主动释放所有 Slate Widget 共享指针 — 避免自然析构时 Slate 子系统已关闭导致崩溃
	StatusDetailWidget.Reset();
	InputTextBox.Reset();
	SlashMenuAnchor.Reset();
	SlashListView.Reset();
	SendModeCheckBox.Reset();
	QuickInputWrapBox.Reset();
	QuickInputExpandableArea.Reset();
	QuickInputEditNameBox.Reset();
	QuickInputEditContentBox.Reset();
	AttachmentPreviewBox.Reset();
	AttachmentPreviewBorder.Reset();
	GPinnedSkillsMap.Remove(this);
	SessionMenuAnchor.Reset();
	PlatformListBox.Reset();
	AgentListBox.Reset();

	// 关闭管理面板窗口
	if (ManageWindow.IsValid() && FSlateApplication::IsInitialized())
	{
		ManageWindow->RequestDestroyWindow();
		ManageWindow.Reset();
		ManagePanelWidget.Reset();
	}

	// 释放设置面板窗口
	if (SettingsWindow.IsValid() && FSlateApplication::IsInitialized())
	{
		SettingsWindow->RequestDestroyWindow();
		SettingsWindow.Reset();
	}

	// 释放快捷输入编辑窗口
	if (QuickInputEditWindow.IsValid() && FSlateApplication::IsInitialized())
	{
		QuickInputEditWindow->RequestDestroyWindow();
		QuickInputEditWindow.Reset();
	}

	// 释放 PlatformBridge — 可能持有 Python 资源
	PlatformBridge.Reset();
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

	// 连接成功且 Agent 列表为空时自动刷新一次
	if (bNewStatus && CachedAgents.Num() == 0)
	{
		OnRefreshAgentsClicked();
	}
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
	StreamingTextWidget.Reset();
	StreamingMessageIndex = INDEX_NONE;

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

// ==================================================================
// Pinned Skills — 加载/刷新/交互
// ==================================================================

void SUEAgentDashboard::LoadPinnedSkills()
{
	auto& PinState = GPinnedSkillsMap.FindOrAdd(this);
	PinState.Names.Empty();

	// 方式1: 直接读文件（不依赖 Python，Construct 时更可靠）
	FString ConfigPath = FPaths::Combine(
		FPlatformProcess::UserDir(), TEXT(".artclaw"), TEXT("config.json"));
	// UserDir() 返回 C:/Users/xxx/，但 .artclaw 在 HOME 目录
	// 改用环境变量
	FString HomePath = FPlatformMisc::GetEnvironmentVariable(TEXT("USERPROFILE"));
	if (HomePath.IsEmpty())
	{
		HomePath = FPlatformMisc::GetEnvironmentVariable(TEXT("HOME"));
	}
	ConfigPath = FPaths::Combine(HomePath, TEXT(".artclaw"), TEXT("config.json"));

	UE_LOG(LogTemp, Log, TEXT("[PinnedSkills] Loading config from: %s"), *ConfigPath);

	FString FileContent;
	if (!FFileHelper::LoadFileToString(FileContent, *ConfigPath))
	{
		UE_LOG(LogTemp, Warning, TEXT("[PinnedSkills] Failed to read config file"));
		return;
	}

	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(FileContent);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("[PinnedSkills] Failed to parse config JSON"));
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* Arr;
	if (JsonObj->TryGetArrayField(TEXT("pinned_skills"), Arr))
	{
		for (const auto& Val : *Arr)
		{
			FString Name = Val->AsString();
			if (!Name.IsEmpty())
			{
				PinState.Names.Add(Name);
			}
		}
	}

	UE_LOG(LogTemp, Log, TEXT("[PinnedSkills] Loaded %d pinned skills"), PinState.Names.Num());
}

void SUEAgentDashboard::RebuildPinnedSkillsUI()
{
	auto* PinState = GPinnedSkillsMap.Find(this);
	if (!PinState || !PinState->WrapBox.IsValid()) return;

	PinState->WrapBox->ClearChildren();

	for (const FString& SkillName : PinState->Names)
	{
		// 显示名: 去掉常见前缀 ue57- / artclaw- 让标签更紧凑
		FString DisplayName = SkillName;
		if (DisplayName.StartsWith(TEXT("ue57-"))) DisplayName = DisplayName.Mid(5);
		else if (DisplayName.StartsWith(TEXT("artclaw-"))) DisplayName = DisplayName.Mid(8);

		PinState->WrapBox->AddSlot()
		.Padding(FMargin(2.0f, 1.0f))
		[
			SNew(SBorder)
			.BorderBackgroundColor(FSlateColor(FLinearColor(0.2f, 0.35f, 0.55f, 0.6f)))
			.Padding(FMargin(0.0f))
			[
				SNew(SHorizontalBox)
				// Skill 名称按钮 — 点击插入 @mention
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(SButton)
					.Text(FText::FromString(DisplayName))
					.OnClicked(FOnClicked::CreateSP(this, &SUEAgentDashboard::OnPinnedSkillClicked, SkillName))
					.ButtonStyle(FCoreStyle::Get(), "NoBorder")
					.ContentPadding(FMargin(4.0f, 1.0f, 2.0f, 1.0f))
					.ForegroundColor(FSlateColor(FLinearColor(0.75f, 0.85f, 1.0f)))
					.ToolTipText(FText::Format(
						FUEAgentL10n::Get(TEXT("PinnedSkillClickTip")),
						FText::FromString(SkillName)))
				]
				// × 按钮 — 取消钉选
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(SButton)
					.Text(FText::FromString(TEXT("\u00D7")))  // ×
					.OnClicked(FOnClicked::CreateSP(this, &SUEAgentDashboard::OnUnpinSkillFromChat, SkillName))
					.ButtonStyle(FCoreStyle::Get(), "NoBorder")
					.ContentPadding(FMargin(2.0f, 1.0f, 3.0f, 1.0f))
					.ForegroundColor(FSlateColor(FLinearColor(0.55f, 0.55f, 0.55f)))
					.ToolTipText(FText::Format(
						FUEAgentL10n::Get(TEXT("PinnedSkillUnpinTip")),
						FText::FromString(SkillName)))
				]
			]
		];
	}
}

FReply SUEAgentDashboard::OnPinnedSkillClicked(FString SkillName)
{
	if (!InputTextBox.IsValid()) return FReply::Handled();

	// 将 @skill_name 前缀追加到输入框当前文本
	FString Current = InputTextBox->GetText().ToString();
	FString Mention = FString::Printf(TEXT("@%s "), *SkillName);

	// 如果已经包含这个 mention 就不重复插入
	if (!Current.Contains(Mention.TrimEnd()))
	{
		FString NewText = Mention + Current;
		InputTextBox->SetText(FText::FromString(NewText));
	}

	// 聚焦输入框
	FSlateApplication::Get().SetKeyboardFocus(InputTextBox);

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnUnpinSkillFromChat(FString SkillName)
{
	// 直接用 C++ 读写 config.json（不依赖 Python）
	FString HomePath = FPlatformMisc::GetEnvironmentVariable(TEXT("USERPROFILE"));
	if (HomePath.IsEmpty()) HomePath = FPlatformMisc::GetEnvironmentVariable(TEXT("HOME"));
	FString ConfigPath = FPaths::Combine(HomePath, TEXT(".artclaw"), TEXT("config.json"));

	FString FileContent;
	TSharedPtr<FJsonObject> JsonObj;

	if (FFileHelper::LoadFileToString(FileContent, *ConfigPath))
	{
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(FileContent);
		FJsonSerializer::Deserialize(Reader, JsonObj);
	}
	if (!JsonObj.IsValid())
	{
		JsonObj = MakeShared<FJsonObject>();
	}

	// 移除指定 skill
	TArray<TSharedPtr<FJsonValue>> NewPinned;
	const TArray<TSharedPtr<FJsonValue>>* OldArr;
	if (JsonObj->TryGetArrayField(TEXT("pinned_skills"), OldArr))
	{
		for (const auto& Val : *OldArr)
		{
			if (Val->AsString() != SkillName)
			{
				NewPinned.Add(Val);
			}
		}
	}
	JsonObj->SetArrayField(TEXT("pinned_skills"), NewPinned);

	// 写回
	FString OutputStr;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputStr);
	FJsonSerializer::Serialize(JsonObj.ToSharedRef(), Writer);
	FFileHelper::SaveStringToFile(OutputStr, *ConfigPath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);

	// 刷新本地数据和 UI
	LoadPinnedSkills();
	RebuildPinnedSkillsUI();

	return FReply::Handled();
}
