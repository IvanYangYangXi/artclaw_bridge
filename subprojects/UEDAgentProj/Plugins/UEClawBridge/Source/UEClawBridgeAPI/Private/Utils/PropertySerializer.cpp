// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "Utils/PropertySerializer.h"
#include "JsonObjectConverter.h"
#include "UObject/UnrealType.h"
#include "UObject/TextProperty.h"
#include "UObject/EnumProperty.h"
#include "UEClawBridgeAPI.h"

TSharedPtr<FJsonValue> FPropertySerializer::SerializePropertyValue(
	FProperty* Property,
	const void* Container,
	UObject* Owner,
	int32 Depth,
	int32 MaxDepth)
{
	if (!Property || !Container)
	{
		return nullptr;
	}

	const void* ValuePtr = Property->ContainerPtrToValuePtr<void>(Container);

	// Boolean
	if (FBoolProperty* BoolProp = CastField<FBoolProperty>(Property))
	{
		return MakeShareable(new FJsonValueBoolean(BoolProp->GetPropertyValue(ValuePtr)));
	}

	// Numeric (int, float, double, etc.)
	if (FNumericProperty* NumericProp = CastField<FNumericProperty>(Property))
	{
		if (NumericProp->IsFloatingPoint())
		{
			return MakeShareable(new FJsonValueNumber(NumericProp->GetFloatingPointPropertyValue(ValuePtr)));
		}
		else if (NumericProp->IsInteger())
		{
			return MakeShareable(new FJsonValueNumber(static_cast<double>(NumericProp->GetSignedIntPropertyValue(ValuePtr))));
		}
	}

	// String
	if (FStrProperty* StrProp = CastField<FStrProperty>(Property))
	{
		return MakeShareable(new FJsonValueString(StrProp->GetPropertyValue(ValuePtr)));
	}

	// Name
	if (FNameProperty* NameProp = CastField<FNameProperty>(Property))
	{
		return MakeShareable(new FJsonValueString(NameProp->GetPropertyValue(ValuePtr).ToString()));
	}

	// Text
	if (FTextProperty* TextProp = CastField<FTextProperty>(Property))
	{
		return MakeShareable(new FJsonValueString(TextProp->GetPropertyValue(ValuePtr).ToString()));
	}

	// Enum
	if (FEnumProperty* EnumProp = CastField<FEnumProperty>(Property))
	{
		FNumericProperty* UnderlyingProp = EnumProp->GetUnderlyingProperty();
		int64 EnumValue = UnderlyingProp->GetSignedIntPropertyValue(ValuePtr);
		FString EnumName = EnumProp->GetEnum()->GetNameStringByValue(EnumValue);
		return MakeShareable(new FJsonValueString(EnumName));
	}

	// Byte enum
	if (FByteProperty* ByteProp = CastField<FByteProperty>(Property))
	{
		if (ByteProp->Enum)
		{
			uint8 ByteValue = ByteProp->GetPropertyValue(ValuePtr);
			FString EnumName = ByteProp->Enum->GetNameStringByValue(ByteValue);
			return MakeShareable(new FJsonValueString(EnumName));
		}
		else
		{
			return MakeShareable(new FJsonValueNumber(ByteProp->GetPropertyValue(ValuePtr)));
		}
	}

	// Struct
	if (FStructProperty* StructProp = CastField<FStructProperty>(Property))
	{
		return SerializeStructProperty(StructProp, Container, Owner, Depth, MaxDepth);
	}

	// Array
	if (FArrayProperty* ArrayProp = CastField<FArrayProperty>(Property))
	{
		return SerializeArrayProperty(ArrayProp, Container, Owner, Depth, MaxDepth);
	}

	// Map
	if (FMapProperty* MapProp = CastField<FMapProperty>(Property))
	{
		return SerializeMapProperty(MapProp, Container, Owner, Depth, MaxDepth);
	}

	// Set
	if (FSetProperty* SetProp = CastField<FSetProperty>(Property))
	{
		return SerializeSetProperty(SetProp, Container, Owner, Depth, MaxDepth);
	}

	// Object reference
	if (FObjectProperty* ObjectProp = CastField<FObjectProperty>(Property))
	{
		return SerializeObjectProperty(ObjectProp, Container, Depth, MaxDepth);
	}

	// Soft object reference
	if (FSoftObjectProperty* SoftObjectProp = CastField<FSoftObjectProperty>(Property))
	{
		FSoftObjectPtr SoftPtr = SoftObjectProp->GetPropertyValue(ValuePtr);
		return MakeShareable(new FJsonValueString(SoftPtr.ToString()));
	}

	// Class reference
	if (FClassProperty* ClassProp = CastField<FClassProperty>(Property))
	{
		UClass* ClassValue = Cast<UClass>(ClassProp->GetObjectPropertyValue(ValuePtr));
		if (ClassValue)
		{
			return MakeShareable(new FJsonValueString(ClassValue->GetPathName()));
		}
		return MakeShareable(new FJsonValueNull());
	}

	// Fallback: use ExportText
	FString ExportedValue;
	Property->ExportText_Direct(ExportedValue, ValuePtr, ValuePtr, Owner, PPF_None);
	return MakeShareable(new FJsonValueString(ExportedValue));
}

TSharedPtr<FJsonObject> FPropertySerializer::SerializeProperty(
	FProperty* Property,
	const void* Container,
	UObject* Owner,
	int32 Depth,
	int32 MaxDepth,
	bool bIncludeMetadata)
{
	if (!Property || !Container)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> PropJson = MakeShareable(new FJsonObject);
	PropJson->SetStringField(TEXT("name"), Property->GetName());
	PropJson->SetStringField(TEXT("type"), GetPropertyTypeString(Property));

	if (bIncludeMetadata)
	{
		FString Category = Property->GetMetaData(TEXT("Category"));
		if (!Category.IsEmpty())
		{
			PropJson->SetStringField(TEXT("category"), Category);
		}

		FString Tooltip = Property->GetMetaData(TEXT("ToolTip"));
		if (!Tooltip.IsEmpty())
		{
			PropJson->SetStringField(TEXT("tooltip"), Tooltip);
		}

		// Property flags
		if (Property->HasAnyPropertyFlags(CPF_Edit))
		{
			PropJson->SetBoolField(TEXT("editable"), true);
		}
		if (Property->HasAnyPropertyFlags(CPF_BlueprintVisible))
		{
			PropJson->SetBoolField(TEXT("blueprint_visible"), true);
		}
	}

	TSharedPtr<FJsonValue> Value = SerializePropertyValue(Property, Container, Owner, Depth, MaxDepth);
	if (Value.IsValid())
	{
		PropJson->SetField(TEXT("value"), Value);
	}

	return PropJson;
}

TSharedPtr<FJsonObject> FPropertySerializer::SerializeUObjectProperties(
	UObject* Object,
	int32 Depth,
	int32 MaxDepth,
	EPropertyFlags RequiredFlags,
	EPropertyFlags ExcludeFlags)
{
	if (!Object)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	TArray<TSharedPtr<FJsonValue>> PropertiesArray;

	for (TFieldIterator<FProperty> It(Object->GetClass()); It; ++It)
	{
		FProperty* Property = *It;

		// Check required flags
		if (RequiredFlags != CPF_None && !Property->HasAllPropertyFlags(RequiredFlags))
		{
			continue;
		}

		// Check exclude flags
		if (ExcludeFlags != CPF_None && Property->HasAnyPropertyFlags(ExcludeFlags))
		{
			continue;
		}

		TSharedPtr<FJsonObject> PropJson = SerializeProperty(Property, Object, Object, Depth, MaxDepth);
		if (PropJson.IsValid())
		{
			PropertiesArray.Add(MakeShareable(new FJsonValueObject(PropJson)));
		}
	}

	Result->SetArrayField(TEXT("properties"), PropertiesArray);
	Result->SetStringField(TEXT("class"), Object->GetClass()->GetName());
	Result->SetNumberField(TEXT("property_count"), PropertiesArray.Num());

	return Result;
}

FString FPropertySerializer::GetPropertyTypeString(FProperty* Property)
{
	if (!Property) return TEXT("unknown");

	if (Property->IsA<FBoolProperty>()) return TEXT("bool");
	if (Property->IsA<FIntProperty>()) return TEXT("int32");
	if (Property->IsA<FInt64Property>()) return TEXT("int64");
	if (Property->IsA<FFloatProperty>()) return TEXT("float");
	if (Property->IsA<FDoubleProperty>()) return TEXT("double");
	if (Property->IsA<FStrProperty>()) return TEXT("FString");
	if (Property->IsA<FNameProperty>()) return TEXT("FName");
	if (Property->IsA<FTextProperty>()) return TEXT("FText");

	if (FByteProperty* ByteProp = CastField<FByteProperty>(Property))
	{
		if (ByteProp->Enum)
		{
			return ByteProp->Enum->GetName();
		}
		return TEXT("uint8");
	}

	if (FEnumProperty* EnumProp = CastField<FEnumProperty>(Property))
	{
		return EnumProp->GetEnum()->GetName();
	}

	if (FStructProperty* StructProp = CastField<FStructProperty>(Property))
	{
		return StructProp->Struct ? StructProp->Struct->GetName() : TEXT("struct");
	}

	if (FObjectProperty* ObjProp = CastField<FObjectProperty>(Property))
	{
		return ObjProp->PropertyClass ? FString::Printf(TEXT("TObjectPtr<%s>"), *ObjProp->PropertyClass->GetName()) : TEXT("UObject*");
	}

	if (FSoftObjectProperty* SoftObjProp = CastField<FSoftObjectProperty>(Property))
	{
		return SoftObjProp->PropertyClass ? FString::Printf(TEXT("TSoftObjectPtr<%s>"), *SoftObjProp->PropertyClass->GetName()) : TEXT("TSoftObjectPtr<>");
	}

	if (FClassProperty* ClassProp = CastField<FClassProperty>(Property))
	{
		return ClassProp->MetaClass ? FString::Printf(TEXT("TSubclassOf<%s>"), *ClassProp->MetaClass->GetName()) : TEXT("UClass*");
	}

	if (FArrayProperty* ArrayProp = CastField<FArrayProperty>(Property))
	{
		return FString::Printf(TEXT("TArray<%s>"), *GetPropertyTypeString(ArrayProp->Inner));
	}

	if (FMapProperty* MapProp = CastField<FMapProperty>(Property))
	{
		return FString::Printf(TEXT("TMap<%s, %s>"),
			*GetPropertyTypeString(MapProp->KeyProp),
			*GetPropertyTypeString(MapProp->ValueProp));
	}

	if (FSetProperty* SetProp = CastField<FSetProperty>(Property))
	{
		return FString::Printf(TEXT("TSet<%s>"), *GetPropertyTypeString(SetProp->ElementProp));
	}

	return Property->GetClass()->GetName();
}

UClass* FPropertySerializer::ResolveClass(const FString& ClassName, FString& OutError)
{
	if (ClassName.IsEmpty())
	{
		OutError = TEXT("Class name is empty");
		return nullptr;
	}

	UClass* ResolvedClass = nullptr;

	// Try as Blueprint class path (e.g., "/Game/BP_MyClass.BP_MyClass_C")
	if (ClassName.StartsWith(TEXT("/")))
	{
		ResolvedClass = LoadClass<UObject>(nullptr, *ClassName);
		if (ResolvedClass)
		{
			return ResolvedClass;
		}

		// Maybe it's an object path, try loading
		UObject* LoadedObj = StaticLoadObject(UClass::StaticClass(), nullptr, *ClassName);
		if (UClass* LoadedClass = Cast<UClass>(LoadedObj))
		{
			return LoadedClass;
		}

		// Try appending _C for Blueprint classes
		if (!ClassName.EndsWith(TEXT("_C")))
		{
			FString BlueprintClassName = ClassName + TEXT("_C");
			ResolvedClass = LoadClass<UObject>(nullptr, *BlueprintClassName);
			if (ResolvedClass)
			{
				return ResolvedClass;
			}
		}
	}

	// Try as short class name (e.g., "Actor", "MaterialExpressionAdd")
	ResolvedClass = FindFirstObject<UClass>(*ClassName, EFindFirstObjectOptions::ExactClass);
	if (ResolvedClass)
	{
		return ResolvedClass;
	}

	// Try with common prefixes
	TArray<FString> Prefixes = { TEXT("U"), TEXT("A"), TEXT("F") };
	for (const FString& Prefix : Prefixes)
	{
		FString PrefixedName = Prefix + ClassName;
		ResolvedClass = FindFirstObject<UClass>(*PrefixedName, EFindFirstObjectOptions::ExactClass);
		if (ResolvedClass)
		{
			return ResolvedClass;
		}
	}

	OutError = FString::Printf(TEXT("Class not found: %s"), *ClassName);
	return nullptr;
}

// Helper to serialize struct properties
TSharedPtr<FJsonValue> FPropertySerializer::SerializeStructProperty(
	FStructProperty* StructProp,
	const void* Container,
	UObject* Owner,
	int32 Depth,
	int32 MaxDepth)
{
	if (Depth >= MaxDepth || !StructProp || !Container)
	{
		return nullptr;
	}

	const void* StructPtr = StructProp->ContainerPtrToValuePtr<void>(Container);
	UScriptStruct* Struct = StructProp->Struct;

	// Handle common UE structs with special serialization
	if (Struct == TBaseStructure<FVector>::Get())
	{
		const FVector* Vec = static_cast<const FVector*>(StructPtr);
		TArray<TSharedPtr<FJsonValue>> VecArray;
		VecArray.Add(MakeShareable(new FJsonValueNumber(Vec->X)));
		VecArray.Add(MakeShareable(new FJsonValueNumber(Vec->Y)));
		VecArray.Add(MakeShareable(new FJsonValueNumber(Vec->Z)));
		return MakeShareable(new FJsonValueArray(VecArray));
	}

	if (Struct == TBaseStructure<FRotator>::Get())
	{
		const FRotator* Rot = static_cast<const FRotator*>(StructPtr);
		TArray<TSharedPtr<FJsonValue>> RotArray;
		RotArray.Add(MakeShareable(new FJsonValueNumber(Rot->Pitch)));
		RotArray.Add(MakeShareable(new FJsonValueNumber(Rot->Yaw)));
		RotArray.Add(MakeShareable(new FJsonValueNumber(Rot->Roll)));
		return MakeShareable(new FJsonValueArray(RotArray));
	}

	if (Struct == TBaseStructure<FLinearColor>::Get())
	{
		const FLinearColor* Color = static_cast<const FLinearColor*>(StructPtr);
		TArray<TSharedPtr<FJsonValue>> ColorArray;
		ColorArray.Add(MakeShareable(new FJsonValueNumber(Color->R)));
		ColorArray.Add(MakeShareable(new FJsonValueNumber(Color->G)));
		ColorArray.Add(MakeShareable(new FJsonValueNumber(Color->B)));
		ColorArray.Add(MakeShareable(new FJsonValueNumber(Color->A)));
		return MakeShareable(new FJsonValueArray(ColorArray));
	}

	if (Struct == TBaseStructure<FVector2D>::Get())
	{
		const FVector2D* Vec2D = static_cast<const FVector2D*>(StructPtr);
		TArray<TSharedPtr<FJsonValue>> Vec2DArray;
		Vec2DArray.Add(MakeShareable(new FJsonValueNumber(Vec2D->X)));
		Vec2DArray.Add(MakeShareable(new FJsonValueNumber(Vec2D->Y)));
		return MakeShareable(new FJsonValueArray(Vec2DArray));
	}

	// Use generic UStruct to JSON conversion
	TSharedRef<FJsonObject> StructJson = MakeShareable(new FJsonObject);
	if (FJsonObjectConverter::UStructToJsonObject(Struct, StructPtr, StructJson, 0, 0))
	{
		return MakeShareable(new FJsonValueObject(StructJson));
	}

	return nullptr;
}

// Helper to serialize array properties  
TSharedPtr<FJsonValue> FPropertySerializer::SerializeArrayProperty(
	FArrayProperty* ArrayProp,
	const void* Container,
	UObject* Owner,
	int32 Depth,
	int32 MaxDepth)
{
	if (Depth >= MaxDepth || !ArrayProp || !Container)
	{
		return nullptr;
	}

	FScriptArrayHelper ArrayHelper(ArrayProp, ArrayProp->ContainerPtrToValuePtr<void>(Container));
	TArray<TSharedPtr<FJsonValue>> JsonArray;

	for (int32 i = 0; i < ArrayHelper.Num(); ++i)
	{
		const void* ElementPtr = ArrayHelper.GetRawPtr(i);
		TSharedPtr<FJsonValue> ElementValue = SerializePropertyValue(ArrayProp->Inner, ElementPtr, Owner, Depth + 1, MaxDepth);
		if (ElementValue.IsValid())
		{
			JsonArray.Add(ElementValue);
		}
	}

	return MakeShareable(new FJsonValueArray(JsonArray));
}

// Helper to serialize object properties
TSharedPtr<FJsonValue> FPropertySerializer::SerializeObjectProperty(
	FObjectProperty* ObjectProp,
	const void* Container,
	int32 Depth,
	int32 MaxDepth)
{
	if (Depth >= MaxDepth || !ObjectProp || !Container)
	{
		return nullptr;
	}

	UObject* ObjectValue = ObjectProp->GetObjectPropertyValue(ObjectProp->ContainerPtrToValuePtr<void>(Container));
	if (!ObjectValue)
	{
		return MakeShareable(new FJsonValueNull());
	}

	// For object references, just return the path name to avoid deep recursion
	return MakeShareable(new FJsonValueString(ObjectValue->GetPathName()));
}

// Helper to serialize map properties
TSharedPtr<FJsonValue> FPropertySerializer::SerializeMapProperty(
	FMapProperty* MapProp,
	const void* Container,
	UObject* Owner,
	int32 Depth,
	int32 MaxDepth)
{
	if (Depth >= MaxDepth || !MapProp || !Container)
	{
		return nullptr;
	}

	FScriptMapHelper MapHelper(MapProp, MapProp->ContainerPtrToValuePtr<void>(Container));
	TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);

	for (int32 i = 0; i < MapHelper.Num(); ++i)
	{
		if (!MapHelper.IsValidIndex(i))
		{
			continue;
		}

		const void* KeyPtr = MapHelper.GetKeyPtr(i);
		const void* ValuePtr = MapHelper.GetValuePtr(i);

		// Serialize key to string
		FString KeyString;
		if (FStrProperty* KeyStrProp = CastField<FStrProperty>(MapProp->KeyProp))
		{
			KeyString = KeyStrProp->GetPropertyValue(KeyPtr);
		}
		else if (FNameProperty* KeyNameProp = CastField<FNameProperty>(MapProp->KeyProp))
		{
			KeyString = KeyNameProp->GetPropertyValue(KeyPtr).ToString();
		}
		else
		{
			// For other types, use ExportText
			MapProp->KeyProp->ExportText_Direct(KeyString, KeyPtr, KeyPtr, Owner, PPF_None);
		}

		// Serialize value
		TSharedPtr<FJsonValue> ValueJson = SerializePropertyValue(MapProp->ValueProp, ValuePtr, Owner, Depth + 1, MaxDepth);
		if (ValueJson.IsValid())
		{
			JsonObject->SetField(KeyString, ValueJson);
		}
	}

	return MakeShareable(new FJsonValueObject(JsonObject));
}

// Helper to serialize set properties
TSharedPtr<FJsonValue> FPropertySerializer::SerializeSetProperty(
	FSetProperty* SetProp,
	const void* Container,
	UObject* Owner,
	int32 Depth,
	int32 MaxDepth)
{
	if (Depth >= MaxDepth || !SetProp || !Container)
	{
		return nullptr;
	}

	FScriptSetHelper SetHelper(SetProp, SetProp->ContainerPtrToValuePtr<void>(Container));
	TArray<TSharedPtr<FJsonValue>> JsonArray;

	for (int32 i = 0; i < SetHelper.Num(); ++i)
	{
		if (!SetHelper.IsValidIndex(i))
		{
			continue;
		}

		const void* ElementPtr = SetHelper.GetElementPtr(i);
		TSharedPtr<FJsonValue> ElementValue = SerializePropertyValue(SetProp->ElementProp, ElementPtr, Owner, Depth + 1, MaxDepth);
		if (ElementValue.IsValid())
		{
			JsonArray.Add(ElementValue);
		}
	}

	return MakeShareable(new FJsonValueArray(JsonArray));
}