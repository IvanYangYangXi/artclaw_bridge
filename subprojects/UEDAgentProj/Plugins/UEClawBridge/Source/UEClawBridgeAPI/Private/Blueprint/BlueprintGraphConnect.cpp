// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "Blueprint/BlueprintGraphConnect.h"
#include "UEClawBridgeAPI.h"
#include "Utils/JsonHelpers.h"
#include "Utils/AssetModifier.h"
#include "Utils/GraphLayoutUtil.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "ScopedTransaction.h"

FString UBlueprintGraphConnect::ConnectGraphPins(
	const FString& AssetPath,
	const FString& SourceNode,
	const FString& SourcePin,
	const FString& TargetNode,
	const FString& TargetPin)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("ConnectGraphPins: %s.%s -> %s.%s in %s"),
		*SourceNode, *SourcePin, *TargetNode, *TargetPin, *AssetPath);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	FString Error;
	UEdGraphNode* SourceGraphNode = FindNodeByGuid(Blueprint, SourceNode, Error);
	if (!SourceGraphNode) return ClawJson::MakeError(FString::Printf(TEXT("Source node not found: %s"), *Error));

	UEdGraphNode* TargetGraphNode = FindNodeByGuid(Blueprint, TargetNode, Error);
	if (!TargetGraphNode) return ClawJson::MakeError(FString::Printf(TEXT("Target node not found: %s"), *Error));

	UEdGraphPin* SourceGraphPin = FindPinByName(SourceGraphNode, SourcePin, Error);
	if (!SourceGraphPin) return ClawJson::MakeError(FString::Printf(TEXT("Source pin not found: %s"), *Error));

	UEdGraphPin* TargetGraphPin = FindPinByName(TargetGraphNode, TargetPin, Error);
	if (!TargetGraphPin) return ClawJson::MakeError(FString::Printf(TEXT("Target pin not found: %s"), *Error));

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(TEXT("Connect graph pins"));
	FAssetModifier::MarkModified(Blueprint);

	if (!ValidateConnection(SourceGraphPin, TargetGraphPin, Error))
	{
		return ClawJson::MakeError(Error);
	}

	bool bConnected = MakeConnection(SourceGraphPin, TargetGraphPin, Error);

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetBoolField(TEXT("success"), bConnected);

	if (bConnected)
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FAssetModifier::MarkPackageDirty(Blueprint);
		Result->SetBoolField(TEXT("needs_compile"), true);
		Result->SetBoolField(TEXT("needs_save"), true);
	}
	else
	{
		Result->SetStringField(TEXT("error"), Error);
	}

	return ClawJson::ToString(Result);
}

FString UBlueprintGraphConnect::DisconnectGraphPin(
	const FString& AssetPath,
	const FString& NodeGuid,
	const FString& PinName,
	const FString& TargetNode,
	const FString& TargetPin)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("DisconnectGraphPin: %s.%s in %s"), *NodeGuid, *PinName, *AssetPath);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	FString Error;
	UEdGraphNode* GraphNode = FindNodeByGuid(Blueprint, NodeGuid, Error);
	if (!GraphNode) return ClawJson::MakeError(Error);

	UEdGraphPin* Pin = FindPinByName(GraphNode, PinName, Error);
	if (!Pin) return ClawJson::MakeError(Error);

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(TEXT("Disconnect graph pin"));
	FAssetModifier::MarkModified(Blueprint);

	int32 DisconnectedCount = 0;

	if (!TargetNode.IsEmpty())
	{
		UEdGraphNode* TargetGraphNode = FindNodeByGuid(Blueprint, TargetNode, Error);
		if (TargetGraphNode)
		{
			UEdGraphPin* TargetGraphPin = nullptr;
			if (!TargetPin.IsEmpty())
			{
				TargetGraphPin = FindPinByName(TargetGraphNode, TargetPin, Error);
			}

			for (int32 i = Pin->LinkedTo.Num() - 1; i >= 0; i--)
			{
				UEdGraphPin* LinkedPin = Pin->LinkedTo[i];
				if (LinkedPin && LinkedPin->GetOwningNode() == TargetGraphNode)
				{
					if (!TargetGraphPin || LinkedPin == TargetGraphPin)
					{
						Pin->BreakLinkTo(LinkedPin);
						DisconnectedCount++;
						if (TargetGraphPin) break;
					}
				}
			}
		}
	}
	else
	{
		DisconnectedCount = Pin->LinkedTo.Num();
		Pin->BreakAllPinLinks();
	}

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetBoolField(TEXT("success"), DisconnectedCount > 0);
	Result->SetNumberField(TEXT("disconnected_count"), DisconnectedCount);

	if (DisconnectedCount > 0)
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FAssetModifier::MarkPackageDirty(Blueprint);
		Result->SetBoolField(TEXT("needs_compile"), true);
		Result->SetBoolField(TEXT("needs_save"), true);
	}

	return ClawJson::ToString(Result);
}

FString UBlueprintGraphConnect::InsertGraphNode(
	const FString& AssetPath,
	const FString& NodeClass,
	const FString& SourceGuid,
	const FString& SourcePin,
	const FString& TargetGuid,
	const FString& TargetPin,
	const FString& GraphName)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("InsertGraphNode: %s between %s.%s -> %s.%s"),
		*NodeClass, *SourceGuid, *SourcePin, *TargetGuid, *TargetPin);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	UEdGraph* TargetGraph = FAssetModifier::FindGraphByName(Blueprint, GraphName);
	if (!TargetGraph) return ClawJson::MakeError(FString::Printf(TEXT("Graph not found: %s"), *GraphName));

	FString Error;
	UEdGraphNode* SourceNode = FindNodeByGuid(Blueprint, SourceGuid, Error);
	if (!SourceNode) return ClawJson::MakeError(FString::Printf(TEXT("Source node not found: %s"), *Error));

	UEdGraphNode* TargetNode = FindNodeByGuid(Blueprint, TargetGuid, Error);
	if (!TargetNode) return ClawJson::MakeError(FString::Printf(TEXT("Target node not found: %s"), *Error));

	UEdGraphPin* SourceGraphPin = FindPinByName(SourceNode, SourcePin, Error);
	if (!SourceGraphPin) return ClawJson::MakeError(FString::Printf(TEXT("Source pin not found: %s"), *Error));

	UEdGraphPin* TargetGraphPin = FindPinByName(TargetNode, TargetPin, Error);
	if (!TargetGraphPin) return ClawJson::MakeError(FString::Printf(TEXT("Target pin not found: %s"), *Error));

	bool bWereConnected = SourceGraphPin->LinkedTo.Contains(TargetGraphPin);

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Insert %s node"), *NodeClass));

	if (bWereConnected)
	{
		SourceGraphPin->BreakLinkTo(TargetGraphPin);
	}

	// Placeholder — full implementation requires node creation logic
	return ClawJson::MakeError(TEXT("InsertGraphNode not fully implemented - requires node creation logic"));
}

FString UBlueprintGraphConnect::BatchConnectPins(
	const FString& AssetPath,
	const FString& ConnectionsJson)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("BatchConnectPins: %s"), *AssetPath);

	FString LoadError;
	UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(AssetPath, LoadError);
	if (!Blueprint) return ClawJson::MakeError(LoadError);

	FString JsonError;
	TSharedPtr<FJsonValue> JsonValue;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ConnectionsJson);
	if (!FJsonSerializer::Deserialize(Reader, JsonValue) || !JsonValue.IsValid())
	{
		return ClawJson::MakeError(TEXT("Invalid connections JSON format"));
	}

	const TArray<TSharedPtr<FJsonValue>>* ConnectionsArray;
	if (!JsonValue->TryGetArray(ConnectionsArray))
	{
		return ClawJson::MakeError(TEXT("Expected array of connection objects"));
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(TEXT("Batch connect pins"));
	FAssetModifier::MarkModified(Blueprint);

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("asset"), AssetPath);

	TArray<TSharedPtr<FJsonValue>> SuccessArray;
	TArray<TSharedPtr<FJsonValue>> FailedArray;
	int32 SuccessCount = 0;

	for (const TSharedPtr<FJsonValue>& ConnValue : *ConnectionsArray)
	{
		const TSharedPtr<FJsonObject>* ConnObj;
		if (!ConnValue->TryGetObject(ConnObj)) continue;

		FString FromNode, FromPin, ToNode, ToPin;
		if (!(*ConnObj)->TryGetStringField(TEXT("from_node"), FromNode) ||
			!(*ConnObj)->TryGetStringField(TEXT("from_pin"), FromPin) ||
			!(*ConnObj)->TryGetStringField(TEXT("to_node"), ToNode) ||
			!(*ConnObj)->TryGetStringField(TEXT("to_pin"), ToPin))
		{
			continue;
		}

		FString Error;
		UEdGraphNode* SrcNode = FindNodeByGuid(Blueprint, FromNode, Error);
		UEdGraphNode* DstNode = FindNodeByGuid(Blueprint, ToNode, Error);

		if (SrcNode && DstNode)
		{
			UEdGraphPin* SrcPin = FindPinByName(SrcNode, FromPin, Error);
			UEdGraphPin* DstPin = FindPinByName(DstNode, ToPin, Error);

			if (SrcPin && DstPin && ValidateConnection(SrcPin, DstPin, Error) && MakeConnection(SrcPin, DstPin, Error))
			{
				TSharedPtr<FJsonObject> SuccessObj = MakeShareable(new FJsonObject);
				SuccessObj->SetStringField(TEXT("from_node"), FromNode);
				SuccessObj->SetStringField(TEXT("from_pin"), FromPin);
				SuccessObj->SetStringField(TEXT("to_node"), ToNode);
				SuccessObj->SetStringField(TEXT("to_pin"), ToPin);
				SuccessArray.Add(MakeShareable(new FJsonValueObject(SuccessObj)));
				SuccessCount++;
				continue;
			}
		}

		TSharedPtr<FJsonObject> FailedObj = MakeShareable(new FJsonObject);
		FailedObj->SetStringField(TEXT("from_node"), FromNode);
		FailedObj->SetStringField(TEXT("from_pin"), FromPin);
		FailedObj->SetStringField(TEXT("to_node"), ToNode);
		FailedObj->SetStringField(TEXT("to_pin"), ToPin);
		FailedObj->SetStringField(TEXT("error"), Error);
		FailedArray.Add(MakeShareable(new FJsonValueObject(FailedObj)));
	}

	Result->SetBoolField(TEXT("success"), SuccessCount > 0);
	Result->SetNumberField(TEXT("success_count"), SuccessCount);
	Result->SetNumberField(TEXT("failed_count"), FailedArray.Num());
	Result->SetArrayField(TEXT("successful_connections"), SuccessArray);
	Result->SetArrayField(TEXT("failed_connections"), FailedArray);

	if (SuccessCount > 0)
	{
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
		FAssetModifier::MarkPackageDirty(Blueprint);
		Result->SetBoolField(TEXT("needs_compile"), true);
		Result->SetBoolField(TEXT("needs_save"), true);
	}

	return ClawJson::ToString(Result);
}

// === Implementation helpers ===

bool UBlueprintGraphConnect::ValidateConnection(UEdGraphPin* SourcePin, UEdGraphPin* TargetPin, FString& OutError)
{
	if (!SourcePin || !TargetPin)
	{
		OutError = TEXT("Invalid pins");
		return false;
	}

	const UEdGraphSchema* Schema = SourcePin->GetSchema();
	if (!Schema)
	{
		OutError = TEXT("No schema available");
		return false;
	}

	FPinConnectionResponse Response = Schema->CanCreateConnection(SourcePin, TargetPin);
	if (Response.Response == CONNECT_RESPONSE_DISALLOW)
	{
		OutError = Response.Message.ToString();
		return false;
	}

	return true;
}

bool UBlueprintGraphConnect::MakeConnection(UEdGraphPin* SourcePin, UEdGraphPin* TargetPin, FString& OutError)
{
	if (!SourcePin || !TargetPin)
	{
		OutError = TEXT("Invalid pins");
		return false;
	}

	const UEdGraphSchema* Schema = SourcePin->GetSchema();
	if (!Schema)
	{
		OutError = TEXT("No schema available");
		return false;
	}

	bool bConnected = Schema->TryCreateConnection(SourcePin, TargetPin);
	if (!bConnected)
	{
		OutError = TEXT("Failed to create connection");
		return false;
	}

	return true;
}

UEdGraphNode* UBlueprintGraphConnect::FindNodeByGuid(UBlueprint* Blueprint, const FString& NodeGuidStr, FString& OutError)
{
	FGuid NodeGuid;
	if (!FGuid::Parse(NodeGuidStr, NodeGuid))
	{
		OutError = FString::Printf(TEXT("Invalid GUID format: %s"), *NodeGuidStr);
		return nullptr;
	}

	UEdGraphNode* Node = FAssetModifier::FindNodeByGuid(Blueprint, NodeGuid);
	if (!Node)
	{
		OutError = FString::Printf(TEXT("Node not found: %s"), *NodeGuidStr);
		return nullptr;
	}

	return Node;
}

UEdGraphPin* UBlueprintGraphConnect::FindPinByName(UEdGraphNode* Node, const FString& PinName, FString& OutError)
{
	if (!Node)
	{
		OutError = TEXT("Invalid node");
		return nullptr;
	}

	for (UEdGraphPin* Pin : Node->Pins)
	{
		if (Pin && Pin->PinName.ToString().Equals(PinName, ESearchCase::IgnoreCase))
		{
			return Pin;
		}
	}

	OutError = FString::Printf(TEXT("Pin not found: %s"), *PinName);
	return nullptr;
}

TSharedPtr<FJsonObject> UBlueprintGraphConnect::ParseJsonString(const FString& JsonString, FString& OutError)
{
	return ClawJson::Parse(JsonString, OutError);
}
