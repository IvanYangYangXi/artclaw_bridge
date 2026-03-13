// Copyright Epic Games, Inc. All Rights Reserved.

#include "UEEditorAgentCommands.h"

#define LOCTEXT_NAMESPACE "FUEEditorAgentModule"

void FUEEditorAgentCommands::RegisterCommands()
{
	UI_COMMAND(PluginAction, "UEEditorAgent", "Execute UEEditorAgent action", EUserInterfaceActionType::Button, FInputChord());
}

#undef LOCTEXT_NAMESPACE
