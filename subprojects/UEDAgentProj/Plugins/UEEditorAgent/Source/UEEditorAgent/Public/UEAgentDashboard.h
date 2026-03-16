// Copyright ArtClaw Project. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

class UUEAgentSubsystem;

/**
 * SUEAgentDashboard
 * 可停靠的 Dashboard 面板，实时显示插件版本号、连接状态、统计信息。
 * 通过绑定 UUEAgentSubsystem 的委托实现状态变更自动刷新。
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

	/** 构造 Slate 控件树 */
	void Construct(const FArguments& InArgs);

	/** 析构时解绑委托 */
	virtual ~SUEAgentDashboard() override;

private:
	// --- 委托回调 ---

	/** 当 UUEAgentSubsystem 连接状态变更时触发（Dynamic Delegate 回调） */
	void HandleConnectionStatusChanged(bool bNewStatus);

	// --- 辅助方法 ---

	/** 获取连接状态显示文本 */
	FText GetConnectionStatusText() const;

	/** 获取连接状态颜色 */
	FSlateColor GetConnectionStatusColor() const;

	/** 获取版本号文本 */
	FText GetVersionText() const;

	/** 获取 MCP 服务器地址文本 */
	FText GetServerAddressText() const;

	/** 获取统计信息文本 */
	FText GetStatsText() const;

	// --- 按钮回调 ---

	/** "Open Chat" 按钮：打开 Chat Panel Tab (阶段 2.1) */
	FReply OnOpenChatClicked();

	/** "Test Connection" 按钮：切换连接状态 */
	FReply OnTestConnectionClicked();

	/** "View Logs" 按钮：打开 Output Log */
	FReply OnViewLogsClicked();

private:
	/** 缓存的 Subsystem 指针 */
	TWeakObjectPtr<UUEAgentSubsystem> CachedSubsystem;

	/** 当前连接状态（本地缓存，用于 UI 绑定） */
	bool bCachedIsConnected = false;
};