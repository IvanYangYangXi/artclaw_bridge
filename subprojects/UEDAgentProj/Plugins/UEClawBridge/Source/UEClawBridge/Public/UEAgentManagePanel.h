// Copyright ArtClaw Project. All Rights Reserved.
// 管理面板外壳 — Tab 切换 + 托管 MCP Tab / Skill Tab

#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

class SUEAgentMcpTab;
class SUEAgentSkillTab;

/**
 * SUEAgentManagePanel
 * 管理面板外壳 — Tab 切换框架，具体内容委托给子 Widget
 *
 * 文件拆分:
 *   UEAgentManagePanel.h/cpp  — 外壳 (Tab bar + 刷新)
 *   UEAgentMcpTab.h/cpp       — MCP Server 管理
 *   UEAgentSkillTab.h/cpp     — Skill 管理
 *   UEAgentManageUtils.h/cpp  — 共享工具 (Python IPC / 文件 IO)
 */
class SUEAgentManagePanel : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SUEAgentManagePanel) {}
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);

private:
	enum class EManageTab : uint8 { MCP, Skill };
	EManageTab ActiveTab = EManageTab::Skill;

	FReply OnMcpTabClicked();
	FReply OnSkillTabClicked();
	FReply OnRefreshClicked();
	void RebuildContent();

	FSlateColor GetTabColor(EManageTab Tab) const;

	TSharedPtr<SVerticalBox> ContentBox;
	TSharedPtr<SUEAgentMcpTab> McpTab;
	TSharedPtr<SUEAgentSkillTab> SkillTab;
};
