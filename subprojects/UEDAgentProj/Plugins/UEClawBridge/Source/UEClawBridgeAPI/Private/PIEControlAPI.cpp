// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "PIEControlAPI.h"
#include "UEClawBridgeAPI.h"
#include "Editor.h"
#include "LevelEditor.h" 
#include "LevelEditorSubsystem.h"
#include "Engine/World.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/WorldSettings.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/Guid.h"
#include "EngineUtils.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#include "HAL/PlatformProcess.h"
#include "Modules/ModuleManager.h"

namespace
{
	FString ClawJsonToString(const TSharedPtr<FJsonObject>& Obj)
	{
		FString Output;
		auto Writer = TJsonWriterFactory<>::Create(&Output);
		FJsonSerializer::Serialize(Obj.ToSharedRef(), Writer);
		return Output;
	}

	FString ClawMakeError(const FString& Message)
	{
		TSharedPtr<FJsonObject> Obj = MakeShareable(new FJsonObject);
		Obj->SetBoolField(TEXT("success"), false);
		Obj->SetStringField(TEXT("error"), Message);
		return ClawJsonToString(Obj);
	}

	FString GenerateSessionId()
	{
		return FString::Printf(TEXT("pie_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Short));
	}
}

FString UPIEControlAPI::PIEStart(const FString& Mode, const FString& MapPath, float Timeout)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("PIEStart: mode=%s, map=%s, timeout=%.1f"), 
		*Mode, MapPath.IsEmpty() ? TEXT("current") : *MapPath, Timeout);

	// Check if PIE is already running
	if (GEditor->IsPlaySessionInProgress())
	{
		UWorld* PIEWorld = GetPIEWorld();
		if (PIEWorld)
		{
			TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
			Result->SetBoolField(TEXT("success"), true);
			Result->SetStringField(TEXT("session_id"), GenerateSessionId());
			Result->SetStringField(TEXT("world_name"), PIEWorld->GetName());
			Result->SetStringField(TEXT("state"), TEXT("already_running"));
			return ClawJsonToString(Result);
		}
	}

	// Load specific map if requested
	if (!MapPath.IsEmpty())
	{
		ULevelEditorSubsystem* LevelEditorSubsystem = GEditor->GetEditorSubsystem<ULevelEditorSubsystem>();
		if (LevelEditorSubsystem && !LevelEditorSubsystem->LoadLevel(MapPath))
		{
			return ClawMakeError(FString::Printf(TEXT("Failed to load map: %s"), *MapPath));
		}
	}

	// Configure PIE settings
	FRequestPlaySessionParams Params;
	Params.WorldType = EPlaySessionWorldType::PlayInEditor;

	if (Mode.Equals(TEXT("new_window"), ESearchCase::IgnoreCase) ||
		Mode.Equals(TEXT("standalone"), ESearchCase::IgnoreCase))
	{
		Params.DestinationSlateViewport = nullptr;
	}
	else // viewport (default)
	{
		FLevelEditorModule& LevelEditorModule = FModuleManager::GetModuleChecked<FLevelEditorModule>(TEXT("LevelEditor"));
		TSharedPtr<IAssetViewport> ActiveViewport = LevelEditorModule.GetFirstActiveViewport();
		if (ActiveViewport.IsValid())
		{
			Params.DestinationSlateViewport = ActiveViewport;
		}
	}

	GEditor->RequestPlaySession(Params);

	if (!WaitForPIEReady(Timeout))
	{
		return ClawMakeError(FString::Printf(TEXT("PIE did not start within %.0f seconds"), Timeout));
	}

	UWorld* PIEWorld = GetPIEWorld();
	if (!PIEWorld)
	{
		return ClawMakeError(TEXT("PIE started but could not find PIE world"));
	}

	// Get player info
	TArray<double> PlayerStartLocation = {0, 0, 0};
	TArray<AActor*> PlayerStarts;
	UGameplayStatics::GetAllActorsOfClass(PIEWorld, APlayerStart::StaticClass(), PlayerStarts);
	if (PlayerStarts.Num() > 0)
	{
		FVector Loc = PlayerStarts[0]->GetActorLocation();
		PlayerStartLocation = {Loc.X, Loc.Y, Loc.Z};
	}

	APlayerController* PC = PIEWorld->GetFirstPlayerController();
	FString PlayerPawnName = PC && PC->GetPawn() ? PC->GetPawn()->GetName() : TEXT("None");

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("session_id"), GenerateSessionId());
	Result->SetStringField(TEXT("world_name"), PIEWorld->GetName());
	Result->SetStringField(TEXT("state"), TEXT("running"));
	Result->SetStringField(TEXT("player_pawn"), PlayerPawnName);

	TArray<TSharedPtr<FJsonValue>> StartLocArray;
	for (double Val : PlayerStartLocation)
	{
		StartLocArray.Add(MakeShareable(new FJsonValueNumber(Val)));
	}
	Result->SetArrayField(TEXT("player_start"), StartLocArray);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("PIEStart: Started (world=%s)"), *PIEWorld->GetName());
	return ClawJsonToString(Result);
}

FString UPIEControlAPI::PIEStop()
{
	if (!GEditor->IsPlaySessionInProgress())
	{
		TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
		Result->SetBoolField(TEXT("success"), true);
		Result->SetStringField(TEXT("state"), TEXT("not_running"));
		return ClawJsonToString(Result);
	}

	GEditor->RequestEndPlayMap();

	const double WaitStart = FPlatformTime::Seconds();
	while (GEditor->IsPlaySessionInProgress() && (FPlatformTime::Seconds() - WaitStart) < 5.0)
	{
		FPlatformProcess::Sleep(0.05f);
	}

	if (GEditor->IsPlaySessionInProgress())
	{
		return ClawMakeError(TEXT("Failed to stop PIE within timeout"));
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("state"), TEXT("stopped"));

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("PIEStop: Stopped"));
	return ClawJsonToString(Result);
}

FString UPIEControlAPI::PIEPause()
{
	if (!GEditor->IsPlaySessionInProgress())
	{
		return ClawMakeError(TEXT("No PIE session running"));
	}

	UWorld* PIEWorld = GetPIEWorld();
	if (!PIEWorld)
	{
		return ClawMakeError(TEXT("PIE world not found"));
	}

	if (PIEWorld->IsPaused())
	{
		TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
		Result->SetBoolField(TEXT("success"), true);
		Result->SetBoolField(TEXT("paused"), true);
		Result->SetStringField(TEXT("message"), TEXT("Already paused"));
		return ClawJsonToString(Result);
	}

	if (GEditor->PlayWorld)
	{
		GEditor->PlayWorld->bDebugPauseExecution = true;
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetBoolField(TEXT("paused"), true);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("PIEPause: Paused"));
	return ClawJsonToString(Result);
}

FString UPIEControlAPI::PIEResume()
{
	if (!GEditor->IsPlaySessionInProgress())
	{
		return ClawMakeError(TEXT("No PIE session running"));
	}

	UWorld* PIEWorld = GetPIEWorld();
	if (!PIEWorld)
	{
		return ClawMakeError(TEXT("PIE world not found"));
	}

	if (!PIEWorld->IsPaused())
	{
		TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
		Result->SetBoolField(TEXT("success"), true);
		Result->SetBoolField(TEXT("paused"), false);
		Result->SetStringField(TEXT("message"), TEXT("Already running"));
		return ClawJsonToString(Result);
	}

	if (GEditor->PlayWorld)
	{
		GEditor->PlayWorld->bDebugPauseExecution = false;
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetBoolField(TEXT("paused"), false);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("PIEResume: Resumed"));
	return ClawJsonToString(Result);
}

FString UPIEControlAPI::PIEGetState(const FString& Include)
{
	TSet<FString> IncludeSet;
	TArray<FString> IncludeArray;
	Include.ParseIntoArray(IncludeArray, TEXT(","), true);
	for (const FString& Item : IncludeArray)
	{
		IncludeSet.Add(Item.TrimStartAndEnd().ToLower());
	}

	bool bIncludeWorld = IncludeSet.Num() == 0 || IncludeSet.Contains(TEXT("world")) || Include.Equals(TEXT("all"), ESearchCase::IgnoreCase);
	bool bIncludePlayers = IncludeSet.Num() == 0 || IncludeSet.Contains(TEXT("players")) || Include.Equals(TEXT("all"), ESearchCase::IgnoreCase);

	bool bRunning = GEditor->IsPlaySessionInProgress();

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("running"), bRunning);

	if (!bRunning)
	{
		Result->SetStringField(TEXT("state"), TEXT("not_running"));
		return ClawJsonToString(Result);
	}

	UWorld* PIEWorld = GetPIEWorld();
	if (!PIEWorld)
	{
		Result->SetStringField(TEXT("state"), TEXT("initializing"));
		return ClawJsonToString(Result);
	}

	Result->SetStringField(TEXT("state"), TEXT("running"));
	Result->SetBoolField(TEXT("paused"), PIEWorld->IsPaused());

	if (bIncludeWorld)
	{
		Result->SetObjectField(TEXT("world"), GetWorldInfo(PIEWorld));
	}

	if (bIncludePlayers)
	{
		Result->SetArrayField(TEXT("players"), GetPlayersInfo(PIEWorld));
	}

	return ClawJsonToString(Result);
}

FString UPIEControlAPI::PIEWaitFor(const FString& ActorName, const FString& PropertyName, 
	const FString& Operator, const FString& ExpectedValue, float Timeout, float PollInterval)
{
	if (!GEditor->IsPlaySessionInProgress())
	{
		return ClawMakeError(TEXT("No PIE session running"));
	}

	UWorld* PIEWorld = GetPIEWorld();
	if (!PIEWorld)
	{
		return ClawMakeError(TEXT("PIE world not found"));
	}

	if (ActorName.IsEmpty())
	{
		return ClawMakeError(TEXT("ActorName is required"));
	}
	if (PropertyName.IsEmpty())
	{
		return ClawMakeError(TEXT("PropertyName is required"));
	}

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("PIEWaitFor: Waiting for %s.%s %s %s"), 
		*ActorName, *PropertyName, *Operator, *ExpectedValue);

	const double StartTime = FPlatformTime::Seconds();
	const double EndTime = StartTime + Timeout;
	bool bConditionMet = false;
	TSharedPtr<FJsonValue> ActualValue;

	while (FPlatformTime::Seconds() < EndTime)
	{
		// Check if PIE is still running
		if (!GEditor->IsPlaySessionInProgress())
		{
			return ClawMakeError(TEXT("PIE session ended while waiting"));
		}

		// Find actor
		AActor* Actor = FindActorByName(PIEWorld, ActorName);
		if (!Actor)
		{
			// Actor might not exist yet, keep waiting
			FPlatformProcess::Sleep(PollInterval);
			continue;
		}

		// Get property value
		ActualValue = GetActorProperty(Actor, PropertyName);
		if (!ActualValue.IsValid())
		{
			FPlatformProcess::Sleep(PollInterval);
			continue;
		}

		// Compare values
		bool bMatch = false;
		if (Operator.Equals(TEXT("equals"), ESearchCase::IgnoreCase) || 
			Operator.Equals(TEXT("eq"), ESearchCase::IgnoreCase) || 
			Operator.Equals(TEXT("=="), ESearchCase::IgnoreCase))
		{
			if (ActualValue->Type == EJson::Boolean)
			{
				bool ExpectedBool = ExpectedValue.Equals(TEXT("true"), ESearchCase::IgnoreCase);
				bMatch = ActualValue->AsBool() == ExpectedBool;
			}
			else if (ActualValue->Type == EJson::Number)
			{
				double ExpectedNum = FCString::Atod(*ExpectedValue);
				bMatch = FMath::IsNearlyEqual(ActualValue->AsNumber(), ExpectedNum, 0.001);
			}
			else
			{
				bMatch = ActualValue->AsString().Equals(ExpectedValue, ESearchCase::IgnoreCase);
			}
		}
		else if (Operator.Equals(TEXT("not_equals"), ESearchCase::IgnoreCase) || 
				 Operator.Equals(TEXT("ne"), ESearchCase::IgnoreCase) || 
				 Operator.Equals(TEXT("!="), ESearchCase::IgnoreCase))
		{
			if (ActualValue->Type == EJson::Boolean)
			{
				bool ExpectedBool = ExpectedValue.Equals(TEXT("true"), ESearchCase::IgnoreCase);
				bMatch = ActualValue->AsBool() != ExpectedBool;
			}
			else if (ActualValue->Type == EJson::Number)
			{
				double ExpectedNum = FCString::Atod(*ExpectedValue);
				bMatch = !FMath::IsNearlyEqual(ActualValue->AsNumber(), ExpectedNum, 0.001);
			}
			else
			{
				bMatch = !ActualValue->AsString().Equals(ExpectedValue);
			}
		}
		else if (Operator.Equals(TEXT("less_than"), ESearchCase::IgnoreCase) || 
				 Operator.Equals(TEXT("lt"), ESearchCase::IgnoreCase) || 
				 Operator.Equals(TEXT("<"), ESearchCase::IgnoreCase))
		{
			double ExpectedNum = FCString::Atod(*ExpectedValue);
			bMatch = ActualValue->AsNumber() < ExpectedNum;
		}
		else if (Operator.Equals(TEXT("greater_than"), ESearchCase::IgnoreCase) || 
				 Operator.Equals(TEXT("gt"), ESearchCase::IgnoreCase) || 
				 Operator.Equals(TEXT(">"), ESearchCase::IgnoreCase))
		{
			double ExpectedNum = FCString::Atod(*ExpectedValue);
			bMatch = ActualValue->AsNumber() > ExpectedNum;
		}
		else if (Operator.Equals(TEXT("contains"), ESearchCase::IgnoreCase))
		{
			bMatch = ActualValue->AsString().Contains(ExpectedValue);
		}

		if (bMatch)
		{
			bConditionMet = true;
			break;
		}

		FPlatformProcess::Sleep(PollInterval);
	}

	double WaitTime = FPlatformTime::Seconds() - StartTime;

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), bConditionMet);
	Result->SetBoolField(TEXT("condition_met"), bConditionMet);
	Result->SetNumberField(TEXT("wait_time_seconds"), WaitTime);

	if (ActualValue.IsValid())
	{
		Result->SetField(TEXT("actual_value"), ActualValue);
	}

	if (!bConditionMet)
	{
		Result->SetStringField(TEXT("message"), FString::Printf(TEXT("Timeout after %.1f seconds"), WaitTime));
		UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("PIEWaitFor: timed out after %.1fs"), WaitTime);
	}
	else
	{
		UE_LOG(LogUEClawBridgeAPI, Log, TEXT("PIEWaitFor: condition met in %.1fs"), WaitTime);
	}

	return ClawJsonToString(Result);
}

UWorld* UPIEControlAPI::GetPIEWorld()
{
	for (const FWorldContext& WorldContext : GEngine->GetWorldContexts())
	{
		if (WorldContext.WorldType == EWorldType::PIE && WorldContext.World())
		{
			return WorldContext.World();
		}
	}
	return nullptr;
}

bool UPIEControlAPI::WaitForPIEReady(float TimeoutSeconds)
{
	const double EndTime = FPlatformTime::Seconds() + TimeoutSeconds;

	while (FPlatformTime::Seconds() < EndTime)
	{
		FPlatformProcess::Sleep(0.1f);

		if (GEditor->IsPlaySessionInProgress())
		{
			UWorld* PIEWorld = GetPIEWorld();
			if (PIEWorld && PIEWorld->GetFirstPlayerController())
			{
				return true;
			}
		}
	}
	return false;
}

TSharedPtr<FJsonObject> UPIEControlAPI::GetWorldInfo(UWorld* PIEWorld)
{
	TSharedPtr<FJsonObject> WorldInfo = MakeShareable(new FJsonObject);
	WorldInfo->SetStringField(TEXT("name"), PIEWorld->GetName());
	WorldInfo->SetStringField(TEXT("map_name"), PIEWorld->GetMapName());
	WorldInfo->SetNumberField(TEXT("time_seconds"), PIEWorld->GetTimeSeconds());

	int32 ActorCount = 0;
	for (TActorIterator<AActor> It(PIEWorld); It; ++It) { ActorCount++; }
	WorldInfo->SetNumberField(TEXT("actor_count"), ActorCount);

	return WorldInfo;
}

TArray<TSharedPtr<FJsonValue>> UPIEControlAPI::GetPlayersInfo(UWorld* PIEWorld)
{
	TArray<TSharedPtr<FJsonValue>> PlayersArray;

	int32 PlayerIndex = 0;
	for (FConstPlayerControllerIterator It = PIEWorld->GetPlayerControllerIterator(); It; ++It)
	{
		APlayerController* PC = It->Get();
		if (!PC) continue;

		TSharedPtr<FJsonObject> PlayerInfo = MakeShareable(new FJsonObject);
		PlayerInfo->SetNumberField(TEXT("player_index"), PlayerIndex);
		PlayerInfo->SetStringField(TEXT("controller_name"), PC->GetName());

		if (APawn* Pawn = PC->GetPawn())
		{
			PlayerInfo->SetStringField(TEXT("pawn_name"), Pawn->GetName());
			PlayerInfo->SetStringField(TEXT("pawn_class"), Pawn->GetClass()->GetName());

			FVector Loc = Pawn->GetActorLocation();
			TArray<TSharedPtr<FJsonValue>> LocArray;
			LocArray.Add(MakeShareable(new FJsonValueNumber(Loc.X)));
			LocArray.Add(MakeShareable(new FJsonValueNumber(Loc.Y)));
			LocArray.Add(MakeShareable(new FJsonValueNumber(Loc.Z)));
			PlayerInfo->SetArrayField(TEXT("location"), LocArray);

			PlayerInfo->SetNumberField(TEXT("speed"), Pawn->GetVelocity().Size());
		}

		PlayersArray.Add(MakeShareable(new FJsonValueObject(PlayerInfo)));
		PlayerIndex++;
	}

	return PlayersArray;
}

AActor* UPIEControlAPI::FindActorByName(UWorld* World, const FString& ActorName)
{
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if ((*It)->GetName().Equals(ActorName, ESearchCase::IgnoreCase))
		{
			return *It;
		}
	}
	return nullptr;
}

TSharedPtr<FJsonValue> UPIEControlAPI::GetActorProperty(AActor* Actor, const FString& PropertyName)
{
	if (!Actor) return nullptr;

	FProperty* Property = Actor->GetClass()->FindPropertyByName(FName(*PropertyName));
	if (!Property) return nullptr;

	void* ValuePtr = Property->ContainerPtrToValuePtr<void>(Actor);

	if (FNumericProperty* NumProp = CastField<FNumericProperty>(Property))
	{
		if (NumProp->IsFloatingPoint())
		{
			double Value = 0;
			NumProp->GetValue_InContainer(Actor, &Value);
			return MakeShareable(new FJsonValueNumber(Value));
		}
		else
		{
			int64 Value = 0;
			NumProp->GetValue_InContainer(Actor, &Value);
			return MakeShareable(new FJsonValueNumber(static_cast<double>(Value)));
		}
	}
	else if (FBoolProperty* BoolProp = CastField<FBoolProperty>(Property))
	{
		return MakeShareable(new FJsonValueBoolean(BoolProp->GetPropertyValue(ValuePtr)));
	}
	else if (FStrProperty* StrProp = CastField<FStrProperty>(Property))
	{
		return MakeShareable(new FJsonValueString(StrProp->GetPropertyValue(ValuePtr)));
	}

	// Fallback
	FString ExportedText;
	Property->ExportTextItem_Direct(ExportedText, ValuePtr, nullptr, nullptr, PPF_None);
	return MakeShareable(new FJsonValueString(ExportedText));
}