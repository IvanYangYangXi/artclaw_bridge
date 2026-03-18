// Copyright Epic Games, Inc. All Rights Reserved.

#include "UEClawBridgeStyle.h"
#include "UEClawBridge.h"
#include "Framework/Application/SlateApplication.h"
#include "Styling/SlateStyleRegistry.h"
#include "Slate/SlateGameResources.h"
#include "Interfaces/IPluginManager.h"
#include "Styling/SlateStyleMacros.h"

#define RootToContentDir Style->RootToContentDir

TSharedPtr<FSlateStyleSet> FUEClawBridgeStyle::StyleInstance = nullptr;

void FUEClawBridgeStyle::Initialize()
{
	if (!StyleInstance.IsValid())
	{
		StyleInstance = Create();
		FSlateStyleRegistry::RegisterSlateStyle(*StyleInstance);
	}
}

void FUEClawBridgeStyle::Shutdown()
{
	FSlateStyleRegistry::UnRegisterSlateStyle(*StyleInstance);
	ensure(StyleInstance.IsUnique());
	StyleInstance.Reset();
}

FName FUEClawBridgeStyle::GetStyleSetName()
{
	static FName StyleSetName(TEXT("UEClawBridgeStyle"));
	return StyleSetName;
}


const FVector2D Icon16x16(16.0f, 16.0f);
const FVector2D Icon20x20(20.0f, 20.0f);

TSharedRef< FSlateStyleSet > FUEClawBridgeStyle::Create()
{
	TSharedRef< FSlateStyleSet > Style = MakeShareable(new FSlateStyleSet("UEClawBridgeStyle"));
	Style->SetContentRoot(IPluginManager::Get().FindPlugin("UEClawBridge")->GetBaseDir() / TEXT("Resources"));

	Style->Set("UEClawBridge.PluginAction", new IMAGE_BRUSH_SVG(TEXT("PlaceholderButtonIcon"), Icon20x20));
	return Style;
}

void FUEClawBridgeStyle::ReloadTextures()
{
	if (FSlateApplication::IsInitialized())
	{
		FSlateApplication::Get().GetRenderer()->ReloadTextureResources();
	}
}

const ISlateStyle& FUEClawBridgeStyle::Get()
{
	return *StyleInstance;
}
