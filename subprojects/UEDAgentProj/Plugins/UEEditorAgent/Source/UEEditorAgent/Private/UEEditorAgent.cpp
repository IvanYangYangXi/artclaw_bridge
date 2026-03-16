// Copyright ArtClaw Project. All Rights Reserved.

#include "UEEditorAgent.h"
#include "UEEditorAgentStyle.h"
#include "UEEditorAgentCommands.h"
#include "UEAgentDashboard.h"
#include "ToolMenus.h"
#include "Widgets/Docking/SDockTab.h"
#include "Framework/Docking/TabManager.h"

static const FName UEEditorAgentTabName("UEEditorAgent");

// Dashboard Tab 的全局唯一标识
const FName FUEEditorAgentModule::DashboardTabName("UEEditorAgentDashboard");

#define LOCTEXT_NAMESPACE "FUEEditorAgentModule"

void FUEEditorAgentModule::StartupModule()
{
	FUEEditorAgentStyle::Initialize();
	FUEEditorAgentStyle::ReloadTextures();

	FUEEditorAgentCommands::Register();
	
	PluginCommands = MakeShareable(new FUICommandList);

	PluginCommands->MapAction(
		FUEEditorAgentCommands::Get().PluginAction,
		FExecuteAction::CreateRaw(this, &FUEEditorAgentModule::PluginButtonClicked),
		FCanExecuteAction());

	UToolMenus::RegisterStartupCallback(
		FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FUEEditorAgentModule::RegisterMenus));

	// 注册可停靠的 Dashboard Tab (已整合 Chat Panel)
	RegisterDashboardTab();
}

void FUEEditorAgentModule::ShutdownModule()
{
	UToolMenus::UnRegisterStartupCallback(this);
	UToolMenus::UnregisterOwner(this);

	FUEEditorAgentStyle::Shutdown();
	FUEEditorAgentCommands::Unregister();

	// 注销 Tab Spawner
	FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(DashboardTabName);
}

void FUEEditorAgentModule::PluginButtonClicked()
{
	// 打开 / 聚焦 Dashboard 可停靠窗口
	FGlobalTabmanager::Get()->TryInvokeTab(DashboardTabName);
}

void FUEEditorAgentModule::RegisterMenus()
{
	FToolMenuOwnerScoped OwnerScoped(this);

	// Window 菜单入口
	{
		UToolMenu* Menu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Window");
		{
			FToolMenuSection& Section = Menu->FindOrAddSection("WindowLayout");
			Section.AddMenuEntryWithCommandList(
				FUEEditorAgentCommands::Get().PluginAction, PluginCommands);
		}
	}

	// 工具栏按钮
	{
		UToolMenu* ToolbarMenu = UToolMenus::Get()->ExtendMenu(
			"LevelEditor.LevelEditorToolBar.PlayToolBar");
		{
			FToolMenuSection& Section = ToolbarMenu->FindOrAddSection("PluginTools");
			{
				FToolMenuEntry& Entry = Section.AddEntry(
					FToolMenuEntry::InitToolBarButton(
						FUEEditorAgentCommands::Get().PluginAction));
				Entry.SetCommandList(PluginCommands);
			}
		}
	}
}

void FUEEditorAgentModule::RegisterDashboardTab()
{
	FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
		DashboardTabName,
		FOnSpawnTab::CreateRaw(this, &FUEEditorAgentModule::SpawnDashboardTab))
		.SetDisplayName(LOCTEXT("DashboardTabTitle", "UE Editor Agent"))
		.SetMenuType(ETabSpawnerMenuType::Hidden)  // 不在 Window 菜单重复显示
		.SetIcon(FSlateIcon(FUEEditorAgentStyle::GetStyleSetName(),
			"UEEditorAgent.PluginAction"));
}

TSharedRef<SDockTab> FUEEditorAgentModule::SpawnDashboardTab(const FSpawnTabArgs& Args)
{
	return SNew(SDockTab)
		.TabRole(ETabRole::NomadTab)
		[
			SNew(SUEAgentDashboard)
		];
}

#undef LOCTEXT_NAMESPACE
	
IMPLEMENT_MODULE(FUEEditorAgentModule, UEEditorAgent)