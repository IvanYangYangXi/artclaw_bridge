// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Engine/Blueprint.h"
#include "BlueprintNodeProperty.generated.h"

/**
 * Blueprint node property and compilation API.
 * Provides operations for modifying node properties, compiling Blueprints, and managing interfaces.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UBlueprintNodeProperty : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Set properties on a Blueprint node.
	 * Supports nested properties, pin default values, and complex data types.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param NodeGuid GUID of the target node
	 * @param PropertiesJson JSON object with properties to set: {"PropertyName": "Value", ...}
	 * @return JSON string with operation results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString SetNodeProperty(
		const FString& AssetPath,
		const FString& NodeGuid,
		const FString& PropertiesJson);

	/**
	 * Compile a Blueprint and check for compilation errors.
	 * Provides detailed error reporting and success status.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @return JSON string with compilation results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString CompileBlueprint(const FString& AssetPath);

	/**
	 * Add or remove interfaces from a Blueprint.
	 * Manages interface implementation with proper graph creation.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param Action "add" or "remove"
	 * @param InterfaceName Name or path of the interface
	 * @return JSON string with operation results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString ModifyInterface(
		const FString& AssetPath,
		const FString& Action,
		const FString& InterfaceName);

	/**
	 * Create or modify Blueprint variables.
	 * Supports all variable types with metadata and default values.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param VariableName Name of the variable
	 * @param VariableTypeJson JSON object with type specification: {"Type": "int32", "DefaultValue": 0, ...}
	 * @param bIsArray Whether the variable should be an array
	 * @param CategoryName Category for organization
	 * @return JSON string with operation results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString SetBlueprintVariable(
		const FString& AssetPath,
		const FString& VariableName,
		const FString& VariableTypeJson,
		bool bIsArray = false,
		const FString& CategoryName = TEXT("Default"));

	/**
	 * Refresh and validate Blueprint structure.
	 * Performs comprehensive structure validation and fixes common issues.
	 * 
	 * @param AssetPath Asset path to the Blueprint
	 * @param bAutoFix Whether to automatically fix detected issues
	 * @return JSON string with validation results or error object
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
	static FString ValidateBlueprintStructure(
		const FString& AssetPath,
		bool bAutoFix = true);

private:
	// Property modification helpers
	static TArray<FString> ApplyNodeProperties(
		UObject* Node,
		const TSharedPtr<class FJsonObject>& Properties);

	static bool SetPinDefaultValue(
		class UEdGraphNode* Node,
		const FString& PinName,
		const FString& Value);

	// Compilation helpers
	static void CollectCompilationErrors(
		UBlueprint* Blueprint,
		TArray<FString>& OutErrors,
		TArray<FString>& OutWarnings);

	// Interface management helpers
	static class UClass* FindInterfaceClass(
		const FString& InterfaceName,
		FString& OutError);

	static bool AddInterfaceToBlueprint(
		UBlueprint* Blueprint,
		UClass* InterfaceClass,
		FString& OutError);

	static bool RemoveInterfaceFromBlueprint(
		UBlueprint* Blueprint,
		UClass* InterfaceClass,
		FString& OutError);

	// Variable management helpers
	static struct FBPVariableDescription* FindBlueprintVariable(
		UBlueprint* Blueprint,
		const FString& VariableName);

	static bool CreateBlueprintVariable(
		UBlueprint* Blueprint,
		const FString& VariableName,
		const struct FEdGraphPinType& PinType,
		const FString& CategoryName,
		FString& OutError);

	// Utility helpers
	static TSharedPtr<class FJsonObject> ParseJsonString(
		const FString& JsonString,
		FString& OutError);

	static struct FEdGraphPinType ParseVariableType(
		const TSharedPtr<class FJsonObject>& TypeJson,
		FString& OutError);
};