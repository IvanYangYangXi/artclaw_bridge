// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "ActorReflectionAPI.h"
#include "UEClawBridgeAPI.h"
#include "Utils/PropertySerializer.h"
#include "Utils/AssetModifier.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Components/ActorComponent.h"
#include "EngineUtils.h"
#include "UObject/UnrealType.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

#if WITH_EDITOR
#include "Editor.h"
#include "ScopedTransaction.h"
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
		TSharedPtr<FJsonObject> Obj = MakeShareable(new FJsonObject);
		Obj->SetBoolField(TEXT("success"), false);
		Obj->SetStringField(TEXT("error"), Msg);
		return ClawJsonToString(Obj);
	}

	TSharedPtr<FJsonObject> ParseJsonArgsString(const FString& ArgsJson, FString& OutError)
	{
		if (ArgsJson.IsEmpty())
		{
			return MakeShareable(new FJsonObject); // Empty but valid
		}

		TSharedPtr<FJsonObject> JsonObject;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ArgsJson);
		
		if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
		{
			OutError = TEXT("Invalid JSON format in arguments");
			return nullptr;
		}

		return JsonObject;
	}
}

UWorld* UActorReflectionAPI::FindWorldByType(const FString& WorldType)
{
	if (WorldType.IsEmpty() || WorldType.Equals(TEXT("editor"), ESearchCase::IgnoreCase))
	{
#if WITH_EDITOR
		if (GEditor && GEditor->GetEditorWorldContext().World())
		{
			return GEditor->GetEditorWorldContext().World();
		}
#endif
	}
	else if (WorldType.Equals(TEXT("pie"), ESearchCase::IgnoreCase))
	{
#if WITH_EDITOR
		if (GEditor)
		{
			for (const FWorldContext& Context : GEditor->GetWorldContexts())
			{
				if (Context.WorldType == EWorldType::PIE && Context.World())
				{
					return Context.World();
				}
			}
		}
#endif
	}
	else if (WorldType.Equals(TEXT("game"), ESearchCase::IgnoreCase))
	{
		for (const FWorldContext& Context : GEngine->GetWorldContexts())
		{
			if (Context.WorldType == EWorldType::Game && Context.World())
			{
				return Context.World();
			}
		}
	}

	// Fallback: return first available world
	for (const FWorldContext& Context : GEngine->GetWorldContexts())
	{
		if (Context.World())
		{
			return Context.World();
		}
	}

	return nullptr;
}

bool UActorReflectionAPI::MatchesWildcard(const FString& Text, const FString& Pattern)
{
	if (!Pattern.Contains(TEXT("*")))
	{
		return Text.Equals(Pattern, ESearchCase::IgnoreCase);
	}

	// Simple wildcard matching
	FString Left, Right;
	if (Pattern.Split(TEXT("*"), &Left, &Right))
	{
		return Text.StartsWith(Left, ESearchCase::IgnoreCase) && Text.EndsWith(Right, ESearchCase::IgnoreCase);
	}

	return false;
}

FString UActorReflectionAPI::GetActorLabelSafe(AActor* Actor)
{
	if (!Actor) return TEXT("");

#if WITH_EDITOR
	return Actor->GetActorLabel();
#else
	return Actor->GetName();
#endif
}

AActor* UActorReflectionAPI::FindActor(UWorld* World, const FString& ActorName)
{
	if (!World || ActorName.IsEmpty()) return nullptr;

	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (!Actor) continue;

		if (MatchesWildcard(Actor->GetName(), ActorName) || 
			MatchesWildcard(GetActorLabelSafe(Actor), ActorName))
		{
			return Actor;
		}
	}

	return nullptr;
}

UObject* UActorReflectionAPI::ResolveTargetObject(const FString& TargetPath, const FString& WorldType, FString& OutError)
{
	// If path starts with '/', treat as asset path
	if (TargetPath.StartsWith(TEXT("/")))
	{
		return FAssetModifier::LoadAssetByPath(TargetPath, OutError);
	}

	// Otherwise, treat as actor name in world
	UWorld* World = FindWorldByType(WorldType);
	if (!World)
	{
		OutError = FString::Printf(TEXT("No world available for type: %s"), *WorldType);
		return nullptr;
	}

	AActor* Actor = FindActor(World, TargetPath);
	if (!Actor)
	{
		OutError = FString::Printf(TEXT("Actor not found: %s"), *TargetPath);
		return nullptr;
	}

	return Actor;
}

FProperty* UActorReflectionAPI::ResolvePropertyPath(UObject* Object, const FString& PropertyPath, UObject*& OutTargetObject, void*& OutContainer, FString& OutError)
{
	if (!Object)
	{
		OutError = TEXT("Object is null");
		return nullptr;
	}

	OutTargetObject = Object;
	OutContainer = Object;

	TArray<FString> PathParts;
	PropertyPath.ParseIntoArray(PathParts, TEXT("."), true);

	if (PathParts.Num() == 0)
	{
		OutError = TEXT("Empty property path");
		return nullptr;
	}

	// Navigate through path parts
	for (int32 i = 0; i < PathParts.Num(); ++i)
	{
		FString CurrentPart = PathParts[i];
		bool bIsLastPart = (i == PathParts.Num() - 1);

		// Check for array index syntax: "PropertyName[Index]"
		FString PropName = CurrentPart;
		int32 ArrayIndex = INDEX_NONE;
		
		int32 BracketStart, BracketEnd;
		if (CurrentPart.FindChar(TEXT('['), BracketStart) && CurrentPart.FindLastChar(TEXT(']'), BracketEnd))
		{
			PropName = CurrentPart.Left(BracketStart);
			FString IndexStr = CurrentPart.Mid(BracketStart + 1, BracketEnd - BracketStart - 1);
			ArrayIndex = FCString::Atoi(*IndexStr);
		}

		// Find property in current object
		FProperty* Property = nullptr;
		for (TFieldIterator<FProperty> PropIt(OutTargetObject->GetClass()); PropIt; ++PropIt)
		{
			if (PropIt->GetName().Equals(PropName, ESearchCase::IgnoreCase))
			{
				Property = *PropIt;
				break;
			}
		}

		if (!Property)
		{
			// Try to find component if this is the first part
			if (i == 0)
			{
				if (AActor* Actor = Cast<AActor>(OutTargetObject))
				{
					TArray<UActorComponent*> Components;
					Actor->GetComponents(Components);
					for (UActorComponent* Component : Components)
					{
						if (Component && Component->GetName().Equals(PropName, ESearchCase::IgnoreCase))
						{
							OutTargetObject = Component;
							OutContainer = Component;
							continue; // Skip to next path part
						}
					}
				}
			}
			
			OutError = FString::Printf(TEXT("Property '%s' not found on %s"), *PropName, *OutTargetObject->GetClass()->GetName());
			return nullptr;
		}

		if (bIsLastPart)
		{
			// This is the target property
			return Property;
		}

		// Navigate deeper
		void* PropertyPtr = Property->ContainerPtrToValuePtr<void>(OutContainer);

		if (FArrayProperty* ArrayProp = CastField<FArrayProperty>(Property))
		{
			if (ArrayIndex == INDEX_NONE)
			{
				OutError = TEXT("Array property requires index: use PropertyName[Index]");
				return nullptr;
			}

			FScriptArrayHelper ArrayHelper(ArrayProp, PropertyPtr);
			if (ArrayIndex < 0 || ArrayIndex >= ArrayHelper.Num())
			{
				OutError = FString::Printf(TEXT("Array index %d out of range (0-%d)"), ArrayIndex, ArrayHelper.Num() - 1);
				return nullptr;
			}

			OutContainer = ArrayHelper.GetRawPtr(ArrayIndex);
			
			// For object arrays, update target object
			if (FObjectProperty* ObjectProp = CastField<FObjectProperty>(ArrayProp->Inner))
			{
				UObject* ElementObject = ObjectProp->GetObjectPropertyValue(OutContainer);
				if (!ElementObject)
				{
					OutError = FString::Printf(TEXT("Array element %d is null"), ArrayIndex);
					return nullptr;
				}
				OutTargetObject = ElementObject;
				OutContainer = ElementObject;
			}
		}
		else if (FStructProperty* StructProp = CastField<FStructProperty>(Property))
		{
			// Update container to point to struct data
			OutContainer = PropertyPtr;
		}
		else if (FObjectProperty* ObjectProp = CastField<FObjectProperty>(Property))
		{
			UObject* NextObject = ObjectProp->GetObjectPropertyValue(PropertyPtr);
			if (!NextObject)
			{
				OutError = FString::Printf(TEXT("Object property '%s' is null"), *PropName);
				return nullptr;
			}
			OutTargetObject = NextObject;
			OutContainer = NextObject;
		}
		else
		{
			OutError = FString::Printf(TEXT("Property '%s' is not navigable (not struct, object, or array)"), *PropName);
			return nullptr;
		}
	}

	OutError = TEXT("Property path navigation failed");
	return nullptr;
}

FString UActorReflectionAPI::CallFunction(const FString& ActorName, const FString& FunctionName, const FString& ArgsJson, const FString& WorldType)
{
	if (ActorName.IsEmpty() || FunctionName.IsEmpty())
	{
		return ClawMakeError(TEXT("ActorName and FunctionName are required"));
	}

	FString Error;
	UObject* TargetObject = ResolveTargetObject(ActorName, WorldType, Error);
	if (!TargetObject)
	{
		return ClawMakeError(Error);
	}

	// Find the UFunction
	UFunction* Function = TargetObject->FindFunction(*FunctionName);
	if (!Function)
	{
		return ClawMakeError(FString::Printf(TEXT("Function '%s' not found on '%s'"), *FunctionName, *TargetObject->GetClass()->GetName()));
	}

	// Parse arguments
	TSharedPtr<FJsonObject> FuncArgs = ParseJsonArgsString(ArgsJson, Error);
	if (!FuncArgs)
	{
		return ClawMakeError(Error);
	}

	// Allocate parameter memory
	TArray<uint8> ParamBuffer;
	ParamBuffer.SetNumZeroed(Function->ParmsSize);

	// Initialize and set parameters
	for (TFieldIterator<FProperty> PropIt(Function); PropIt && (PropIt->PropertyFlags & CPF_Parm); ++PropIt)
	{
		FProperty* Prop = *PropIt;
		if (Prop->PropertyFlags & CPF_ReturnParm) continue;

		void* ParamPtr = Prop->ContainerPtrToValuePtr<void>(ParamBuffer.GetData());
		Prop->InitializeValue(ParamPtr);

		// Set argument value if provided
		FString PropName = Prop->GetName();
		const TSharedPtr<FJsonValue>* ArgVal = FuncArgs->Values.Find(PropName);
		if (ArgVal && ArgVal->IsValid())
		{
			if (!FPropertySerializer::DeserializePropertyValue(Prop, ParamBuffer.GetData(), *ArgVal, Error))
			{
				// Cleanup and return error
				for (TFieldIterator<FProperty> CleanupIt(Function); CleanupIt && (CleanupIt->PropertyFlags & CPF_Parm); ++CleanupIt)
				{
					CleanupIt->DestroyValue(CleanupIt->ContainerPtrToValuePtr<void>(ParamBuffer.GetData()));
				}
				return ClawMakeError(FString::Printf(TEXT("Failed to set parameter '%s': %s"), *PropName, *Error));
			}
		}
	}

	// Call the function
	TargetObject->ProcessEvent(Function, ParamBuffer.GetData());

	// Collect return value and output parameters
	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("target"), TargetObject->GetName());
	Result->SetStringField(TEXT("function"), FunctionName);

	TSharedPtr<FJsonObject> Outputs = MakeShareable(new FJsonObject);
	for (TFieldIterator<FProperty> PropIt(Function); PropIt && (PropIt->PropertyFlags & CPF_Parm); ++PropIt)
	{
		FProperty* Prop = *PropIt;
		if (!(Prop->PropertyFlags & CPF_OutParm) && !(Prop->PropertyFlags & CPF_ReturnParm)) continue;

		void* ParamPtr = Prop->ContainerPtrToValuePtr<void>(ParamBuffer.GetData());
		TSharedPtr<FJsonValue> SerializedValue = FPropertySerializer::SerializePropertyValue(Prop, ParamBuffer.GetData(), TargetObject);
		if (SerializedValue.IsValid())
		{
			Outputs->SetField(Prop->GetName(), SerializedValue);
		}
	}
	Result->SetObjectField(TEXT("outputs"), Outputs);

	// Cleanup parameter objects
	for (TFieldIterator<FProperty> PropIt(Function); PropIt && (PropIt->PropertyFlags & CPF_Parm); ++PropIt)
	{
		PropIt->DestroyValue(PropIt->ContainerPtrToValuePtr<void>(ParamBuffer.GetData()));
	}

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("call-function: %s::%s"), *TargetObject->GetName(), *FunctionName);
	return ClawJsonToString(Result);
}

FString UActorReflectionAPI::GetProperty(const FString& TargetPath, const FString& PropertyPath, const FString& WorldType)
{
	if (TargetPath.IsEmpty() || PropertyPath.IsEmpty())
	{
		return ClawMakeError(TEXT("TargetPath and PropertyPath are required"));
	}

	FString Error;
	UObject* TargetObject = ResolveTargetObject(TargetPath, WorldType, Error);
	if (!TargetObject)
	{
		return ClawMakeError(Error);
	}

	UObject* FinalObject = nullptr;
	void* Container = nullptr;
	FProperty* Property = ResolvePropertyPath(TargetObject, PropertyPath, FinalObject, Container, Error);
	if (!Property)
	{
		return ClawMakeError(Error);
	}

	// Serialize property value
	TSharedPtr<FJsonValue> SerializedValue = FPropertySerializer::SerializePropertyValue(Property, Container, FinalObject);
	if (!SerializedValue.IsValid())
	{
		return ClawMakeError(TEXT("Failed to serialize property value"));
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("target"), TargetObject->GetName());
	Result->SetStringField(TEXT("property"), PropertyPath);
	Result->SetStringField(TEXT("type"), FPropertySerializer::GetPropertyTypeString(Property));
	Result->SetField(TEXT("value"), SerializedValue);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("get-property: %s.%s"), *TargetPath, *PropertyPath);
	return ClawJsonToString(Result);
}

FString UActorReflectionAPI::SetProperty(const FString& TargetPath, const FString& PropertyPath, const FString& ValueJson, const FString& WorldType)
{
	if (TargetPath.IsEmpty() || PropertyPath.IsEmpty() || ValueJson.IsEmpty())
	{
		return ClawMakeError(TEXT("TargetPath, PropertyPath, and ValueJson are required"));
	}

	FString Error;
	UObject* TargetObject = ResolveTargetObject(TargetPath, WorldType, Error);
	if (!TargetObject)
	{
		return ClawMakeError(Error);
	}

	UObject* FinalObject = nullptr;
	void* Container = nullptr;
	FProperty* Property = ResolvePropertyPath(TargetObject, PropertyPath, FinalObject, Container, Error);
	if (!Property)
	{
		return ClawMakeError(Error);
	}

	// Parse value JSON — support both bare values (false, 42, "hello") and JSON objects/arrays
	TSharedPtr<FJsonValue> JsonValue;
	{
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ValueJson);
		if (!FJsonSerializer::Deserialize(Reader, JsonValue) || !JsonValue.IsValid())
		{
			// UE's JSON parser rejects bare values as top-level — wrap in object and extract
			FString Wrapped = FString::Printf(TEXT("{\"_v\":%s}"), *ValueJson);
			TSharedRef<TJsonReader<>> WrappedReader = TJsonReaderFactory<>::Create(Wrapped);
			TSharedPtr<FJsonObject> WrappedObj;
			if (FJsonSerializer::Deserialize(WrappedReader, WrappedObj) && WrappedObj.IsValid())
			{
				JsonValue = WrappedObj->TryGetField(TEXT("_v"));
			}
			if (!JsonValue.IsValid())
			{
				return ClawMakeError(TEXT("Invalid JSON format in ValueJson"));
			}
		}
	}

	// Begin transaction for undo support
#if WITH_EDITOR
	TSharedPtr<FScopedTransaction> Transaction;
	if (GEditor)
	{
		Transaction = FAssetModifier::BeginTransaction(
			FString::Printf(TEXT("Set %s.%s"), *TargetPath, *PropertyPath));
		FAssetModifier::MarkModified(FinalObject);
	}
#endif

	// Set property value
	if (!FPropertySerializer::DeserializePropertyValue(Property, Container, JsonValue, Error))
	{
		return ClawMakeError(FString::Printf(TEXT("Failed to set property: %s"), *Error));
	}

#if WITH_EDITOR
	// Notify object of change
	if (FinalObject)
	{
		FinalObject->PostEditChange();
		FAssetModifier::MarkPackageDirty(FinalObject);
	}
#endif

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("target"), TargetObject->GetName());
	Result->SetStringField(TEXT("property"), PropertyPath);
	Result->SetStringField(TEXT("type"), FPropertySerializer::GetPropertyTypeString(Property));
	Result->SetStringField(TEXT("value"), ValueJson);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("set-property: %s.%s = %s"), *TargetPath, *PropertyPath, *ValueJson);
	return ClawJsonToString(Result);
}