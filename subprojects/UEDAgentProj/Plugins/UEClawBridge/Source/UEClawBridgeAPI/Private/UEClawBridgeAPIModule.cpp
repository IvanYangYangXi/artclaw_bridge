// Copyright ArtClaw. All Rights Reserved.

#include "UEClawBridgeAPI.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY(LogUEClawBridgeAPI);

#define LOCTEXT_NAMESPACE "FUEClawBridgeAPIModule"

void FUEClawBridgeAPIModule::StartupModule()
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("UEClawBridgeAPI module started"));
}

void FUEClawBridgeAPIModule::ShutdownModule()
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("UEClawBridgeAPI module shutdown"));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FUEClawBridgeAPIModule, UEClawBridgeAPI)