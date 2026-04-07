// Copyright ArtClaw. All Rights Reserved.
// Ref: docs/UEClawBridge/features/UE全能力API开发清单.md

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

DECLARE_LOG_CATEGORY_EXTERN(LogUEClawBridgeAPI, Log, All);

class FUEClawBridgeAPIModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};