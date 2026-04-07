// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "DataTableAPI.generated.h"

/**
 * DataTable management API for ArtClaw.
 * Provides DataTable row manipulation and query capabilities.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UDataTableAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Add or update a DataTable row.
	 * Creates new row or updates existing row with provided values.
	 * 
	 * @param AssetPath DataTable asset path (e.g., /Game/Data/DT_Items)
	 * @param RowName Name of the row to add/update
	 * @param ValuesJson JSON string with row values matching the DataTable struct
	 * @return JSON string with operation result
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|DataTable")
	static FString AddDataTableRow(
		const FString& AssetPath,
		const FString& RowName,
		const FString& ValuesJson);

	/**
	 * Query DataTable rows with filtering and schema information.
	 * Returns row data along with struct schema for understanding the table structure.
	 * 
	 * @param AssetPath DataTable asset path
	 * @param RowFilter Optional row name filter (supports wildcards)
	 * @return JSON string with rows and schema information
	 */
	UFUNCTION(BlueprintCallable, Category="ArtClaw|DataTable")
	static FString QueryDataTable(
		const FString& AssetPath,
		const FString& RowFilter = TEXT(""));

private:
	// Helper to validate DataTable and get struct info
	static class UDataTable* LoadAndValidateDataTable(const FString& AssetPath, FString& OutError);
	
	// Helper to parse row values from JSON
	static bool ParseRowValuesFromJson(
		const class UScriptStruct* RowStruct,
		const FString& ValuesJson,
		TArray<uint8>& OutRowData,
		FString& OutError);
	
	// Helper to serialize row data to JSON
	static TSharedPtr<class FJsonObject> SerializeRowToJson(
		const class UScriptStruct* RowStruct,
		const uint8* RowData);
	
	// Helper to get struct schema information
	static TSharedPtr<class FJsonObject> GetStructSchema(const class UScriptStruct* Struct);
	
	// Helper for wildcard matching
	static bool MatchesWildcard(const FString& Text, const FString& Pattern);
};