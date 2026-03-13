// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "Framework/Commands/Commands.h"
#include "UEEditorAgentStyle.h"

class FUEEditorAgentCommands : public TCommands<FUEEditorAgentCommands>
{
public:

	FUEEditorAgentCommands()
		: TCommands<FUEEditorAgentCommands>(TEXT("UEEditorAgent"), NSLOCTEXT("Contexts", "UEEditorAgent", "UEEditorAgent Plugin"), NAME_None, FUEEditorAgentStyle::GetStyleSetName())
	{
	}

	// TCommands<> interface
	virtual void RegisterCommands() override;

public:
	TSharedPtr< FUICommandInfo > PluginAction;
};
