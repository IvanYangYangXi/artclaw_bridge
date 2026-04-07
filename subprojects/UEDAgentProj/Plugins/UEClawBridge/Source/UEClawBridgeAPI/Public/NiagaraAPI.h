// Copyright ArtClaw. All Rights Reserved.
// NOTE: Requires additional modules in UEClawBridgeAPI.Build.cs:
//   "Niagara", "NiagaraEditor"

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "NiagaraAPI.generated.h"

/**
 * Blueprint Function Library for Niagara particle system operations.
 * Provides tools to query, modify, and manage Niagara Systems and Emitters.
 */
UCLASS()
class UECLAWBRIDGEAPI_API UNiagaraAPI : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Query Niagara System structure: emitters, modules, parameters.
	 * 
	 * @param AssetPath Path to the Niagara System asset (e.g., "/Game/Effects/MySystem")
	 * @return JSON string with system information or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|Niagara")
	static FString QueryNiagaraSystem(const FString& AssetPath);

	/**
	 * Set Niagara user parameter value.
	 * 
	 * @param AssetPath Path to the Niagara System asset
	 * @param ParameterName Name of the parameter to set
	 * @param ValueJson JSON string representing the value (e.g., "5.0", "[1.0,0.0,0.0]")
	 * @return JSON string with success status or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|Niagara")
	static FString SetNiagaraParameter(
		const FString& AssetPath,
		const FString& ParameterName,
		const FString& ValueJson);

	/**
	 * Query Niagara Emitter details.
	 * 
	 * @param AssetPath Path to the Niagara System asset
	 * @param EmitterName Name of the emitter within the system
	 * @return JSON string with emitter information or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|Niagara")
	static FString QueryNiagaraEmitter(
		const FString& AssetPath,
		const FString& EmitterName);

	/**
	 * Add module to Niagara Emitter stack.
	 * 
	 * @param AssetPath Path to the Niagara System asset
	 * @param EmitterName Name of the emitter to modify
	 * @param ModuleClass Class name of the module to add
	 * @param StackGroup Stack group to add to ("Emitter Spawn", "Emitter Update", "Particle Spawn", "Particle Update", "Render")
	 * @return JSON string with success status or error
	 */
	UFUNCTION(BlueprintCallable, Category = "ArtClaw|Niagara")
	static FString AddNiagaraModule(
		const FString& AssetPath,
		const FString& EmitterName,
		const FString& ModuleClass,
		const FString& StackGroup = TEXT("Particle Update"));
};