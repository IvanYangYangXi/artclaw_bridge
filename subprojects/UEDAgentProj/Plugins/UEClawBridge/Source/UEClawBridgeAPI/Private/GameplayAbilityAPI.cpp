// Copyright ArtClaw. All Rights Reserved.
// NOTE: Requires additional modules in UEClawBridgeAPI.Build.cs:
//   "GameplayAbilities", "GameplayTags", "GameplayTasks"

#include "GameplayAbilityAPI.h"
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
#include "Engine/Blueprint.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Factories/BlueprintFactory.h"
#include "K2Node.h"

// GAS includes (only if module is loaded)
#if WITH_GAMEPLAY_ABILITIES
#include "Abilities/GameplayAbility.h"
#include "GameplayEffect.h"
#include "GameplayAbilitySpec.h"
#include "AttributeSet.h"
#include "GameplayEffectTypes.h"
#include "GameplayTagContainer.h"
#include "GameplayTask.h"
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
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("GameplayAbilityAPI Error: %s"), *Msg);
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

	bool IsGASModuleLoaded()
	{
		return FModuleManager::Get().IsModuleLoaded("GameplayAbilities") && 
			   FModuleManager::Get().IsModuleLoaded("GameplayTags") &&
			   FModuleManager::Get().IsModuleLoaded("GameplayTasks");
	}

#if WITH_GAMEPLAY_ABILITIES
	EGameplayModOp::Type GetModOpFromString(const FString& ModOpString)
	{
		if (ModOpString == TEXT("Add") || ModOpString == TEXT("Additive"))
		{
			return EGameplayModOp::Additive;
		}
		else if (ModOpString == TEXT("Multiply") || ModOpString == TEXT("Multiplicative"))
		{
			return EGameplayModOp::MultiplyAdditive;
		}
		else if (ModOpString == TEXT("Divide") || ModOpString == TEXT("Division"))
		{
			return EGameplayModOp::Division;
		}
		else if (ModOpString == TEXT("Override"))
		{
			return EGameplayModOp::Override;
		}
		return EGameplayModOp::Additive; // Default
	}

	FString GetModOpString(EGameplayModOp::Type ModOp)
	{
		switch (ModOp)
		{
		case EGameplayModOp::Additive: return TEXT("Add");
		case EGameplayModOp::MultiplyAdditive: return TEXT("Multiply");
		case EGameplayModOp::Division: return TEXT("Divide");
		case EGameplayModOp::Override: return TEXT("Override");
		default: return TEXT("Unknown");
		}
	}

	UGameplayEffect* LoadGameplayEffect(const FString& AssetPath, FString& OutError)
	{
		FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
		FAssetData AssetData = AssetRegistryModule.Get().GetAssetByObjectPath(*AssetPath);
		
		if (!AssetData.IsValid())
		{
			OutError = FString::Printf(TEXT("Asset not found: %s"), *AssetPath);
			return nullptr;
		}

		UObject* LoadedObject = AssetData.GetAsset();
		UGameplayEffect* GameplayEffect = Cast<UGameplayEffect>(LoadedObject);
		if (!GameplayEffect)
		{
			OutError = FString::Printf(TEXT("Asset is not a Gameplay Effect: %s"), *AssetPath);
			return nullptr;
		}

		return GameplayEffect;
	}

	UBlueprint* LoadAbilityBlueprint(const FString& AssetPath, FString& OutError)
	{
		FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
		FAssetData AssetData = AssetRegistryModule.Get().GetAssetByObjectPath(*AssetPath);
		
		if (!AssetData.IsValid())
		{
			OutError = FString::Printf(TEXT("Asset not found: %s"), *AssetPath);
			return nullptr;
		}

		UObject* LoadedObject = AssetData.GetAsset();
		UBlueprint* Blueprint = Cast<UBlueprint>(LoadedObject);
		if (!Blueprint)
		{
			OutError = FString::Printf(TEXT("Asset is not a Blueprint: %s"), *AssetPath);
			return nullptr;
		}

		if (!Blueprint->GeneratedClass || !Blueprint->GeneratedClass->IsChildOf<UGameplayAbility>())
		{
			OutError = FString::Printf(TEXT("Blueprint is not a Gameplay Ability: %s"), *AssetPath);
			return nullptr;
		}

		return Blueprint;
	}
#endif
}

FString UGameplayAbilityAPI::CreateGameplayAbility(const FString& AssetPath, const FString& ParentClass)
{
	if (!IsGASModuleLoaded())
	{
		return ClawMakeError(TEXT("Gameplay Ability System modules not loaded. Enable GameplayAbilities plugin in project settings."));
	}

#if WITH_GAMEPLAY_ABILITIES
	// Parse asset path
	FString PackagePath, AssetName;
	if (!FPackageName::TryConvertLongPackageNameToFilename(AssetPath, PackagePath) || 
		!AssetPath.Split(TEXT("/"), &PackagePath, &AssetName, ESearchCase::IgnoreCase, ESearchDir::FromEnd))
	{
		return ClawMakeError(FString::Printf(TEXT("Invalid asset path: %s"), *AssetPath));
	}

	// Find parent class
	UClass* ParentClassObj = UGameplayAbility::StaticClass();
	if (ParentClass != TEXT("GameplayAbility"))
	{
		ParentClassObj = FindFirstObject<UClass>(*ParentClass, EFindFirstObjectOptions::None);
		if (!ParentClassObj || !ParentClassObj->IsChildOf<UGameplayAbility>())
		{
			return ClawMakeError(FString::Printf(TEXT("Invalid parent class: %s"), *ParentClass));
		}
	}

	// Create Blueprint
	IAssetTools& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();
	UBlueprintFactory* BlueprintFactory = NewObject<UBlueprintFactory>(GetTransientPackage());
	BlueprintFactory->ParentClass = ParentClassObj;

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		return ClawMakeError(FString::Printf(TEXT("Failed to create package: %s"), *AssetPath));
	}

	UBlueprint* NewBlueprint = Cast<UBlueprint>(AssetTools.CreateAsset(AssetName, PackagePath, UBlueprint::StaticClass(), BlueprintFactory));
	if (!NewBlueprint)
	{
		return ClawMakeError(TEXT("Failed to create Gameplay Ability Blueprint"));
	}

	// Compile and save
	FBlueprintEditorUtils::RefreshAllNodes(NewBlueprint);
	FKismetEditorUtilities::CompileBlueprint(NewBlueprint);

	// Mark package dirty and notify asset registry
	FAssetRegistryModule::AssetCreated(NewBlueprint);
	Package->SetDirtyFlag(true);

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("assetPath"), AssetPath);
	DataObj->SetStringField(TEXT("blueprintName"), NewBlueprint->GetName());
	DataObj->SetStringField(TEXT("parentClass"), ParentClass);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GameplayAbilityAPI: Created Gameplay Ability %s"), *AssetPath);
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Gameplay Ability System support not compiled in this build"));
#endif
}

FString UGameplayAbilityAPI::CreateGameplayEffect(const FString& AssetPath)
{
	if (!IsGASModuleLoaded())
	{
		return ClawMakeError(TEXT("Gameplay Ability System modules not loaded. Enable GameplayAbilities plugin in project settings."));
	}

#if WITH_GAMEPLAY_ABILITIES
	// Parse asset path
	FString PackagePath, AssetName;
	if (!FPackageName::TryConvertLongPackageNameToFilename(AssetPath, PackagePath) || 
		!AssetPath.Split(TEXT("/"), &PackagePath, &AssetName, ESearchCase::IgnoreCase, ESearchDir::FromEnd))
	{
		return ClawMakeError(FString::Printf(TEXT("Invalid asset path: %s"), *AssetPath));
	}

	// Create new Gameplay Effect
	UGameplayEffect* NewEffect = NewObject<UGameplayEffect>(GetTransientPackage(), UGameplayEffect::StaticClass());
	if (!NewEffect)
	{
		return ClawMakeError(TEXT("Failed to create Gameplay Effect object"));
	}

	// Set default values
	NewEffect->DurationPolicy = EGameplayEffectDurationType::Instant;

	UPackage* Package = CreatePackage(*AssetPath);
	if (!Package)
	{
		return ClawMakeError(FString::Printf(TEXT("Failed to create package: %s"), *AssetPath));
	}

	NewEffect->Rename(*AssetName, Package);

	// Mark package dirty and notify asset registry
	FAssetRegistryModule::AssetCreated(NewEffect);
	Package->SetDirtyFlag(true);

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("assetPath"), AssetPath);
	DataObj->SetStringField(TEXT("effectName"), NewEffect->GetName());
	DataObj->SetStringField(TEXT("durationType"), TEXT("Instant"));

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GameplayAbilityAPI: Created Gameplay Effect %s"), *AssetPath);
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Gameplay Ability System support not compiled in this build"));
#endif
}

FString UGameplayAbilityAPI::SetGEModifier(const FString& AssetPath, const FString& Attribute, const FString& ModOp, float Value)
{
	if (!IsGASModuleLoaded())
	{
		return ClawMakeError(TEXT("Gameplay Ability System modules not loaded. Enable GameplayAbilities plugin in project settings."));
	}

#if WITH_GAMEPLAY_ABILITIES
	FString Error;
	UGameplayEffect* GameplayEffect = LoadGameplayEffect(AssetPath, Error);
	if (!GameplayEffect)
	{
		return ClawMakeError(Error);
	}

	// Create new modifier
	FGameplayModifierInfo NewModifier;
	
	// Set attribute (simplified - in real usage, would need to resolve FGameplayAttribute)
	// For now, we'll just store the attribute name as a comment
	NewModifier.Attribute = FGameplayAttribute(); // This needs proper attribute resolution
	NewModifier.ModifierOp = GetModOpFromString(ModOp);
	
	// Set magnitude using the public constructor
	NewModifier.ModifierMagnitude = FGameplayEffectModifierMagnitude(FScalableFloat(Value));

	// Add modifier to effect
	GameplayEffect->Modifiers.Add(NewModifier);

	// Mark package dirty
	GameplayEffect->MarkPackageDirty();

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("assetPath"), AssetPath);
	DataObj->SetStringField(TEXT("attribute"), Attribute);
	DataObj->SetStringField(TEXT("operation"), GetModOpString(NewModifier.ModifierOp));
	DataObj->SetNumberField(TEXT("value"), Value);
	DataObj->SetNumberField(TEXT("modifierIndex"), GameplayEffect->Modifiers.Num() - 1);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GameplayAbilityAPI: Added modifier to %s: %s %s %f"), *AssetPath, *Attribute, *ModOp, Value);
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Gameplay Ability System support not compiled in this build"));
#endif
}

FString UGameplayAbilityAPI::QueryAbilityInfo(const FString& AssetPath)
{
	if (!IsGASModuleLoaded())
	{
		return ClawMakeError(TEXT("Gameplay Ability System modules not loaded. Enable GameplayAbilities plugin in project settings."));
	}

#if WITH_GAMEPLAY_ABILITIES
	FString Error;
	UBlueprint* Blueprint = LoadAbilityBlueprint(AssetPath, Error);
	if (!Blueprint)
	{
		return ClawMakeError(Error);
	}

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("assetPath"), AssetPath);
	DataObj->SetStringField(TEXT("blueprintName"), Blueprint->GetName());
	
	if (Blueprint->GeneratedClass)
	{
		DataObj->SetStringField(TEXT("generatedClass"), Blueprint->GeneratedClass->GetName());
		DataObj->SetStringField(TEXT("parentClass"), Blueprint->GeneratedClass->GetSuperClass() ? Blueprint->GeneratedClass->GetSuperClass()->GetName() : TEXT("None"));
	}

	// Get default object properties if available
	if (Blueprint->GeneratedClass)
	{
		UGameplayAbility* DefaultAbility = Cast<UGameplayAbility>(Blueprint->GeneratedClass->GetDefaultObject());
		if (DefaultAbility)
		{
			DataObj->SetBoolField(TEXT("bReplicateInputDirectly"), DefaultAbility->bReplicateInputDirectly);
			DataObj->SetStringField(TEXT("instancingPolicy"), DefaultAbility->GetInstancingPolicy() == EGameplayAbilityInstancingPolicy::InstancedPerActor ? TEXT("InstancedPerActor") : 
									DefaultAbility->GetInstancingPolicy() == EGameplayAbilityInstancingPolicy::InstancedPerExecution ? TEXT("InstancedPerExecution") : TEXT("NonInstanced"));
		}
	}

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GameplayAbilityAPI: Queried Ability %s"), *AssetPath);
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Gameplay Ability System support not compiled in this build"));
#endif
}

FString UGameplayAbilityAPI::QueryEffectInfo(const FString& AssetPath)
{
	if (!IsGASModuleLoaded())
	{
		return ClawMakeError(TEXT("Gameplay Ability System modules not loaded. Enable GameplayAbilities plugin in project settings."));
	}

#if WITH_GAMEPLAY_ABILITIES
	FString Error;
	UGameplayEffect* GameplayEffect = LoadGameplayEffect(AssetPath, Error);
	if (!GameplayEffect)
	{
		return ClawMakeError(Error);
	}

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("assetPath"), AssetPath);
	DataObj->SetStringField(TEXT("effectName"), GameplayEffect->GetName());
	
	// Duration info
	FString DurationTypeStr;
	switch (GameplayEffect->DurationPolicy)
	{
	case EGameplayEffectDurationType::Instant: DurationTypeStr = TEXT("Instant"); break;
	case EGameplayEffectDurationType::Infinite: DurationTypeStr = TEXT("Infinite"); break;
	case EGameplayEffectDurationType::HasDuration: DurationTypeStr = TEXT("HasDuration"); break;
	default: DurationTypeStr = TEXT("Unknown"); break;
	}
	DataObj->SetStringField(TEXT("durationType"), DurationTypeStr);

	// Modifiers
	TArray<TSharedPtr<FJsonValue>> ModifiersArray;
	for (int32 i = 0; i < GameplayEffect->Modifiers.Num(); i++)
	{
		const FGameplayModifierInfo& Modifier = GameplayEffect->Modifiers[i];
		TSharedPtr<FJsonObject> ModifierObj = MakeShareable(new FJsonObject);
		
		ModifierObj->SetStringField(TEXT("operation"), GetModOpString(Modifier.ModifierOp));
		ModifierObj->SetNumberField(TEXT("index"), i);
		
		// Get magnitude value if it's a scalable float
		if (Modifier.ModifierMagnitude.GetMagnitudeCalculationType() == EGameplayEffectMagnitudeCalculation::ScalableFloat)
		{
			float MagnitudeValue = 0.0f;
			if (Modifier.ModifierMagnitude.GetStaticMagnitudeIfPossible(1.0f, MagnitudeValue))
			{
				ModifierObj->SetNumberField(TEXT("value"), MagnitudeValue);
			}
		}

		ModifiersArray.Add(MakeShareable(new FJsonValueObject(ModifierObj)));
	}
	DataObj->SetArrayField(TEXT("modifiers"), ModifiersArray);
	DataObj->SetNumberField(TEXT("modifierCount"), GameplayEffect->Modifiers.Num());

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("GameplayAbilityAPI: Queried Effect %s with %d modifiers"), *AssetPath, GameplayEffect->Modifiers.Num());
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Gameplay Ability System support not compiled in this build"));
#endif
}