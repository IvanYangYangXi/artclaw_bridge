// Copyright ArtClaw Project. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

class UUEAgentSubsystem;
class SScrollBox;
class SEditableTextBox;

/**
 * SUEAgentChatPanel
 * 编辑器内对话面板 (阶段 2.1)
 *
 * 可停靠的 Chat Tab，提供与 AI 的交互界面。
 * 使用原生 Slate 控件实现消息展示和文本输入。
 *
 * 宪法约束:
 *   - 开发路线图 §2.1: 编辑器内对话面板, 可停靠, 消息历史, 主题同步
 *   - 系统架构设计 §2.3: C++ 负责 UI
 *   - 核心机制 §4: 混合 UI 交互
 */
class SUEAgentChatPanel : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SUEAgentChatPanel) {}
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	virtual ~SUEAgentChatPanel() override;

private:
	// --- 消息模型 ---
	struct FChatMessage
	{
		FString Sender;   // "user" or "assistant"
		FString Content;
		FDateTime Timestamp;
		bool bIsCode = false;
	};

	// --- UI 回调 ---

	/** 发送按钮 / Enter 键 */
	FReply OnSendClicked();

	/** 清空聊天记录 */
	FReply OnClearClicked();

	/** 输入框文本提交 (Enter) */
	void OnInputTextCommitted(const FText& NewText, ETextCommit::Type CommitType);

	/** 连接状态变更 */
	void HandleConnectionStatusChanged(bool bNewStatus);

	// --- 辅助方法 ---

	/** 添加消息到历史 */
	void AddMessage(const FString& Sender, const FString& Content, bool bIsCode = false);

	/** 重建消息列表 UI */
	void RebuildMessageList();

	/** 获取发送者颜色 */
	FSlateColor GetSenderColor(const FString& Sender) const;

	/** 获取状态栏文本 */
	FText GetStatusBarText() const;

private:
	/** 消息历史 */
	TArray<FChatMessage> Messages;

	/** 消息列表滚动容器 */
	TSharedPtr<SScrollBox> MessageScrollBox;

	/** 输入框 */
	TSharedPtr<SEditableTextBox> InputTextBox;

	/** Subsystem 引用 */
	TWeakObjectPtr<UUEAgentSubsystem> CachedSubsystem;

	/** 连接状态缓存 */
	bool bCachedIsConnected = false;

	/** 最大消息历史数 */
	static constexpr int32 MaxMessages = 500;
};