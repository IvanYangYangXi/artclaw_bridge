// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "Blueprint/BlueprintGraphQuery.h"
#include "UEClawBridgeAPI.h"
#include "Utils/AssetModifier.h"
#include "Utils/PropertySerializer.h"
#include "Engine/Blueprint.h"
#include "Animation/AnimBlueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "K2Node_Event.h"
#include "K2Node_CustomEvent.h"
#include "K2Node_FunctionEntry.h"
#include "EdGraphSchema_K2.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "AnimationGraph.h"
#include "AnimationStateMachineGraph.h"
#include "AnimationStateGraph.h"
#include "AnimationTransitionGraph.h"

FString UBlueprintGraphQuery::QueryBlueprintGraph(
	const FString& AssetPath,
	const FString& GraphName,
	const FString& GraphType,
	const FString& NodeGuid,
	const FString& Search,
	bool bIncludePositions)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryBlueprintGraph: %s, search='%s'"), *AssetPath, *Search);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint)
	{
		TSharedPtr<FJsonObject> ErrorObj = MakeShareable(new FJsonObject);
		ErrorObj->SetStringField(TEXT("error"), LoadError);
		FString OutputString;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
		FJsonSerializer::Serialize(ErrorObj.ToSharedRef(), Writer);
		return OutputString;
	}

	UAnimBlueprint* AnimBP = Cast<UAnimBlueprint>(Blueprint);
	bool bIsAnimBlueprint = (AnimBP != nullptr);

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetStringField(TEXT("blueprint"), AssetPath);
	Result->SetStringField(TEXT("parent_class"), Blueprint->ParentClass ? Blueprint->ParentClass->GetName() : TEXT("None"));
	Result->SetBoolField(TEXT("is_anim_blueprint"), bIsAnimBlueprint);

	if (bIsAnimBlueprint && AnimBP->TargetSkeleton)
	{
		Result->SetStringField(TEXT("target_skeleton"), AnimBP->TargetSkeleton->GetPathName());
	}

	// Mode 1: Get specific node by GUID
	if (!NodeGuid.IsEmpty())
	{
		FGuid ParsedGuid;
		if (!FGuid::Parse(NodeGuid, ParsedGuid))
		{
			TSharedPtr<FJsonObject> ErrorObj = MakeShareable(new FJsonObject);
			ErrorObj->SetStringField(TEXT("error"), FString::Printf(TEXT("Invalid GUID format: %s"), *NodeGuid));
			FString OutputString;
			TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
			FJsonSerializer::Serialize(ErrorObj.ToSharedRef(), Writer);
			return OutputString;
		}

		FString OutGraphName, OutGraphType;
		UEdGraphNode* Node = FindNodeByGuid(Blueprint, ParsedGuid, OutGraphName, OutGraphType);
		
		if (!Node)
		{
			TSharedPtr<FJsonObject> ErrorObj = MakeShareable(new FJsonObject);
			ErrorObj->SetStringField(TEXT("error"), FString::Printf(TEXT("Node not found: %s"), *NodeGuid));
			FString OutputString;
			TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
			FJsonSerializer::Serialize(ErrorObj.ToSharedRef(), Writer);
			return OutputString;
		}

		Result->SetStringField(TEXT("graph_name"), OutGraphName);
		Result->SetStringField(TEXT("graph_type"), OutGraphType);
		Result->SetObjectField(TEXT("node"), NodeToJson(Node, bIncludePositions));

		FString OutputString;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
		FJsonSerializer::Serialize(Result.ToSharedRef(), Writer);
		return OutputString;
	}

	// Mode 2: List all graphs with full node details
	TArray<TSharedPtr<FJsonValue>> GraphsArray;

	// Event graphs
	if (GraphType.IsEmpty() || GraphType == TEXT("event"))
	{
		for (UEdGraph* Graph : Blueprint->UbergraphPages)
		{
			if (!Graph) continue;
			if (!GraphName.IsEmpty() && Graph->GetName() != GraphName) continue;

			TSharedPtr<FJsonObject> GraphJson = GraphToJson(Graph, TEXT("event"), bIncludePositions, Search);
			if (GraphJson.IsValid())
			{
				GraphsArray.Add(MakeShareable(new FJsonValueObject(GraphJson)));
			}
		}
	}

	// Function graphs
	if (GraphType.IsEmpty() || GraphType == TEXT("function"))
	{
		for (UEdGraph* Graph : Blueprint->FunctionGraphs)
		{
			if (!Graph) continue;
			if (!GraphName.IsEmpty() && Graph->GetName() != GraphName) continue;

			TSharedPtr<FJsonObject> GraphJson = GraphToJson(Graph, TEXT("function"), bIncludePositions, Search);
			if (GraphJson.IsValid())
			{
				GraphsArray.Add(MakeShareable(new FJsonValueObject(GraphJson)));
			}
		}
	}

	// Macro graphs
	if (GraphType.IsEmpty() || GraphType == TEXT("macro"))
	{
		for (UEdGraph* Graph : Blueprint->MacroGraphs)
		{
			if (!Graph) continue;
			if (!GraphName.IsEmpty() && Graph->GetName() != GraphName) continue;

			TSharedPtr<FJsonObject> GraphJson = GraphToJson(Graph, TEXT("macro"), bIncludePositions, Search);
			if (GraphJson.IsValid())
			{
				GraphsArray.Add(MakeShareable(new FJsonValueObject(GraphJson)));
			}
		}
	}

	// Interface implementation graphs
	if (GraphType.IsEmpty() || GraphType == TEXT("interface"))
	{
		for (const FBPInterfaceDescription& InterfaceDesc : Blueprint->ImplementedInterfaces)
		{
			if (!InterfaceDesc.Interface) continue;
			for (UEdGraph* Graph : InterfaceDesc.Graphs)
			{
				if (!Graph) continue;
				if (!GraphName.IsEmpty() && Graph->GetName() != GraphName) continue;
				TSharedPtr<FJsonObject> GraphJson = GraphToJson(Graph, TEXT("interface"), bIncludePositions, Search);
				if (GraphJson.IsValid())
				{
					GraphsArray.Add(MakeShareable(new FJsonValueObject(GraphJson)));
				}
			}
		}
	}

	// Animation Blueprint specific graphs
	if (bIsAnimBlueprint)
	{
		ProcessAnimBlueprintGraphs(AnimBP, GraphName, GraphType, bIncludePositions, Search, GraphsArray);
	}

	Result->SetArrayField(TEXT("graphs"), GraphsArray);
	Result->SetNumberField(TEXT("graph_count"), GraphsArray.Num());

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(Result.ToSharedRef(), Writer);
	return OutputString;
}

FString UBlueprintGraphQuery::ListBlueprintCallables(const FString& AssetPath)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("ListBlueprintCallables: %s"), *AssetPath);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint)
	{
		TSharedPtr<FJsonObject> ErrorObj = MakeShareable(new FJsonObject);
		ErrorObj->SetStringField(TEXT("error"), LoadError);
		FString OutputString;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
		FJsonSerializer::Serialize(ErrorObj.ToSharedRef(), Writer);
		return OutputString;
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetStringField(TEXT("blueprint"), AssetPath);

	TArray<TSharedPtr<FJsonValue>> EventsArray, FunctionsArray, MacrosArray;

	ExtractEvents(Blueprint, EventsArray);
	ExtractFunctions(Blueprint, FunctionsArray);
	ExtractMacros(Blueprint, MacrosArray);

	Result->SetArrayField(TEXT("events"), EventsArray);
	Result->SetArrayField(TEXT("functions"), FunctionsArray);
	Result->SetArrayField(TEXT("macros"), MacrosArray);
	Result->SetNumberField(TEXT("total_callables"), EventsArray.Num() + FunctionsArray.Num() + MacrosArray.Num());

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(Result.ToSharedRef(), Writer);
	return OutputString;
}

// Helper to find node by GUID across all graphs
UEdGraphNode* UBlueprintGraphQuery::FindNodeByGuid(UBlueprint* Blueprint, const FGuid& NodeGuid, FString& OutGraphName, FString& OutGraphType)
{
	if (!Blueprint)
	{
		return nullptr;
	}

	// Search in Ubergraph pages (Event graphs)
	for (UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		if (!Graph) continue;
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (Node && Node->NodeGuid == NodeGuid)
			{
				OutGraphName = Graph->GetName();
				OutGraphType = TEXT("event");
				return Node;
			}
		}
	}

	// Search in Function graphs
	for (UEdGraph* Graph : Blueprint->FunctionGraphs)
	{
		if (!Graph) continue;
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (Node && Node->NodeGuid == NodeGuid)
			{
				OutGraphName = Graph->GetName();
				OutGraphType = TEXT("function");
				return Node;
			}
		}
	}

	// Search in Macro graphs
	for (UEdGraph* Graph : Blueprint->MacroGraphs)
	{
		if (!Graph) continue;
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (Node && Node->NodeGuid == NodeGuid)
			{
				OutGraphName = Graph->GetName();
				OutGraphType = TEXT("macro");
				return Node;
			}
		}
	}

	// Search in Interface graphs
	for (const FBPInterfaceDescription& InterfaceDesc : Blueprint->ImplementedInterfaces)
	{
		for (UEdGraph* Graph : InterfaceDesc.Graphs)
		{
			if (!Graph) continue;
			for (UEdGraphNode* Node : Graph->Nodes)
			{
				if (Node && Node->NodeGuid == NodeGuid)
				{
					OutGraphName = Graph->GetName();
					OutGraphType = TEXT("interface");
					return Node;
				}
			}
		}
	}

	// Search in AnimBlueprint graphs
	if (UAnimBlueprint* AnimBP = Cast<UAnimBlueprint>(Blueprint))
	{
		// Animation graphs
		for (UEdGraph* Graph : AnimBP->FunctionGraphs)
		{
			if (!Graph) continue;
			FString GraphTypeStr = GetAnimGraphTypeString(Graph);
			if (GraphTypeStr.IsEmpty()) continue;

			for (UEdGraphNode* Node : Graph->Nodes)
			{
				if (Node && Node->NodeGuid == NodeGuid)
				{
					OutGraphName = Graph->GetName();
					OutGraphType = GraphTypeStr;
					return Node;
				}
			}
		}
	}

	return nullptr;
}

// Helper to get pin direction as string
FString UBlueprintGraphQuery::GetPinDirectionString(EEdGraphPinDirection Direction)
{
	switch (Direction)
	{
		case EGPD_Input: return TEXT("input");
		case EGPD_Output: return TEXT("output");
		default: return TEXT("unknown");
	}
}

// Helper to get pin category as string
FString UBlueprintGraphQuery::GetPinCategoryString(FName Category)
{
	if (Category == UEdGraphSchema_K2::PC_Boolean) return TEXT("bool");
	if (Category == UEdGraphSchema_K2::PC_Byte) return TEXT("byte");
	if (Category == UEdGraphSchema_K2::PC_Int) return TEXT("int");
	if (Category == UEdGraphSchema_K2::PC_Int64) return TEXT("int64");
	if (Category == UEdGraphSchema_K2::PC_Float) return TEXT("float");
	if (Category == UEdGraphSchema_K2::PC_Double) return TEXT("double");
	if (Category == UEdGraphSchema_K2::PC_String) return TEXT("string");
	if (Category == UEdGraphSchema_K2::PC_Text) return TEXT("text");
	if (Category == UEdGraphSchema_K2::PC_Name) return TEXT("name");
	if (Category == UEdGraphSchema_K2::PC_Object) return TEXT("object");
	if (Category == UEdGraphSchema_K2::PC_Class) return TEXT("class");
	if (Category == UEdGraphSchema_K2::PC_Struct) return TEXT("struct");
	if (Category == UEdGraphSchema_K2::PC_Enum) return TEXT("enum");
	if (Category == UEdGraphSchema_K2::PC_Exec) return TEXT("exec");
	if (Category == UEdGraphSchema_K2::PC_Wildcard) return TEXT("wildcard");
	return Category.ToString();
}

// Helper to match wildcards
bool UBlueprintGraphQuery::MatchesWildcard(const FString& Text, const FString& Pattern)
{
	if (Pattern.IsEmpty()) return true;
	
	if (Pattern.StartsWith(TEXT("*")) && Pattern.EndsWith(TEXT("*")))
	{
		FString Middle = Pattern.Mid(1, Pattern.Len() - 2);
		return Text.Contains(Middle);
	}
	else if (Pattern.StartsWith(TEXT("*")))
	{
		FString Suffix = Pattern.Mid(1);
		return Text.EndsWith(Suffix);
	}
	else if (Pattern.EndsWith(TEXT("*")))
	{
		FString Prefix = Pattern.Left(Pattern.Len() - 1);
		return Text.StartsWith(Prefix);
	}
	else
	{
		return Text.Contains(Pattern);
	}
}

// === QueryBlueprintInfo ===

FString UBlueprintGraphQuery::QueryBlueprintInfo(const FString& AssetPath, const FString& Include)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryBlueprintInfo: %s, include=%s"), *AssetPath, *Include);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint)
	{
		TSharedPtr<FJsonObject> ErrorObj = MakeShareable(new FJsonObject);
		ErrorObj->SetBoolField(TEXT("success"), false);
		ErrorObj->SetStringField(TEXT("error"), LoadError);
		FString OutputString;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
		FJsonSerializer::Serialize(ErrorObj.ToSharedRef(), Writer);
		return OutputString;
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("blueprint"), AssetPath);
	Result->SetStringField(TEXT("name"), Blueprint->GetName());
	Result->SetStringField(TEXT("parent_class"), Blueprint->ParentClass ? Blueprint->ParentClass->GetName() : TEXT("None"));
	Result->SetStringField(TEXT("blueprint_type"), Blueprint->GetClass()->GetName());

	bool bAll = (Include == TEXT("all"));

	// Graph counts
	if (bAll || Include.Contains(TEXT("graphs")))
	{
		Result->SetNumberField(TEXT("event_graph_count"), Blueprint->UbergraphPages.Num());
		Result->SetNumberField(TEXT("function_count"), Blueprint->FunctionGraphs.Num());
		Result->SetNumberField(TEXT("macro_count"), Blueprint->MacroGraphs.Num());
		Result->SetNumberField(TEXT("interface_count"), Blueprint->ImplementedInterfaces.Num());
	}

	// Variables
	if (bAll || Include.Contains(TEXT("variables")))
	{
		TArray<TSharedPtr<FJsonValue>> VarsArray;
		for (const FBPVariableDescription& Var : Blueprint->NewVariables)
		{
			TSharedPtr<FJsonObject> VarObj = MakeShareable(new FJsonObject);
			VarObj->SetStringField(TEXT("name"), Var.VarName.ToString());
			VarObj->SetStringField(TEXT("type"), Var.VarType.PinCategory.ToString());
			VarsArray.Add(MakeShareable(new FJsonValueObject(VarObj)));
		}
		Result->SetArrayField(TEXT("variables"), VarsArray);
	}

	// Callables
	if (bAll || Include.Contains(TEXT("callables")))
	{
		TArray<TSharedPtr<FJsonValue>> EventsArray, FunctionsArray, MacrosArray;
		ExtractEvents(Blueprint, EventsArray);
		ExtractFunctions(Blueprint, FunctionsArray);
		ExtractMacros(Blueprint, MacrosArray);

		Result->SetArrayField(TEXT("events"), EventsArray);
		Result->SetArrayField(TEXT("functions"), FunctionsArray);
		Result->SetArrayField(TEXT("macros"), MacrosArray);
	}

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(Result.ToSharedRef(), Writer);
	return OutputString;
}

// === Missing implementations ===

TSharedPtr<FJsonObject> UBlueprintGraphQuery::PinToJson(UEdGraphPin* Pin)
{
	if (!Pin) return nullptr;

	TSharedPtr<FJsonObject> PinObj = MakeShareable(new FJsonObject);
	PinObj->SetStringField(TEXT("name"), Pin->GetName());
	PinObj->SetStringField(TEXT("direction"), GetPinDirectionString(Pin->Direction));
	PinObj->SetStringField(TEXT("type"), GetPinCategoryString(Pin->PinType.PinCategory));
	PinObj->SetStringField(TEXT("default_value"), Pin->DefaultValue);
	PinObj->SetBoolField(TEXT("connected"), Pin->LinkedTo.Num() > 0);
	PinObj->SetNumberField(TEXT("connections"), Pin->LinkedTo.Num());

	if (Pin->PinType.PinSubCategoryObject.IsValid())
	{
		PinObj->SetStringField(TEXT("sub_type"), Pin->PinType.PinSubCategoryObject->GetName());
	}

	return PinObj;
}

TSharedPtr<FJsonObject> UBlueprintGraphQuery::NodeToJson(UEdGraphNode* Node, bool bIncludePositions)
{
	if (!Node) return nullptr;

	TSharedPtr<FJsonObject> NodeObj = MakeShareable(new FJsonObject);
	NodeObj->SetStringField(TEXT("class"), Node->GetClass()->GetName());
	NodeObj->SetStringField(TEXT("title"), Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString());
	NodeObj->SetStringField(TEXT("guid"), Node->NodeGuid.ToString());
	NodeObj->SetStringField(TEXT("comment"), Node->NodeComment);

	if (bIncludePositions)
	{
		NodeObj->SetNumberField(TEXT("pos_x"), Node->NodePosX);
		NodeObj->SetNumberField(TEXT("pos_y"), Node->NodePosY);
	}

	// Pins
	TArray<TSharedPtr<FJsonValue>> InputPins, OutputPins;
	for (UEdGraphPin* Pin : Node->Pins)
	{
		if (!Pin) continue;
		TSharedPtr<FJsonObject> PinJson = PinToJson(Pin);
		if (PinJson.IsValid())
		{
			if (Pin->Direction == EGPD_Input)
				InputPins.Add(MakeShareable(new FJsonValueObject(PinJson)));
			else
				OutputPins.Add(MakeShareable(new FJsonValueObject(PinJson)));
		}
	}
	NodeObj->SetArrayField(TEXT("inputs"), InputPins);
	NodeObj->SetArrayField(TEXT("outputs"), OutputPins);

	return NodeObj;
}

TSharedPtr<FJsonObject> UBlueprintGraphQuery::GraphToJson(
	UEdGraph* Graph,
	const FString& GraphType,
	bool bIncludePositions,
	const FString& SearchFilter)
{
	if (!Graph) return nullptr;

	TSharedPtr<FJsonObject> GraphObj = MakeShareable(new FJsonObject);
	GraphObj->SetStringField(TEXT("name"), Graph->GetName());
	GraphObj->SetStringField(TEXT("type"), GraphType);
	GraphObj->SetNumberField(TEXT("node_count"), Graph->Nodes.Num());

	TArray<TSharedPtr<FJsonValue>> NodesArray;
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		if (!Node) continue;

		// Apply search filter if specified
		if (!SearchFilter.IsEmpty())
		{
			FString NodeTitle = Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString();
			FString NodeClass = Node->GetClass()->GetName();
			if (!MatchesWildcard(NodeTitle, SearchFilter) && !MatchesWildcard(NodeClass, SearchFilter))
			{
				continue;
			}
		}

		TSharedPtr<FJsonObject> NodeJson = NodeToJson(Node, bIncludePositions);
		if (NodeJson.IsValid())
		{
			NodesArray.Add(MakeShareable(new FJsonValueObject(NodeJson)));
		}
	}

	GraphObj->SetArrayField(TEXT("nodes"), NodesArray);
	GraphObj->SetNumberField(TEXT("filtered_node_count"), NodesArray.Num());

	return GraphObj;
}

void UBlueprintGraphQuery::ExtractEvents(UBlueprint* Blueprint, TArray<TSharedPtr<FJsonValue>>& OutArray)
{
	if (!Blueprint) return;

	for (UEdGraph* Graph : Blueprint->UbergraphPages)
	{
		if (!Graph) continue;
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			UK2Node_Event* EventNode = Cast<UK2Node_Event>(Node);
			UK2Node_CustomEvent* CustomEventNode = Cast<UK2Node_CustomEvent>(Node);
			if (!EventNode && !CustomEventNode) continue;

			TSharedPtr<FJsonObject> EventObj = MakeShareable(new FJsonObject);
			EventObj->SetStringField(TEXT("name"), Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString());
			EventObj->SetStringField(TEXT("class"), Node->GetClass()->GetName());
			EventObj->SetStringField(TEXT("guid"), Node->NodeGuid.ToString());
			EventObj->SetStringField(TEXT("graph"), Graph->GetName());
			EventObj->SetBoolField(TEXT("is_custom"), CustomEventNode != nullptr);

			OutArray.Add(MakeShareable(new FJsonValueObject(EventObj)));
		}
	}
}

void UBlueprintGraphQuery::ExtractFunctions(UBlueprint* Blueprint, TArray<TSharedPtr<FJsonValue>>& OutArray)
{
	if (!Blueprint) return;

	for (UEdGraph* Graph : Blueprint->FunctionGraphs)
	{
		if (!Graph) continue;

		TSharedPtr<FJsonObject> FuncObj = MakeShareable(new FJsonObject);
		FuncObj->SetStringField(TEXT("name"), Graph->GetName());
		FuncObj->SetStringField(TEXT("type"), TEXT("function"));
		FuncObj->SetNumberField(TEXT("node_count"), Graph->Nodes.Num());

		// Find entry node for parameter info
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			UK2Node_FunctionEntry* EntryNode = Cast<UK2Node_FunctionEntry>(Node);
			if (EntryNode)
			{
				TArray<TSharedPtr<FJsonValue>> ParamsArray;
				for (UEdGraphPin* Pin : EntryNode->Pins)
				{
					if (Pin && Pin->Direction == EGPD_Output && Pin->PinType.PinCategory != UEdGraphSchema_K2::PC_Exec)
					{
						TSharedPtr<FJsonObject> ParamObj = MakeShareable(new FJsonObject);
						ParamObj->SetStringField(TEXT("name"), Pin->GetName());
						ParamObj->SetStringField(TEXT("type"), GetPinCategoryString(Pin->PinType.PinCategory));
						ParamsArray.Add(MakeShareable(new FJsonValueObject(ParamObj)));
					}
				}
				FuncObj->SetArrayField(TEXT("parameters"), ParamsArray);
				break;
			}
		}

		OutArray.Add(MakeShareable(new FJsonValueObject(FuncObj)));
	}
}

void UBlueprintGraphQuery::ExtractMacros(UBlueprint* Blueprint, TArray<TSharedPtr<FJsonValue>>& OutArray)
{
	if (!Blueprint) return;

	for (UEdGraph* Graph : Blueprint->MacroGraphs)
	{
		if (!Graph) continue;

		TSharedPtr<FJsonObject> MacroObj = MakeShareable(new FJsonObject);
		MacroObj->SetStringField(TEXT("name"), Graph->GetName());
		MacroObj->SetStringField(TEXT("type"), TEXT("macro"));
		MacroObj->SetNumberField(TEXT("node_count"), Graph->Nodes.Num());

		OutArray.Add(MakeShareable(new FJsonValueObject(MacroObj)));
	}
}

FString UBlueprintGraphQuery::GetAnimGraphTypeString(UEdGraph* Graph)
{
	if (!Graph) return TEXT("");

	if (Graph->IsA<UAnimationGraph>())
	{
		return TEXT("anim_graph");
	}
	else if (Graph->IsA<UAnimationStateMachineGraph>())
	{
		return TEXT("state_machine");
	}
	else if (Graph->IsA<UAnimationStateGraph>())
	{
		return TEXT("state");
	}
	else if (Graph->IsA<UAnimationTransitionGraph>())
	{
		return TEXT("transition");
	}

	return TEXT("");
}

void UBlueprintGraphQuery::ProcessAnimBlueprintGraphs(
	UAnimBlueprint* AnimBP,
	const FString& GraphNameFilter,
	const FString& GraphTypeFilter,
	bool bIncludePositions,
	const FString& SearchFilter,
	TArray<TSharedPtr<FJsonValue>>& OutGraphsArray)
{
	if (!AnimBP) return;

	// Process all graphs in the AnimBlueprint's FunctionGraphs (which include anim graphs)
	for (UEdGraph* Graph : AnimBP->FunctionGraphs)
	{
		if (!Graph) continue;

		FString AnimGraphType = GetAnimGraphTypeString(Graph);
		if (AnimGraphType.IsEmpty()) continue;

		// Apply graph name filter
		if (!GraphNameFilter.IsEmpty() && Graph->GetName() != GraphNameFilter) continue;
		// Apply graph type filter
		if (!GraphTypeFilter.IsEmpty() && GraphTypeFilter != AnimGraphType) continue;

		TSharedPtr<FJsonObject> GraphJson = GraphToJson(Graph, AnimGraphType, bIncludePositions, SearchFilter);
		if (GraphJson.IsValid())
		{
			OutGraphsArray.Add(MakeShareable(new FJsonValueObject(GraphJson)));
		}
	}
}