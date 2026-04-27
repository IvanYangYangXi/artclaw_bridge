// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Engine/Blueprint.h"
#include "BlueprintGraphConnect.generated.h"

/**
 * Blueprint graph connection API.
 * Provides operations for connecting, disconnecting, and inserting nodes in Blueprint graphs.
 * Supports execution flow and data connections with automatic validation.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UBlueprintGraphConnect : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Connect two pins in a Blueprint graph.
	 * Validates connection compatibility and handles automatic type conversion.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param SourceNode GUID of the source node
	 * @param SourcePin Name of the source pin
	 * @param TargetNode GUID of the target node
	 * @param TargetPin Name of the target pin
	 * @return JSON string with connection results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString ConnectGraphPins(
		const FString& AssetPath,
		const FString& SourceNode,
		const FString& SourcePin,
		const FString& TargetNode,
		const FString& TargetPin);

	/**
	 * Disconnect a pin from its connections.
	 * Can disconnect all connections or a specific connection.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param NodeGuid GUID of the node containing the pin
	 * @param PinName Name of the pin to disconnect
	 * @param TargetNode Optional: specific target node GUID to disconnect from
	 * @param TargetPin Optional: specific target pin name to disconnect from
	 * @return JSON string with disconnection results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString DisconnectGraphPin(
		const FString& AssetPath,
		const FString& NodeGuid,
		const FString& PinName,
		const FString& TargetNode = TEXT(""),
		const FString& TargetPin = TEXT(""));

	/**
	 * Insert a node between two connected nodes.
	 * Automatically handles pin connections and type compatibility.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param NodeClass Class of the node to insert
	 * @param SourceGuid GUID of the source node
	 * @param SourcePin Name of the source pin
	 * @param TargetGuid GUID of the target node
	 * @param TargetPin Name of the target pin
	 * @param GraphName Target graph name (default: "EventGraph")
	 * @return JSON string with insertion results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString InsertGraphNode(
		const FString& AssetPath,
		const FString& NodeClass,
		const FString& SourceGuid,
		const FString& SourcePin,
		const FString& TargetGuid,
		const FString& TargetPin,
		const FString& GraphName = TEXT("EventGraph"));

	/**
	 * Batch connect multiple pins in a single operation.
	 * Efficient for creating complex node networks.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param ConnectionsJson JSON array of connection objects: [{"from_node": "...", "from_pin": "...", "to_node": "...", "to_pin": "..."}, ...]
	 * @return JSON string with batch connection results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString BatchConnectPins(
		const FString& AssetPath,
		const FString& ConnectionsJson);

private:
	// Connection validation helpers
	static bool ValidateConnection(
		class UEdGraphPin* SourcePin,
		class UEdGraphPin* TargetPin,
		FString& OutError);

	static bool MakeConnection(
		class UEdGraphPin* SourcePin,
		class UEdGraphPin* TargetPin,
		FString& OutError);

	// Node and pin search helpers
	static class UEdGraphNode* FindNodeByGuid(
		UBlueprint* Blueprint,
		const FString& NodeGuidStr,
		FString& OutError);

	static class UEdGraphPin* FindPinByName(
		class UEdGraphNode* Node,
		const FString& PinName,
		FString& OutError);

	// Utility helpers
	static TSharedPtr<class FJsonObject> ParseJsonString(
		const FString& JsonString,
		FString& OutError);
};