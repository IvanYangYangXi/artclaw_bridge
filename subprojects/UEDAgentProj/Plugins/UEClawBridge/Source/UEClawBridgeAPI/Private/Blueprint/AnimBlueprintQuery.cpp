// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "Blueprint/AnimBlueprintQuery.h"
#include "UEClawBridgeAPI.h"
#include "Utils/AssetModifier.h"
#include "Utils/PropertySerializer.h"
#include "Animation/AnimBlueprint.h"
#include "AnimationGraph.h"
#include "AnimationStateMachineGraph.h"
#include "AnimationStateGraph.h"
#include "AnimationTransitionGraph.h"
#include "AnimGraphNode_StateMachine.h"
#include "AnimGraphNode_Base.h"
#include "AnimStateNode.h"
#include "AnimStateTransitionNode.h"
#include "AnimStateConduitNode.h"
#include "Animation/AnimNodeBase.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

FString UAnimBlueprintQuery::QueryStateMachineHierarchy(
	const FString& AssetPath,
	const FString& StateMachineName,
	bool bIncludePositions,
	bool bIncludeNestedGraphs)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryStateMachineHierarchy: %s, StateMachine='%s'"), *AssetPath, *StateMachineName);

	FString LoadError;
	UAnimBlueprint* AnimBP = FAssetModifier::LoadAssetByPath<UAnimBlueprint>(AssetPath, LoadError);
	if (!AnimBP)
	{
		TSharedPtr<FJsonObject> ErrorObj = MakeShareable(new FJsonObject);
		ErrorObj->SetStringField(TEXT("error"), LoadError);
		FString OutputString;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
		FJsonSerializer::Serialize(ErrorObj.ToSharedRef(), Writer);
		return OutputString;
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetStringField(TEXT("anim_blueprint"), AssetPath);
	Result->SetStringField(TEXT("target_skeleton"), AnimBP->TargetSkeleton ? AnimBP->TargetSkeleton->GetPathName() : TEXT("None"));

	TArray<TSharedPtr<FJsonValue>> StateMachinesArray;

	// Get all graphs and find state machines
	TArray<UEdGraph*> AllGraphs;
	AnimBP->GetAllGraphs(AllGraphs);

	for (UEdGraph* Graph : AllGraphs)
	{
		if (!Graph) continue;

		UAnimationStateMachineGraph* StateMachineGraph = Cast<UAnimationStateMachineGraph>(Graph);
		if (!StateMachineGraph) continue;

		// Apply name filter
		if (!StateMachineName.IsEmpty() && Graph->GetName() != StateMachineName)
		{
			continue;
		}

		TSharedPtr<FJsonObject> StateMachineJson = StateMachineToJson(StateMachineGraph, bIncludePositions, bIncludeNestedGraphs);
		if (StateMachineJson.IsValid())
		{
			StateMachinesArray.Add(MakeShareable(new FJsonValueObject(StateMachineJson)));
		}
	}

	Result->SetArrayField(TEXT("state_machines"), StateMachinesArray);
	Result->SetNumberField(TEXT("state_machine_count"), StateMachinesArray.Num());

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(Result.ToSharedRef(), Writer);
	return OutputString;
}

FString UAnimBlueprintQuery::QueryAnimGraphNodes(
	const FString& AssetPath,
	const FString& GraphName,
	bool bIncludeAnimNodeProperties)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryAnimGraphNodes: %s, GraphName='%s'"), *AssetPath, *GraphName);

	FString LoadError;
	UAnimBlueprint* AnimBP = FAssetModifier::LoadAssetByPath<UAnimBlueprint>(AssetPath, LoadError);
	if (!AnimBP)
	{
		TSharedPtr<FJsonObject> ErrorObj = MakeShareable(new FJsonObject);
		ErrorObj->SetStringField(TEXT("error"), LoadError);
		FString OutputString;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
		FJsonSerializer::Serialize(ErrorObj.ToSharedRef(), Writer);
		return OutputString;
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetStringField(TEXT("anim_blueprint"), AssetPath);

	TArray<TSharedPtr<FJsonValue>> AnimGraphsArray;

	// Get all AnimGraphs
	TArray<UAnimationGraph*> AnimGraphs = GetAllAnimGraphs(AnimBP);

	for (UAnimationGraph* AnimGraph : AnimGraphs)
	{
		if (!AnimGraph) continue;

		// Apply name filter
		if (!GraphName.IsEmpty() && AnimGraph->GetName() != GraphName)
		{
			continue;
		}

		TSharedPtr<FJsonObject> GraphJson = MakeShareable(new FJsonObject);
		GraphJson->SetStringField(TEXT("name"), AnimGraph->GetName());
		GraphJson->SetStringField(TEXT("type"), TEXT("anim_graph"));

		TArray<TSharedPtr<FJsonValue>> NodesArray;

		for (UEdGraphNode* Node : AnimGraph->Nodes)
		{
			if (!Node) continue;

			TSharedPtr<FJsonObject> NodeJson = MakeShareable(new FJsonObject);
			NodeJson->SetStringField(TEXT("guid"), Node->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens));
			NodeJson->SetStringField(TEXT("class"), Node->GetClass()->GetName());
			NodeJson->SetStringField(TEXT("title"), Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString());

			// Extract AnimNode properties if requested
			if (bIncludeAnimNodeProperties)
			{
				if (UAnimGraphNode_Base* AnimGraphNode = Cast<UAnimGraphNode_Base>(Node))
				{
					TSharedPtr<FJsonObject> AnimPropsJson = ExtractAnimNodeProperties(AnimGraphNode);
					if (AnimPropsJson.IsValid())
					{
						NodeJson->SetObjectField(TEXT("anim_node_properties"), AnimPropsJson);
					}
				}
			}

			// Add pins information
			TArray<TSharedPtr<FJsonValue>> PinsArray;
			for (UEdGraphPin* Pin : Node->Pins)
			{
				if (!Pin) continue;

				TSharedPtr<FJsonObject> PinJson = MakeShareable(new FJsonObject);
				PinJson->SetStringField(TEXT("name"), Pin->PinName.ToString());
				PinJson->SetStringField(TEXT("direction"), Pin->Direction == EGPD_Input ? TEXT("input") : TEXT("output"));
				PinJson->SetStringField(TEXT("category"), Pin->PinType.PinCategory.ToString());

				if (!Pin->DefaultValue.IsEmpty())
				{
					PinJson->SetStringField(TEXT("default_value"), Pin->DefaultValue);
				}

				PinsArray.Add(MakeShareable(new FJsonValueObject(PinJson)));
			}
			NodeJson->SetArrayField(TEXT("pins"), PinsArray);

			NodesArray.Add(MakeShareable(new FJsonValueObject(NodeJson)));
		}

		GraphJson->SetArrayField(TEXT("nodes"), NodesArray);
		GraphJson->SetNumberField(TEXT("node_count"), NodesArray.Num());
		AnimGraphsArray.Add(MakeShareable(new FJsonValueObject(GraphJson)));
	}

	Result->SetArrayField(TEXT("anim_graphs"), AnimGraphsArray);
	Result->SetNumberField(TEXT("anim_graph_count"), AnimGraphsArray.Num());

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(Result.ToSharedRef(), Writer);
	return OutputString;
}

FString UAnimBlueprintQuery::QueryAnimLayerInterfaces(const FString& AssetPath)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryAnimLayerInterfaces: %s"), *AssetPath);

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
	Result->SetBoolField(TEXT("is_interface"), Blueprint->BlueprintType == BPTYPE_Interface);

	TArray<TSharedPtr<FJsonValue>> InterfacesArray;

	// For AnimLayerInterface Blueprints
	if (Blueprint->BlueprintType == BPTYPE_Interface)
	{
		// List all function graphs as interface functions
		for (UEdGraph* Graph : Blueprint->FunctionGraphs)
		{
			if (!Graph) continue;

			TSharedPtr<FJsonObject> IntfFunc = MakeShareable(new FJsonObject);
			IntfFunc->SetStringField(TEXT("name"), Graph->GetName());
			IntfFunc->SetStringField(TEXT("type"), TEXT("anim_layer_function"));

			// Check if this is an AnimationGraph
			if (UAnimationGraph* AnimGraph = Cast<UAnimationGraph>(Graph))
			{
				IntfFunc->SetBoolField(TEXT("is_anim_graph"), true);
			}

			InterfacesArray.Add(MakeShareable(new FJsonValueObject(IntfFunc)));
		}
	}
	else
	{
		// For regular AnimBlueprints, list implemented interfaces
		for (const FBPInterfaceDescription& InterfaceDesc : Blueprint->ImplementedInterfaces)
		{
			if (!InterfaceDesc.Interface) continue;

			TSharedPtr<FJsonObject> IntfObj = MakeShareable(new FJsonObject);
			IntfObj->SetStringField(TEXT("name"), InterfaceDesc.Interface->GetName());
			IntfObj->SetStringField(TEXT("path"), InterfaceDesc.Interface->GetPathName());

			// List interface functions
			TArray<TSharedPtr<FJsonValue>> FunctionsArray;
			for (UEdGraph* Graph : InterfaceDesc.Graphs)
			{
				if (!Graph) continue;

				TSharedPtr<FJsonObject> FuncObj = MakeShareable(new FJsonObject);
				FuncObj->SetStringField(TEXT("name"), Graph->GetName());
				FuncObj->SetBoolField(TEXT("is_anim_graph"), Cast<UAnimationGraph>(Graph) != nullptr);

				FunctionsArray.Add(MakeShareable(new FJsonValueObject(FuncObj)));
			}
			IntfObj->SetArrayField(TEXT("functions"), FunctionsArray);

			InterfacesArray.Add(MakeShareable(new FJsonValueObject(IntfObj)));
		}
	}

	Result->SetArrayField(TEXT("interfaces"), InterfacesArray);
	Result->SetNumberField(TEXT("interface_count"), InterfacesArray.Num());

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(Result.ToSharedRef(), Writer);
	return OutputString;
}

// === Implementation helpers ===

TSharedPtr<FJsonObject> UAnimBlueprintQuery::StateMachineToJson(
	UAnimationStateMachineGraph* StateMachineGraph,
	bool bIncludePositions,
	bool bIncludeNestedGraphs)
{
	if (!StateMachineGraph)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> StateMachineJson = MakeShareable(new FJsonObject);
	StateMachineJson->SetStringField(TEXT("name"), StateMachineGraph->GetName());
	StateMachineJson->SetStringField(TEXT("type"), TEXT("state_machine"));

	TArray<TSharedPtr<FJsonValue>> StatesArray;
	TArray<TSharedPtr<FJsonValue>> TransitionsArray;
	TArray<TSharedPtr<FJsonValue>> ConduitsArray;

	for (UEdGraphNode* Node : StateMachineGraph->Nodes)
	{
		if (!Node) continue;

		// Extract state nodes
		if (UAnimStateNode* StateNode = Cast<UAnimStateNode>(Node))
		{
			TSharedPtr<FJsonObject> StateJson = AnimStateNodeToJson(StateNode, bIncludePositions, bIncludeNestedGraphs);
			if (StateJson.IsValid())
			{
				StatesArray.Add(MakeShareable(new FJsonValueObject(StateJson)));
			}
		}
		// Extract transition nodes
		else if (UAnimStateTransitionNode* TransitionNode = Cast<UAnimStateTransitionNode>(Node))
		{
			TSharedPtr<FJsonObject> TransitionJson = TransitionNodeToJson(TransitionNode, bIncludePositions, bIncludeNestedGraphs);
			if (TransitionJson.IsValid())
			{
				TransitionsArray.Add(MakeShareable(new FJsonValueObject(TransitionJson)));
			}
		}
		// Extract conduit nodes
		else if (UAnimStateConduitNode* ConduitNode = Cast<UAnimStateConduitNode>(Node))
		{
			TSharedPtr<FJsonObject> ConduitJson = MakeShareable(new FJsonObject);
			ConduitJson->SetStringField(TEXT("guid"), ConduitNode->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens));
			ConduitJson->SetStringField(TEXT("name"), ConduitNode->GetStateName());
			ConduitJson->SetStringField(TEXT("type"), TEXT("conduit"));

			if (bIncludePositions)
			{
				TSharedPtr<FJsonObject> PositionJson = MakeShareable(new FJsonObject);
				PositionJson->SetNumberField(TEXT("x"), ConduitNode->NodePosX);
				PositionJson->SetNumberField(TEXT("y"), ConduitNode->NodePosY);
				ConduitJson->SetObjectField(TEXT("position"), PositionJson);
			}

			ConduitsArray.Add(MakeShareable(new FJsonValueObject(ConduitJson)));
		}
	}

	StateMachineJson->SetArrayField(TEXT("states"), StatesArray);
	StateMachineJson->SetArrayField(TEXT("transitions"), TransitionsArray);
	StateMachineJson->SetArrayField(TEXT("conduits"), ConduitsArray);
	StateMachineJson->SetNumberField(TEXT("state_count"), StatesArray.Num());
	StateMachineJson->SetNumberField(TEXT("transition_count"), TransitionsArray.Num());
	StateMachineJson->SetNumberField(TEXT("conduit_count"), ConduitsArray.Num());

	return StateMachineJson;
}

TSharedPtr<FJsonObject> UAnimBlueprintQuery::AnimStateNodeToJson(
	UAnimStateNode* StateNode,
	bool bIncludePositions,
	bool bIncludeNestedGraph)
{
	if (!StateNode)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> StateJson = MakeShareable(new FJsonObject);
	StateJson->SetStringField(TEXT("guid"), StateNode->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens));
	StateJson->SetStringField(TEXT("name"), StateNode->GetStateName());
	StateJson->SetStringField(TEXT("type"), TEXT("state"));

	if (bIncludePositions)
	{
		TSharedPtr<FJsonObject> PositionJson = MakeShareable(new FJsonObject);
		PositionJson->SetNumberField(TEXT("x"), StateNode->NodePosX);
		PositionJson->SetNumberField(TEXT("y"), StateNode->NodePosY);
		StateJson->SetObjectField(TEXT("position"), PositionJson);
	}

	// Check if this state has a nested graph
	if (UAnimationStateGraph* StateGraph = Cast<UAnimationStateGraph>(StateNode->BoundGraph))
	{
		StateJson->SetBoolField(TEXT("has_graph"), true);
		StateJson->SetStringField(TEXT("graph_name"), StateGraph->GetName());

		if (bIncludeNestedGraph)
		{
			TArray<TSharedPtr<FJsonValue>> NodesArray;
			for (UEdGraphNode* Node : StateGraph->Nodes)
			{
				if (!Node) continue;

				TSharedPtr<FJsonObject> NodeJson = MakeShareable(new FJsonObject);
				NodeJson->SetStringField(TEXT("guid"), Node->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens));
				NodeJson->SetStringField(TEXT("class"), Node->GetClass()->GetName());
				NodeJson->SetStringField(TEXT("title"), Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString());

				NodesArray.Add(MakeShareable(new FJsonValueObject(NodeJson)));
			}
			StateJson->SetArrayField(TEXT("nodes"), NodesArray);
		}
	}

	return StateJson;
}

TSharedPtr<FJsonObject> UAnimBlueprintQuery::TransitionNodeToJson(
	UAnimStateTransitionNode* TransitionNode,
	bool bIncludePositions,
	bool bIncludeNestedGraph)
{
	if (!TransitionNode)
	{
		return nullptr;
	}

	TSharedPtr<FJsonObject> TransitionJson = MakeShareable(new FJsonObject);
	TransitionJson->SetStringField(TEXT("guid"), TransitionNode->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens));
	TransitionJson->SetStringField(TEXT("type"), TEXT("transition"));

	// Get connected states
	if (UAnimStateNodeBase* PrevState = TransitionNode->GetPreviousState())
	{
		TransitionJson->SetStringField(TEXT("from_state"), PrevState->GetStateName());
	}
	if (UAnimStateNodeBase* NextState = TransitionNode->GetNextState())
	{
		TransitionJson->SetStringField(TEXT("to_state"), NextState->GetStateName());
	}

	// Check if has transition graph
	if (UAnimationTransitionGraph* TransitionGraph = Cast<UAnimationTransitionGraph>(TransitionNode->BoundGraph))
	{
		TransitionJson->SetBoolField(TEXT("has_graph"), true);
		TransitionJson->SetStringField(TEXT("graph_name"), TransitionGraph->GetName());

		if (bIncludeNestedGraph)
		{
			TArray<TSharedPtr<FJsonValue>> NodesArray;
			for (UEdGraphNode* Node : TransitionGraph->Nodes)
			{
				if (!Node) continue;

				TSharedPtr<FJsonObject> NodeJson = MakeShareable(new FJsonObject);
				NodeJson->SetStringField(TEXT("guid"), Node->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens));
				NodeJson->SetStringField(TEXT("class"), Node->GetClass()->GetName());
				NodeJson->SetStringField(TEXT("title"), Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString());

				NodesArray.Add(MakeShareable(new FJsonValueObject(NodeJson)));
			}
			TransitionJson->SetArrayField(TEXT("nodes"), NodesArray);
		}
	}

	if (bIncludePositions)
	{
		TSharedPtr<FJsonObject> PositionJson = MakeShareable(new FJsonObject);
		PositionJson->SetNumberField(TEXT("x"), TransitionNode->NodePosX);
		PositionJson->SetNumberField(TEXT("y"), TransitionNode->NodePosY);
		TransitionJson->SetObjectField(TEXT("position"), PositionJson);
	}

	return TransitionJson;
}

TSharedPtr<FJsonObject> UAnimBlueprintQuery::ExtractAnimNodeProperties(UAnimGraphNode_Base* AnimGraphNode)
{
	if (!AnimGraphNode)
	{
		return nullptr;
	}

	UScriptStruct* AnimNodeBaseStruct = FAnimNode_Base::StaticStruct();

	// Find the embedded FAnimNode_* struct property via reflection
	for (TFieldIterator<FStructProperty> It(AnimGraphNode->GetClass()); It; ++It)
	{
		FStructProperty* StructProp = *It;
		UScriptStruct* Struct = StructProp->Struct;

		if (!Struct || !Struct->IsChildOf(AnimNodeBaseStruct))
		{
			continue;
		}

		TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
		Result->SetStringField(TEXT("struct_type"), Struct->GetName());

		const void* StructPtr = StructProp->ContainerPtrToValuePtr<void>(AnimGraphNode);

		// Serialize all editable properties of the embedded struct
		TSharedPtr<FJsonObject> PropsObj = MakeShareable(new FJsonObject);
		for (TFieldIterator<FProperty> PropIt(Struct); PropIt; ++PropIt)
		{
			FProperty* Property = *PropIt;

			// Skip transient/internal runtime state
			if (Property->HasAnyPropertyFlags(CPF_Transient | CPF_DuplicateTransient))
			{
				continue;
			}

			TSharedPtr<FJsonValue> Value = FPropertySerializer::SerializePropertyValue(
				Property, StructPtr, AnimGraphNode, 0, 2);

			if (Value.IsValid())
			{
				PropsObj->SetField(Property->GetName(), Value);
			}
		}

		Result->SetObjectField(TEXT("properties"), PropsObj);
		return Result;
	}

	return nullptr;
}

UAnimationStateMachineGraph* UAnimBlueprintQuery::FindStateMachineByName(
	UAnimBlueprint* AnimBP,
	const FString& StateMachineName)
{
	if (!AnimBP) return nullptr;

	TArray<UEdGraph*> AllGraphs;
	AnimBP->GetAllGraphs(AllGraphs);

	for (UEdGraph* Graph : AllGraphs)
	{
		if (UAnimationStateMachineGraph* StateMachine = Cast<UAnimationStateMachineGraph>(Graph))
		{
			if (Graph->GetName().Equals(StateMachineName, ESearchCase::IgnoreCase))
			{
				return StateMachine;
			}
		}
	}

	return nullptr;
}

TArray<UAnimationGraph*> UAnimBlueprintQuery::GetAllAnimGraphs(UAnimBlueprint* AnimBP)
{
	TArray<UAnimationGraph*> AnimGraphs;
	if (!AnimBP) return AnimGraphs;

	TArray<UEdGraph*> AllGraphs;
	AnimBP->GetAllGraphs(AllGraphs);

	for (UEdGraph* Graph : AllGraphs)
	{
		if (UAnimationGraph* AnimGraph = Cast<UAnimationGraph>(Graph))
		{
			AnimGraphs.Add(AnimGraph);
		}
	}

	return AnimGraphs;
}