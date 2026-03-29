// Copyright ArtClaw Project. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "Widgets/Views/SListView.h"
#include "Containers/Ticker.h"

class IAgentPlatformBridge;
class UUEAgentSubsystem;
class SScrollBox;
#include "Widgets/Input/SMultiLineEditableTextBox.h"
class SMenuAnchor;
class SCheckBox;
class SExpandableArea;
class SEditableTextBox;
class SWrapBox;

// ==================================================================
// Plan 模式数据模型 (任务 5.9)
// ==================================================================

/** Plan 步骤状态 */
enum class EPlanStepStatus : uint8
{
	Pending,    // 待执行
	Running,    // 执行中
	Done,       // 已完成
	Failed,     // 失败
	Skipped,    // 已跳过/已删除
};

/** 单个步骤 */
struct FPlanStep
{
	int32 Index = 0;
	FString Title;
	FString Description;
	EPlanStepStatus Status = EPlanStepStatus::Pending;
	FString Result;          // 执行结果摘要
};

/** 完整 Plan */
struct FPlan
{
	FString PlanId;          // UUID
	FString UserRequest;     // 原始用户请求
	TArray<FPlanStep> Steps;
	bool bIsExecuting = false;
	bool bIsPaused = false;
	int32 CurrentStepIndex = -1;
};

/**
 * SUEAgentDashboard
 * 一体化 Agent 面板：顶部状态信息 + 底部聊天区域 (阶段 2.1 合并优化)
 *
 * 功能:
 *   - 状态栏: 版本号、连接状态、服务器地址（可折叠）
 *   - 聊天区: 消息历史滚动列表
 *   - 输入区: 多行文本输入，支持 "/" 快捷命令提示
 *
 * 宪法约束:
 *   - C++ 负责 UI / 生命周期 / 主线程调度 (系统架构设计 §2.3)
 *   - Slate 原生 UI (概要设计 §1.1、核心机制 §4)
 *   - 与 UUEAgentSubsystem 状态实时同步 (0.3 里程碑)
 */
class SUEAgentDashboard : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SUEAgentDashboard) {}
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	virtual ~SUEAgentDashboard() override;

private:
	// --- 消息模型 ---
	struct FChatMessage
	{
		FString Sender;   // "user", "assistant", "system", "tool_call", "tool_result"
		FString Content;
		FDateTime Timestamp;
		bool bIsCode = false;

		// 工具调用信息 (Sender == "tool_call" 或 "tool_result" 时使用)
		FString ToolName;         // 工具名称
		FString ToolId;           // 工具调用 ID
		FString ToolArguments;    // 参数 JSON 字符串
		FString ToolResult;       // 结果内容
		bool bToolError = false;  // 是否报错
		bool bToolCollapsed = true; // 默认折叠
	};

	// --- Slash 命令模型 ---
	struct FSlashCommand
	{
		FString Command;      // 例如 "/select"
		FString Description;  // 例如 "List selected actors"
		bool bIsLocal = false; // true = 本地执行, false = 发送给 AI
	};
	typedef TSharedPtr<FSlashCommand> FSlashCommandPtr;

	// --- 委托回调 ---
	void HandleConnectionStatusChanged(bool bNewStatus);

	// --- 状态栏辅助方法 ---
	FText GetConnectionStatusText() const;
	FSlateColor GetConnectionStatusColor() const;
	FText GetVersionText() const;
	FText GetServerAddressText() const;
	FText GetStatsText() const;
	FText GetStatusSummaryText() const;

	// --- 按钮回调 ---
	FReply OnToggleStatusClicked();
	FReply OnConnectClicked();
	FReply OnDisconnectClicked();
	FReply OnDiagnoseClicked();
	FReply OnViewLogsClicked();
	FReply OnSendClicked();
	FReply OnNewChatClicked();
	FReply OnStopClicked();

	// --- 聊天输入回调 ---
	void OnInputTextChanged(const FText& NewText);
	void OnInputTextCommitted(const FText& NewText, ETextCommit::Type CommitType);
	FReply OnInputKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent);

	// --- 发送模式切换 ---
	void OnSendModeChanged(ECheckBoxState NewState);
	bool ShouldSendOnEnter() const;
	FText GetSendHintText() const;

	// --- Slash 命令菜单 ---
	void InitSlashCommands();
	void UpdateSlashSuggestions(const FString& InputText);
	TSharedRef<ITableRow> GenerateSlashCommandRow(
		FSlashCommandPtr Item, const TSharedRef<STableViewBase>& OwnerTable);
	void OnSlashCommandSelected(FSlashCommandPtr Item, ESelectInfo::Type SelectInfo);

	// --- 聊天辅助方法 ---
	void AddMessage(const FString& Sender, const FString& Content, bool bIsCode = false);
	void AddToolCallMessage(const FString& ToolName, const FString& ToolId, const FString& Arguments);
	void AddToolResultMessage(const FString& ToolName, const FString& ToolId, const FString& ResultContent, bool bIsError);
	void RebuildMessageList();
	FSlateColor GetSenderColor(const FString& Sender) const;

	/** 工具调用折叠切换 */
	FReply OnToggleToolCollapse(int32 MessageIndex);

	// --- OpenClaw Bridge 连接管理 ---
	void ConnectOpenClawBridge();
	void DisconnectOpenClawBridge();
	void RunDiagnoseConnection();
	void HandleSlashCommand(const FString& Command, const FString& Args);

	/** 连接成功后向 AI 发送环境上下文信息 */
	void SendEnvironmentContext();

	// --- OpenClaw Gateway 通信 (阶段 3) — via Python Bridge ---
	void SendToOpenClaw(const FString& UserMessage);
	void HandlePythonResponse(const FString& Response);

	// --- 流式显示辅助 ---
	/** 更新 "Thinking..." 消息为流式内容 */
	void UpdateStreamingMessage(const FString& Sender, const FString& Content);

	// --- 快捷输入 (Quick Inputs) ---

	/** 快捷输入数据模型 */
	struct FQuickInput
	{
		FString Id;       // UUID
		FString Name;     // 显示名称
		FString Content;  // 实际填充文本
	};

	/** 加载快捷输入配置 */
	void LoadQuickInputs();

	/** 保存快捷输入配置 */
	void SaveQuickInputs();

	/** 获取配置文件路径 */
	FString GetQuickInputConfigPath() const;

	/** 重建快捷输入 UI */
	void RebuildQuickInputPanel();

	/** 点击快捷输入项 → 填充到对话框 */
	FReply OnQuickInputClicked(int32 Index);

	/** 添加新快捷输入 */
	FReply OnAddQuickInputClicked();

	/** 删除快捷输入 */
	FReply OnDeleteQuickInputClicked(int32 Index);

	/** 编辑快捷输入 (弹出编辑窗口) */
	FReply OnEditQuickInputClicked(int32 Index);

	/** 编辑名称提交 */
	void OnQuickInputNameCommitted(const FText& NewText, ETextCommit::Type CommitType, int32 Index);

	/** 编辑内容提交 */
	void OnQuickInputContentCommitted(const FText& NewText, ETextCommit::Type CommitType, int32 Index);

private:
	/** Subsystem */
	TWeakObjectPtr<UUEAgentSubsystem> CachedSubsystem;
	bool bCachedIsConnected = false;

	/** AI 平台通信桥接 (当前: OpenClaw) */
	TSharedPtr<IAgentPlatformBridge> PlatformBridge;

	/** 状态栏折叠 */
	bool bStatusExpanded = false;
	TSharedPtr<SWidget> StatusDetailWidget;

	/** 消息历史 */
	TArray<FChatMessage> Messages;
	TSharedPtr<SScrollBox> MessageScrollBox;

	/** 多行输入框 */
	TSharedPtr<SMultiLineEditableTextBox> InputTextBox;

	/** Slash 命令菜单 */
	TSharedPtr<SMenuAnchor> SlashMenuAnchor;
	TArray<FSlashCommandPtr> AllSlashCommands;
	TArray<FSlashCommandPtr> FilteredSlashCommands;
	TSharedPtr<SListView<FSlashCommandPtr>> SlashListView;

	/** 发送模式: true = Enter 直接发送, false = Ctrl+Enter 发送 */
	bool bEnterToSend = true;
	TSharedPtr<SCheckBox> SendModeCheckBox;

	/** OpenClaw Gateway 通信 (via Python Bridge) */
	bool bIsWaitingForResponse = false;
	FTSTicker::FDelegateHandle PollTimerHandle;
	TArray<FString> PendingPythonResult;

	/** Bridge 连接状态持续轮询 */
	FTSTicker::FDelegateHandle BridgeStatusPollHandle;
	double LastBridgeStatusTimestamp = 0.0;

	/** 环境上下文待发送标记：Connect 成功后设为 true，等 mcp_ready 后实际发送 */
	bool bEnvContextPending = false;

	/** Connect 成功后的宽限期截止时间 (FPlatformTime::Seconds)，期间忽略轮询的 connected=false */
	double ConnectGraceUntil = 0.0;

	/** 流式显示: 已读取的流式文件行数 */
	int32 StreamLinesRead = 0;
	/** 流式显示: 是否已显示过 thinking 消息 */
	bool bHasStreamingMessage = false;

	/** 快捷输入列表 */
	TArray<FQuickInput> QuickInputs;

	/** 快捷输入按钮容器 (WrapBox) */
	TSharedPtr<SWrapBox> QuickInputWrapBox;

	/** 快捷输入折叠区域 */
	TSharedPtr<SExpandableArea> QuickInputExpandableArea;

	/** 是否处于编辑模式 */
	bool bQuickInputEditMode = false;

	/** 当前会话名称标签 (任务 5.4) */
	FString CurrentSessionLabel;

	/** Token usage 跟踪 (任务 5.5) */
	int32 LastTotalTokens = 0;
	int32 ContextWindowSize = 200000;  // 默认 200K (claude-opus-4-6)

	// --- 多会话管理 (任务 5.8) ---

	/** 会话条目数据模型 */
	struct FSessionEntry
	{
		FString SessionKey;       // bridge 格式: "xiaoyou/ue-editor:1711612345000"
		FString SessionId;        // Gateway transcript 的 session id
		FString Label;            // "对话 03-28 09:15"
		FDateTime CreatedAt;
		bool bIsActive = false;
	};

	/** 所有会话列表 */
	TArray<FSessionEntry> SessionEntries;

	/** 当前活跃会话的索引 */
	int32 ActiveSessionIndex = -1;

	/** 会话选择下拉菜单锚点 */
	TSharedPtr<SMenuAnchor> SessionMenuAnchor;

	/** 初始化首个会话条目 */
	void InitFirstSession();

	/** 会话下拉按钮点击 */
	FReply OnSessionMenuClicked();

	/** 构建会话下拉菜单内容 */
	TSharedRef<SWidget> BuildSessionMenuContent();

	/** 切换到指定会话 */
	void OnSessionSelected(int32 Index);

	/** 删除指定会话 */
	void OnDeleteSession(int32 Index);

	/** 从 Gateway transcript 加载会话历史 */
	void LoadSessionHistory(const FString& SessionKey);

	/** 获取当前活跃会话的标签文本 */
	FText GetActiveSessionLabel() const;

	// --- Skill 创建集成 (阶段 D — v2 对话式) ---

	/** "Create Skill" 按钮回调: 在输入框填充引导文本 */
	FReply OnCreateSkillClicked();

	/** 管理面板按钮回调: 打开 Skill/MCP 管理窗口 */
	FReply OnManageClicked();

	/** 语言切换按钮回调 */
	FReply OnToggleLanguageClicked();

	/** 语言切换后重建整个 UI（刷新所有文本） */
	void RebuildAfterLanguageChange();

	// --- Plan 模式 (任务 5.9) ---

	/** Plan 模式开关 */
	bool bPlanMode = false;

	/** 当前 Plan (TOptional 管理生命周期) */
	TOptional<FPlan> CurrentPlan;

	/** 最后一次 Plan 请求的用户原始输入 */
	FString LastPlanRequest;

	/** 切换 Plan 模式 */
	FReply OnTogglePlanModeClicked();

	/** 获取 Plan 模式按钮文本 */
	FText GetPlanModeButtonText() const;

	/** 尝试从 AI 回复中解析 Plan JSON */
	void TryParsePlan(const FString& Response);

	/** 在消息流中添加 Plan 展示卡片 */
	void AddPlanMessage();

	/** 执行 Plan 中的下一个 Pending 步骤 */
	void ExecuteNextPlanStep();

	/** "执行全部" 按钮回调 */
	FReply OnExecutePlanClicked();

	/** "暂停" 按钮回调 */
	FReply OnPausePlanClicked();

	/** "继续" 按钮回调 */
	FReply OnResumePlanClicked();

	/** "取消计划" 按钮回调 */
	FReply OnCancelPlanClicked();

	/** 删除指定步骤 (标记为 Skipped) */
	FReply OnDeletePlanStep(int32 StepIndex);

	// --- 文件操作确认弹窗 (阶段 5.6) ---

	/** 确认请求轮询定时器 */
	FTSTicker::FDelegateHandle ConfirmPollHandle;

	/** 轮询 _confirm_request.json 并弹出确认对话框 */
	void PollConfirmationRequests();

	/** 显示自定义确认弹窗 (支持复选框) */
	void ShowConfirmationDialog(const FString& RiskLevel,
	                            const TArray<TSharedPtr<FJsonValue>>& Operations,
	                            const FString& CodePreview);

	// --- 静默模式 (阶段 5.7) ---

	/** 中风险静默 (从 config.json 同步) */
	bool bSilentMedium = false;

	/** 高风险静默 (从 config.json 同步) */
	bool bSilentHigh = false;

	/** 读取 ~/.artclaw/config.json 中的静默模式配置 */
	void LoadSilentModeFromConfig();

	/** 更新 ~/.artclaw/config.json 中的静默模式配置 */
	void SaveSilentModeToConfig();

	/** 中风险静默切换按钮回调 */
	FReply OnToggleSilentMediumClicked();

	/** 高风险静默切换按钮回调 */
	FReply OnToggleSilentHighClicked();

	static constexpr int32 MaxMessages = 500;
};
