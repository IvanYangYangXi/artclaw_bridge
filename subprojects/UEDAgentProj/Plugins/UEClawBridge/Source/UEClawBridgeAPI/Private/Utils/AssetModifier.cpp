// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "Utils/AssetModifier.h"
#include "Utils/PropertySerializer.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "ISourceControlModule.h"
#include "ISourceControlProvider.h"
#include "SourceControlOperations.h"
#include "ScopedTransaction.h"
#include "UObject/SavePackage.h"
#include "UEClawBridgeAPI.h"

TSharedPtr<FScopedTransaction> FAssetModifier::BeginTransaction(const FString& Description)
{
	return MakeShareable(new FScopedTransaction(FText::FromString(Description)));
}

UObject* FAssetModifier::LoadAssetByPath(const FString& AssetPath, FString& OutError)
{
	if (!ValidateAssetPath(AssetPath))
	{
		OutError = FString::Printf(TEXT("Invalid asset path format: %s"), *AssetPath);
		return nullptr;
	}

	UObject* LoadedAsset = StaticLoadObject(UObject::StaticClass(), nullptr, *AssetPath);
	if (!LoadedAsset)
	{
		OutError = FString::Printf(TEXT("Failed to load asset: %s"), *AssetPath);
		return nullptr;
	}

	UE_LOG(LogUEClawBridgeAPI, Verbose, TEXT("Successfully loaded asset: %s"), *AssetPath);
	return LoadedAsset;
}

bool FAssetModifier::ValidateAssetPath(const FString& AssetPath)
{
	// Basic validation: must start with '/' and contain valid characters
	if (!AssetPath.StartsWith(TEXT("/")))
	{
		return false;
	}

	// Check for invalid characters
	const TCHAR* InvalidChars = TEXT("\"*<>?|");
	for (int32 i = 0; i < FCString::Strlen(InvalidChars); i++)
	{
		if (AssetPath.Contains(FString::Chr(InvalidChars[i])))
		{
			return false;
		}
	}

	return true;
}

bool FAssetModifier::AssetExists(const FString& AssetPath)
{
	FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
	IAssetRegistry& AssetRegistry = AssetRegistryModule.Get();

	FSoftObjectPath SoftPath(AssetPath);
	FAssetData AssetData = AssetRegistry.GetAssetByObjectPath(SoftPath);
	return AssetData.IsValid();
}

void FAssetModifier::MarkModified(UObject* Object)
{
	if (Object)
	{
		Object->Modify();
		UE_LOG(LogUEClawBridgeAPI, Verbose, TEXT("Marked object as modified: %s"), *Object->GetName());
	}
}

void FAssetModifier::MarkPackageDirty(UObject* Object)
{
	if (Object && Object->GetPackage())
	{
		Object->GetPackage()->SetDirtyFlag(true);
		UE_LOG(LogUEClawBridgeAPI, Verbose, TEXT("Marked package as dirty: %s"), *Object->GetPackage()->GetName());
	}
}

bool FAssetModifier::SaveAsset(UObject* Asset, FString& OutError)
{
	if (!Asset)
	{
		OutError = TEXT("Asset is null");
		return false;
	}

	UPackage* Package = Asset->GetPackage();
	if (!Package)
	{
		OutError = TEXT("Asset has no package");
		return false;
	}

	// Check if package is read-only
	FString PackageFilename = FPackageName::LongPackageNameToFilename(Package->GetName(), FPackageName::GetAssetPackageExtension());
	if (FPlatformFileManager::Get().GetPlatformFile().IsReadOnly(*PackageFilename))
	{
		// Try to checkout from source control
		FString CheckoutError;
		if (!CheckoutFile(PackageFilename, CheckoutError))
		{
			OutError = FString::Printf(TEXT("File is read-only and checkout failed: %s"), *CheckoutError);
			return false;
		}
	}

	// Save package using UE5 API
	FSavePackageArgs SaveArgs;
	SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
	SaveArgs.SaveFlags = SAVE_NoError;

	FSavePackageResultStruct SaveResult = UPackage::Save(Package, Asset, *PackageFilename, SaveArgs);
	
	if (SaveResult.Result != ESavePackageResult::Success)
	{
		OutError = FString::Printf(TEXT("Failed to save package: result code %d"), (int32)SaveResult.Result);
		return false;
	}

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Successfully saved asset: %s"), *Asset->GetName());
	return true;
}

bool FAssetModifier::CheckoutFile(const FString& FilePath, FString& OutError)
{
	ISourceControlModule& SourceControlModule = ISourceControlModule::Get();
	if (!SourceControlModule.IsEnabled() || !SourceControlModule.GetProvider().IsAvailable())
	{
		// No source control, consider success
		return true;
	}

	ISourceControlProvider& SourceControlProvider = SourceControlModule.GetProvider();
	
	// Create checkout operation
	TSharedRef<FCheckOut, ESPMode::ThreadSafe> CheckOutOperation = ISourceControlOperation::Create<FCheckOut>();
	ECommandResult::Type Result = SourceControlProvider.Execute(CheckOutOperation, FilePath);

	if (Result != ECommandResult::Succeeded)
	{
		OutError = FString::Printf(TEXT("Source control checkout failed for: %s"), *FilePath);
		return false;
	}

	UE_LOG(LogUEClawBridgeAPI, Verbose, TEXT("Successfully checked out file: %s"), *FilePath);
	return true;
}

bool FAssetModifier::CompileBlueprint(UBlueprint* Blueprint, FString& OutError)
{
	if (!Blueprint)
	{
		OutError = TEXT("Blueprint is null");
		return false;
	}

	// Mark as modified before compilation
	MarkModified(Blueprint);

	// Compile the Blueprint
	FKismetEditorUtilities::CompileBlueprint(Blueprint, EBlueprintCompileOptions::None);

	// Check compilation status
	if (Blueprint->Status == BS_Error)
	{
		OutError = FString::Printf(TEXT("Blueprint compilation failed with errors: %s"), *Blueprint->GetName());
		return false;
	}

	if (Blueprint->Status == BS_UpToDateWithWarnings)
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("Blueprint compiled with warnings: %s"), *Blueprint->GetName());
	}

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Successfully compiled Blueprint: %s"), *Blueprint->GetName());
	return true;
}

void FAssetModifier::RefreshBlueprintNodes(UBlueprint* Blueprint)
{
	if (!Blueprint)
	{
		return;
	}

	// Refresh all graphs
	for (UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		if (Graph)
		{
			FBlueprintEditorUtils::RefreshGraphNodes(Graph);
		}
	}

	// Refresh function graphs
	for (UEdGraph* FunctionGraph : Blueprint->FunctionGraphs)
	{
		if (FunctionGraph)
		{
			FBlueprintEditorUtils::RefreshGraphNodes(FunctionGraph);
		}
	}

	// Refresh macro graphs
	for (UEdGraph* MacroGraph : Blueprint->MacroGraphs)
	{
		if (MacroGraph)
		{
			FBlueprintEditorUtils::RefreshGraphNodes(MacroGraph);
		}
	}

	UE_LOG(LogUEClawBridgeAPI, Verbose, TEXT("Refreshed Blueprint nodes: %s"), *Blueprint->GetName());
}

void FAssetModifier::RefreshMaterial(UMaterial* Material)
{
	if (!Material)
	{
		return;
	}

	// Trigger recompilation and editor refresh
	Material->PreEditChange(nullptr);
	Material->PostEditChange();
	
	UE_LOG(LogUEClawBridgeAPI, Verbose, TEXT("Refreshed Material: %s"), *Material->GetName());
}

UEdGraph* FAssetModifier::FindGraphByName(UBlueprint* Blueprint, const FString& GraphName)
{
	if (!Blueprint)
	{
		return nullptr;
	}

	// Search in Ubergraph pages
	for (UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		if (Graph && Graph->GetFName().ToString() == GraphName)
		{
			return Graph;
		}
	}

	// Search in function graphs
	for (UEdGraph* Graph : Blueprint->FunctionGraphs)
	{
		if (Graph && Graph->GetFName().ToString() == GraphName)
		{
			return Graph;
		}
	}

	// Search in macro graphs
	for (UEdGraph* Graph : Blueprint->MacroGraphs)
	{
		if (Graph && Graph->GetFName().ToString() == GraphName)
		{
			return Graph;
		}
	}

	// For AnimBlueprint, anim graphs are in regular graph arrays — no special handling needed in UE 5.7

	return nullptr;
}

UEdGraphNode* FAssetModifier::FindNodeByGuid(UBlueprint* Blueprint, const FGuid& NodeGuid)
{
	if (!Blueprint || !NodeGuid.IsValid())
	{
		return nullptr;
	}

	TArray<UEdGraph*> AllGraphs = GetAllSearchableGraphs(Blueprint);

	for (UEdGraph* Graph : AllGraphs)
	{
		if (!Graph)
		{
			continue;
		}

		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (Node && Node->NodeGuid == NodeGuid)
			{
				return Node;
			}
		}
	}

	return nullptr;
}

TArray<UEdGraph*> FAssetModifier::GetAllSearchableGraphs(UBlueprint* Blueprint)
{
	TArray<UEdGraph*> AllGraphs;

	if (!Blueprint)
	{
		return AllGraphs;
	}

	// Add all standard Blueprint graphs
	AllGraphs.Append(Blueprint->UbergraphPages);
	AllGraphs.Append(Blueprint->FunctionGraphs);
	AllGraphs.Append(Blueprint->MacroGraphs);

	// AnimBlueprint anim graphs are included in the standard graph arrays in UE 5.7

	return AllGraphs;
}

FProperty* FAssetModifier::FindPropertyByPath(
	UObject* Object,
	const FString& PropertyPath,
	void*& OutContainer,
	FString& OutError)
{
	if (!Object)
	{
		OutError = TEXT("Object is null");
		return nullptr;
	}

	if (PropertyPath.IsEmpty())
	{
		OutError = TEXT("Property path is empty");
		return nullptr;
	}

	TArray<FString> PathSegments;
	PropertyPath.ParseIntoArray(PathSegments, TEXT("."), true);

	UObject* CurrentObject = Object;
	void* CurrentContainer = Object;
	FProperty* CurrentProperty = nullptr;

	for (int32 SegmentIndex = 0; SegmentIndex < PathSegments.Num(); SegmentIndex++)
	{
		const FString& Segment = PathSegments[SegmentIndex];
		
		// Parse potential array index
		FString PropertyName;
		int32 ArrayIndex = INDEX_NONE;
		if (!ParseArrayIndex(Segment, PropertyName, ArrayIndex))
		{
			OutError = FString::Printf(TEXT("Failed to parse property segment: %s"), *Segment);
			return nullptr;
		}

		// Find property in current object's class
		FProperty* Property = nullptr;
		if (CurrentObject)
		{
			Property = CurrentObject->GetClass()->FindPropertyByName(*PropertyName);
		}
		else
		{
			// We're dealing with a struct property
			if (FStructProperty* StructProp = CastField<FStructProperty>(CurrentProperty))
			{
				Property = StructProp->Struct->FindPropertyByName(*PropertyName);
			}
		}

		if (!Property)
		{
			OutError = FString::Printf(TEXT("Property not found: %s"), *PropertyName);
			return nullptr;
		}

		// Handle array indexing
		if (ArrayIndex != INDEX_NONE)
		{
			FArrayProperty* ArrayProp = CastField<FArrayProperty>(Property);
			if (!ArrayProp)
			{
				OutError = FString::Printf(TEXT("Property is not an array: %s"), *PropertyName);
				return nullptr;
			}

			const void* ArrayPtr = Property->ContainerPtrToValuePtr<void>(CurrentContainer);
			FScriptArrayHelper ArrayHelper(ArrayProp, ArrayPtr);

			if (!ArrayHelper.IsValidIndex(ArrayIndex))
			{
				OutError = FString::Printf(TEXT("Array index out of bounds: %s[%d]"), *PropertyName, ArrayIndex);
				return nullptr;
			}

			// If this is the last segment, return the array property with container pointing to the element
			if (SegmentIndex == PathSegments.Num() - 1)
			{
				OutContainer = static_cast<void*>(ArrayHelper.GetRawPtr(ArrayIndex));
				return ArrayProp->Inner;
			}

			// Move to the array element for nested access
			CurrentContainer = static_cast<void*>(ArrayHelper.GetRawPtr(ArrayIndex));
			CurrentProperty = ArrayProp->Inner;

			// If it's an object property, get the object
			if (FObjectProperty* ObjProp = CastField<FObjectProperty>(ArrayProp->Inner))
			{
				CurrentObject = ObjProp->GetObjectPropertyValue(CurrentContainer);
			}
			else
			{
				CurrentObject = nullptr;
			}
		}
		else
		{
			// If this is the last segment, we found our target property
			if (SegmentIndex == PathSegments.Num() - 1)
			{
				OutContainer = CurrentContainer;
				return Property;
			}

			// Move deeper into the object hierarchy
			if (FObjectProperty* ObjectProp = CastField<FObjectProperty>(Property))
			{
				const void* PropertyPtr = Property->ContainerPtrToValuePtr<void>(CurrentContainer);
				CurrentObject = ObjectProp->GetObjectPropertyValue(PropertyPtr);
				CurrentContainer = CurrentObject;
			}
			else if (FStructProperty* StructProp = CastField<FStructProperty>(Property))
			{
				CurrentContainer = Property->ContainerPtrToValuePtr<void>(CurrentContainer);
				CurrentObject = nullptr;
			}
			else
			{
				OutError = FString::Printf(TEXT("Cannot navigate into property: %s (not object or struct)"), *PropertyName);
				return nullptr;
			}

			CurrentProperty = Property;
		}
	}

	OutError = TEXT("Unexpected end of property path");
	return nullptr;
}

bool FAssetModifier::SetPropertyFromJson(
	FProperty* Property,
	void* Container,
	const TSharedPtr<FJsonValue>& JsonValue,
	FString& OutError)
{
	// Delegate to PropertySerializer
	return FPropertySerializer::DeserializePropertyValue(Property, Container, JsonValue, OutError);
}

bool FAssetModifier::ParseArrayIndex(const FString& PathSegment, FString& OutName, int32& OutIndex)
{
	OutIndex = INDEX_NONE;

	int32 BracketStart = PathSegment.Find(TEXT("["));
	if (BracketStart == INDEX_NONE)
	{
		// No brackets, just a simple property name
		OutName = PathSegment;
		return true;
	}

	int32 BracketEnd = PathSegment.Find(TEXT("]"), ESearchCase::IgnoreCase, ESearchDir::FromStart, BracketStart);
	if (BracketEnd == INDEX_NONE)
	{
		// Opening bracket without closing bracket
		return false;
	}

	// Extract property name (before bracket)
	OutName = PathSegment.Left(BracketStart);

	// Extract index (between brackets)
	FString IndexStr = PathSegment.Mid(BracketStart + 1, BracketEnd - BracketStart - 1);
	if (!IndexStr.IsNumeric())
	{
		return false;
	}

	OutIndex = FCString::Atoi(*IndexStr);
	return OutIndex >= 0;
}