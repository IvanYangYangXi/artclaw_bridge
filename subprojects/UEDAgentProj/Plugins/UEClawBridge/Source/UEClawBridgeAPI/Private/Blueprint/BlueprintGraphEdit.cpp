// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "Blueprint/BlueprintGraphEdit.h"
#include "UEClawBridgeAPI.h"
#include "Utils/JsonHelpers.h"
#include "Utils/AssetModifier.h"
#include "Utils/PropertySerializer.h"
#include "Utils/GraphLayoutUtil.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "K2Node.h"
#include "K2Node_CallFunction.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet/KismetSystemLibrary.h"
#include "UObject/UObjectIterator.h"
#include "ScopedTransaction.h"

FString UBlueprintGraphEdit::AddGraphNode(
	const FString& AssetPath,
	const FString& NodeClass,
	const FString& GraphName,
	float PosX,
	float PosY,
	bool bAutoPosition,
	const FString& ConnectToNode,
	const FString& ConnectToPin,
	const FString& PropertiesJson)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("AddGraphNode: %s, class=%s, graph=%s"), *AssetPath, *NodeClass, *GraphName);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	UEdGraph* TargetGraph = FAssetModifier::FindGraphByName(Blueprint, GraphName);
	if (!TargetGraph) return ClawJson::MakeError(FString::Printf(TEXT("Graph not found: %s"), *GraphName));

	TSharedPtr<FJsonObject> Properties;
	if (!PropertiesJson.IsEmpty())
	{
		FString JsonError;
		Properties = ClawJson::Parse(PropertiesJson, JsonError);
		if (!Properties.IsValid())
		{
			return ClawJson::MakeError(FString::Printf(TEXT("Invalid properties JSON: %s"), *JsonError));
		}
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Add %s node"), *NodeClass));

	FVector2D Position(PosX, PosY);
	FString Error;
	UEdGraphNode* NewNode = CreateBlueprintNode(
		Blueprint, TargetGraph, NodeClass, Position, bAutoPosition,
		ConnectToNode, ConnectToPin, Properties, Error);

	if (!NewNode) return ClawJson::MakeError(Error);

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetStringField(TEXT("node_guid"), NewNode->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens));
	Result->SetStringField(TEXT("node_class"), NewNode->GetClass()->GetName());
	Result->SetStringField(TEXT("graph"), GraphName);
	Result->SetBoolField(TEXT("needs_compile"), true);
	Result->SetBoolField(TEXT("needs_save"), true);

	TSharedPtr<FJsonObject> PositionJson = MakeShareable(new FJsonObject);
	PositionJson->SetNumberField(TEXT("x"), NewNode->NodePosX);
	PositionJson->SetNumberField(TEXT("y"), NewNode->NodePosY);
	Result->SetObjectField(TEXT("position"), PositionJson);

	if (!Error.IsEmpty())
	{
		Result->SetStringField(TEXT("property_warnings"), Error);
	}

	return ClawJson::ToString(Result);
}

bool UBlueprintGraphEdit::RemoveGraphNode(const FString& AssetPath, const FString& NodeGuid)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("RemoveGraphNode: %s, node=%s"), *AssetPath, *NodeGuid);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return false;

	FGuid ParsedGuid;
	if (!FGuid::Parse(NodeGuid, ParsedGuid)) return false;

	UEdGraphNode* Node = FAssetModifier::FindNodeByGuid(Blueprint, ParsedGuid);
	if (!Node) return false;

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(TEXT("Remove graph node"));
	FAssetModifier::MarkModified(Blueprint);

	UEdGraph* Graph = Node->GetGraph();
	if (Graph)
	{
		Graph->RemoveNode(Node, true);
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FAssetModifier::MarkPackageDirty(Blueprint);
	return true;
}

FString UBlueprintGraphEdit::SetNodePositions(const FString& AssetPath, const FString& PositionsJson)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("SetNodePositions: %s"), *AssetPath);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	TSharedPtr<FJsonValue> JsonValue;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PositionsJson);
	if (!FJsonSerializer::Deserialize(Reader, JsonValue) || !JsonValue.IsValid())
	{
		return ClawJson::MakeError(TEXT("Invalid JSON format"));
	}

	const TArray<TSharedPtr<FJsonValue>>* PositionsArray;
	if (!JsonValue->TryGetArray(PositionsArray))
	{
		return ClawJson::MakeError(TEXT("Expected array of position objects"));
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(TEXT("Set node positions"));
	FAssetModifier::MarkModified(Blueprint);

	TArray<TSharedPtr<FJsonValue>> UpdatedArray;
	int32 UpdatedCount = 0;

	for (const TSharedPtr<FJsonValue>& PosValue : *PositionsArray)
	{
		const TSharedPtr<FJsonObject>* PosObj;
		if (!PosValue->TryGetObject(PosObj)) continue;

		FString GuidStr;
		double X, Y;
		if (!(*PosObj)->TryGetStringField(TEXT("guid"), GuidStr) ||
			!(*PosObj)->TryGetNumberField(TEXT("x"), X) ||
			!(*PosObj)->TryGetNumberField(TEXT("y"), Y))
		{
			continue;
		}

		FGuid NodeGuid;
		if (FGuid::Parse(GuidStr, NodeGuid))
		{
			UEdGraphNode* Node = FAssetModifier::FindNodeByGuid(Blueprint, NodeGuid);
			if (Node)
			{
				Node->NodePosX = FMath::RoundToInt(X);
				Node->NodePosY = FMath::RoundToInt(Y);

				TSharedPtr<FJsonObject> UpdatedObj = MakeShareable(new FJsonObject);
				UpdatedObj->SetStringField(TEXT("guid"), GuidStr);
				UpdatedObj->SetNumberField(TEXT("x"), Node->NodePosX);
				UpdatedObj->SetNumberField(TEXT("y"), Node->NodePosY);
				UpdatedArray.Add(MakeShareable(new FJsonValueObject(UpdatedObj)));
				UpdatedCount++;
			}
		}
	}

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetNumberField(TEXT("updated_count"), UpdatedCount);
	Result->SetArrayField(TEXT("updated_nodes"), UpdatedArray);
	Result->SetBoolField(TEXT("needs_save"), UpdatedCount > 0);

	if (UpdatedCount > 0)
	{
		FAssetModifier::MarkPackageDirty(Blueprint);
	}

	return ClawJson::ToString(Result);
}

FString UBlueprintGraphEdit::CreateFunctionGraph(
	const FString& AssetPath,
	const FString& FunctionName,
	bool bIsPublic,
	const FString& ReturnTypeJson,
	const FString& ParametersJson)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("CreateFunctionGraph: %s, function=%s"), *AssetPath, *FunctionName);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	if (FAssetModifier::FindGraphByName(Blueprint, FunctionName))
	{
		return ClawJson::MakeError(FString::Printf(TEXT("Function already exists: %s"), *FunctionName));
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Create function %s"), *FunctionName));

	FAssetModifier::MarkModified(Blueprint);

	UEdGraph* NewGraph = FBlueprintEditorUtils::CreateNewGraph(
		Blueprint, FName(*FunctionName), UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());

	if (!NewGraph) return ClawJson::MakeError(TEXT("Failed to create function graph"));

	FBlueprintEditorUtils::AddFunctionGraph(Blueprint, NewGraph, true, static_cast<UFunction*>(nullptr));

	FGraphNodeCreator<UK2Node_FunctionEntry> EntryCreator(*NewGraph);
	UK2Node_FunctionEntry* EntryNode = EntryCreator.CreateNode();
	EntryNode->NodePosX = 0;
	EntryNode->NodePosY = 0;
	EntryCreator.Finalize();

	if (bIsPublic)
	{
		// Mark as public/callable — entry node flags handle visibility
		NewGraph->GetSchema()->SetNodeMetaData(EntryNode, FNodeMetadata::DefaultGraphNode);
	}

	FGraphNodeCreator<UK2Node_FunctionResult> ResultCreator(*NewGraph);
	UK2Node_FunctionResult* ResultNode = ResultCreator.CreateNode();
	ResultNode->NodePosX = 400;
	ResultNode->NodePosY = 0;
	ResultCreator.Finalize();

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FAssetModifier::MarkPackageDirty(Blueprint);

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetStringField(TEXT("function_name"), FunctionName);
	Result->SetStringField(TEXT("graph_name"), NewGraph->GetName());
	Result->SetBoolField(TEXT("is_public"), bIsPublic);
	Result->SetBoolField(TEXT("needs_compile"), true);
	Result->SetBoolField(TEXT("needs_save"), true);

	return ClawJson::ToString(Result);
}

// === Implementation helpers ===

UEdGraphNode* UBlueprintGraphEdit::CreateBlueprintNode(
	UBlueprint* Blueprint,
	UEdGraph* Graph,
	const FString& NodeClassName,
	const FVector2D& Position,
	bool bAutoPosition,
	const FString& ConnectToNodeGuid,
	const FString& ConnectToPinName,
	const TSharedPtr<FJsonObject>& Properties,
	FString& OutError)
{
	FString ClassError;
	UClass* NodeClass = FPropertySerializer::ResolveClass(NodeClassName, ClassError);

	if (!NodeClass && !NodeClassName.StartsWith(TEXT("K2Node")) && !NodeClassName.StartsWith(TEXT("UK2Node")))
	{
		FString PrefixedName = TEXT("UK2Node_") + NodeClassName;
		NodeClass = FPropertySerializer::ResolveClass(PrefixedName, ClassError);
		if (!NodeClass)
		{
			PrefixedName = TEXT("K2Node_") + NodeClassName;
			NodeClass = FPropertySerializer::ResolveClass(PrefixedName, ClassError);
		}
	}

	if (!NodeClass)
	{
		OutError = FString::Printf(TEXT("Node class not found: %s"), *NodeClassName);
		return nullptr;
	}

	if (!NodeClass->IsChildOf<UEdGraphNode>())
	{
		OutError = FString::Printf(TEXT("Class '%s' is not a UEdGraphNode subclass"), *NodeClassName);
		return nullptr;
	}

	FAssetModifier::MarkModified(Blueprint);

	UEdGraphNode* NewNode = NewObject<UEdGraphNode>(Graph, NodeClass, NAME_None, RF_Transactional);
	if (!NewNode)
	{
		OutError = FString::Printf(TEXT("Failed to create node of class %s"), *NodeClass->GetName());
		return nullptr;
	}

	NewNode->CreateNewGuid();

	FVector2D FinalPosition = Position;
	if (bAutoPosition)
	{
		UEdGraphNode* TargetNode = nullptr;
		UEdGraphPin* TargetPin = nullptr;

		if (!ConnectToNodeGuid.IsEmpty())
		{
			FGuid NodeGuid;
			if (FGuid::Parse(ConnectToNodeGuid, NodeGuid))
			{
				TargetNode = FAssetModifier::FindNodeByGuid(Blueprint, NodeGuid);
				if (TargetNode && !ConnectToPinName.IsEmpty())
				{
					for (UEdGraphPin* Pin : TargetNode->Pins)
					{
						if (Pin && Pin->PinName.ToString() == ConnectToPinName)
						{
							TargetPin = Pin;
							break;
						}
					}
				}
			}
		}

		FinalPosition = FGraphLayoutUtil::CalculateBlueprintNodePosition(Graph, TargetNode, TargetPin);
	}

	NewNode->NodePosX = FMath::RoundToInt(FinalPosition.X);
	NewNode->NodePosY = FMath::RoundToInt(FinalPosition.Y);

	// For K2Node_CallFunction: must set FunctionReference BEFORE AllocateDefaultPins,
	// because pin generation depends on knowing which function to call.
	UK2Node_CallFunction* CallFuncNode = Cast<UK2Node_CallFunction>(NewNode);
	if (CallFuncNode && Properties.IsValid())
	{
		// Extract FunctionReference to set it early
		const TSharedPtr<FJsonObject>* FuncRefObj = nullptr;
		if (Properties->HasField(TEXT("FunctionReference")))
		{
			const TSharedPtr<FJsonValue>& FuncRefVal = Properties->Values.FindChecked(TEXT("FunctionReference"));
			if (FuncRefVal->Type == EJson::Object)
			{
				FuncRefObj = &(FuncRefVal->AsObject());
			}
		}

		if (FuncRefObj && FuncRefObj->IsValid())
		{
			FString MemberName;
			if ((*FuncRefObj)->TryGetStringField(TEXT("MemberName"), MemberName))
			{
				FString MemberParent;
				(*FuncRefObj)->TryGetStringField(TEXT("MemberParent"), MemberParent);

				UClass* OwnerClass = nullptr;
				if (!MemberParent.IsEmpty())
				{
					FString ResolveError;
					OwnerClass = FPropertySerializer::ResolveClass(MemberParent, ResolveError);
				}
				if (!OwnerClass)
				{
					OwnerClass = UKismetSystemLibrary::StaticClass();
				}

				UFunction* Func = OwnerClass->FindFunctionByName(*MemberName);
				if (!Func)
				{
					// Search all classes for the function
					for (TObjectIterator<UClass> It; It; ++It)
					{
						Func = It->FindFunctionByName(*MemberName);
						if (Func)
						{
							OwnerClass = *It;
							break;
						}
					}
				}

				if (Func)
				{
					CallFuncNode->SetFromFunction(Func);
				}
				else
				{
					// Fallback: set member reference directly
					FMemberReference FuncRef;
					FuncRef.SetExternalMember(FName(*MemberName), OwnerClass);
					CallFuncNode->FunctionReference = FuncRef;
				}
			}
		}
	}

	// Allocate pins (for CallFunction this now works because FunctionReference is set)
	if (UK2Node* K2Node = Cast<UK2Node>(NewNode))
	{
		K2Node->AllocateDefaultPins();
	}
	else
	{
		NewNode->AllocateDefaultPins();
	}

	Graph->AddNode(NewNode, true, true);

	if (Properties.IsValid())
	{
		// For CallFunction, skip FunctionReference since it was already applied
		TSharedPtr<FJsonObject> RemainingProps = Properties;
		if (CallFuncNode && Properties->HasField(TEXT("FunctionReference")))
		{
			RemainingProps = MakeShareable(new FJsonObject);
			for (const auto& Pair : Properties->Values)
			{
				if (Pair.Key != TEXT("FunctionReference"))
				{
					RemainingProps->SetField(Pair.Key, Pair.Value);
				}
			}
		}

		if (RemainingProps->Values.Num() > 0)
		{
			TArray<FString> PropertyErrors = ApplyNodeProperties(NewNode, RemainingProps);
			if (PropertyErrors.Num() > 0)
			{
				OutError = FString::Join(PropertyErrors, TEXT("; "));
			}
		}
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FAssetModifier::MarkPackageDirty(Blueprint);

	return NewNode;
}

TArray<FString> UBlueprintGraphEdit::ApplyNodeProperties(UObject* Node, const TSharedPtr<FJsonObject>& Properties)
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

	// Try unresolved properties as pin default values
	UEdGraphNode* GraphNode = Cast<UEdGraphNode>(Node);
	if (GraphNode)
	{
		TArray<FString> ResolvedByPin;
		for (const FString& ErrMsg : Errors)
		{
			if (!ErrMsg.StartsWith(TEXT("Property not found: "))) continue;
			FString PropName = ErrMsg.RightChop(20);
			if (PropName.IsEmpty()) continue;

			for (UEdGraphPin* Pin : GraphNode->Pins)
			{
				if (Pin && Pin->PinName.ToString() == PropName)
				{
					const TSharedPtr<FJsonValue>* ValuePtr = Properties->Values.Find(PropName);
					if (ValuePtr && ValuePtr->IsValid())
					{
						FString StringValue;
						if ((*ValuePtr)->Type == EJson::Number)
							StringValue = FString::Printf(TEXT("%g"), (*ValuePtr)->AsNumber());
						else if ((*ValuePtr)->Type == EJson::Boolean)
							StringValue = (*ValuePtr)->AsBool() ? TEXT("true") : TEXT("false");
						else
							StringValue = (*ValuePtr)->AsString();

						Pin->DefaultValue = StringValue;
						ResolvedByPin.Add(PropName);
					}
					break;
				}
			}
		}

		for (const FString& Resolved : ResolvedByPin)
		{
			Errors.Remove(FString::Printf(TEXT("Property not found: %s"), *Resolved));
		}
	}

	return Errors;
}

TSharedPtr<FJsonObject> UBlueprintGraphEdit::ParseJsonString(const FString& JsonString, FString& OutError)
{
	return ClawJson::Parse(JsonString, OutError);
}
