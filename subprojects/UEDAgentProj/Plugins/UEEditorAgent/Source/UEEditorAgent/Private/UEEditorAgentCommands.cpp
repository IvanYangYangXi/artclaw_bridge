// Copyright Epic Games, Inc. All Rights Reserved.

#include "UEEditorAgentCommands.h"

#define LOCTEXT_NAMESPACE "FUEEditorAgentModule"

void FUEEditorAgentCommands::RegisterCommands()
{
	UI_COMMAND(PluginAction, "UE Claw Bridge", "Open UE Claw Bridge panel", EUserInterfaceActionType::Button, FInputChord());
}

#undef LOCTEXT_NAMESPACE