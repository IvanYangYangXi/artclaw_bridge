// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "StateTreeAPI.h"
#include "UEClawBridgeAPI.h"
#include "Utils/AssetModifier.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

// Conditional StateTree includes - handle gracefully if module not available
#if WITH_EDITOR
	#include "StateTree.h"
	#include "StateTreeState.h"
	#include "StateTreeEditorData.h"
	#include "StateTreeTaskBase.h"
	#include "StateTreeEvaluatorBase.h"
	#include "StateTreeConditionBase.h"
	#include "StateTreeTypes.h"
	#include "StateTreePropertyBindings.h"
	#include "StructUtils/InstancedStructContainer.h"
	#include "Engine/Engine.h"
	#include "UObject/UObjectIterator.h"
#endif

namespace
{
	/** Convert JSON object to formatted string */
	FString ClawJsonToString(const TSharedPtr<FJsonObject>& Obj)
	{
		if (!Obj.IsValid()) return TEXT("{}");
		
		FString OutputString;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
		FJsonSerializer::Serialize(Obj.ToSharedRef(), Writer);
		return OutputString;
	}

	/** Create error response JSON */
	FString ClawMakeError(const FString& Msg)
	{
		TSharedPtr<FJsonObject> Error = MakeShareable(new FJsonObject);
		Error->SetBoolField(TEXT("success"), false);
		Error->SetStringField(TEXT("error"), Msg);
		return ClawJsonToString(Error);
	}
}

bool UStateTreeAPI::IsStateTreeModuleAvailable()
{
#if WITH_EDITOR
	// Check if StateTree module is loaded
	return FModuleManager::Get().IsModuleLoaded("StateTreeModule") || 
		   FModuleManager::Get().IsModuleLoaded("StateTreeEditorModule");
#else
	return false;
#endif
}

FString UStateTreeAPI::JsonObjectToString(const TSharedPtr<FJsonObject>& JsonObject)
{
	return ClawJsonToString(JsonObject);
}

FString UStateTreeAPI::ClawMakeError(const FString& ErrorMessage)
{
	return ::ClawMakeError(ErrorMessage);
}

FString UStateTreeAPI::QueryStateTree(const FString& AssetPath)
{
	if (!IsStateTreeModuleAvailable())
	{
		return ClawMakeError(TEXT("StateTree module not available in this UE version"));
	}

#if WITH_EDITOR
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryStateTree: %s"), *AssetPath);

	// Load the StateTree asset
	FString LoadError;
	UStateTree* StateTree = FAssetModifier::LoadAssetByPath<UStateTree>(AssetPath, LoadError);
	if (!StateTree)
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("QueryStateTree failed: %s"), *LoadError);
		return ClawMakeError(LoadError);
	}

	// Build result JSON
	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("name"), StateTree->GetName());
	Result->SetStringField(TEXT("path"), AssetPath);

	// Get StateTree schema info
	if (StateTree->GetSchema())
	{
		Result->SetStringField(TEXT("schema"), StateTree->GetSchema()->GetName());
	}

	// Extract states
	TSharedPtr<FJsonObject> StatesObj = MakeShareable(new FJsonObject);
	TArray<TSharedPtr<FJsonValue>> StateArray;

	TConstArrayView<FCompactStateTreeState> States = StateTree->GetStates();
	for (int32 i = 0; i < States.Num(); ++i)
	{
		const FCompactStateTreeState& State = States[i];

		TSharedPtr<FJsonObject> StateObj = MakeShareable(new FJsonObject);
		StateObj->SetStringField(TEXT("name"), State.Name.ToString());
		StateObj->SetNumberField(TEXT("index"), i);
		
		// State type
		FString StateTypeStr;
		switch (State.Type)
		{
		case EStateTreeStateType::State: StateTypeStr = TEXT("State"); break;
		case EStateTreeStateType::Group: StateTypeStr = TEXT("Group"); break;
		case EStateTreeStateType::Linked: StateTypeStr = TEXT("Linked"); break;
		case EStateTreeStateType::LinkedAsset: StateTypeStr = TEXT("LinkedAsset"); break;
		case EStateTreeStateType::Subtree: StateTypeStr = TEXT("Subtree"); break;
		default: StateTypeStr = TEXT("Unknown");
		}
		StateObj->SetStringField(TEXT("type"), StateTypeStr);
		StateObj->SetNumberField(TEXT("depth"), State.Depth);
		StateObj->SetBoolField(TEXT("enabled"), State.bEnabled);

		// Parent info
		if (State.Parent.IsValid())
		{
			StateObj->SetNumberField(TEXT("parent_index"), State.Parent.Index);
		}

		// Children info
		if (State.HasChildren())
		{
			StateObj->SetNumberField(TEXT("children_begin"), State.ChildrenBegin);
			StateObj->SetNumberField(TEXT("children_end"), State.ChildrenEnd);
		}

		StateArray.Add(MakeShareable(new FJsonValueObject(StateObj)));
	}

	StatesObj->SetArrayField(TEXT("items"), StateArray);
	StatesObj->SetNumberField(TEXT("count"), StateArray.Num());
	Result->SetObjectField(TEXT("states"), StatesObj);

	// Extract tasks
	TSharedPtr<FJsonObject> TasksObj = MakeShareable(new FJsonObject);
	TArray<TSharedPtr<FJsonValue>> TaskArray;

	const FInstancedStructContainer& Nodes = StateTree->GetNodes();
	for (int32 i = 0; i < Nodes.Num(); ++i)
	{
		FConstStructView Node = Nodes[i];
		if (const FStateTreeTaskBase* Task = Node.GetPtr<const FStateTreeTaskBase>())
		{
			TSharedPtr<FJsonObject> TaskObj = MakeShareable(new FJsonObject);
			TaskObj->SetNumberField(TEXT("index"), i);
			TaskObj->SetStringField(TEXT("name"), Task->Name.ToString());
			TaskObj->SetBoolField(TEXT("enabled"), Task->bTaskEnabled);

			if (const UScriptStruct* Struct = Node.GetScriptStruct())
			{
				TaskObj->SetStringField(TEXT("type"), Struct->GetName());
			}

			TaskArray.Add(MakeShareable(new FJsonValueObject(TaskObj)));
		}
	}

	TasksObj->SetArrayField(TEXT("items"), TaskArray);
	TasksObj->SetNumberField(TEXT("count"), TaskArray.Num());
	Result->SetObjectField(TEXT("tasks"), TasksObj);

	return ClawJsonToString(Result);
#else
	return ClawMakeError(TEXT("StateTree operations require Editor build"));
#endif
}

FString UStateTreeAPI::AddStateTreeState(
	const FString& AssetPath,
	const FString& ParentStateName,
	const FString& StateName,
	const FString& StateType)
{
	if (!IsStateTreeModuleAvailable())
	{
		return ClawMakeError(TEXT("StateTree module not available in this UE version"));
	}

#if WITH_EDITOR
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("AddStateTreeState: %s -> %s (%s)"), *AssetPath, *StateName, *StateType);

	// Load StateTree
	FString LoadError;
	UStateTree* StateTree = FAssetModifier::LoadAssetByPath<UStateTree>(AssetPath, LoadError);
	if (!StateTree)
	{
		return ClawMakeError(LoadError);
	}

	// Get editor data
	UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(StateTree->EditorData);
	if (!EditorData)
	{
		return ClawMakeError(TEXT("StateTree has no editor data. Cannot modify."));
	}

	// Parse state type
	EStateTreeStateType StateTypeEnum = EStateTreeStateType::State;
	if (StateType.Equals(TEXT("Group"), ESearchCase::IgnoreCase))
	{
		StateTypeEnum = EStateTreeStateType::Group;
	}
	else if (StateType.Equals(TEXT("Linked"), ESearchCase::IgnoreCase))
	{
		StateTypeEnum = EStateTreeStateType::Linked;
	}
	else if (StateType.Equals(TEXT("Subtree"), ESearchCase::IgnoreCase))
	{
		StateTypeEnum = EStateTreeStateType::Subtree;
	}

	// Begin transaction
	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Add StateTree State: %s"), *StateName));

	FAssetModifier::MarkModified(StateTree);
	FAssetModifier::MarkModified(EditorData);

	// Find parent state if specified
	UStateTreeState* ParentState = nullptr;
	if (!ParentStateName.IsEmpty())
	{
		// Search for parent in subtrees
		for (UStateTreeState* RootState : EditorData->SubTrees)
		{
			if (RootState && RootState->Name.ToString() == ParentStateName)
			{
				ParentState = RootState;
				break;
			}
			// TODO: Add recursive search for nested parents
		}

		if (!ParentState)
		{
			return ClawMakeError(FString::Printf(TEXT("Parent state '%s' not found"), *ParentStateName));
		}
	}

	// Create new state
	UStateTreeState* NewState = NewObject<UStateTreeState>(EditorData, NAME_None, RF_Transactional);
	NewState->Name = FName(*StateName);
	NewState->Type = StateTypeEnum;
	NewState->SelectionBehavior = EStateTreeStateSelectionBehavior::TryEnterState;

	// Add to parent or root
	if (ParentState)
	{
		ParentState->Children.Add(NewState);
		NewState->Parent = ParentState;
	}
	else
	{
		EditorData->SubTrees.Add(NewState);
	}

	FAssetModifier::MarkPackageDirty(StateTree);

	// Build result
	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("asset_path"), AssetPath);
	Result->SetStringField(TEXT("state_name"), StateName);
	Result->SetStringField(TEXT("state_type"), StateType);
	Result->SetStringField(TEXT("message"), FString::Printf(TEXT("State '%s' added to StateTree"), *StateName));

	return ClawJsonToString(Result);
#else
	return ClawMakeError(TEXT("StateTree operations require Editor build"));
#endif
}

FString UStateTreeAPI::AddStateTreeTask(
	const FString& AssetPath,
	const FString& StateName,
	const FString& TaskClass,
	const FString& PropertiesJson)
{
	if (!IsStateTreeModuleAvailable())
	{
		return ClawMakeError(TEXT("StateTree module not available in this UE version"));
	}

#if WITH_EDITOR
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("AddStateTreeTask: %s -> %s (%s)"), *AssetPath, *StateName, *TaskClass);

	// Load StateTree
	FString LoadError;
	UStateTree* StateTree = FAssetModifier::LoadAssetByPath<UStateTree>(AssetPath, LoadError);
	if (!StateTree)
	{
		return ClawMakeError(LoadError);
	}

	UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(StateTree->EditorData);
	if (!EditorData)
	{
		return ClawMakeError(TEXT("StateTree has no editor data. Cannot modify."));
	}

	// Find the task struct type
	UScriptStruct* TaskStruct = nullptr;
	for (TObjectIterator<UScriptStruct> It; It; ++It)
	{
		UScriptStruct* Struct = *It;
		if (Struct->GetName() == TaskClass || Struct->GetName().Contains(TaskClass))
		{
			if (Struct->IsChildOf(FStateTreeTaskBase::StaticStruct()))
			{
				TaskStruct = Struct;
				break;
			}
		}
	}

	if (!TaskStruct)
	{
		return ClawMakeError(FString::Printf(TEXT("Task class '%s' not found"), *TaskClass));
	}

	// Find target state
	UStateTreeState* TargetState = nullptr;
	for (UStateTreeState* RootState : EditorData->SubTrees)
	{
		if (RootState && RootState->Name.ToString() == StateName)
		{
			TargetState = RootState;
			break;
		}
		// TODO: Add recursive search for nested states
	}

	if (!TargetState)
	{
		return ClawMakeError(FString::Printf(TEXT("State '%s' not found"), *StateName));
	}

	// Begin transaction
	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Add StateTree Task: %s"), *TaskClass));

	FAssetModifier::MarkModified(StateTree);
	FAssetModifier::MarkModified(EditorData);
	FAssetModifier::MarkModified(TargetState);

	// Create and add the task
	FStateTreeEditorNode NewTaskNode;
	NewTaskNode.Node.InitializeAs(TaskStruct);

	if (FStateTreeTaskBase* Task = NewTaskNode.Node.GetMutablePtr<FStateTreeTaskBase>())
	{
		Task->Name = FName(*TaskClass);
		Task->bTaskEnabled = true;
	}

	TargetState->Tasks.Add(NewTaskNode);
	FAssetModifier::MarkPackageDirty(StateTree);

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("asset_path"), AssetPath);
	Result->SetStringField(TEXT("state_name"), StateName);
	Result->SetStringField(TEXT("task_class"), TaskStruct->GetName());
	Result->SetStringField(TEXT("message"), FString::Printf(TEXT("Task '%s' added to state '%s'"), *TaskClass, *StateName));

	return ClawJsonToString(Result);
#else
	return ClawMakeError(TEXT("StateTree operations require Editor build"));
#endif
}

FString UStateTreeAPI::AddStateTreeTransition(
	const FString& AssetPath,
	const FString& SourceState,
	const FString& TargetState,
	const FString& Trigger)
{
	if (!IsStateTreeModuleAvailable())
	{
		return ClawMakeError(TEXT("StateTree module not available in this UE version"));
	}

#if WITH_EDITOR
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("AddStateTreeTransition: %s -> %s (%s)"), *SourceState, *TargetState, *Trigger);

	// Load StateTree
	FString LoadError;
	UStateTree* StateTree = FAssetModifier::LoadAssetByPath<UStateTree>(AssetPath, LoadError);
	if (!StateTree)
	{
		return ClawMakeError(LoadError);
	}

	UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(StateTree->EditorData);
	if (!EditorData)
	{
		return ClawMakeError(TEXT("StateTree has no editor data. Cannot modify."));
	}

	// Find source state
	UStateTreeState* SourceStateObj = nullptr;
	for (UStateTreeState* RootState : EditorData->SubTrees)
	{
		if (RootState && RootState->Name.ToString() == SourceState)
		{
			SourceStateObj = RootState;
			break;
		}
		// TODO: Add recursive search
	}

	if (!SourceStateObj)
	{
		return ClawMakeError(FString::Printf(TEXT("Source state '%s' not found"), *SourceState));
	}

	// Parse trigger type
	EStateTreeTransitionTrigger TriggerEnum = EStateTreeTransitionTrigger::OnStateCompleted;
	if (Trigger.Equals(TEXT("OnStateFailed"), ESearchCase::IgnoreCase))
	{
		TriggerEnum = EStateTreeTransitionTrigger::OnStateFailed;
	}
	else if (Trigger.Equals(TEXT("OnTick"), ESearchCase::IgnoreCase))
	{
		TriggerEnum = EStateTreeTransitionTrigger::OnTick;
	}
	else if (Trigger.Equals(TEXT("OnEvent"), ESearchCase::IgnoreCase))
	{
		TriggerEnum = EStateTreeTransitionTrigger::OnEvent;
	}

	// Begin transaction
	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Add StateTree Transition: %s -> %s"), *SourceState, *TargetState));

	FAssetModifier::MarkModified(StateTree);
	FAssetModifier::MarkModified(EditorData);
	FAssetModifier::MarkModified(SourceStateObj);

	// Create transition
	FStateTreeTransition NewTransition;
	NewTransition.Trigger = TriggerEnum;
	NewTransition.Priority = EStateTreeTransitionPriority::Normal;

	// Set target state - handle special cases
	if (TargetState.Equals(TEXT("Succeeded"), ESearchCase::IgnoreCase))
	{
		NewTransition.State = FStateTreeStateLink(EStateTreeTransitionType::Succeeded);
	}
	else if (TargetState.Equals(TEXT("Failed"), ESearchCase::IgnoreCase))
	{
		NewTransition.State = FStateTreeStateLink(EStateTreeTransitionType::Failed);
	}
	else if (TargetState.Equals(TEXT("Next"), ESearchCase::IgnoreCase))
	{
		NewTransition.State = FStateTreeStateLink(EStateTreeTransitionType::NextSelectableState);
	}
	else
	{
		// Find target state
		UStateTreeState* TargetStateObj = nullptr;
		for (UStateTreeState* RootState : EditorData->SubTrees)
		{
			if (RootState && RootState->Name.ToString() == TargetState)
			{
				TargetStateObj = RootState;
				break;
			}
		}

		if (!TargetStateObj)
		{
			return ClawMakeError(FString::Printf(TEXT("Target state '%s' not found"), *TargetState));
		}

		NewTransition.State.ID = TargetStateObj->ID;
		NewTransition.State.LinkType = EStateTreeTransitionType::GotoState;
		NewTransition.State.Name = TargetStateObj->Name;
	}

	SourceStateObj->Transitions.Add(NewTransition);
	FAssetModifier::MarkPackageDirty(StateTree);

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("asset_path"), AssetPath);
	Result->SetStringField(TEXT("source_state"), SourceState);
	Result->SetStringField(TEXT("target_state"), TargetState);
	Result->SetStringField(TEXT("trigger"), Trigger);
	Result->SetStringField(TEXT("message"), FString::Printf(TEXT("Transition added: %s -> %s"), *SourceState, *TargetState));

	return ClawJsonToString(Result);
#else
	return ClawMakeError(TEXT("StateTree operations require Editor build"));
#endif
}

bool UStateTreeAPI::RemoveStateTreeState(const FString& AssetPath, const FString& StateName)
{
	if (!IsStateTreeModuleAvailable())
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("StateTree module not available"));
		return false;
	}

#if WITH_EDITOR
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("RemoveStateTreeState: %s from %s"), *StateName, *AssetPath);

	// Load StateTree
	FString LoadError;
	UStateTree* StateTree = FAssetModifier::LoadAssetByPath<UStateTree>(AssetPath, LoadError);
	if (!StateTree)
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("RemoveStateTreeState failed: %s"), *LoadError);
		return false;
	}

	UStateTreeEditorData* EditorData = Cast<UStateTreeEditorData>(StateTree->EditorData);
	if (!EditorData)
	{
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("StateTree has no editor data"));
		return false;
	}

	// Begin transaction
	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Remove StateTree State: %s"), *StateName));

	FAssetModifier::MarkModified(StateTree);
	FAssetModifier::MarkModified(EditorData);

	// Find and remove the state
	for (int32 i = 0; i < EditorData->SubTrees.Num(); ++i)
	{
		UStateTreeState* RootState = EditorData->SubTrees[i];
		if (RootState && RootState->Name.ToString() == StateName)
		{
			EditorData->SubTrees.RemoveAt(i);
			FAssetModifier::MarkPackageDirty(StateTree);
			return true;
		}
	}

	UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("State '%s' not found"), *StateName);
	return false;
#else
	UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("StateTree operations require Editor build"));
	return false;
#endif
}