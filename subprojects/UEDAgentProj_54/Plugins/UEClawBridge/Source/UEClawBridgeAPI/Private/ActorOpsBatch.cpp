// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)
// Batch actor operations (spawn/modify/delete).

#include "ActorOpsAPI.h"
#include "UEClawBridgeAPI.h"
#include "Utils/JsonHelpers.h"
#include "Utils/AssetModifier.h"
#include "Editor.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "ScopedTransaction.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

FString UActorOpsAPI::BatchSpawnActors(const FString& ActorsJson)
{
	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ActorsJson);
	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		return ClawJson::MakeError(TEXT("Invalid JSON format"));
	}

	const TArray<TSharedPtr<FJsonValue>>* ActorsArray;
	if (!JsonObject->TryGetArrayField(TEXT("actors"), ActorsArray))
	{
		return ClawJson::MakeError(TEXT("Missing 'actors' array"));
	}

	UWorld* World = FindWorldByType(TEXT("editor"));
	if (!World)
	{
		return ClawJson::MakeError(TEXT("Editor world not found"));
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		TEXT("Batch Spawn Actors"));

	int32 SuccessCount = 0;
	int32 FailCount = 0;
	TArray<TSharedPtr<FJsonValue>> Results;

	for (const auto& ActorValue : *ActorsArray)
	{
		const TSharedPtr<FJsonObject>* ActorObj;
		if (!ActorValue->TryGetObject(ActorObj) || !ActorObj->IsValid())
		{
			FailCount++;
			continue;
		}

		FString ClassName = (*ActorObj)->GetStringField(TEXT("class"));
		if (ClassName.IsEmpty())
		{
			FailCount++;
			continue;
		}

		// Parse location
		FVector Location(0, 0, 0);
		const TArray<TSharedPtr<FJsonValue>>* LocArray;
		if ((*ActorObj)->TryGetArrayField(TEXT("location"), LocArray) && LocArray->Num() >= 3)
		{
			Location.X = (*LocArray)[0]->AsNumber();
			Location.Y = (*LocArray)[1]->AsNumber();
			Location.Z = (*LocArray)[2]->AsNumber();
		}

		// Parse rotation
		FRotator Rotation(0, 0, 0);
		const TArray<TSharedPtr<FJsonValue>>* RotArray;
		if ((*ActorObj)->TryGetArrayField(TEXT("rotation"), RotArray) && RotArray->Num() >= 3)
		{
			Rotation.Pitch = (*RotArray)[0]->AsNumber();
			Rotation.Yaw = (*RotArray)[1]->AsNumber();
			Rotation.Roll = (*RotArray)[2]->AsNumber();
		}

		// Parse scale
		FVector Scale(1, 1, 1);
		const TArray<TSharedPtr<FJsonValue>>* ScaleArray;
		if ((*ActorObj)->TryGetArrayField(TEXT("scale"), ScaleArray) && ScaleArray->Num() >= 3)
		{
			Scale.X = (*ScaleArray)[0]->AsNumber();
			Scale.Y = (*ScaleArray)[1]->AsNumber();
			Scale.Z = (*ScaleArray)[2]->AsNumber();
		}

		FString ClassError;
		UClass* SpawnClass = ResolveActorClass(ClassName, ClassError);
		if (!SpawnClass)
		{
			FailCount++;
			continue;
		}

		FActorSpawnParameters SpawnParams;
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

		AActor* SpawnedActor = World->SpawnActor<AActor>(SpawnClass, Location, Rotation, SpawnParams);
		if (SpawnedActor)
		{
			SpawnedActor->SetActorScale3D(Scale);

			// Apply properties if provided
			const TSharedPtr<FJsonObject>* PropsObj;
			if ((*ActorObj)->TryGetObjectField(TEXT("properties"), PropsObj) && PropsObj->IsValid())
			{
				TArray<FString> PropErrors;
				ApplyPropertiesFromJson(SpawnedActor, *PropsObj, PropErrors);
			}

			TSharedPtr<FJsonObject> ActorResult = MakeShareable(new FJsonObject);
			ActorResult->SetStringField(TEXT("name"), GetActorLabelSafe(SpawnedActor));
			ActorResult->SetStringField(TEXT("class"), ClassName);
			Results.Add(MakeShareable(new FJsonValueObject(ActorResult)));
			SuccessCount++;
		}
		else
		{
			FailCount++;
		}
	}

	auto Result = ClawJson::MakeSuccess();
	Result->SetNumberField(TEXT("spawned_count"), SuccessCount);
	Result->SetNumberField(TEXT("failed_count"), FailCount);
	Result->SetArrayField(TEXT("spawned_actors"), Results);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Batch spawn: %d succeeded, %d failed"), 
		SuccessCount, FailCount);

	return ClawJson::ToString(Result);
}

FString UActorOpsAPI::BatchModifyActors(const FString& ModificationsJson)
{
	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ModificationsJson);
	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		return ClawJson::MakeError(TEXT("Invalid JSON format"));
	}

	const TArray<TSharedPtr<FJsonValue>>* ModArray;
	if (!JsonObject->TryGetArrayField(TEXT("modifications"), ModArray))
	{
		return ClawJson::MakeError(TEXT("Missing 'modifications' array"));
	}

	UWorld* World = FindWorldByType(TEXT("editor"));
	if (!World)
	{
		return ClawJson::MakeError(TEXT("Editor world not found"));
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		TEXT("Batch Modify Actors"));

	int32 SuccessCount = 0;
	int32 FailCount = 0;
	TArray<TSharedPtr<FJsonValue>> Results;

	for (const auto& ModValue : *ModArray)
	{
		const TSharedPtr<FJsonObject>* ModObj;
		if (!ModValue->TryGetObject(ModObj) || !ModObj->IsValid())
		{
			FailCount++;
			continue;
		}

		FString ActorName = (*ModObj)->GetStringField(TEXT("actor"));
		if (ActorName.IsEmpty())
		{
			FailCount++;
			continue;
		}

		AActor* Actor = FindActor(World, ActorName);
		if (!Actor)
		{
			FailCount++;
			continue;
		}

		const TSharedPtr<FJsonObject>* PropsObj;
		if (!(*ModObj)->TryGetObjectField(TEXT("properties"), PropsObj) || !PropsObj->IsValid())
		{
			FailCount++;
			continue;
		}

		FAssetModifier::MarkModified(Actor);

		TArray<FString> PropErrors;
		if (ApplyPropertiesFromJson(Actor, *PropsObj, PropErrors))
		{
			TSharedPtr<FJsonObject> ActorResult = MakeShareable(new FJsonObject);
			ActorResult->SetStringField(TEXT("name"), GetActorLabelSafe(Actor));
			if (PropErrors.Num() > 0)
			{
				TArray<TSharedPtr<FJsonValue>> ErrorArray;
				for (const FString& Error : PropErrors)
				{
					ErrorArray.Add(MakeShareable(new FJsonValueString(Error)));
				}
				ActorResult->SetArrayField(TEXT("property_errors"), ErrorArray);
			}
			Results.Add(MakeShareable(new FJsonValueObject(ActorResult)));
			SuccessCount++;
		}
		else
		{
			FailCount++;
		}
	}

	auto Result = ClawJson::MakeSuccess();
	Result->SetNumberField(TEXT("modified_count"), SuccessCount);
	Result->SetNumberField(TEXT("failed_count"), FailCount);
	Result->SetArrayField(TEXT("modified_actors"), Results);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Batch modify: %d succeeded, %d failed"), 
		SuccessCount, FailCount);

	return ClawJson::ToString(Result);
}

FString UActorOpsAPI::BatchDeleteActors(const FString& ActorNamesJson)
{
	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ActorNamesJson);
	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		return ClawJson::MakeError(TEXT("Invalid JSON format"));
	}

	const TArray<TSharedPtr<FJsonValue>>* NamesArray;
	if (!JsonObject->TryGetArrayField(TEXT("actors"), NamesArray))
	{
		return ClawJson::MakeError(TEXT("Missing 'actors' array"));
	}

	UWorld* World = FindWorldByType(TEXT("editor"));
	if (!World)
	{
		return ClawJson::MakeError(TEXT("Editor world not found"));
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		TEXT("Batch Delete Actors"));

	int32 SuccessCount = 0;
	int32 FailCount = 0;
	TArray<FString> DeletedNames;

	for (const auto& NameValue : *NamesArray)
	{
		FString ActorName = NameValue->AsString();
		if (ActorName.IsEmpty())
		{
			FailCount++;
			continue;
		}

		AActor* Actor = FindActor(World, ActorName);
		if (Actor)
		{
			FString SavedName = GetActorLabelSafe(Actor);
			Actor->Destroy();
			DeletedNames.Add(SavedName);
			SuccessCount++;
		}
		else
		{
			FailCount++;
		}
	}

	auto Result = ClawJson::MakeSuccess();
	Result->SetNumberField(TEXT("deleted_count"), SuccessCount);
	Result->SetNumberField(TEXT("failed_count"), FailCount);
	
	TArray<TSharedPtr<FJsonValue>> NamesArray2;
	for (const FString& Name : DeletedNames)
	{
		NamesArray2.Add(MakeShareable(new FJsonValueString(Name)));
	}
	Result->SetArrayField(TEXT("deleted_actors"), NamesArray2);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Batch delete: %d succeeded, %d failed"), 
		SuccessCount, FailCount);

	return ClawJson::ToString(Result);
}
