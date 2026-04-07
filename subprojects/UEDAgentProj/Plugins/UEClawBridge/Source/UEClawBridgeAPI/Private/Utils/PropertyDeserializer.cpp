// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "Utils/PropertySerializer.h"
#include "JsonObjectConverter.h"
#include "UObject/UnrealType.h"
#include "UObject/TextProperty.h"
#include "UObject/EnumProperty.h"
#include "UEClawBridgeAPI.h"

bool FPropertySerializer::DeserializePropertyValue(
	FProperty* Property,
	void* Container,
	const TSharedPtr<FJsonValue>& Value,
	FString& OutError)
{
	if (!Property || !Container || !Value.IsValid())
	{
		OutError = TEXT("Invalid parameters");
		return false;
	}

	void* ValuePtr = Property->ContainerPtrToValuePtr<void>(Container);

	// Boolean
	if (FBoolProperty* BoolProp = CastField<FBoolProperty>(Property))
	{
		bool BoolValue = false;
		if (!Value->TryGetBool(BoolValue))
		{
			OutError = TEXT("Expected boolean value");
			return false;
		}
		BoolProp->SetPropertyValue(ValuePtr, BoolValue);
		return true;
	}

	// Numeric
	if (FNumericProperty* NumericProp = CastField<FNumericProperty>(Property))
	{
		if (NumericProp->IsFloatingPoint())
		{
			double NumValue = 0.0;
			if (!Value->TryGetNumber(NumValue))
			{
				OutError = TEXT("Expected numeric value");
				return false;
			}
			NumericProp->SetFloatingPointPropertyValue(ValuePtr, NumValue);
		}
		else
		{
			int64 NumValue = 0;
			if (!Value->TryGetNumber(NumValue))
			{
				OutError = TEXT("Expected integer value");
				return false;
			}
			NumericProp->SetIntPropertyValue(ValuePtr, NumValue);
		}
		return true;
	}

	// String
	if (FStrProperty* StrProp = CastField<FStrProperty>(Property))
	{
		FString StrValue;
		if (!Value->TryGetString(StrValue))
		{
			OutError = TEXT("Expected string value");
			return false;
		}
		StrProp->SetPropertyValue(ValuePtr, StrValue);
		return true;
	}

	// Name
	if (FNameProperty* NameProp = CastField<FNameProperty>(Property))
	{
		FString StrValue;
		if (!Value->TryGetString(StrValue))
		{
			OutError = TEXT("Expected string value for FName");
			return false;
		}
		NameProp->SetPropertyValue(ValuePtr, FName(*StrValue));
		return true;
	}

	// Text
	if (FTextProperty* TextProp = CastField<FTextProperty>(Property))
	{
		FString StrValue;
		if (!Value->TryGetString(StrValue))
		{
			OutError = TEXT("Expected string value for FText");
			return false;
		}
		TextProp->SetPropertyValue(ValuePtr, FText::FromString(StrValue));
		return true;
	}

	// Enum
	if (FEnumProperty* EnumProp = CastField<FEnumProperty>(Property))
	{
		FString StrValue;
		int64 IntValue;

		if (Value->TryGetString(StrValue))
		{
			int64 EnumValue = EnumProp->GetEnum()->GetValueByNameString(StrValue);
			if (EnumValue == INDEX_NONE)
			{
				OutError = FString::Printf(TEXT("Invalid enum value: %s"), *StrValue);
				return false;
			}
			EnumProp->GetUnderlyingProperty()->SetIntPropertyValue(ValuePtr, EnumValue);
		}
		else if (Value->TryGetNumber(IntValue))
		{
			EnumProp->GetUnderlyingProperty()->SetIntPropertyValue(ValuePtr, IntValue);
		}
		else
		{
			OutError = TEXT("Expected string or integer for enum");
			return false;
		}
		return true;
	}

	// Struct
	if (FStructProperty* StructProp = CastField<FStructProperty>(Property))
	{
		const TSharedPtr<FJsonObject>* JsonObject = nullptr;
		if (Value->TryGetObject(JsonObject) && JsonObject->IsValid())
		{
			if (!FJsonObjectConverter::JsonObjectToUStruct(JsonObject->ToSharedRef(), StructProp->Struct, ValuePtr))
			{
				OutError = TEXT("Failed to convert JSON to struct");
				return false;
			}
			return true;
		}

		// Try array for vector types
		const TArray<TSharedPtr<FJsonValue>>* JsonArray = nullptr;
		if (Value->TryGetArray(JsonArray))
		{
			// FVector
			if (StructProp->Struct == TBaseStructure<FVector>::Get() && JsonArray->Num() >= 3)
			{
				FVector* Vec = static_cast<FVector*>(ValuePtr);
				Vec->X = (*JsonArray)[0]->AsNumber();
				Vec->Y = (*JsonArray)[1]->AsNumber();
				Vec->Z = (*JsonArray)[2]->AsNumber();
				return true;
			}
			// FRotator
			if (StructProp->Struct == TBaseStructure<FRotator>::Get() && JsonArray->Num() >= 3)
			{
				FRotator* Rot = static_cast<FRotator*>(ValuePtr);
				Rot->Pitch = (*JsonArray)[0]->AsNumber();
				Rot->Yaw = (*JsonArray)[1]->AsNumber();
				Rot->Roll = (*JsonArray)[2]->AsNumber();
				return true;
			}
			// FLinearColor
			if (StructProp->Struct == TBaseStructure<FLinearColor>::Get() && JsonArray->Num() >= 3)
			{
				FLinearColor* Color = static_cast<FLinearColor*>(ValuePtr);
				Color->R = (*JsonArray)[0]->AsNumber();
				Color->G = (*JsonArray)[1]->AsNumber();
				Color->B = (*JsonArray)[2]->AsNumber();
				Color->A = JsonArray->Num() >= 4 ? (*JsonArray)[3]->AsNumber() : 1.0f;
				return true;
			}
			// FVector2D
			if (StructProp->Struct == TBaseStructure<FVector2D>::Get() && JsonArray->Num() >= 2)
			{
				FVector2D* Vec2D = static_cast<FVector2D*>(ValuePtr);
				Vec2D->X = (*JsonArray)[0]->AsNumber();
				Vec2D->Y = (*JsonArray)[1]->AsNumber();
				return true;
			}
		}

		OutError = TEXT("Expected object or array value for struct");
		return false;
	}

	// Array
	if (FArrayProperty* ArrayProp = CastField<FArrayProperty>(Property))
	{
		return DeserializeArrayProperty(ArrayProp, Container, Value, OutError);
	}

	// Map
	if (FMapProperty* MapProp = CastField<FMapProperty>(Property))
	{
		return DeserializeMapProperty(MapProp, Container, Value, OutError);
	}

	// Set
	if (FSetProperty* SetProp = CastField<FSetProperty>(Property))
	{
		return DeserializeSetProperty(SetProp, Container, Value, OutError);
	}

	// Object reference
	if (FObjectProperty* ObjectProp = CastField<FObjectProperty>(Property))
	{
		return DeserializeObjectProperty(ObjectProp, Container, Value, OutError);
	}

	// Soft object reference
	if (FSoftObjectProperty* SoftObjectProp = CastField<FSoftObjectProperty>(Property))
	{
		FString StrValue;
		if (!Value->TryGetString(StrValue))
		{
			OutError = TEXT("Expected string path for soft object reference");
			return false;
		}
		FSoftObjectPath SoftPath(StrValue);
		SoftObjectProp->SetPropertyValue(ValuePtr, FSoftObjectPtr(SoftPath));
		return true;
	}

	OutError = FString::Printf(TEXT("Unsupported property type: %s"), *Property->GetClass()->GetName());
	return false;
}

// Helper to deserialize array properties
bool FPropertySerializer::DeserializeArrayProperty(
	FArrayProperty* ArrayProp,
	void* Container,
	const TSharedPtr<FJsonValue>& Value,
	FString& OutError)
{
	if (!ArrayProp || !Container || !Value.IsValid())
	{
		OutError = TEXT("Invalid parameters");
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* JsonArray = nullptr;
	if (!Value->TryGetArray(JsonArray))
	{
		OutError = TEXT("Expected array value");
		return false;
	}

	FScriptArrayHelper ArrayHelper(ArrayProp, ArrayProp->ContainerPtrToValuePtr<void>(Container));
	ArrayHelper.EmptyValues();

	for (int32 i = 0; i < JsonArray->Num(); ++i)
	{
		ArrayHelper.AddValue();
		void* ElementPtr = ArrayHelper.GetRawPtr(i);

		FString ElementError;
		if (!DeserializePropertyValue(ArrayProp->Inner, ElementPtr, (*JsonArray)[i], ElementError))
		{
			OutError = FString::Printf(TEXT("Array element %d: %s"), i, *ElementError);
			return false;
		}
	}

	return true;
}

// Helper to deserialize map properties
bool FPropertySerializer::DeserializeMapProperty(
	FMapProperty* MapProp,
	void* Container,
	const TSharedPtr<FJsonValue>& Value,
	FString& OutError)
{
	if (!MapProp || !Container || !Value.IsValid())
	{
		OutError = TEXT("Invalid parameters");
		return false;
	}

	const TSharedPtr<FJsonObject>* JsonObject = nullptr;
	if (!Value->TryGetObject(JsonObject) || !JsonObject->IsValid())
	{
		OutError = TEXT("Expected object value for map");
		return false;
	}

	FScriptMapHelper MapHelper(MapProp, MapProp->ContainerPtrToValuePtr<void>(Container));
	MapHelper.EmptyValues();

	for (auto& Pair : (*JsonObject)->Values)
	{
		const FString& KeyStr = Pair.Key;
		const TSharedPtr<FJsonValue>& ValueJson = Pair.Value;

		// Add new pair
		int32 NewIndex = MapHelper.AddDefaultValue_Invalid_NeedsRehash();
		void* KeyPtr = MapHelper.GetKeyPtr(NewIndex);
		void* ValuePtr = MapHelper.GetValuePtr(NewIndex);

		// Deserialize key (assume string key for simplicity)
		if (FStrProperty* KeyStrProp = CastField<FStrProperty>(MapProp->KeyProp))
		{
			KeyStrProp->SetPropertyValue(KeyPtr, KeyStr);
		}
		else if (FNameProperty* KeyNameProp = CastField<FNameProperty>(MapProp->KeyProp))
		{
			KeyNameProp->SetPropertyValue(KeyPtr, FName(*KeyStr));
		}
		else
		{
			// For other key types, try to deserialize from string
			TSharedPtr<FJsonValue> KeyJsonValue = MakeShareable(new FJsonValueString(KeyStr));
			FString KeyError;
			if (!DeserializePropertyValue(MapProp->KeyProp, KeyPtr, KeyJsonValue, KeyError))
			{
				OutError = FString::Printf(TEXT("Map key '%s': %s"), *KeyStr, *KeyError);
				return false;
			}
		}

		// Deserialize value
		FString ValueError;
		if (!DeserializePropertyValue(MapProp->ValueProp, ValuePtr, ValueJson, ValueError))
		{
			OutError = FString::Printf(TEXT("Map value for key '%s': %s"), *KeyStr, *ValueError);
			return false;
		}
	}

	MapHelper.Rehash();
	return true;
}

// Helper to deserialize set properties
bool FPropertySerializer::DeserializeSetProperty(
	FSetProperty* SetProp,
	void* Container,
	const TSharedPtr<FJsonValue>& Value,
	FString& OutError)
{
	if (!SetProp || !Container || !Value.IsValid())
	{
		OutError = TEXT("Invalid parameters");
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* JsonArray = nullptr;
	if (!Value->TryGetArray(JsonArray))
	{
		OutError = TEXT("Expected array value for set");
		return false;
	}

	FScriptSetHelper SetHelper(SetProp, SetProp->ContainerPtrToValuePtr<void>(Container));
	SetHelper.EmptyElements();

	for (int32 i = 0; i < JsonArray->Num(); ++i)
	{
		int32 NewIndex = SetHelper.AddDefaultValue_Invalid_NeedsRehash();
		void* ElementPtr = SetHelper.GetElementPtr(NewIndex);

		FString ElementError;
		if (!DeserializePropertyValue(SetProp->ElementProp, ElementPtr, (*JsonArray)[i], ElementError))
		{
			OutError = FString::Printf(TEXT("Set element %d: %s"), i, *ElementError);
			return false;
		}
	}

	SetHelper.Rehash();
	return true;
}

// Helper to deserialize object properties
bool FPropertySerializer::DeserializeObjectProperty(
	FObjectProperty* ObjectProp,
	void* Container,
	const TSharedPtr<FJsonValue>& Value,
	FString& OutError)
{
	if (!ObjectProp || !Container || !Value.IsValid())
	{
		OutError = TEXT("Invalid parameters");
		return false;
	}

	void* ValuePtr = ObjectProp->ContainerPtrToValuePtr<void>(Container);

	if (Value->IsNull())
	{
		ObjectProp->SetObjectPropertyValue(ValuePtr, nullptr);
		return true;
	}

	FString ObjectPath;
	if (!Value->TryGetString(ObjectPath))
	{
		OutError = TEXT("Expected string path for object reference");
		return false;
	}

	if (ObjectPath.IsEmpty())
	{
		ObjectProp->SetObjectPropertyValue(ValuePtr, nullptr);
		return true;
	}

	// Try to load the object by path
	UObject* LoadedObject = StaticLoadObject(ObjectProp->PropertyClass, nullptr, *ObjectPath);
	if (!LoadedObject)
	{
		OutError = FString::Printf(TEXT("Failed to load object: %s"), *ObjectPath);
		return false;
	}

	ObjectProp->SetObjectPropertyValue(ValuePtr, LoadedObject);
	return true;
}

