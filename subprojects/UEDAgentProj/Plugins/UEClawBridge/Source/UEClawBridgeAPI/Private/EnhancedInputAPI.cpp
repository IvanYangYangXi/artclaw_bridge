// Copyright ArtClaw. All Rights Reserved.
// NOTE: Requires additional modules in UEClawBridgeAPI.Build.cs:
//   "EnhancedInput"

#include "EnhancedInputAPI.h"
#include "UEClawBridgeAPI.h"
#include "Utils/AssetModifier.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Modules/ModuleManager.h"
#include "Engine/AssetManager.h"
#include "AssetToolsModule.h"
#include "IAssetTools.h"
#include "Factories/Factory.h"

// Enhanced Input includes (only if module is loaded)
#if WITH_ENHANCED_INPUT
#include "InputMappingContext.h"
#include "InputAction.h"
#include "EnhancedInputModule.h"
#include "InputModifiers.h"
#include "InputTriggers.h"
#include "PlayerMappableInputConfig.h"
#endif

namespace
{
	FString ClawJsonToString(const TSharedPtr<FJsonObject>& Obj)
	{
		FString Output;
		auto Writer = TJsonWriterFactory<>::Create(&Output);
		FJsonSerializer::Serialize(Obj.ToSharedRef(), Writer);
		return Output;
	}

	FString ClawMakeError(const FString& Msg)
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("EnhancedInputAPI Error: %s"), *Msg);
		TSharedPtr<FJsonObject> Obj = MakeShareable(new FJsonObject);
		Obj->SetBoolField(TEXT("success"), false);
		Obj->SetStringField(TEXT("error"), Msg);
		return ClawJsonToString(Obj);
	}

	FString ClawMakeSuccess(const TSharedPtr<FJsonObject>& Data = nullptr)
	{
		TSharedPtr<FJsonObject> Obj = MakeShareable(new FJsonObject);
		Obj->SetBoolField(TEXT("success"), true);
		if (Data.IsValid())
		{
			Obj->SetObjectField(TEXT("data"), Data);
		}
		return ClawJsonToString(Obj);
	}

	bool IsEnhancedInputModuleLoaded()
	{
		return FModuleManager::Get().IsModuleLoaded("EnhancedInput");
	}

#if WITH_ENHANCED_INPUT
	EInputActionValueType GetValueTypeFromString(const FString& ValueTypeString)
	{
		if (ValueTypeString == TEXT("Bool") || ValueTypeString == TEXT("Boolean"))
		{
			return EInputActionValueType::Boolean;
		}
		else if (ValueTypeString == TEXT("Axis1D") || ValueTypeString == TEXT("Float"))
		{
			return EInputActionValueType::Axis1D;
		}
		else if (ValueTypeString == TEXT("Axis2D") || ValueTypeString == TEXT("Vector2D"))
		{
			return EInputActionValueType::Axis2D;
		}
		else if (ValueTypeString == TEXT("Axis3D") || ValueTypeString == TEXT("Vector"))
		{
			return EInputActionValueType::Axis3D;
		}
		return EInputActionValueType::Boolean; // Default
	}

	FString GetValueTypeString(EInputActionValueType ValueType)
	{
		switch (ValueType)
		{
		case EInputActionValueType::Boolean: return TEXT("Bool");
		case EInputActionValueType::Axis1D: return TEXT("Axis1D");
		case EInputActionValueType::Axis2D: return TEXT("Axis2D");
		case EInputActionValueType::Axis3D: return TEXT("Axis3D");
		default: return TEXT("Unknown");
		}
	}

	UInputMappingContext* LoadInputMappingContext(const FString& AssetPath, FString& OutError)
	{
		FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
		FAssetData AssetData = AssetRegistryModule.Get().GetAssetByObjectPath(*AssetPath);
		
		if (!AssetData.IsValid())
		{
			OutError = FString::Printf(TEXT("Asset not found: %s"), *AssetPath);
			return nullptr;
		}

		UObject* LoadedObject = AssetData.GetAsset();
		UInputMappingContext* Context = Cast<UInputMappingContext>(LoadedObject);
		if (!Context)
		{
			OutError = FString::Printf(TEXT("Asset is not an Input Mapping Context: %s"), *AssetPath);
			return nullptr;
		}

		return Context;
	}

	UInputAction* LoadInputAction(const FString& AssetPath, FString& OutError)
	{
		FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
		FAssetData AssetData = AssetRegistryModule.Get().GetAssetByObjectPath(*AssetPath);
		
		if (!AssetData.IsValid())
		{
			OutError = FString::Printf(TEXT("Asset not found: %s"), *AssetPath);
			return nullptr;
		}

		UObject* LoadedObject = AssetData.GetAsset();
		UInputAction* Action = Cast<UInputAction>(LoadedObject);
		if (!Action)
		{
			OutError = FString::Printf(TEXT("Asset is not an Input Action: %s"), *AssetPath);
			return nullptr;
		}

		return Action;
	}

	FKey GetKeyFromString(const FString& KeyString)
	{
		return FKey(*KeyString);
	}
#endif
}

FString UEnhancedInputAPI::QueryInputMappingContext(const FString& AssetPath)
{
	if (!IsEnhancedInputModuleLoaded())
	{
		return ClawMakeError(TEXT("EnhancedInput module not loaded. Enable EnhancedInput plugin in project settings."));
	}

#if WITH_ENHANCED_INPUT
	FString Error;
	UInputMappingContext* Context = LoadInputMappingContext(AssetPath, Error);
	if (!Context)
	{
		return ClawMakeError(Error);
	}

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("assetPath"), AssetPath);
	DataObj->SetStringField(TEXT("contextName"), Context->GetName());
	DataObj->SetStringField(TEXT("description"), TEXT(""));

	// Get mappings
	TArray<TSharedPtr<FJsonValue>> MappingsArray;
	const TArray<FEnhancedActionKeyMapping>& Mappings = Context->GetMappings();

	for (const FEnhancedActionKeyMapping& Mapping : Mappings)
	{
		TSharedPtr<FJsonObject> MappingObj = MakeShareable(new FJsonObject);
		
		if (Mapping.Action)
		{
			MappingObj->SetStringField(TEXT("actionName"), Mapping.Action->GetName());
			MappingObj->SetStringField(TEXT("actionPath"), Mapping.Action->GetPathName());
		}

		MappingObj->SetStringField(TEXT("key"), Mapping.Key.GetFName().ToString());
		
		// Get modifiers
		TArray<TSharedPtr<FJsonValue>> ModifiersArray;
		for (const UInputModifier* Modifier : Mapping.Modifiers)
		{
			if (Modifier)
			{
				TSharedPtr<FJsonObject> ModifierObj = MakeShareable(new FJsonObject);
				ModifierObj->SetStringField(TEXT("class"), Modifier->GetClass()->GetName());
				ModifiersArray.Add(MakeShareable(new FJsonValueObject(ModifierObj)));
			}
		}
		MappingObj->SetArrayField(TEXT("modifiers"), ModifiersArray);

		// Get triggers
		TArray<TSharedPtr<FJsonValue>> TriggersArray;
		for (const UInputTrigger* Trigger : Mapping.Triggers)
		{
			if (Trigger)
			{
				TSharedPtr<FJsonObject> TriggerObj = MakeShareable(new FJsonObject);
				TriggerObj->SetStringField(TEXT("class"), Trigger->GetClass()->GetName());
				TriggersArray.Add(MakeShareable(new FJsonValueObject(TriggerObj)));
			}
		}
		MappingObj->SetArrayField(TEXT("triggers"), TriggersArray);

		MappingsArray.Add(MakeShareable(new FJsonValueObject(MappingObj)));
	}
	
	DataObj->SetArrayField(TEXT("mappings"), MappingsArray);
	DataObj->SetNumberField(TEXT("mappingCount"), Mappings.Num());

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("EnhancedInputAPI: Queried context %s with %d mappings"), *AssetPath, Mappings.Num());
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Enhanced Input support not compiled in this build"));
#endif
}

FString UEnhancedInputAPI::CreateInputAction(const FString& AssetPath, const FString& ValueType)
{
	if (!IsEnhancedInputModuleLoaded())
	{
		return ClawMakeError(TEXT("EnhancedInput module not loaded. Enable EnhancedInput plugin in project settings."));
	}

#if WITH_ENHANCED_INPUT
	// Parse asset path
	FString PackagePath, AssetName;
	if (!FPackageName::TryConvertLongPackageNameToFilename(AssetPath, PackagePath) || 
		!AssetPath.Split(TEXT("/"), &PackagePath, &AssetName, ESearchCase::IgnoreCase, ESearchDir::FromEnd))
	{
		return ClawMakeError(FString::Printf(TEXT("Invalid asset path: %s"), *AssetPath));
	}

	// Create new Input Action
	EInputActionValueType ActionValueType = GetValueTypeFromString(ValueType);
	
	UInputAction* NewAction = NewObject<UInputAction>(GetTransientPackage(), UInputAction::StaticClass());
	if (!NewAction)
	{
		return ClawMakeError(TEXT("Failed to create Input Action object"));
	}

	NewAction->ValueType = ActionValueType;

	// Try to save the asset
	FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
	IAssetTools& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		return ClawMakeError(FString::Printf(TEXT("Failed to create package: %s"), *AssetPath));
	}

	NewAction->Rename(*AssetName, Package);

	// Mark package dirty and notify asset registry
	FAssetRegistryModule::AssetCreated(NewAction);
	Package->SetDirtyFlag(true);

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("assetPath"), AssetPath);
	DataObj->SetStringField(TEXT("actionName"), NewAction->GetName());
	DataObj->SetStringField(TEXT("valueType"), GetValueTypeString(ActionValueType));

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("EnhancedInputAPI: Created Input Action %s with value type %s"), *AssetPath, *ValueType);
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Enhanced Input support not compiled in this build"));
#endif
}

FString UEnhancedInputAPI::AddInputMapping(const FString& ContextPath, const FString& ActionPath, const FString& Key, const FString& ModifiersJson)
{
	if (!IsEnhancedInputModuleLoaded())
	{
		return ClawMakeError(TEXT("EnhancedInput module not loaded. Enable EnhancedInput plugin in project settings."));
	}

#if WITH_ENHANCED_INPUT
	FString Error;
	UInputMappingContext* Context = LoadInputMappingContext(ContextPath, Error);
	if (!Context)
	{
		return ClawMakeError(Error);
	}

	UInputAction* Action = LoadInputAction(ActionPath, Error);
	if (!Action)
	{
		return ClawMakeError(Error);
	}

	FKey InputKey = GetKeyFromString(Key);
	if (!InputKey.IsValid())
	{
		return ClawMakeError(FString::Printf(TEXT("Invalid key: %s"), *Key));
	}

	// Create new mapping
	FEnhancedActionKeyMapping& NewMapping = Context->MapKey(Action, InputKey);

	// Parse and add modifiers if provided
	if (!ModifiersJson.IsEmpty() && ModifiersJson != TEXT(""))
	{
		TArray<TSharedPtr<FJsonValue>> ModifierValues;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ModifiersJson);
		if (FJsonSerializer::Deserialize(Reader, ModifierValues))
		{
			for (const TSharedPtr<FJsonValue>& ModifierValue : ModifierValues)
			{
				FString ModifierClassName = ModifierValue->AsString();
				UClass* ModifierClass = FindFirstObject<UClass>(*ModifierClassName, EFindFirstObjectOptions::None);
				if (ModifierClass && ModifierClass->IsChildOf<UInputModifier>())
				{
					UInputModifier* Modifier = NewObject<UInputModifier>(Context, ModifierClass);
					if (Modifier)
					{
						NewMapping.Modifiers.Add(Modifier);
					}
				}
			}
		}
	}

	// Mark package dirty
	Context->MarkPackageDirty();

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("contextPath"), ContextPath);
	DataObj->SetStringField(TEXT("actionPath"), ActionPath);
	DataObj->SetStringField(TEXT("key"), Key);
	DataObj->SetNumberField(TEXT("mappingIndex"), Context->GetMappings().Num() - 1);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("EnhancedInputAPI: Added mapping %s -> %s in context %s"), *Key, *ActionPath, *ContextPath);
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Enhanced Input support not compiled in this build"));
#endif
}

FString UEnhancedInputAPI::QueryInputAction(const FString& AssetPath)
{
	if (!IsEnhancedInputModuleLoaded())
	{
		return ClawMakeError(TEXT("EnhancedInput module not loaded. Enable EnhancedInput plugin in project settings."));
	}

#if WITH_ENHANCED_INPUT
	FString Error;
	UInputAction* Action = LoadInputAction(AssetPath, Error);
	if (!Action)
	{
		return ClawMakeError(Error);
	}

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("assetPath"), AssetPath);
	DataObj->SetStringField(TEXT("actionName"), Action->GetName());
	DataObj->SetStringField(TEXT("valueType"), GetValueTypeString(Action->ValueType));
	DataObj->SetBoolField(TEXT("bConsumeInput"), Action->bConsumeInput);
	DataObj->SetBoolField(TEXT("bTriggerWhenPaused"), Action->bTriggerWhenPaused);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("EnhancedInputAPI: Queried Input Action %s"), *AssetPath);
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Enhanced Input support not compiled in this build"));
#endif
}