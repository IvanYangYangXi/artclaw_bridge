// Copyright Epic Games, Inc. All Rights Reserved.

#include "UEEditorAgent.h"
#include "UEEditorAgentStyle.h"
#include "UEEditorAgentCommands.h"
#include "UEAgentSubsystem.h"
#include "Misc/MessageDialog.h"
#include "ToolMenus.h"
#include "Widgets/Docking/SDockTab.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SVerticalBox.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SHorizontalBox.h"
#include "Framework/Docking/TabManager.h"
#include "Styling/CoreStyle.h"

static const FName UEEditorAgentTabName("UEAgentDashboard");

#define LOCTEXT_NAMESPACE "FUEEditorAgentModule"

void FUEEditorAgentModule::StartupModule()
{
	// This code will execute after your module is loaded into memory; the exact timing is specified in the .uplugin file per-module
	
	FUEEditorAgentStyle::Initialize();
	FUEEditorAgentStyle::ReloadTextures();

	FUEEditorAgentCommands::Register();
	
	PluginCommands = MakeShareable(new FUICommandList);

	PluginCommands->MapAction(
		FUEEditorAgentCommands::Get().PluginAction,
		FExecuteAction::CreateRaw(this, &FUEEditorAgentModule::PluginButtonClicked),
		FCanExecuteAction());

	// 注册Tab Spawner
	FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
		UEEditorAgentTabName,
		FOnSpawnTab::CreateRaw(this, &FUEEditorAgentModule::OnSpawnPluginTab))
		.SetDisplayName(LOCTEXT("TabTitle", "UE Editor Agent"))
		.SetTooltipText(LOCTEXT("TooltipText", "Open the UE Editor Agent dashboard tab."))
		.SetIcon(FSlateIcon(FUEEditorAgentStyle::GetStyleSetName(), "UEEditorAgent.PluginAction"));

	UToolMenus::RegisterStartupCallback(FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FUEEditorAgentModule::RegisterMenus));
}

void FUEEditorAgentModule::ShutdownModule()
{
	// This function may be called during shutdown to clean up your module.  For modules that support dynamic reloading,
	// we call this function before unloading the module.

	UToolMenus::UnRegisterStartupCallback(this);

	UToolMenus::UnregisterOwner(this);

	FUEEditorAgentStyle::Shutdown();

	FUEEditorAgentCommands::Unregister();
}

// Dashboard Widget 实现
class SUEAgentDashboardWidget : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SUEAgentDashboardWidget) {}
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs)
	{
		// 获取子系统单例
		Subsystem = GEditor->GetEditorSubsystem<UUEAgentSubsystem>();

		// 初始化文本绑定
		StatusText = SNew(STextBlock);
		VersionText = SNew(STextBlock).Text(FText::FromString(TEXT("Plugin Version: 1.0.0-alpha")));
		StatsText = SNew(STextBlock).Text(FText::FromString(TEXT("Commands Executed: 0")));

		// 构建UI布局
		ChildSlot
		[
			SNew(SVerticalBox)
			// 标题区域
			+ SVerticalBox::Slot().AutoHeight().Padding(16, 16, 16, 8)
			[
				SNew(STextBlock)
				.Text(FText::FromString(TEXT("UE Editor Agent Dashboard")))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 18))
			]

			// 状态信息区域
			+ SVerticalBox::Slot().AutoHeight().Padding(16, 8, 16, 8)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight().Padding(0, 2)
				[
					VersionText.ToSharedRef()
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0, 2)
				[
					StatusText.ToSharedRef()
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0, 2)
				[
					StatsText.ToSharedRef()
				]
			]

			// 分割线
			+ SVerticalBox::Slot().AutoHeight().Padding(16, 8, 16, 8)
			[
				SNew(SSeparator)
			]

			// 操作按钮区域
			+ SVerticalBox::Slot().AutoHeight().Padding(16, 8, 16, 16)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().Padding(0, 0, 8, 0)
				[
					SNew(SButton)
					.Text(FText::FromString(TEXT("Test Connection")))
					.OnClicked(this, &SUEAgentDashboardWidget::OnTestConnection)
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(8, 0, 0, 0)
				[
					SNew(SButton)
					.Text(FText::FromString(TEXT("View Logs")))
					.OnClicked(this, &SUEAgentDashboardWidget::OnViewLogs)
				]
			]
		];

		// 绑定状态变更委托（实时刷新核心）
		if (Subsystem)
		{
			Subsystem->OnConnectionStatusChanged.AddSP(this, &SUEAgentDashboardWidget::OnConnectionStatusChanged);
			UpdateStatusText(Subsystem->GetConnectionStatus());
		}
	}

	~SUEAgentDashboardWidget()
	{
		if (Subsystem)
		{
			Subsystem->OnConnectionStatusChanged.RemoveAll(this);
		}
	}

private:
	// 状态变更回调（实时刷新）
	void OnConnectionStatusChanged(bool bIsConnected)
	{
		UpdateStatusText(bIsConnected);
	}

	void UpdateStatusText(bool bIsConnected)
	{
		FString Status = bIsConnected ? TEXT("Online") : TEXT("Offline");
		FLinearColor Color = bIsConnected ? 
			FLinearColor::Green : FLinearColor::Red;

		StatusText->SetText(FText::FromString(FString::Printf(TEXT("Status: %s"), *Status)));
		StatusText->SetColorAndOpacity(FSlateColor(Color));
	}

	FReply OnTestConnection()
	{
		if (Subsystem)
		{
			Subsystem->SetConnectionStatus(!Subsystem->GetConnectionStatus());
		}
		return FReply::Handled();
	}

	FReply OnViewLogs()
	{
		FGlobalTabmanager::Get()->TryInvokeTab(FName("OutputLog"));
		return FReply::Handled();
	}

private:
	TWeakObjectPtr<UUEAgentSubsystem> Subsystem;
	TSharedPtr<STextBlock> StatusText;
	TSharedPtr<STextBlock> VersionText;
	TSharedPtr<STextBlock> StatsText;
};

// Tab Spawner 绑定
TSharedRef<SDockTab> FUEEditorAgentModule::OnSpawnPluginTab(const FSpawnTabArgs& SpawnTabArgs)
{
	return SNew(SDockTab)
		.TabRole(ETabRole::NomadTab)
		[
			SNew(SUEAgentDashboardWidget)
		];
}

void FUEEditorAgentModule::PluginButtonClicked()
{
	FGlobalTabmanager::Get()->TryInvokeTab(UEEditorAgentTabName);
}

void FUEEditorAgentModule::RegisterMenus()
{
	// Owner will be used for cleanup in call to UToolMenus::UnregisterOwner
	FToolMenuOwnerScoped OwnerScoped(this);

	{
		UToolMenu* Menu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Window");
		{
			FToolMenuSection& Section = Menu->FindOrAddSection("WindowLayout");
			Section.AddMenuEntryWithCommandList(FUEEditorAgentCommands::Get().PluginAction, PluginCommands);
		}
	}

	{
		UToolMenu* ToolbarMenu = UToolMenus::Get()->ExtendMenu("LevelEditor.LevelEditorToolBar");
		{
			FToolMenuSection& Section = ToolbarMenu->FindOrAddSection("Settings");
			FToolMenuEntry& Entry = Section.AddEntry(FToolMenuEntry::InitToolBarButton(
				FUEEditorAgentCommands::Get().PluginAction));
			Entry.SetCommandList(PluginCommands);
		}
	}
}

#undef LOCTEXT_NAMESPACE
	
IMPLEMENT_MODULE(FUEEditorAgentModule, UEEditorAgent)