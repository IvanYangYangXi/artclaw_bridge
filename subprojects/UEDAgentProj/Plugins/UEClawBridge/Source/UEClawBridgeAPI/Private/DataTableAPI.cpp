// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "DataTableAPI.h"
#include "UEClawBridgeAPI.h"
#include "Utils/AssetModifier.h"
#include "Utils/PropertySerializer.h"
#include "Engine/DataTable.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonReader.h"
#include "UObject/UnrealType.h"

namespace
{
	FString ClawJsonToString(const TSharedPtr<FJsonObject>& Obj)
	{
		if (!Obj.IsValid())
		{
			return TEXT("{}");
		}
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

	TSharedPtr<FJsonObject> ClawMakeSuccess()
	{
		TSharedPtr<FJsonObject> Obj = MakeShareable(new FJsonObject);
		Obj->SetBoolField(TEXT("success"), true);
		return Obj;
	}
}

FString UDataTableAPI::AddDataTableRow(const FString& AssetPath, const FString& RowName, const FString& ValuesJson)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("AddDataTableRow: table='%s', row='%s'"), *AssetPath, *RowName);

	if (AssetPath.IsEmpty() || RowName.IsEmpty() || ValuesJson.IsEmpty())
	{
		return ClawMakeError(TEXT("AssetPath, RowName, and ValuesJson are required"));
	}

	// Load and validate DataTable
	FString Error;
	UDataTable* DataTable = LoadAndValidateDataTable(AssetPath, Error);
	if (!DataTable)
	{
		return ClawMakeError(Error);
	}

	const UScriptStruct* RowStruct = DataTable->GetRowStruct();
	if (!RowStruct)
	{
		return ClawMakeError(TEXT("DataTable has no row struct defined"));
	}

	// Parse JSON values
	TArray<uint8> RowData;
	if (!ParseRowValuesFromJson(RowStruct, ValuesJson, RowData, Error))
	{
		return ClawMakeError(Error);
	}

	// Begin transaction
	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Add DataTable Row %s"), *RowName));

	// Mark DataTable as modified
	FAssetModifier::MarkModified(DataTable);

	// Add or update the row
	FName RowFName = FName(*RowName);
	bool bWasExisting = DataTable->GetRowMap().Contains(RowFName);

	// Allocate new row data
	uint8* NewRowData = (uint8*)FMemory::Malloc(RowStruct->GetStructureSize());
	RowStruct->InitializeStruct(NewRowData);
	
	// Copy our parsed data
	FMemory::Memcpy(NewRowData, RowData.GetData(), RowStruct->GetStructureSize());

	// Add to DataTable
	DataTable->AddRow(RowFName, *reinterpret_cast<FTableRowBase*>(NewRowData));

	// Mark package as dirty
	FAssetModifier::MarkPackageDirty(DataTable);

	// Build result
	auto Result = ClawMakeSuccess();
	Result->SetStringField(TEXT("asset_path"), AssetPath);
	Result->SetStringField(TEXT("row_name"), RowName);
	Result->SetBoolField(TEXT("was_existing"), bWasExisting);
	Result->SetStringField(TEXT("operation"), bWasExisting ? TEXT("updated") : TEXT("added"));
	Result->SetStringField(TEXT("struct_type"), RowStruct->GetName());

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("AddDataTableRow: %s row '%s' in table %s"), 
		bWasExisting ? TEXT("Updated") : TEXT("Added"), *RowName, *AssetPath);

	return ClawJsonToString(Result);
}

FString UDataTableAPI::QueryDataTable(const FString& AssetPath, const FString& RowFilter)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryDataTable: table='%s', filter='%s'"), *AssetPath, *RowFilter);

	if (AssetPath.IsEmpty())
	{
		return ClawMakeError(TEXT("AssetPath is required"));
	}

	// Load and validate DataTable
	FString Error;
	UDataTable* DataTable = LoadAndValidateDataTable(AssetPath, Error);
	if (!DataTable)
	{
		return ClawMakeError(Error);
	}

	const UScriptStruct* RowStruct = DataTable->GetRowStruct();
	if (!RowStruct)
	{
		return ClawMakeError(TEXT("DataTable has no row struct defined"));
	}

	// Build result
	auto Result = ClawMakeSuccess();
	Result->SetStringField(TEXT("asset_path"), AssetPath);
	Result->SetStringField(TEXT("struct_name"), RowStruct->GetName());
	Result->SetStringField(TEXT("struct_path"), RowStruct->GetPathName());

	// Add struct schema
	TSharedPtr<FJsonObject> Schema = GetStructSchema(RowStruct);
	Result->SetObjectField(TEXT("schema"), Schema);

	// Get all rows
	TArray<FName> AllRowNames = DataTable->GetRowNames();
	TArray<TSharedPtr<FJsonValue>> RowsArray;

	for (const FName& RowNameFName : AllRowNames)
	{
		FString RowNameStr = RowNameFName.ToString();

		// Apply row filter if specified
		if (!RowFilter.IsEmpty() && !MatchesWildcard(RowNameStr, RowFilter))
		{
			continue;
		}

		// Get row data
		const uint8* RowData = DataTable->FindRowUnchecked(RowNameFName);
		if (!RowData)
		{
			continue;
		}

		// Serialize row to JSON
		TSharedPtr<FJsonObject> RowJson = SerializeRowToJson(RowStruct, RowData);
		if (RowJson.IsValid())
		{
			RowJson->SetStringField(TEXT("row_name"), RowNameStr);
			RowsArray.Add(MakeShareable(new FJsonValueObject(RowJson)));
		}
	}

	Result->SetArrayField(TEXT("rows"), RowsArray);
	Result->SetNumberField(TEXT("row_count"), RowsArray.Num());
	Result->SetNumberField(TEXT("total_rows"), AllRowNames.Num());
	Result->SetBoolField(TEXT("filtered"), !RowFilter.IsEmpty());

	if (!RowFilter.IsEmpty())
	{
		Result->SetStringField(TEXT("row_filter"), RowFilter);
	}

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryDataTable: Returned %d rows (total: %d)"), 
		RowsArray.Num(), AllRowNames.Num());

	return ClawJsonToString(Result);
}

FString UDataTableAPI::SetDataTableObjectProperty(
	const FString& TablePath,
	const FString& RowName,
	const FString& ColumnName,
	const FString& ObjectPath)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("SetDataTableObjectProperty: table='%s' row='%s' col='%s' obj='%s'"),
		*TablePath, *RowName, *ColumnName, *ObjectPath);

	if (TablePath.IsEmpty() || RowName.IsEmpty() || ColumnName.IsEmpty())
	{
		return ClawMakeError(TEXT("TablePath, RowName, and ColumnName are required"));
	}

	FString Error;
	UDataTable* DataTable = LoadAndValidateDataTable(TablePath, Error);
	if (!DataTable) return ClawMakeError(Error);

	const UScriptStruct* RowStruct = DataTable->GetRowStruct();
	if (!RowStruct) return ClawMakeError(TEXT("DataTable has no row struct"));

	// Find the row
	FName RowFName(*RowName);
	uint8* RowData = DataTable->FindRowUnchecked(RowFName);
	if (!RowData)
	{
		return ClawMakeError(FString::Printf(TEXT("Row '%s' not found"), *RowName));
	}

	// Find the property by FriendlyName or VarName
	FProperty* TargetProp = nullptr;
	for (TFieldIterator<FProperty> It(RowStruct); It; ++It)
	{
		FProperty* Prop = *It;
		// Match by property name or by display name (FriendlyName for UDS)
		FString DisplayName = Prop->GetDisplayNameText().ToString();
		if (Prop->GetName() == ColumnName || DisplayName == ColumnName)
		{
			TargetProp = Prop;
			break;
		}
	}
	if (!TargetProp)
	{
		return ClawMakeError(FString::Printf(TEXT("Column '%s' not found in struct"), *ColumnName));
	}

	// Mark modified
	DataTable->Modify();

	void* PropertyContainer = TargetProp->ContainerPtrToValuePtr<void>(RowData);

	if (ObjectPath.IsEmpty() || ObjectPath == TEXT("None"))
	{
		// Clear the property
		TargetProp->ClearValue(PropertyContainer);
	}
	else
	{
		// Load the target object
		UObject* LoadedObject = StaticLoadObject(UObject::StaticClass(), nullptr, *ObjectPath);
		if (!LoadedObject)
		{
			// Try with .ObjectName appended
			FString TryPath = ObjectPath;
			if (!TryPath.Contains(TEXT(".")))
			{
				FString ObjName = FPaths::GetCleanFilename(TryPath);
				TryPath = TryPath + TEXT(".") + ObjName;
				LoadedObject = StaticLoadObject(UObject::StaticClass(), nullptr, *TryPath);
			}
		}
		if (!LoadedObject)
		{
			return ClawMakeError(FString::Printf(TEXT("Failed to load object: %s"), *ObjectPath));
		}

		// Handle different property types
		if (FObjectProperty* ObjProp = CastField<FObjectProperty>(TargetProp))
		{
			ObjProp->SetObjectPropertyValue(PropertyContainer, LoadedObject);
		}
		else if (FSoftObjectProperty* SoftProp = CastField<FSoftObjectProperty>(TargetProp))
		{
			FSoftObjectPtr SoftPtr(LoadedObject);
			SoftProp->SetPropertyValue(PropertyContainer, SoftPtr);
		}
		else if (FStructProperty* StructProp = CastField<FStructProperty>(TargetProp))
		{
			// Check if it's FSoftObjectPath struct
			if (StructProp->Struct == TBaseStructure<FSoftObjectPath>::Get())
			{
				FSoftObjectPath* PathPtr = static_cast<FSoftObjectPath*>(PropertyContainer);
				*PathPtr = FSoftObjectPath(LoadedObject);
			}
			else
			{
				return ClawMakeError(FString::Printf(TEXT("Column '%s' is struct type '%s', not an object property"),
					*ColumnName, *StructProp->Struct->GetName()));
			}
		}
		else
		{
			// Fallback: try ImportText
			FString TextValue = LoadedObject->GetPathName();
			const TCHAR* Buffer = *TextValue;
			if (!TargetProp->ImportText_Direct(Buffer, PropertyContainer, nullptr, PPF_None))
			{
				return ClawMakeError(FString::Printf(TEXT("Column '%s' (type %s) does not support object assignment"),
					*ColumnName, *TargetProp->GetCPPType()));
			}
		}
	}

	DataTable->MarkPackageDirty();
	DataTable->HandleDataTableChanged(RowFName);

	auto Result = ClawMakeSuccess();
	Result->SetStringField(TEXT("row"), RowName);
	Result->SetStringField(TEXT("column"), ColumnName);
	Result->SetStringField(TEXT("object"), ObjectPath);
	return ClawJsonToString(Result);
}

FString UDataTableAPI::BatchSetDataTableObjectProperties(
	const FString& TablePath,
	const FString& EntriesJson)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("BatchSetDataTableObjectProperties: table='%s' entries_len=%d"),
		*TablePath, EntriesJson.Len());

	if (TablePath.IsEmpty() || EntriesJson.IsEmpty())
	{
		return ClawMakeError(TEXT("TablePath and EntriesJson are required"));
	}

	// Parse JSON array
	TArray<TSharedPtr<FJsonValue>> EntriesArray;
	auto Reader = TJsonReaderFactory<>::Create(EntriesJson);
	if (!FJsonSerializer::Deserialize(Reader, EntriesArray))
	{
		return ClawMakeError(TEXT("Failed to parse EntriesJson as JSON array"));
	}

	FString Error;
	UDataTable* DataTable = LoadAndValidateDataTable(TablePath, Error);
	if (!DataTable) return ClawMakeError(Error);

	const UScriptStruct* RowStruct = DataTable->GetRowStruct();
	if (!RowStruct) return ClawMakeError(TEXT("DataTable has no row struct"));

	DataTable->Modify();

	int32 SuccessCount = 0;
	int32 FailCount = 0;
	TArray<TSharedPtr<FJsonValue>> Errors;

	// Build column lookup cache: FriendlyName/VarName -> FProperty*
	TMap<FString, FProperty*> PropCache;
	for (TFieldIterator<FProperty> It(RowStruct); It; ++It)
	{
		FProperty* Prop = *It;
		PropCache.Add(Prop->GetName(), Prop);
		FString DisplayName = Prop->GetDisplayNameText().ToString();
		if (!DisplayName.IsEmpty())
		{
			PropCache.Add(DisplayName, Prop);
		}
	}

	for (const auto& EntryVal : EntriesArray)
	{
		const TSharedPtr<FJsonObject>* EntryObj;
		if (!EntryVal->TryGetObject(EntryObj)) { FailCount++; continue; }

		FString RowName = (*EntryObj)->GetStringField(TEXT("row"));
		FString ColName = (*EntryObj)->GetStringField(TEXT("column"));
		FString ObjPath = (*EntryObj)->GetStringField(TEXT("asset"));

		if (RowName.IsEmpty() || ColName.IsEmpty()) { FailCount++; continue; }

		FName RowFName(*RowName);
		uint8* RowData = DataTable->FindRowUnchecked(RowFName);
		if (!RowData) { FailCount++; continue; }

		FProperty** FoundProp = PropCache.Find(ColName);
		if (!FoundProp || !*FoundProp) { FailCount++; continue; }

		FProperty* TargetProp = *FoundProp;
		void* Container = TargetProp->ContainerPtrToValuePtr<void>(RowData);

		if (ObjPath.IsEmpty() || ObjPath == TEXT("None"))
		{
			TargetProp->ClearValue(Container);
			SuccessCount++;
			continue;
		}

		UObject* Obj = StaticLoadObject(UObject::StaticClass(), nullptr, *ObjPath);
		if (!Obj)
		{
			FString TryPath = ObjPath;
			if (!TryPath.Contains(TEXT(".")))
			{
				TryPath = TryPath + TEXT(".") + FPaths::GetCleanFilename(TryPath);
				Obj = StaticLoadObject(UObject::StaticClass(), nullptr, *TryPath);
			}
		}
		if (!Obj) { FailCount++; continue; }

		if (FObjectProperty* ObjProp = CastField<FObjectProperty>(TargetProp))
		{
			ObjProp->SetObjectPropertyValue(Container, Obj);
			SuccessCount++;
		}
		else if (FSoftObjectProperty* SoftProp = CastField<FSoftObjectProperty>(TargetProp))
		{
			SoftProp->SetPropertyValue(Container, FSoftObjectPtr(Obj));
			SuccessCount++;
		}
		else if (FStructProperty* StructProp = CastField<FStructProperty>(TargetProp))
		{
			if (StructProp->Struct == TBaseStructure<FSoftObjectPath>::Get())
			{
				*static_cast<FSoftObjectPath*>(Container) = FSoftObjectPath(Obj);
				SuccessCount++;
			}
			else { FailCount++; }
		}
		else { FailCount++; }
	}

	DataTable->MarkPackageDirty();

	auto Result = ClawMakeSuccess();
	Result->SetStringField(TEXT("table"), TablePath);
	Result->SetNumberField(TEXT("total"), EntriesArray.Num());
	Result->SetNumberField(TEXT("success"), SuccessCount);
	Result->SetNumberField(TEXT("failed"), FailCount);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("BatchSetDataTableObjectProperties: %d/%d succeeded"),
		SuccessCount, EntriesArray.Num());

	return ClawJsonToString(Result);
}

UDataTable* UDataTableAPI::LoadAndValidateDataTable(const FString& AssetPath, FString& OutError)
{
	// Load asset
	UObject* Asset = FAssetModifier::LoadAssetByPath(AssetPath, OutError);
	if (!Asset)
	{
		return nullptr;
	}

	// Cast to DataTable
	UDataTable* DataTable = Cast<UDataTable>(Asset);
	if (!DataTable)
	{
		OutError = FString::Printf(TEXT("Asset is not a DataTable: %s"), *AssetPath);
		return nullptr;
	}

	return DataTable;
}

bool UDataTableAPI::ParseRowValuesFromJson(const UScriptStruct* RowStruct, const FString& ValuesJson, TArray<uint8>& OutRowData, FString& OutError)
{
	if (!RowStruct)
	{
		OutError = TEXT("RowStruct is null");
		return false;
	}

	// Parse JSON
	TSharedPtr<FJsonObject> JsonObject;
	auto JsonReader = TJsonReaderFactory<>::Create(ValuesJson);
	if (!FJsonSerializer::Deserialize(JsonReader, JsonObject) || !JsonObject.IsValid())
	{
		OutError = TEXT("Failed to parse ValuesJson as JSON object");
		return false;
	}

	// Allocate struct memory
	int32 StructSize = RowStruct->GetStructureSize();
	OutRowData.SetNumZeroed(StructSize);
	uint8* StructData = OutRowData.GetData();

	// Initialize struct
	RowStruct->InitializeStruct(StructData);

	// Set properties from JSON
	for (TFieldIterator<FProperty> PropIt(RowStruct); PropIt; ++PropIt)
	{
		FProperty* Property = *PropIt;
		if (!Property)
		{
			continue;
		}

		FString PropertyName = Property->GetName();
		if (!JsonObject->HasField(PropertyName))
		{
			continue; // Skip missing properties, use default values
		}

		// Get property container
		void* PropertyContainer = Property->ContainerPtrToValuePtr<void>(StructData);
		if (!PropertyContainer)
		{
			continue;
		}

		// Get JSON value
		TSharedPtr<FJsonValue> JsonValue = JsonObject->TryGetField(PropertyName);
		if (!JsonValue.IsValid())
		{
			continue;
		}

		// Deserialize property
		FString PropertyError;
		if (!FPropertySerializer::DeserializePropertyValue(Property, PropertyContainer, JsonValue, PropertyError))
		{
			UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("Failed to set property '%s': %s"), *PropertyName, *PropertyError);
		}
	}

	return true;
}

TSharedPtr<FJsonObject> UDataTableAPI::SerializeRowToJson(const UScriptStruct* RowStruct, const uint8* RowData)
{
	if (!RowStruct || !RowData)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> RowJson = MakeShareable(new FJsonObject);

	// Serialize each property
	for (TFieldIterator<FProperty> PropIt(RowStruct); PropIt; ++PropIt)
	{
		FProperty* Property = *PropIt;
		if (!Property)
		{
			continue;
		}

		FString PropertyName = Property->GetName();
		const void* PropertyContainer = Property->ContainerPtrToValuePtr<void>(RowData);
		if (!PropertyContainer)
		{
			continue;
		}

		// Serialize property value
		TSharedPtr<FJsonValue> JsonValue = FPropertySerializer::SerializePropertyValue(Property, PropertyContainer);
		if (JsonValue.IsValid())
		{
			RowJson->SetField(PropertyName, JsonValue);
		}
	}

	return RowJson;
}

TSharedPtr<FJsonObject> UDataTableAPI::GetStructSchema(const UScriptStruct* Struct)
{
	if (!Struct)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> Schema = MakeShareable(new FJsonObject);
	Schema->SetStringField(TEXT("name"), Struct->GetName());
	Schema->SetStringField(TEXT("path"), Struct->GetPathName());

	// Get properties
	TArray<TSharedPtr<FJsonValue>> PropertiesArray;

	for (TFieldIterator<FProperty> PropIt(Struct); PropIt; ++PropIt)
	{
		FProperty* Property = *PropIt;
		if (!Property)
		{
			continue;
		}

		TSharedPtr<FJsonObject> PropInfo = MakeShareable(new FJsonObject);
		PropInfo->SetStringField(TEXT("name"), Property->GetName());
		PropInfo->SetStringField(TEXT("type"), FPropertySerializer::GetPropertyTypeString(Property));
		
		// Add metadata
		FString Category = Property->GetMetaData(TEXT("Category"));
		if (!Category.IsEmpty())
		{
			PropInfo->SetStringField(TEXT("category"), Category);
		}

		FString Tooltip = Property->GetMetaData(TEXT("Tooltip"));
		if (!Tooltip.IsEmpty())
		{
			PropInfo->SetStringField(TEXT("tooltip"), Tooltip);
		}

		// Property flags
		PropInfo->SetBoolField(TEXT("required"), Property->HasAnyPropertyFlags(CPF_RequiredParm));
		PropInfo->SetBoolField(TEXT("editable"), Property->HasAnyPropertyFlags(CPF_Edit));

		PropertiesArray.Add(MakeShareable(new FJsonValueObject(PropInfo)));
	}

	Schema->SetArrayField(TEXT("properties"), PropertiesArray);
	Schema->SetNumberField(TEXT("property_count"), PropertiesArray.Num());
	Schema->SetNumberField(TEXT("struct_size"), Struct->GetStructureSize());

	return Schema;
}

bool UDataTableAPI::MatchesWildcard(const FString& Text, const FString& Pattern)
{
	// Simple wildcard matching (* and ? support)
	FString RegexPattern = Pattern;
	RegexPattern.ReplaceInline(TEXT("*"), TEXT(".*"));
	RegexPattern.ReplaceInline(TEXT("?"), TEXT("."));
	
	// Use case-insensitive matching
	FRegexPattern Regex(RegexPattern, ERegexPatternFlags::CaseInsensitive);
	FRegexMatcher Matcher(Regex, Text);
	
	return Matcher.FindNext();
}