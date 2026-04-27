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
#include "K2Node_MacroInstance.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_DynamicCast.h"
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

	// --- K2Node_VariableGet / K2Node_VariableSet: set VariableReference before AllocateDefaultPins ---
	UK2Node_Variable* VarNode = Cast<UK2Node_Variable>(NewNode);
	if (VarNode && Properties.IsValid())
	{
		FString VarName;
		// Accept "VariableName" (shorthand) or "VariableReference.MemberName"
		if (Properties->TryGetStringField(TEXT("VariableName"), VarName) ||
			Properties->TryGetStringField(TEXT("variable_name"), VarName))
		{
			// Good — we have a name from shorthand
		}
		else if (Properties->HasField(TEXT("VariableReference")))
		{
			const auto& VarRefVal = Properties->Values.FindChecked(TEXT("VariableReference"));
			if (VarRefVal->Type == EJson::Object)
			{
				VarRefVal->AsObject()->TryGetStringField(TEXT("MemberName"), VarName);
			}
		}

		if (!VarName.IsEmpty())
		{
			// Find the property on the Blueprint's generated class or its parents
			UClass* VarOwnerClass = Blueprint->GeneratedClass
				? Blueprint->GeneratedClass
				: Blueprint->ParentClass;

			FProperty* FoundProp = VarOwnerClass
				? VarOwnerClass->FindPropertyByName(FName(*VarName))
				: nullptr;

			if (FoundProp)
			{
				// Use SetFromProperty for correct MemberGuid resolution on BP variables
				FMemberReference VarRef;
				VarRef.SetFromField<FProperty>(FoundProp, false);  // bSelfContext = false initially
				VarNode->VariableReference = VarRef;
				// Ensure self-context is set for own variables
				if (FoundProp->GetOwnerClass() && Blueprint->GeneratedClass &&
					FoundProp->GetOwnerClass()->IsChildOf(Blueprint->GeneratedClass->GetSuperClass()))
				{
					VarNode->VariableReference.SetSelfMember(FName(*VarName));
				}
			}
			else
			{
				// Property not found on compiled class — set by name with self-context
				// (works for BP variables when blueprint hasn't been compiled yet)
				VarNode->VariableReference.SetSelfMember(FName(*VarName));
			}
		}
	}

	// --- K2Node_MacroInstance: find macro graph (apply AFTER AddNode) ---
	UK2Node_MacroInstance* MacroNode = Cast<UK2Node_MacroInstance>(NewNode);
	UEdGraph* FoundMacroGraph = nullptr;
	if (MacroNode && Properties.IsValid())
	{
		FString MacroName;
		// Accept "MacroReference.MacroName" or "MacroName" shorthand
		if (Properties->TryGetStringField(TEXT("MacroName"), MacroName) ||
			Properties->TryGetStringField(TEXT("macro_name"), MacroName))
		{
			// Good
		}
		else if (Properties->HasField(TEXT("MacroReference")))
		{
			const auto& MacroRefVal = Properties->Values.FindChecked(TEXT("MacroReference"));
			if (MacroRefVal->Type == EJson::Object)
			{
				MacroRefVal->AsObject()->TryGetStringField(TEXT("MacroName"), MacroName);
			}
		}

		if (!MacroName.IsEmpty())
		{
			// Search for the macro graph: first in this BP, then in parent BPs, then engine macros
			// Search in this blueprint
			for (UEdGraph* Graph_ : Blueprint->MacroGraphs)
			{
				if (Graph_ && Graph_->GetFName() == FName(*MacroName))
				{
					FoundMacroGraph = Graph_;
					break;
				}
			}

			// Search in parent blueprints
			if (!FoundMacroGraph)
			{
				TArray<UBlueprint*> ParentBPStack;
				UBlueprint::GetBlueprintHierarchyFromClass(Blueprint->GeneratedClass
					? Blueprint->GeneratedClass : Blueprint->ParentClass, ParentBPStack);

				for (UBlueprint* ParentBP : ParentBPStack)
				{
					if (!ParentBP) continue;
					for (UEdGraph* Graph_ : ParentBP->MacroGraphs)
					{
						if (Graph_ && Graph_->GetFName() == FName(*MacroName))
						{
							FoundMacroGraph = Graph_;
							break;
						}
					}
					if (FoundMacroGraph) break;
				}
			}

			// Search in all loaded macro libraries (for engine macros like ForLoop, WhileLoop, etc.)
			if (!FoundMacroGraph)
			{
				for (TObjectIterator<UBlueprint> It; It; ++It)
				{
					UBlueprint* BP_ = *It;
					if (!BP_ || BP_->BlueprintType != BPTYPE_MacroLibrary) continue;
					for (UEdGraph* Graph_ : BP_->MacroGraphs)
					{
						if (Graph_ && Graph_->GetFName() == FName(*MacroName))
						{
							FoundMacroGraph = Graph_;
							break;
						}
					}
					if (FoundMacroGraph) break;
				}
			}

			if (!FoundMacroGraph)
			{
				OutError = FString::Printf(TEXT("Macro not found: %s"), *MacroName);
			}
		}
	}

	// --- K2Node_DynamicCast: set TargetType before AllocateDefaultPins ---
	UK2Node_DynamicCast* CastNode = Cast<UK2Node_DynamicCast>(NewNode);
	if (CastNode && Properties.IsValid())
	{
		FString TargetTypePath;
		if (Properties->TryGetStringField(TEXT("TargetType"), TargetTypePath) ||
			Properties->TryGetStringField(TEXT("target_type"), TargetTypePath))
		{
			UClass* TargetClass = FPropertySerializer::ResolveClass(TargetTypePath, OutError);
			if (TargetClass)
			{
				CastNode->TargetType = TargetClass;
			}
		}
	}

	// Add node to graph first (some nodes need graph context for pin allocation)
	Graph->AddNode(NewNode, true, false);

	// For MacroInstance: SetMacroGraph AFTER AddNode (needs graph context)
	// SetMacroGraph internally calls ReconstructNode which allocates pins
	if (MacroNode && FoundMacroGraph)
	{
		UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Setting macro graph: %s (nodes=%d)"),
			*FoundMacroGraph->GetName(), FoundMacroGraph->Nodes.Num());
		MacroNode->SetMacroGraph(FoundMacroGraph);
		// Ensure pins are created — SetMacroGraph may not always call ReconstructNode
		if (MacroNode->Pins.Num() == 0)
		{
			UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("MacroNode has 0 pins after SetMacroGraph, forcing ReconstructNode"));
			MacroNode->ReconstructNode();
		}
		UE_LOG(LogUEClawBridgeAPI, Log, TEXT("MacroNode pins after setup: %d"), MacroNode->Pins.Num());
	}
	else if (MacroNode)
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("FoundMacroGraph is null for MacroInstance"));
	}

	// Allocate pins for non-macro nodes (macro pins already set by SetMacroGraph)
	// Skip K2Node_AddComponent — it requires ComponentTemplate and crashes without it
	bool bIsUnsupportedNode = (NodeClassName == TEXT("K2Node_AddComponent"));
	if (bIsUnsupportedNode)
	{
		// Remove the node we just added — it can't be properly initialized
		Graph->RemoveNode(NewNode);
		OutError = FString::Printf(TEXT("Node type '%s' is not supported for programmatic creation. Use AddComponentByClass + Cast instead."), *NodeClassName);
		return nullptr;
	}
	if (!MacroNode || !FoundMacroGraph)
	{
		if (UK2Node* K2Node = Cast<UK2Node>(NewNode))
		{
			K2Node->AllocateDefaultPins();
		}
		else
		{
			NewNode->AllocateDefaultPins();
		}
	}

	// Post-add: ReconstructNode for VariableGet/Set and DynamicCast to refresh pins
	if (VarNode)
	{
		VarNode->ReconstructNode();
	}
	if (CastNode && CastNode->TargetType)
	{
		CastNode->ReconstructNode();
	}

	if (Properties.IsValid())
	{
		// Skip properties that were already applied during node creation
		TSharedPtr<FJsonObject> RemainingProps = Properties;
		
		// Collect keys to skip
		TSet<FString> SkipKeys;
		if (CallFuncNode && Properties->HasField(TEXT("FunctionReference")))
		{
			SkipKeys.Add(TEXT("FunctionReference"));
		}
		if (VarNode)
		{
			SkipKeys.Add(TEXT("VariableName"));
			SkipKeys.Add(TEXT("variable_name"));
			SkipKeys.Add(TEXT("VariableReference"));
		}
		if (MacroNode)
		{
			SkipKeys.Add(TEXT("MacroName"));
			SkipKeys.Add(TEXT("macro_name"));
			SkipKeys.Add(TEXT("MacroReference"));
		}

		if (CastNode)
		{
			SkipKeys.Add(TEXT("TargetType"));
			SkipKeys.Add(TEXT("target_type"));
		}

		if (SkipKeys.Num() > 0)
		{
			RemainingProps = MakeShareable(new FJsonObject);
			for (const auto& Pair : Properties->Values)
			{
				if (!SkipKeys.Contains(Pair.Key))
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

		// Priority: check if this matches a pin name first (for class/object pins)
		UEdGraphNode* GraphNode_Inner = Cast<UEdGraphNode>(Node);
		bool bHandledAsPin = false;
		if (GraphNode_Inner && Value.IsValid())
		{
			for (UEdGraphPin* Pin : GraphNode_Inner->Pins)
			{
				if (Pin && Pin->PinName.ToString() == PropertyName &&
					(Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_Class ||
					 Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_SoftClass ||
					 Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_Object ||
					 Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_SoftObject))
				{
					FString StringValue = Value->AsString();
					if (!StringValue.IsEmpty())
					{
						if (Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_Class ||
							Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_SoftClass)
						{
							FString ClassError;
							UClass* ResolvedClass = FPropertySerializer::ResolveClass(StringValue, ClassError);
							if (ResolvedClass)
							{
								Pin->DefaultObject = ResolvedClass;
								Pin->DefaultValue.Empty();
								bHandledAsPin = true;
							}
						}
						else
						{
							UObject* ResolvedObj = StaticLoadObject(UObject::StaticClass(), nullptr, *StringValue);
							if (ResolvedObj)
							{
								Pin->DefaultObject = ResolvedObj;
								Pin->DefaultValue.Empty();
								bHandledAsPin = true;
							}
						}
					}
					else
					{
						// Empty string = clear the default
						Pin->DefaultObject = nullptr;
						Pin->DefaultValue.Empty();
						bHandledAsPin = true;
					}
					break;
				}
			}
		}
		if (bHandledAsPin) continue;

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

						// Special handling for class/object pins: set DefaultObject instead of DefaultValue
						if (Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_Class ||
							Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_SoftClass)
						{
							FString ClassError;
							UClass* ResolvedClass = FPropertySerializer::ResolveClass(StringValue, ClassError);
							if (ResolvedClass)
							{
								Pin->DefaultObject = ResolvedClass;
								Pin->DefaultValue.Empty();
								ResolvedByPin.Add(PropName);
							}
							// else: leave in Errors
						}
						else if (Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_Object ||
								 Pin->PinType.PinCategory == UEdGraphSchema_K2::PC_SoftObject)
						{
							UObject* ResolvedObj = StaticLoadObject(UObject::StaticClass(), nullptr, *StringValue);
							if (ResolvedObj)
							{
								Pin->DefaultObject = ResolvedObj;
								Pin->DefaultValue.Empty();
								ResolvedByPin.Add(PropName);
							}
							else
							{
								Pin->DefaultValue = StringValue;
								ResolvedByPin.Add(PropName);
							}
						}
						else
						{
							Pin->DefaultValue = StringValue;
							ResolvedByPin.Add(PropName);
						}
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
