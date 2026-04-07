// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "Blueprint/BlueprintNodeProperty.h"
#include "UEClawBridgeAPI.h"
#include "Utils/JsonHelpers.h"
#include "Utils/AssetModifier.h"
#include "Utils/PropertySerializer.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "K2Node.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "K2Node_CallFunction.h"
#include "ScopedTransaction.h"

FString UBlueprintNodeProperty::SetNodeProperty(
	const FString& AssetPath,
	const FString& NodeGuid,
	const FString& PropertiesJson)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("SetNodeProperty: %s, node=%s"), *AssetPath, *NodeGuid);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	FGuid ParsedGuid;
	if (!FGuid::Parse(NodeGuid, ParsedGuid))
	{
		return ClawJson::MakeError(FString::Printf(TEXT("Invalid GUID format: %s"), *NodeGuid));
	}

	UEdGraphNode* Node = FAssetModifier::FindNodeByGuid(Blueprint, ParsedGuid);
	if (!Node) return ClawJson::MakeError(FString::Printf(TEXT("Node not found: %s"), *NodeGuid));

	FString JsonError;
	TSharedPtr<FJsonObject> Properties = ClawJson::Parse(PropertiesJson, JsonError);
	if (!Properties.IsValid())
	{
		return ClawJson::MakeError(FString::Printf(TEXT("Invalid properties JSON: %s"), *JsonError));
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(TEXT("Set node properties"));
	FAssetModifier::MarkModified(Blueprint);

	TArray<FString> PropertyErrors = ApplyNodeProperties(Node, Properties);

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetStringField(TEXT("node_guid"), NodeGuid);
	Result->SetBoolField(TEXT("success"), PropertyErrors.Num() == 0);
	Result->SetBoolField(TEXT("needs_compile"), true);
	Result->SetBoolField(TEXT("needs_save"), true);

	if (PropertyErrors.Num() > 0)
	{
		TArray<TSharedPtr<FJsonValue>> ErrorsArray;
		for (const FString& Error : PropertyErrors)
		{
			ErrorsArray.Add(MakeShareable(new FJsonValueString(Error)));
		}
		Result->SetArrayField(TEXT("property_errors"), ErrorsArray);
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FAssetModifier::MarkPackageDirty(Blueprint);

	return ClawJson::ToString(Result);
}

FString UBlueprintNodeProperty::CompileBlueprint(const FString& AssetPath)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("CompileBlueprint: %s"), *AssetPath);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	FString CompileError;
	bool bCompileSuccess = FAssetModifier::CompileBlueprint(Blueprint, CompileError);

	TArray<FString> Errors;
	TArray<FString> Warnings;
	CollectCompilationErrors(Blueprint, Errors, Warnings);

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetBoolField(TEXT("success"), bCompileSuccess && Errors.Num() == 0);
	Result->SetBoolField(TEXT("compiled"), true);

	if (!CompileError.IsEmpty())
	{
		Result->SetStringField(TEXT("compile_message"), CompileError);
	}

	TArray<TSharedPtr<FJsonValue>> ErrorsArray;
	for (const FString& Error : Errors) ErrorsArray.Add(MakeShareable(new FJsonValueString(Error)));
	Result->SetArrayField(TEXT("errors"), ErrorsArray);
	Result->SetNumberField(TEXT("error_count"), Errors.Num());

	TArray<TSharedPtr<FJsonValue>> WarningsArray;
	for (const FString& Warning : Warnings) WarningsArray.Add(MakeShareable(new FJsonValueString(Warning)));
	Result->SetArrayField(TEXT("warnings"), WarningsArray);
	Result->SetNumberField(TEXT("warning_count"), Warnings.Num());

	Result->SetStringField(TEXT("status"), Blueprint->Status == BS_UpToDate ? TEXT("up_to_date") :
		Blueprint->Status == BS_Dirty ? TEXT("dirty") :
		Blueprint->Status == BS_Error ? TEXT("error") : TEXT("unknown"));

	return ClawJson::ToString(Result);
}

FString UBlueprintNodeProperty::ModifyInterface(
	const FString& AssetPath,
	const FString& Action,
	const FString& InterfaceName)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("ModifyInterface: %s %s on %s"), *Action, *InterfaceName, *AssetPath);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	FString InterfaceError;
	UClass* InterfaceClass = FindInterfaceClass(InterfaceName, InterfaceError);
	if (!InterfaceClass) return ClawJson::MakeError(InterfaceError);

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("%s interface %s"), *Action, *InterfaceName));
	FAssetModifier::MarkModified(Blueprint);

	FString OperationError;
	bool bSuccess = false;

	if (Action.Equals(TEXT("add"), ESearchCase::IgnoreCase))
		bSuccess = AddInterfaceToBlueprint(Blueprint, InterfaceClass, OperationError);
	else if (Action.Equals(TEXT("remove"), ESearchCase::IgnoreCase))
		bSuccess = RemoveInterfaceFromBlueprint(Blueprint, InterfaceClass, OperationError);
	else
		OperationError = FString::Printf(TEXT("Invalid action: %s. Use 'add' or 'remove'"), *Action);

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetStringField(TEXT("action"), Action);
	Result->SetStringField(TEXT("interface_name"), InterfaceName);
	Result->SetBoolField(TEXT("success"), bSuccess);

	if (!bSuccess)
	{
		Result->SetStringField(TEXT("error"), OperationError);
	}
	else
	{
		Result->SetBoolField(TEXT("needs_compile"), true);
		Result->SetBoolField(TEXT("needs_save"), true);
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FAssetModifier::MarkPackageDirty(Blueprint);
	}

	return ClawJson::ToString(Result);
}

FString UBlueprintNodeProperty::SetBlueprintVariable(
	const FString& AssetPath,
	const FString& VariableName,
	const FString& VariableTypeJson,
	bool bIsArray,
	const FString& CategoryName)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("SetBlueprintVariable: %s, var=%s"), *AssetPath, *VariableName);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	FString JsonError;
	TSharedPtr<FJsonObject> TypeJson = ClawJson::Parse(VariableTypeJson, JsonError);
	if (!TypeJson.IsValid())
	{
		return ClawJson::MakeError(FString::Printf(TEXT("Invalid type JSON: %s"), *JsonError));
	}

	FString TypeError;
	FEdGraphPinType PinType = ParseVariableType(TypeJson, TypeError);
	if (!TypeError.IsEmpty()) return ClawJson::MakeError(TypeError);

	if (bIsArray) PinType.ContainerType = EPinContainerType::Array;

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Set variable %s"), *VariableName));
	FAssetModifier::MarkModified(Blueprint);

	FBPVariableDescription* ExistingVar = FindBlueprintVariable(Blueprint, VariableName);
	bool bIsNewVariable = (ExistingVar == nullptr);

	FString VariableError;
	bool bSuccess = false;

	if (bIsNewVariable)
	{
		bSuccess = CreateBlueprintVariable(Blueprint, VariableName, PinType, CategoryName, VariableError);
	}
	else
	{
		ExistingVar->VarType = PinType;
		ExistingVar->Category = FText::FromString(CategoryName);
		bSuccess = true;
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetStringField(TEXT("variable_name"), VariableName);
	Result->SetBoolField(TEXT("success"), bSuccess);
	Result->SetBoolField(TEXT("is_new_variable"), bIsNewVariable);

	if (!bSuccess)
	{
		Result->SetStringField(TEXT("error"), VariableError);
	}
	else
	{
		Result->SetBoolField(TEXT("needs_compile"), true);
		Result->SetBoolField(TEXT("needs_save"), true);
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FAssetModifier::MarkPackageDirty(Blueprint);
	}

	return ClawJson::ToString(Result);
}

FString UBlueprintNodeProperty::ValidateBlueprintStructure(const FString& AssetPath, bool bAutoFix)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("ValidateBlueprintStructure: %s"), *AssetPath);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	TArray<FString> Issues;
	TArray<FString> Fixes;
	int32 OrphanedNodes = 0;
	int32 DisconnectedPins = 0;
	int32 InvalidConnections = 0;

	TArray<UEdGraph*> AllGraphs = FAssetModifier::GetAllSearchableGraphs(Blueprint);
	for (UEdGraph* Graph : AllGraphs)
	{
		if (!Graph) continue;

		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (!Node) continue;

			bool bHasConnections = false;
			for (UEdGraphPin* Pin : Node->Pins)
			{
				if (Pin && Pin->LinkedTo.Num() > 0) { bHasConnections = true; break; }
			}
			if (!bHasConnections) OrphanedNodes++;

			for (UEdGraphPin* Pin : Node->Pins)
			{
				if (!Pin) continue;
				for (UEdGraphPin* LinkedPin : Pin->LinkedTo)
				{
					if (!LinkedPin || !LinkedPin->GetOwningNode())
					{
						DisconnectedPins++;
						if (bAutoFix)
						{
							Pin->LinkedTo.Remove(LinkedPin);
							Fixes.Add(FString::Printf(TEXT("Removed invalid connection from %s"), *Pin->PinName.ToString()));
						}
					}
				}
			}
		}
	}

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetNumberField(TEXT("orphaned_nodes"), OrphanedNodes);
	Result->SetNumberField(TEXT("disconnected_pins"), DisconnectedPins);
	Result->SetNumberField(TEXT("invalid_connections"), InvalidConnections);

	if (OrphanedNodes > 0) Issues.Add(FString::Printf(TEXT("%d orphaned nodes found"), OrphanedNodes));
	if (DisconnectedPins > 0) Issues.Add(FString::Printf(TEXT("%d disconnected pins found"), DisconnectedPins));

	TArray<TSharedPtr<FJsonValue>> IssuesArray;
	for (const FString& Issue : Issues) IssuesArray.Add(MakeShareable(new FJsonValueString(Issue)));
	Result->SetArrayField(TEXT("issues"), IssuesArray);

	TArray<TSharedPtr<FJsonValue>> FixesArray;
	for (const FString& Fix : Fixes) FixesArray.Add(MakeShareable(new FJsonValueString(Fix)));
	Result->SetArrayField(TEXT("fixes_applied"), FixesArray);

	Result->SetBoolField(TEXT("is_valid"), Issues.Num() == 0);
	Result->SetBoolField(TEXT("auto_fix_enabled"), bAutoFix);
	Result->SetNumberField(TEXT("fixes_count"), Fixes.Num());

	if (Fixes.Num() > 0)
	{
		FAssetModifier::MarkPackageDirty(Blueprint);
		Result->SetBoolField(TEXT("needs_save"), true);
	}

	return ClawJson::ToString(Result);
}

// === Implementation helpers ===

TArray<FString> UBlueprintNodeProperty::ApplyNodeProperties(UObject* Node, const TSharedPtr<FJsonObject>& Properties)
{
	TArray<FString> Errors;
	if (!Node || !Properties.IsValid()) return Errors;

	for (const auto& Pair : Properties->Values)
	{
		const FString& PropertyName = Pair.Key;
		const TSharedPtr<FJsonValue>& Value = Pair.Value;

		FProperty* Property = Node->GetClass()->FindPropertyByName(*PropertyName);
		void* Container = Node;

		if (!Property)
		{
			FString FindError;
			void* TempContainer = nullptr;
			Property = FAssetModifier::FindPropertyByPath(Node, PropertyName, TempContainer, FindError);
			Container = TempContainer;
			if (!Property)
			{
				if (UEdGraphNode* GraphNode = Cast<UEdGraphNode>(Node))
				{
					FString StringValue;
					if (Value->Type == EJson::Number)
						StringValue = FString::Printf(TEXT("%g"), Value->AsNumber());
					else if (Value->Type == EJson::Boolean)
						StringValue = Value->AsBool() ? TEXT("true") : TEXT("false");
					else
						StringValue = Value->AsString();

					if (SetPinDefaultValue(GraphNode, PropertyName, StringValue))
						continue;
				}

				Errors.Add(FString::Printf(TEXT("Property not found: %s"), *PropertyName));
				continue;
			}
		}

		FString SetError;
		if (!FPropertySerializer::DeserializePropertyValue(Property, Container, Value, SetError))
		{
			Errors.Add(FString::Printf(TEXT("Failed to set property %s: %s"), *PropertyName, *SetError));
		}
	}

	return Errors;
}

bool UBlueprintNodeProperty::SetPinDefaultValue(UEdGraphNode* Node, const FString& PinName, const FString& Value)
{
	if (!Node) return false;
	for (UEdGraphPin* Pin : Node->Pins)
	{
		if (Pin && Pin->PinName.ToString() == PinName)
		{
			Pin->DefaultValue = Value;
			return true;
		}
	}
	return false;
}

void UBlueprintNodeProperty::CollectCompilationErrors(UBlueprint* Blueprint, TArray<FString>& OutErrors, TArray<FString>& OutWarnings)
{
	if (Blueprint->Status == BS_Error) OutErrors.Add(TEXT("Blueprint has compilation errors"));
	if (Blueprint->Status == BS_Dirty) OutWarnings.Add(TEXT("Blueprint needs recompilation"));
}

UClass* UBlueprintNodeProperty::FindInterfaceClass(const FString& InterfaceName, FString& OutError)
{
	FString ClassError;
	UClass* InterfaceClass = FPropertySerializer::ResolveClass(InterfaceName, ClassError);
	if (!InterfaceClass) { OutError = FString::Printf(TEXT("Interface class not found: %s"), *InterfaceName); return nullptr; }
	if (!InterfaceClass->HasAnyClassFlags(CLASS_Interface)) { OutError = FString::Printf(TEXT("Class is not an interface: %s"), *InterfaceName); return nullptr; }
	return InterfaceClass;
}

bool UBlueprintNodeProperty::AddInterfaceToBlueprint(UBlueprint* Blueprint, UClass* InterfaceClass, FString& OutError)
{
	for (const FBPInterfaceDescription& InterfaceDesc : Blueprint->ImplementedInterfaces)
	{
		if (InterfaceDesc.Interface == InterfaceClass) { OutError = TEXT("Interface is already implemented"); return false; }
	}
	FBlueprintEditorUtils::ImplementNewInterface(Blueprint, FName(*InterfaceClass->GetName()));
	return true;
}

bool UBlueprintNodeProperty::RemoveInterfaceFromBlueprint(UBlueprint* Blueprint, UClass* InterfaceClass, FString& OutError)
{
	for (int32 i = 0; i < Blueprint->ImplementedInterfaces.Num(); i++)
	{
		if (Blueprint->ImplementedInterfaces[i].Interface == InterfaceClass)
		{
			FBlueprintEditorUtils::RemoveInterface(Blueprint, FName(*InterfaceClass->GetName()));
			return true;
		}
	}
	OutError = TEXT("Interface not found in Blueprint");
	return false;
}

FBPVariableDescription* UBlueprintNodeProperty::FindBlueprintVariable(UBlueprint* Blueprint, const FString& VariableName)
{
	for (FBPVariableDescription& VarDesc : Blueprint->NewVariables)
	{
		if (VarDesc.VarName.ToString() == VariableName) return &VarDesc;
	}
	return nullptr;
}

bool UBlueprintNodeProperty::CreateBlueprintVariable(UBlueprint* Blueprint, const FString& VariableName, const FEdGraphPinType& PinType, const FString& CategoryName, FString& OutError)
{
	FBPVariableDescription NewVar;
	NewVar.VarName = FName(*VariableName);
	NewVar.VarType = PinType;
	NewVar.Category = FText::FromString(CategoryName);
	NewVar.PropertyFlags = CPF_Edit | CPF_BlueprintVisible;
	Blueprint->NewVariables.Add(NewVar);
	return true;
}

TSharedPtr<FJsonObject> UBlueprintNodeProperty::ParseJsonString(const FString& JsonString, FString& OutError)
{
	return ClawJson::Parse(JsonString, OutError);
}

FEdGraphPinType UBlueprintNodeProperty::ParseVariableType(const TSharedPtr<FJsonObject>& TypeJson, FString& OutError)
{
	FEdGraphPinType PinType;

	FString TypeName;
	if (!TypeJson->TryGetStringField(TEXT("Type"), TypeName))
	{
		OutError = TEXT("Missing 'Type' field in variable type JSON");
		return PinType;
	}

	if (TypeName == TEXT("bool"))
		PinType.PinCategory = UEdGraphSchema_K2::PC_Boolean;
	else if (TypeName == TEXT("int32") || TypeName == TEXT("int"))
		PinType.PinCategory = UEdGraphSchema_K2::PC_Int;
	else if (TypeName == TEXT("float"))
		PinType.PinCategory = UEdGraphSchema_K2::PC_Float;
	else if (TypeName == TEXT("FString") || TypeName == TEXT("string"))
		PinType.PinCategory = UEdGraphSchema_K2::PC_String;
	else if (TypeName == TEXT("FVector"))
	{
		PinType.PinCategory = UEdGraphSchema_K2::PC_Struct;
		PinType.PinSubCategoryObject = TBaseStructure<FVector>::Get();
	}
	else if (TypeName == TEXT("FRotator"))
	{
		PinType.PinCategory = UEdGraphSchema_K2::PC_Struct;
		PinType.PinSubCategoryObject = TBaseStructure<FRotator>::Get();
	}
	else
	{
		FString ClassError;
		UClass* ObjectClass = FPropertySerializer::ResolveClass(TypeName, ClassError);
		if (ObjectClass)
		{
			PinType.PinCategory = UEdGraphSchema_K2::PC_Object;
			PinType.PinSubCategoryObject = ObjectClass;
		}
		else
		{
			OutError = FString::Printf(TEXT("Unknown variable type: %s"), *TypeName);
		}
	}

	return PinType;
}
