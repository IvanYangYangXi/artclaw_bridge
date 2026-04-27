// Copyright ArtClaw Project. All Rights Reserved.

#include "UEClawBridge.h"
#include "UEClawBridgeStyle.h"
#include "UEClawBridgeCommands.h"
#include "UEAgentDashboard.h"
#include "ToolMenus.h"
#include "Widgets/Docking/SDockTab.h"
#include "Framework/Docking/TabManager.h"

static const FName UEClawBridgeTabName("UEClawBridge");

// Dashboard Tab 的全局唯一标识
const FName FUEClawBridgeModule::DashboardTabName("UEClawBridgeDashboard");

#define LOCTEXT_NAMESPACE "FUEClawBridgeModule"

void FUEClawBridgeModule::StartupModule()
{
	FUEClawBridgeStyle::Initialize();
	FUEClawBridgeStyle::ReloadTextures();

	FUEClawBridgeCommands::Register();
	
	PluginCommands = MakeShareable(new FUICommandList);

	PluginCommands->MapAction(
		FUEClawBridgeCommands::Get().PluginAction,
		FExecuteAction::CreateRaw(this, &FUEClawBridgeModule::PluginButtonClicked),
		FCanExecuteAction());

	UToolMenus::RegisterStartupCallback(
		FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FUEClawBridgeModule::RegisterMenus));

	// 注册可停靠的 Dashboard Tab (已整合 Chat Panel)
	RegisterDashboardTab();
}

void FUEClawBridgeModule::ShutdownModule()
{
	UToolMenus::UnRegisterStartupCallback(this);
	UToolMenus::UnregisterOwner(this);

	FUEClawBridgeStyle::Shutdown();
	FUEClawBridgeCommands::Unregister();

	// 注销 Tab Spawner
	FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(DashboardTabName);
}

void FUEClawBridgeModule::PluginButtonClicked()
{
	// 打开 / 聚焦 Dashboard 可停靠窗口
	FGlobalTabmanager::Get()->TryInvokeTab(DashboardTabName);
}

void FUEClawBridgeModule::RegisterMenus()
{
	FToolMenuOwnerScoped OwnerScoped(this);

	// Window 菜单入口
	{
		UToolMenu* Menu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Window");
		{
			FToolMenuSection& Section = Menu->FindOrAddSection("WindowLayout");
			Section.AddMenuEntryWithCommandList(
				FUEClawBridgeCommands::Get().PluginAction, PluginCommands);
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
						FUEClawBridgeCommands::Get().PluginAction));
				Entry.SetCommandList(PluginCommands);
			}
		}
	}
}

void FUEClawBridgeModule::RegisterDashboardTab()
{
	FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
		DashboardTabName,
		FOnSpawnTab::CreateRaw(this, &FUEClawBridgeModule::SpawnDashboardTab))
		.SetDisplayName(LOCTEXT("DashboardTabTitle", "UE Claw Bridge"))
		.SetMenuType(ETabSpawnerMenuType::Hidden)  // 不在 Window 菜单重复显示
		.SetIcon(FSlateIcon(FUEClawBridgeStyle::GetStyleSetName(),
			"UEClawBridge.PluginAction"));
}

TSharedRef<SDockTab> FUEClawBridgeModule::SpawnDashboardTab(const FSpawnTabArgs& Args)
{
	return SNew(SDockTab)
		.TabRole(ETabRole::NomadTab)
		[
			SNew(SUEAgentDashboard)
		];
}

#undef LOCTEXT_NAMESPACE
	
IMPLEMENT_MODULE(FUEClawBridgeModule, UEClawBridge)