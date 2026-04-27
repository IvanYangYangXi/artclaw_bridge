// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "Framework/Commands/Commands.h"
#include "UEClawBridgeStyle.h"

class FUEClawBridgeCommands : public TCommands<FUEClawBridgeCommands>
{
public:

	FUEClawBridgeCommands()
		: TCommands<FUEClawBridgeCommands>(TEXT("UEClawBridge"), NSLOCTEXT("Contexts", "UEClawBridge", "UEClawBridge Plugin"), NAME_None, FUEClawBridgeStyle::GetStyleSetName())
	{
	}

	// TCommands<> interface
	virtual void RegisterCommands() override;

public:
	TSharedPtr< FUICommandInfo > PluginAction;
};
