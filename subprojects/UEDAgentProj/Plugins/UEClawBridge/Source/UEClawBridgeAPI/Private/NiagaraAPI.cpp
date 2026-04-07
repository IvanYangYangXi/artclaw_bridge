// Copyright ArtClaw. All Rights Reserved.
// NOTE: Requires additional modules in UEClawBridgeAPI.Build.cs:
//   "Niagara", "NiagaraEditor"

#include "NiagaraAPI.h"
#include "UEClawBridgeAPI.h"
#include "Utils/PropertySerializer.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Modules/ModuleManager.h"

// Niagara includes (only if module is loaded)
#if WITH_NIAGARA
#include "NiagaraSystem.h"
#include "NiagaraEmitter.h"
#include "NiagaraScript.h"
#include "NiagaraParameterStore.h"
#include "NiagaraScriptSource.h"
#include "NiagaraNodeOutput.h"
#include "NiagaraGraph.h"
#include "NiagaraStackEditorData.h"
#include "ViewModels/Stack/NiagaraStackViewModel.h"
#include "ViewModels/NiagaraSystemViewModel.h"
#include "ViewModels/NiagaraEmitterViewModel.h"
#include "NiagaraTypes.h"
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
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("NiagaraAPI Error: %s"), *Msg);
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

	bool IsNiagaraModuleLoaded()
	{
		return FModuleManager::Get().IsModuleLoaded("Niagara") && 
			   FModuleManager::Get().IsModuleLoaded("NiagaraEditor");
	}

#if WITH_NIAGARA
	UNiagaraSystem* LoadNiagaraSystem(const FString& AssetPath, FString& OutError)
	{
		FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
		FAssetData AssetData = AssetRegistryModule.Get().GetAssetByObjectPath(*AssetPath);
		
		if (!AssetData.IsValid())
		{
			OutError = FString::Printf(TEXT("Asset not found: %s"), *AssetPath);
			return nullptr;
		}

		UObject* LoadedObject = AssetData.GetAsset();
		UNiagaraSystem* NiagaraSystem = Cast<UNiagaraSystem>(LoadedObject);
		if (!NiagaraSystem)
		{
			OutError = FString::Printf(TEXT("Asset is not a Niagara System: %s"), *AssetPath);
			return nullptr;
		}

		return NiagaraSystem;
	}

	TSharedPtr<FJsonObject> SerializeNiagaraVariable(const FNiagaraVariable& Variable)
	{
		TSharedPtr<FJsonObject> VarObj = MakeShareable(new FJsonObject);
		VarObj->SetStringField(TEXT("name"), Variable.GetName().ToString());
		VarObj->SetStringField(TEXT("type"), Variable.GetType().GetName());
		
		// Serialize variable value based on type
		if (Variable.IsDataAllocated())
		{
			if (Variable.GetType() == FNiagaraTypeDefinition::GetFloatDef())
			{
				float Value = Variable.GetValue<float>();
				VarObj->SetNumberField(TEXT("value"), Value);
			}
			else if (Variable.GetType() == FNiagaraTypeDefinition::GetIntDef())
			{
				int32 Value = Variable.GetValue<int32>();
				VarObj->SetNumberField(TEXT("value"), Value);
			}
			else if (Variable.GetType() == FNiagaraTypeDefinition::GetBoolDef())
			{
				bool Value = Variable.GetValue<bool>();
				VarObj->SetBoolField(TEXT("value"), Value);
			}
			else if (Variable.GetType() == FNiagaraTypeDefinition::GetVec3Def())
			{
				FVector Value = Variable.GetValue<FVector>();
				TArray<TSharedPtr<FJsonValue>> VecArray;
				VecArray.Add(MakeShareable(new FJsonValueNumber(Value.X)));
				VecArray.Add(MakeShareable(new FJsonValueNumber(Value.Y)));
				VecArray.Add(MakeShareable(new FJsonValueNumber(Value.Z)));
				VarObj->SetArrayField(TEXT("value"), VecArray);
			}
			else
			{
				VarObj->SetStringField(TEXT("value"), TEXT("(complex type)"));
			}
		}
		else
		{
			VarObj->SetStringField(TEXT("value"), TEXT("(no data)"));
		}

		return VarObj;
	}
#endif
}

FString UNiagaraAPI::QueryNiagaraSystem(const FString& AssetPath)
{
	if (!IsNiagaraModuleLoaded())
	{
		return ClawMakeError(TEXT("Niagara module not loaded. Enable Niagara plugin in project settings."));
	}

#if WITH_NIAGARA
	FString Error;
	UNiagaraSystem* NiagaraSystem = LoadNiagaraSystem(AssetPath, Error);
	if (!NiagaraSystem)
	{
		return ClawMakeError(Error);
	}

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("assetPath"), AssetPath);
	DataObj->SetStringField(TEXT("systemName"), NiagaraSystem->GetName());
	
	// Get system user parameters
	const FNiagaraParameterStore& UserParameters = NiagaraSystem->GetExposedParameters();
	TArray<TSharedPtr<FJsonValue>> UserParamsArray;
	
	TArray<FNiagaraVariable> Variables;
	UserParameters.GetParameters(Variables);
	
	for (const FNiagaraVariable& Variable : Variables)
	{
		UserParamsArray.Add(MakeShareable(new FJsonValueObject(SerializeNiagaraVariable(Variable))));
	}
	
	DataObj->SetArrayField(TEXT("userParameters"), UserParamsArray);

	// Get emitters
	TArray<TSharedPtr<FJsonValue>> EmittersArray;
	const TArray<FNiagaraEmitterHandle>& EmitterHandles = NiagaraSystem->GetEmitterHandles();
	
	for (const FNiagaraEmitterHandle& Handle : EmitterHandles)
	{
		if (Handle.GetEmitterData())
		{
			TSharedPtr<FJsonObject> EmitterObj = MakeShareable(new FJsonObject);
			EmitterObj->SetStringField(TEXT("name"), Handle.GetName().ToString());
			EmitterObj->SetStringField(TEXT("uniqueName"), Handle.GetUniqueInstanceName());
			EmitterObj->SetBoolField(TEXT("enabled"), Handle.GetIsEnabled());

			EmittersArray.Add(MakeShareable(new FJsonValueObject(EmitterObj)));
		}
	}
	
	DataObj->SetArrayField(TEXT("emitters"), EmittersArray);
	
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("NiagaraAPI: Queried system %s with %d emitters"), *AssetPath, EmitterHandles.Num());
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Niagara support not compiled in this build"));
#endif
}

FString UNiagaraAPI::SetNiagaraParameter(const FString& AssetPath, const FString& ParameterName, const FString& ValueJson)
{
	if (!IsNiagaraModuleLoaded())
	{
		return ClawMakeError(TEXT("Niagara module not loaded. Enable Niagara plugin in project settings."));
	}

#if WITH_NIAGARA
	FString Error;
	UNiagaraSystem* NiagaraSystem = LoadNiagaraSystem(AssetPath, Error);
	if (!NiagaraSystem)
	{
		return ClawMakeError(Error);
	}

	// Parse JSON value
	TSharedPtr<FJsonValue> JsonValue;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ValueJson);
	if (!FJsonSerializer::Deserialize(Reader, JsonValue) || !JsonValue.IsValid())
	{
		return ClawMakeError(FString::Printf(TEXT("Invalid JSON value: %s"), *ValueJson));
	}

	// Find parameter in exposed parameters
	FNiagaraParameterStore& UserParameters = NiagaraSystem->GetExposedParameters();
	TArray<FNiagaraVariable> Variables;
	UserParameters.GetParameters(Variables);

	FNiagaraVariable* FoundVar = Variables.FindByPredicate([&ParameterName](const FNiagaraVariable& Var) {
		return Var.GetName().ToString() == ParameterName;
	});

	if (!FoundVar)
	{
		return ClawMakeError(FString::Printf(TEXT("Parameter '%s' not found in system"), *ParameterName));
	}

	// Set value based on type
	bool bSuccess = false;
	if (FoundVar->GetType() == FNiagaraTypeDefinition::GetFloatDef())
	{
		if (JsonValue->Type == EJson::Number)
		{
			float Value = JsonValue->AsNumber();
			UserParameters.SetParameterValue(Value, *FoundVar);
			bSuccess = true;
		}
	}
	else if (FoundVar->GetType() == FNiagaraTypeDefinition::GetIntDef())
	{
		if (JsonValue->Type == EJson::Number)
		{
			int32 Value = (int32)JsonValue->AsNumber();
			UserParameters.SetParameterValue(Value, *FoundVar);
			bSuccess = true;
		}
	}
	else if (FoundVar->GetType() == FNiagaraTypeDefinition::GetBoolDef())
	{
		if (JsonValue->Type == EJson::Boolean)
		{
			bool Value = JsonValue->AsBool();
			UserParameters.SetParameterValue(Value, *FoundVar);
			bSuccess = true;
		}
	}
	else if (FoundVar->GetType() == FNiagaraTypeDefinition::GetVec3Def())
	{
		if (JsonValue->Type == EJson::Array)
		{
			const TArray<TSharedPtr<FJsonValue>>& Array = JsonValue->AsArray();
			if (Array.Num() == 3)
			{
				FVector Value(Array[0]->AsNumber(), Array[1]->AsNumber(), Array[2]->AsNumber());
				UserParameters.SetParameterValue(Value, *FoundVar);
				bSuccess = true;
			}
		}
	}

	if (!bSuccess)
	{
		return ClawMakeError(FString::Printf(TEXT("Failed to set parameter '%s' - type mismatch or invalid value"), *ParameterName));
	}

	// Mark package dirty
	NiagaraSystem->MarkPackageDirty();
	
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("NiagaraAPI: Set parameter %s in system %s"), *ParameterName, *AssetPath);
	return ClawMakeSuccess();
#else
	return ClawMakeError(TEXT("Niagara support not compiled in this build"));
#endif
}

FString UNiagaraAPI::QueryNiagaraEmitter(const FString& AssetPath, const FString& EmitterName)
{
	if (!IsNiagaraModuleLoaded())
	{
		return ClawMakeError(TEXT("Niagara module not loaded. Enable Niagara plugin in project settings."));
	}

#if WITH_NIAGARA
	FString Error;
	UNiagaraSystem* NiagaraSystem = LoadNiagaraSystem(AssetPath, Error);
	if (!NiagaraSystem)
	{
		return ClawMakeError(Error);
	}

	// Find emitter by name
	const TArray<FNiagaraEmitterHandle>& EmitterHandles = NiagaraSystem->GetEmitterHandles();
	const FNiagaraEmitterHandle* FoundHandle = EmitterHandles.FindByPredicate([&EmitterName](const FNiagaraEmitterHandle& Handle) {
		return Handle.GetName().ToString() == EmitterName || Handle.GetUniqueInstanceName() == EmitterName;
	});

	if (!FoundHandle || !FoundHandle->GetEmitterData())
	{
		return ClawMakeError(FString::Printf(TEXT("Emitter '%s' not found in system"), *EmitterName));
	}

	TSharedPtr<FJsonObject> DataObj = MakeShareable(new FJsonObject);
	DataObj->SetStringField(TEXT("name"), FoundHandle->GetName().ToString());
	DataObj->SetStringField(TEXT("uniqueName"), FoundHandle->GetUniqueInstanceName());
	DataObj->SetBoolField(TEXT("enabled"), FoundHandle->GetIsEnabled());

	const FVersionedNiagaraEmitterData* EmitterData = FoundHandle->GetEmitterData();
	if (EmitterData)
	{
		// Get emitter spawn script info
		if (EmitterData->SpawnScriptProps.Script)
		{
			TSharedPtr<FJsonObject> SpawnScriptObj = MakeShareable(new FJsonObject);
			SpawnScriptObj->SetStringField(TEXT("scriptName"), EmitterData->SpawnScriptProps.Script->GetName());
			DataObj->SetObjectField(TEXT("spawnScript"), SpawnScriptObj);
		}

		// Get emitter update script info
		if (EmitterData->UpdateScriptProps.Script)
		{
			TSharedPtr<FJsonObject> UpdateScriptObj = MakeShareable(new FJsonObject);
			UpdateScriptObj->SetStringField(TEXT("scriptName"), EmitterData->UpdateScriptProps.Script->GetName());
			DataObj->SetObjectField(TEXT("updateScript"), UpdateScriptObj);
		}

		// Get renderer modules
		TArray<TSharedPtr<FJsonValue>> RenderersArray;
		for (const UNiagaraRendererProperties* Renderer : EmitterData->GetRenderers())
		{
			if (Renderer)
			{
				TSharedPtr<FJsonObject> RendererObj = MakeShareable(new FJsonObject);
				RendererObj->SetStringField(TEXT("type"), Renderer->GetClass()->GetName());
				RendererObj->SetBoolField(TEXT("enabled"), Renderer->GetIsEnabled());
				RenderersArray.Add(MakeShareable(new FJsonValueObject(RendererObj)));
			}
		}
		DataObj->SetArrayField(TEXT("renderers"), RenderersArray);
	}

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("NiagaraAPI: Queried emitter %s in system %s"), *EmitterName, *AssetPath);
	return ClawMakeSuccess(DataObj);
#else
	return ClawMakeError(TEXT("Niagara support not compiled in this build"));
#endif
}

FString UNiagaraAPI::AddNiagaraModule(const FString& AssetPath, const FString& EmitterName, const FString& ModuleClass, const FString& StackGroup)
{
	if (!IsNiagaraModuleLoaded())
	{
		return ClawMakeError(TEXT("Niagara module not loaded. Enable Niagara plugin in project settings."));
	}

#if WITH_NIAGARA
	// This is a complex operation that typically requires the Niagara Editor UI
	// For now, return a placeholder implementation
	return ClawMakeError(TEXT("AddNiagaraModule is not yet fully implemented - requires deep Niagara Editor integration"));
#else
	return ClawMakeError(TEXT("Niagara support not compiled in this build"));
#endif
}