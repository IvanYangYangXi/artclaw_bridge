// Copyright Epic Games, Inc. All Rights Reserved.

#include "UEClawBridgeCommands.h"

#define LOCTEXT_NAMESPACE "FUEClawBridgeModule"

void FUEClawBridgeCommands::RegisterCommands()
{
	UI_COMMAND(PluginAction, "UE Claw Bridge", "Open UE Claw Bridge panel", EUserInterfaceActionType::Button, FInputChord());
}

#undef LOCTEXT_NAMESPACE