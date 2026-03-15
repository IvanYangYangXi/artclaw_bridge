// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentDashboard.h"
#include "UEAgentSubsystem.h"
#include "Editor.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SButton.h"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"

void SUEAgentDashboard::Construct(const FArguments& InArgs)
{
	// 获取 Subsystem 单例
	if (GEditor)
	{
		CachedSubsystem = GEditor->GetEditorSubsystem<UUEAgentSubsystem>();
	}

	// 同步初始状态
	if (CachedSubsystem.IsValid())
	{
		bCachedIsConnected = CachedSubsystem->GetConnectionStatus();

		// 绑定原生委托以接收状态变更
		CachedSubsystem->OnConnectionStatusChangedNative.AddSP(
			this, &SUEAgentDashboard::HandleConnectionStatusChanged);
	}

	// --- 构建 Slate 控件树 ---
	// 遵循 0.3 样式规范: Padding(16,8), Bold 18 标题, 不使用 SSeparator
	ChildSlot
	[
		SNew(SScrollBox)
		+ SScrollBox::Slot()
		.Padding(16.0f, 8.0f)
		[
			SNew(SVerticalBox)

			// ========== 标题区 ==========
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 12.0f)
			[
				SNew(STextBlock)
				.Text(LOCTEXT("DashboardTitle", "UE Editor Agent"))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 18))
			]

			// ========== 版本号 ==========
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 4.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(STextBlock)
					.Text(LOCTEXT("VersionLabel", "Version: "))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(STextBlock)
					.Text(this, &SUEAgentDashboard::GetVersionText)
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
				]
			]

			// ========== 连接状态 ==========
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 4.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(STextBlock)
					.Text(LOCTEXT("StatusLabel", "Status: "))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(STextBlock)
					.Text(this, &SUEAgentDashboard::GetConnectionStatusText)
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
					.ColorAndOpacity(this, &SUEAgentDashboard::GetConnectionStatusColor)
				]
			]

			// ========== 统计信息 ==========
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 8.0f, 0.0f, 12.0f)
			[
				SNew(STextBlock)
				.Text(this, &SUEAgentDashboard::GetStatsText)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
				.AutoWrapText(true)
			]

			// ========== 按钮区 ==========
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(SHorizontalBox)

				// "Test Connection" 按钮
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(0.0f, 0.0f, 8.0f, 0.0f)
				[
					SNew(SButton)
					.Text(LOCTEXT("TestConnectionBtn", "Test Connection"))
					.OnClicked(this, &SUEAgentDashboard::OnTestConnectionClicked)
				]

				// "View Logs" 按钮
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(0.0f, 0.0f, 8.0f, 0.0f)
				[
					SNew(SButton)
					.Text(LOCTEXT("ViewLogsBtn", "View Logs"))
					.OnClicked(this, &SUEAgentDashboard::OnViewLogsClicked)
				]
			]
		]
	];
}

SUEAgentDashboard::~SUEAgentDashboard()
{
	// 安全解绑委托，防止悬挂引用
	if (CachedSubsystem.IsValid())
	{
		CachedSubsystem->OnConnectionStatusChangedNative.RemoveAll(this);
	}
}

// ------------------------------------------------------------------
// 委托回调
// ------------------------------------------------------------------

void SUEAgentDashboard::HandleConnectionStatusChanged(bool bNewStatus)
{
	bCachedIsConnected = bNewStatus;
	// Slate 使用 Attribute 绑定 (Text / ColorAndOpacity)，数据变更后
	// 框架会在下一帧自动重绘，无需手动 Invalidate。
}

// ------------------------------------------------------------------
// 辅助方法
// ------------------------------------------------------------------

FText SUEAgentDashboard::GetConnectionStatusText() const
{
	return bCachedIsConnected
		? LOCTEXT("Connected", "Connected")
		: LOCTEXT("Disconnected", "Disconnected");
}

FSlateColor SUEAgentDashboard::GetConnectionStatusColor() const
{
	return bCachedIsConnected
		? FSlateColor(FLinearColor::Green)
		: FSlateColor(FLinearColor::Red);
}

FText SUEAgentDashboard::GetVersionText() const
{
	if (CachedSubsystem.IsValid())
	{
		return FText::FromString(CachedSubsystem->GetPluginVersion());
	}
	return LOCTEXT("VersionUnknown", "Unknown");
}

FText SUEAgentDashboard::GetStatsText() const
{
	// 基础统计信息（后续阶段会接入 MCP 真实数据）
	FString StatsStr = FString::Printf(
		TEXT("Skills Loaded: 0\nActive Connections: %d\nPending Commands: 0"),
		bCachedIsConnected ? 1 : 0
	);
	return FText::FromString(StatsStr);
}

// ------------------------------------------------------------------
// 按钮回调
// ------------------------------------------------------------------

FReply SUEAgentDashboard::OnTestConnectionClicked()
{
	if (CachedSubsystem.IsValid())
	{
		// 切换连接状态（测试用途）
		CachedSubsystem->SetConnectionStatus(!CachedSubsystem->GetConnectionStatus());
	}
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnViewLogsClicked()
{
	// 打开 UE 的 Output Log 面板
	FGlobalTabmanager::Get()->TryInvokeTab(FName("OutputLog"));
	return FReply::Handled();
}

#undef LOCTEXT_NAMESPACE
