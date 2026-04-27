// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "AssetManagementAPI.h"
#include "UEClawBridgeAPI.h"
#include "Utils/JsonHelpers.h"
#include "Utils/AssetModifier.h"
#include "Utils/PropertySerializer.h"
// Note: Using AssetRegistry/LoadObject instead of EditorAssetLibrary to avoid EditorScriptingUtilities dependency
#include "Engine/Blueprint.h"
#include "Engine/DataAsset.h"
#include "Engine/Texture2D.h"
#include "GameFramework/Actor.h"
#include "Components/ActorComponent.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "Editor.h"
#include "ObjectTools.h"

FString UAssetManagementAPI::CreateAsset(const FString& AssetPath, const FString& AssetClass, const FString& PropertiesJson)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("CreateAsset: path='%s', class='%s'"), *AssetPath, *AssetClass);

	if (AssetPath.IsEmpty() || AssetClass.IsEmpty())
	{
		return ClawJson::MakeError(TEXT("AssetPath and AssetClass are required"));
	}

	if (!FAssetModifier::ValidateAssetPath(AssetPath))
	{
		return ClawJson::MakeError(FString::Printf(TEXT("Invalid asset path format: %s"), *AssetPath));
	}

	if (FAssetModifier::AssetExists(AssetPath))
	{
		return ClawJson::MakeError(FString::Printf(TEXT("Asset already exists: %s"), *AssetPath));
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Create %s"), *FPackageName::GetShortName(AssetPath)));

	FString Error;
	UObject* CreatedAsset = nullptr;

	FString LowerClass = AssetClass.ToLower();
	if (LowerClass == TEXT("blueprint"))
	{
		FString ParentClass = TEXT("Actor");
		if (!PropertiesJson.IsEmpty())
		{
			TSharedPtr<FJsonObject> Props;
			auto JsonReader = TJsonReaderFactory<>::Create(PropertiesJson);
			if (FJsonSerializer::Deserialize(JsonReader, Props) && Props.IsValid())
			{
				ParentClass = Props->GetStringField(TEXT("parent_class"));
			}
		}
		CreatedAsset = CreateBlueprintAsset(AssetPath, ParentClass, Error);
	}
	else if (LowerClass == TEXT("material"))
	{
		CreatedAsset = CreateMaterialAsset(AssetPath, Error);
	}
	else if (LowerClass == TEXT("datatable"))
	{
		FString RowStruct;
		if (!PropertiesJson.IsEmpty())
		{
			TSharedPtr<FJsonObject> Props;
			auto JsonReader = TJsonReaderFactory<>::Create(PropertiesJson);
			if (FJsonSerializer::Deserialize(JsonReader, Props) && Props.IsValid())
			{
				RowStruct = Props->GetStringField(TEXT("row_struct"));
			}
		}
		CreatedAsset = CreateDataTableAsset(AssetPath, RowStruct, Error);
	}
	else if (LowerClass == TEXT("world") || LowerClass == TEXT("level") || LowerClass == TEXT("map"))
	{
		CreatedAsset = CreateWorldAsset(AssetPath, Error);
	}
	else if (LowerClass == TEXT("dataasset"))
	{
		CreatedAsset = CreateDataAsset(AssetPath, UDataAsset::StaticClass(), Error);
	}
	else
	{
		UClass* ResolvedClass = FPropertySerializer::ResolveClass(AssetClass, Error);
		if (ResolvedClass)
		{
			if (ResolvedClass->IsChildOf<UBlueprint>())
			{
				CreatedAsset = CreateBlueprintAsset(AssetPath, TEXT("Actor"), Error);
			}
			else if (ResolvedClass->IsChildOf<UDataAsset>())
			{
				CreatedAsset = CreateDataAsset(AssetPath, ResolvedClass, Error);
			}
			else
			{
				CreatedAsset = CreateGenericAsset(AssetPath, ResolvedClass, Error);
			}
		}
	}

	if (!CreatedAsset)
	{
		return ClawJson::MakeError(Error.IsEmpty() ? TEXT("Failed to create asset") : Error);
	}

	FAssetModifier::MarkPackageDirty(CreatedAsset);

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset_path"), AssetPath);
	Result->SetStringField(TEXT("asset_class"), AssetClass);
	Result->SetStringField(TEXT("created_class"), CreatedAsset->GetClass()->GetName());
	Result->SetBoolField(TEXT("needs_save"), true);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("CreateAsset: Successfully created %s"), *AssetPath);
	return ClawJson::ToString(Result);
}

bool UAssetManagementAPI::DeleteAsset(const FString& AssetPath)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("DeleteAsset: path='%s'"), *AssetPath);

	if (AssetPath.IsEmpty())
	{
		UE_LOG(LogUEClawBridgeAPI, Error, TEXT("DeleteAsset: AssetPath is required"));
		return false;
	}

	if (!FAssetModifier::AssetExists(AssetPath))
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("DeleteAsset: Asset does not exist: %s"), *AssetPath);
		return false;
	}

	FString LoadError;
	UObject* Asset = FAssetModifier::LoadAssetByPath(AssetPath, LoadError);
	if (!Asset)
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("DeleteAsset: Failed to load asset '%s': %s"), *AssetPath, *LoadError);
		return false;
	}
	bool bIsBlueprint = Asset->IsA<UBlueprint>();

	TArray<UObject*> ObjectsToDelete;
	ObjectsToDelete.Add(Asset);
	int32 DeletedCount = ObjectTools::DeleteObjects(ObjectsToDelete, /*bShowConfirmation=*/false);
	bool bSuccess = DeletedCount > 0;

	if (bSuccess && bIsBlueprint)
	{
		CollectGarbage(GARBAGE_COLLECTION_KEEPFLAGS);
		CollectGarbage(GARBAGE_COLLECTION_KEEPFLAGS);
	}

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("DeleteAsset: %s %s"), 
		bSuccess ? TEXT("Deleted") : TEXT("Failed to delete"), *AssetPath);

	return bSuccess;
}

FString UAssetManagementAPI::SaveAsset(const FString& AssetPath, bool bCheckout)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("SaveAsset: path='%s', checkout=%s"), *AssetPath, bCheckout ? TEXT("true") : TEXT("false"));

	if (AssetPath.IsEmpty())
	{
		return ClawJson::MakeError(TEXT("AssetPath is required"));
	}

	FString LoadError;
	UObject* Asset = FAssetModifier::LoadAssetByPath(AssetPath, LoadError);
	if (!Asset)
	{
		return ClawJson::MakeError(FString::Printf(TEXT("Failed to load asset: %s"), *LoadError));
	}

	if (bCheckout)
	{
		FString PackageFileName = FPackageName::LongPackageNameToFilename(Asset->GetPackage()->GetName(), FPackageName::GetAssetPackageExtension());
		FString CheckoutError;
		if (!FAssetModifier::CheckoutFile(PackageFileName, CheckoutError))
		{
			UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("SaveAsset: Checkout failed: %s"), *CheckoutError);
		}
	}

	FString SaveError;
	bool bSaveSuccess = FAssetModifier::SaveAsset(Asset, SaveError);

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset_path"), AssetPath);
	Result->SetBoolField(TEXT("checkout_requested"), bCheckout);
	Result->SetBoolField(TEXT("saved"), bSaveSuccess);

	if (bSaveSuccess)
	{
		Result->SetStringField(TEXT("message"), TEXT("Asset saved successfully"));
	}
	else
	{
		Result->SetBoolField(TEXT("success"), false);
		Result->SetStringField(TEXT("error"), SaveError);
	}

	return ClawJson::ToString(Result);
}

bool UAssetManagementAPI::OpenAsset(const FString& AssetPath)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("OpenAsset: path='%s'"), *AssetPath);

	if (AssetPath.IsEmpty())
	{
		return false;
	}

	FString LoadError;
	UObject* Asset = FAssetModifier::LoadAssetByPath(AssetPath, LoadError);
	if (!Asset)
	{
		UE_LOG(LogUEClawBridgeAPI, Error, TEXT("OpenAsset: Failed to load: %s"), *LoadError);
		return false;
	}

	UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
	if (!AssetEditorSubsystem)
	{
		return false;
	}

	return AssetEditorSubsystem->OpenEditorForAsset(Asset);
}

FString UAssetManagementAPI::SetAssetProperty(const FString& AssetPath, const FString& ComponentName, const FString& PropertyPath, const FString& ValueJson)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("SetAssetProperty: asset='%s', component='%s', property='%s'"), 
		*AssetPath, *ComponentName, *PropertyPath);

	if (AssetPath.IsEmpty() || PropertyPath.IsEmpty() || ValueJson.IsEmpty())
	{
		return ClawJson::MakeError(TEXT("AssetPath, PropertyPath, and ValueJson are required"));
	}

	FString LoadError;
	UObject* Asset = FAssetModifier::LoadAssetByPath(AssetPath, LoadError);
	if (!Asset)
	{
		return ClawJson::MakeError(FString::Printf(TEXT("Failed to load asset: %s"), *LoadError));
	}

	TSharedPtr<FJsonValue> JsonValue;
	auto JsonReader = TJsonReaderFactory<>::Create(ValueJson);
	if (!FJsonSerializer::Deserialize(JsonReader, JsonValue) || !JsonValue.IsValid())
	{
		return ClawJson::MakeError(TEXT("Invalid JSON in ValueJson parameter"));
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Set Property %s"), *PropertyPath));

	FString Error;
	UObject* TargetObject = Asset;

	if (UBlueprint* Blueprint = Cast<UBlueprint>(Asset))
	{
		TargetObject = GetAssetCDO(Blueprint, Error);
		if (!TargetObject)
		{
			return ClawJson::MakeError(Error);
		}

		if (!ComponentName.IsEmpty())
		{
			if (AActor* Actor = Cast<AActor>(TargetObject))
			{
				UActorComponent* Component = FindComponent(Actor, ComponentName, Error);
				if (!Component)
				{
					return ClawJson::MakeError(Error);
				}
				TargetObject = Component;
			}
			else
			{
				return ClawJson::MakeError(TEXT("ComponentName specified but asset CDO is not an Actor"));
			}
		}
	}

	void* PropertyContainer = nullptr;
	FProperty* Property = FAssetModifier::FindPropertyByPath(TargetObject, PropertyPath, PropertyContainer, Error);
	if (!Property)
	{
		return ClawJson::MakeError(Error);
	}

	FAssetModifier::MarkModified(TargetObject);

	if (!FAssetModifier::SetPropertyFromJson(Property, PropertyContainer, JsonValue, Error))
	{
		return ClawJson::MakeError(Error);
	}

	if (UBlueprint* Blueprint = Cast<UBlueprint>(Asset))
	{
		FString CompileError;
		FAssetModifier::CompileBlueprint(Blueprint, CompileError);
	}

	FAssetModifier::MarkPackageDirty(Asset);

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset_path"), AssetPath);
	Result->SetStringField(TEXT("component_name"), ComponentName);
	Result->SetStringField(TEXT("property_path"), PropertyPath);
	Result->SetStringField(TEXT("property_type"), FPropertySerializer::GetPropertyTypeString(Property));
	Result->SetStringField(TEXT("message"), TEXT("Property set successfully"));

	return ClawJson::ToString(Result);
}

FString UAssetManagementAPI::GetAssetDiff(const FString& AssetPath)
{
	return ClawJson::MakeError(TEXT("GetAssetDiff not yet implemented - requires source control integration"));
}

FString UAssetManagementAPI::GetAssetPreview(const FString& AssetPath, const FString& OutputPath)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GetAssetPreview: asset='%s', output='%s'"), *AssetPath, *OutputPath);

	if (AssetPath.IsEmpty())
	{
		return ClawJson::MakeError(TEXT("AssetPath is required"));
	}

	FString LoadError;
	UObject* Asset = FAssetModifier::LoadAssetByPath(AssetPath, LoadError);
	if (!Asset)
	{
		return ClawJson::MakeError(FString::Printf(TEXT("Failed to load asset: %s"), *LoadError));
	}

	TArray<uint8> ImageData;
	FString Format = TEXT("png");
	int32 Resolution = 256;

	if (UTexture2D* Texture = Cast<UTexture2D>(Asset))
	{
		ImageData = ExportTextureData(Texture, Resolution, Format);
	}
	else
	{
		ImageData = RenderAssetThumbnail(Asset, Resolution, Format);
	}

	if (ImageData.Num() == 0)
	{
		return ClawJson::MakeError(TEXT("Failed to generate preview image"));
	}

	FString FilePath = SavePreviewToFile(ImageData, Format, OutputPath);
	if (FilePath.IsEmpty())
	{
		return ClawJson::MakeError(TEXT("Failed to save preview image"));
	}

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset_path"), AssetPath);
	Result->SetStringField(TEXT("file_path"), FilePath);
	Result->SetStringField(TEXT("format"), Format);
	Result->SetNumberField(TEXT("resolution"), Resolution);
	Result->SetNumberField(TEXT("file_size"), ImageData.Num());

	return ClawJson::ToString(Result);
}
