// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)
// Asset creation factory helpers and preview generation.

#include "AssetManagementAPI.h"
#include "UEClawBridgeAPI.h"
#include "Utils/AssetModifier.h"
#include "Utils/PropertySerializer.h"
#include "AssetToolsModule.h"
#include "IAssetTools.h"
#include "Factories/BlueprintFactory.h"
#include "Factories/MaterialFactoryNew.h"
#include "Factories/DataTableFactory.h"
#include "Factories/WorldFactory.h"
#include "Engine/Blueprint.h"
#include "Engine/DataTable.h"
#include "Engine/DataAsset.h"
#include "Materials/Material.h"
#include "Engine/World.h"
#include "Engine/Texture2D.h"
#include "ObjectTools.h"
#include "GameFramework/Actor.h"
#include "Components/ActorComponent.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"

// === Asset creation factories ===

UObject* UAssetManagementAPI::CreateBlueprintAsset(const FString& AssetPath, const FString& ParentClass, FString& OutError)
{
	IAssetTools& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();

	UClass* ParentUClass = AActor::StaticClass();
	if (!ParentClass.IsEmpty())
	{
		ParentUClass = FPropertySerializer::ResolveClass(ParentClass, OutError);
		if (!ParentUClass)
		{
			ParentUClass = AActor::StaticClass();
			OutError.Empty();
		}
	}

	UBlueprintFactory* Factory = NewObject<UBlueprintFactory>(GetTransientPackage());
	Factory->ParentClass = ParentUClass;

	FString PackagePath = FPackageName::GetLongPackagePath(AssetPath);
	FString AssetName = FPackageName::GetShortName(AssetPath);

	return AssetTools.CreateAsset(AssetName, PackagePath, UBlueprint::StaticClass(), Factory);
}

UObject* UAssetManagementAPI::CreateMaterialAsset(const FString& AssetPath, FString& OutError)
{
	IAssetTools& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();

	UMaterialFactoryNew* Factory = NewObject<UMaterialFactoryNew>(GetTransientPackage());

	FString PackagePath = FPackageName::GetLongPackagePath(AssetPath);
	FString AssetName = FPackageName::GetShortName(AssetPath);

	return AssetTools.CreateAsset(AssetName, PackagePath, UMaterial::StaticClass(), Factory);
}

UObject* UAssetManagementAPI::CreateDataTableAsset(const FString& AssetPath, const FString& RowStruct, FString& OutError)
{
	IAssetTools& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();

	UDataTableFactory* Factory = NewObject<UDataTableFactory>(GetTransientPackage());

	if (!RowStruct.IsEmpty())
	{
		UScriptStruct* Struct = FindFirstObject<UScriptStruct>(*RowStruct, EFindFirstObjectOptions::ExactClass);
		if (Struct)
		{
			Factory->Struct = Struct;
		}
	}

	FString PackagePath = FPackageName::GetLongPackagePath(AssetPath);
	FString AssetName = FPackageName::GetShortName(AssetPath);

	return AssetTools.CreateAsset(AssetName, PackagePath, UDataTable::StaticClass(), Factory);
}

UObject* UAssetManagementAPI::CreateWorldAsset(const FString& AssetPath, FString& OutError)
{
	IAssetTools& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();

	UWorldFactory* Factory = NewObject<UWorldFactory>(GetTransientPackage());
	Factory->WorldType = EWorldType::Editor;

	FString PackagePath = FPackageName::GetLongPackagePath(AssetPath);
	FString AssetName = FPackageName::GetShortName(AssetPath);

	return AssetTools.CreateAsset(AssetName, PackagePath, UWorld::StaticClass(), Factory);
}

UObject* UAssetManagementAPI::CreateDataAsset(const FString& AssetPath, UClass* DataAssetClass, FString& OutError)
{
	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		OutError = TEXT("Failed to create package");
		return nullptr;
	}

	FString AssetName = FPackageName::GetShortName(AssetPath);
	return NewObject<UDataAsset>(Package, DataAssetClass, *AssetName, RF_Public | RF_Standalone);
}

UObject* UAssetManagementAPI::CreateGenericAsset(const FString& AssetPath, UClass* AssetClass, FString& OutError)
{
	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		OutError = TEXT("Failed to create package");
		return nullptr;
	}

	FString AssetName = FPackageName::GetShortName(AssetPath);
	return NewObject<UObject>(Package, AssetClass, *AssetName, RF_Public | RF_Standalone);
}

// === Property modification helpers ===

UObject* UAssetManagementAPI::GetAssetCDO(UBlueprint* Blueprint, FString& OutError)
{
	if (!Blueprint)
	{
		OutError = TEXT("Blueprint is null");
		return nullptr;
	}

	if (!Blueprint->GeneratedClass)
	{
		OutError = TEXT("Blueprint has no generated class");
		return nullptr;
	}

	return Blueprint->GeneratedClass->GetDefaultObject();
}

UActorComponent* UAssetManagementAPI::FindComponent(AActor* Actor, const FString& ComponentName, FString& OutError)
{
	if (!Actor)
	{
		OutError = TEXT("Actor is null");
		return nullptr;
	}

	UActorComponent* Component = Actor->GetRootComponent();
	if (Component && Component->GetName() == ComponentName)
	{
		return Component;
	}

	TArray<UActorComponent*> Components;
	Actor->GetComponents(Components);
	
	for (UActorComponent* Comp : Components)
	{
		if (Comp && Comp->GetName() == ComponentName)
		{
			return Comp;
		}
	}

	OutError = FString::Printf(TEXT("Component '%s' not found in actor"), *ComponentName);
	return nullptr;
}

// === Preview generation helpers ===

TArray<uint8> UAssetManagementAPI::RenderAssetThumbnail(UObject* Asset, int32 Resolution, const FString& Format)
{
	if (!Asset)
	{
		return TArray<uint8>();
	}

	FObjectThumbnail Thumbnail;
	ThumbnailTools::RenderThumbnail(Asset, Resolution, Resolution, ThumbnailTools::EThumbnailTextureFlushMode::AlwaysFlush, nullptr, &Thumbnail);

	if (Thumbnail.IsEmpty())
	{
		return TArray<uint8>();
	}

	const TArray<uint8>& ThumbData = Thumbnail.GetUncompressedImageData();
	int32 Width = Thumbnail.GetImageWidth();
	int32 Height = Thumbnail.GetImageHeight();

	if (Width == 0 || Height == 0 || ThumbData.Num() == 0)
	{
		return TArray<uint8>();
	}

	IImageWrapperModule& ImageWrapperModule = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
	TSharedPtr<IImageWrapper> ImageWrapper = ImageWrapperModule.CreateImageWrapper(EImageFormat::PNG);
	
	if (ImageWrapper.IsValid() && ImageWrapper->SetRaw(ThumbData.GetData(), ThumbData.Num(), Width, Height, ERGBFormat::BGRA, 8))
	{
		TArray64<uint8> CompressedData = ImageWrapper->GetCompressed(100);
		TArray<uint8> Result;
		Result.SetNumUninitialized(CompressedData.Num());
		FMemory::Memcpy(Result.GetData(), CompressedData.GetData(), CompressedData.Num());
		return Result;
	}

	return TArray<uint8>();
}

TArray<uint8> UAssetManagementAPI::ExportTextureData(UTexture2D* Texture, int32 Resolution, const FString& Format)
{
	return RenderAssetThumbnail(Texture, Resolution, Format);
}

FString UAssetManagementAPI::SavePreviewToFile(const TArray<uint8>& ImageData, const FString& Format, const FString& OutputPath)
{
	FString FilePath;
	
	if (OutputPath.IsEmpty())
	{
		FString TempDir = FPaths::Combine(FPlatformProcess::UserTempDir(), TEXT("artclaw-previews"));
		IFileManager::Get().MakeDirectory(*TempDir, true);
		
		FString Hash = FMD5::HashBytes(ImageData.GetData(), FMath::Min(1024, ImageData.Num()));
		FString FileName = FString::Printf(TEXT("preview_%s.%s"), *Hash.Left(8), *Format);
		FilePath = FPaths::Combine(TempDir, FileName);
	}
	else
	{
		FilePath = OutputPath;
	}

	if (FFileHelper::SaveArrayToFile(ImageData, *FilePath))
	{
		return FilePath;
	}

	return FString();
}
