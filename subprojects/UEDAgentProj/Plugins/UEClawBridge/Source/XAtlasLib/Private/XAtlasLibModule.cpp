// Copyright ArtClaw. All Rights Reserved.
// XAtlasLib module implementation

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FXAtlasLibModule : public IModuleInterface
{
public:
	virtual void StartupModule() override {}
	virtual void ShutdownModule() override {}
};

IMPLEMENT_MODULE(FXAtlasLibModule, XAtlasLib)
