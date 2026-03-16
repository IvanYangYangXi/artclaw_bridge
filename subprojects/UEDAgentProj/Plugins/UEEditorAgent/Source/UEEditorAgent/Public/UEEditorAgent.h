// Copyright ArtClaw Project. All Rights Reserved.

#pragma once

#include "Modules/ModuleManager.h"

class FToolBarBuilder;
class FMenuBuilder;

/**
 * FUEEditorAgentModule
 * 插件模块入口，负责注册工具栏按钮、Nomad Tab (可停靠窗口) 和命令绑定。
 *
 * 宪法约束:
 *   - C++ 负责模块定义 / UI / 生命周期 (系统架构设计 §2.3)
 *   - 工具栏集成 + 可停靠 Dashboard 窗口 (0.3 里程碑)
 *   - Dashboard 窗口整合 Chat Panel (阶段 2.1)
 */
class FUEEditorAgentModule : public IModuleInterface
{
public:

	/** IModuleInterface implementation */
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
	
	/** 工具栏按钮回调：打开/聚焦 Dashboard Tab */
	void PluginButtonClicked();
	
private:

	/** 注册工具栏/菜单入口 */
	void RegisterMenus();

	/** 注册可停靠的 Nomad Tab Spawner */
	void RegisterDashboardTab();

	/** Tab 生成工厂方法 */
	TSharedRef<class SDockTab> SpawnDashboardTab(const class FSpawnTabArgs& Args);

private:
	TSharedPtr<class FUICommandList> PluginCommands;

	/** Dashboard Tab 标识名 */
	static const FName DashboardTabName;
};