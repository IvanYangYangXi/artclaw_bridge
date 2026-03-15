// Copyright Epic Games, Inc. All Rights Reserved.

#include "UEEditorAgent.h"
#include "UEEditorAgentStyle.h"
#include "UEEditorAgentCommands.h"
#include "Misc/MessageDialog.h"
#include "ToolMenus.h"

static const FName UEEditorAgentTabName("UEEditorAgent");

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

void FUEEditorAgentModule::PluginButtonClicked()
{
	// Put your "OnButtonClicked" stuff here
	FText DialogText = FText::Format(
							LOCTEXT("PluginButtonDialogText", "Add code to {0} in {1} to override this button's actions"),
							FText::FromString(TEXT("FUEEditorAgentModule::PluginButtonClicked()")),
							FText::FromString(TEXT("UEEditorAgent.cpp"))
					   );
	FMessageDialog::Open(EAppMsgType::Ok, DialogText);
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
		UToolMenu* ToolbarMenu = UToolMenus::Get()->ExtendMenu("LevelEditor.LevelEditorToolBar.PlayToolBar");
		{
			FToolMenuSection& Section = ToolbarMenu->FindOrAddSection("PluginTools");
			{
				FToolMenuEntry& Entry = Section.AddEntry(FToolMenuEntry::InitToolBarButton(FUEEditorAgentCommands::Get().PluginAction));
				Entry.SetCommandList(PluginCommands);
			}
		}
	}
}

#undef LOCTEXT_NAMESPACE
	
IMPLEMENT_MODULE(FUEEditorAgentModule, UEEditorAgent)