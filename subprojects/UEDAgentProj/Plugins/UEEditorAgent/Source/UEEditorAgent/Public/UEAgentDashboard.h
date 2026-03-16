// Copyright ArtClaw Project. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "Widgets/Views/SListView.h"
#include "Containers/Ticker.h"

class UUEAgentSubsystem;
class SScrollBox;
class SMultiLineEditableTextBox;
class SMenuAnchor;
class SCheckBox;

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
		FString Sender;   // "user", "assistant", "system"
		FString Content;
		FDateTime Timestamp;
		bool bIsCode = false;
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
	void RebuildMessageList();
	FSlateColor GetSenderColor(const FString& Sender) const;

	// --- OpenClaw Bridge 连接管理 ---
	void ConnectOpenClawBridge();
	void DisconnectOpenClawBridge();
	void RunDiagnoseConnection();
	void HandleSlashCommand(const FString& Command, const FString& Args);

	// --- OpenClaw Gateway 通信 (阶段 3) — via Python Bridge ---
	void SendToOpenClaw(const FString& UserMessage);
	void HandlePythonResponse(const FString& Response);

	// --- 流式显示辅助 ---
	/** 更新 "Thinking..." 消息为流式内容 */
	void UpdateStreamingMessage(const FString& Sender, const FString& Content);

private:
	/** Subsystem */
	TWeakObjectPtr<UUEAgentSubsystem> CachedSubsystem;
	bool bCachedIsConnected = false;

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

	/** 流式显示: 已读取的流式文件行数 */
	int32 StreamLinesRead = 0;
	/** 流式显示: 是否已显示过 thinking 消息 */
	bool bHasStreamingMessage = false;

	static constexpr int32 MaxMessages = 500;
};
