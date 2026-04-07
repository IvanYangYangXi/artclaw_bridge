// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "InputInjectionAPI.h"
#include "UEClawBridgeAPI.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerInput.h"
#include "InputCoreTypes.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#include "HAL/PlatformProcess.h"
#include "Misc/App.h"

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
}

FString UInputInjectionAPI::TriggerKeyInput(const FString& Key, const FString& Action)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("TriggerKeyInput: key=%s, action=%s"), *Key, *Action);

	if (Key.IsEmpty())
	{
		return ClawMakeError(TEXT("Key is required"));
	}

	UWorld* World = FindGameWorld();
	if (!World)
	{
		return ClawMakeError(TEXT("No game world found. Start a PIE session or run a packaged build."));
	}

	APlayerController* PC = GetPlayerController(World, 0);
	if (!PC)
	{
		return ClawMakeError(TEXT("Player controller not found"));
	}

	FKey InputKey(*Key);
	if (!InputKey.IsValid())
	{
		return ClawMakeError(FString::Printf(TEXT("Invalid key: %s"), *Key));
	}

	// Determine press mode
	bool bPressOnly = Action.Equals(TEXT("press"), ESearchCase::IgnoreCase);
	bool bReleaseOnly = Action.Equals(TEXT("release"), ESearchCase::IgnoreCase);
	bool bClick = Action.Equals(TEXT("click"), ESearchCase::IgnoreCase) || 
				  (!bPressOnly && !bReleaseOnly);

	UPlayerInput* PlayerInput = PC->PlayerInput;
	if (!PlayerInput)
	{
		return ClawMakeError(TEXT("Player input not available"));
	}

	// Execute input events
	if (bClick || bPressOnly)
	{
		PlayerInput->InputKey(FInputKeyParams(InputKey, IE_Pressed, 1.0, false));
	}
	if (bClick || bReleaseOnly)
	{
		PlayerInput->InputKey(FInputKeyParams(InputKey, IE_Released, 0.0, false));
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("key"), Key);
	Result->SetStringField(TEXT("event"), 
		bPressOnly ? TEXT("pressed") : 
		(bReleaseOnly ? TEXT("released") : TEXT("clicked")));

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("TriggerKeyInput: Key %s %s successfully"), 
		*Key, *Result->GetStringField(TEXT("event")));

	return ClawJsonToString(Result);
}

FString UInputInjectionAPI::TriggerMouseInput(float X, float Y, const FString& Button, const FString& Action)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("TriggerMouseInput: pos=(%.1f,%.1f), button=%s, action=%s"), 
		X, Y, *Button, *Action);

	UWorld* World = FindGameWorld();
	if (!World)
	{
		return ClawMakeError(TEXT("No game world found. Start a PIE session or run a packaged build."));
	}

	APlayerController* PC = GetPlayerController(World, 0);
	if (!PC)
	{
		return ClawMakeError(TEXT("Player controller not found"));
	}

	// Determine mouse button key
	FKey MouseKey;
	if (Button.Equals(TEXT("left"), ESearchCase::IgnoreCase))
	{
		MouseKey = EKeys::LeftMouseButton;
	}
	else if (Button.Equals(TEXT("right"), ESearchCase::IgnoreCase))
	{
		MouseKey = EKeys::RightMouseButton;
	}
	else if (Button.Equals(TEXT("middle"), ESearchCase::IgnoreCase))
	{
		MouseKey = EKeys::MiddleMouseButton;
	}
	else
	{
		return ClawMakeError(FString::Printf(TEXT("Invalid mouse button: %s. Use 'left', 'right', or 'middle'"), *Button));
	}

	// Determine press mode
	bool bPressOnly = Action.Equals(TEXT("press"), ESearchCase::IgnoreCase);
	bool bReleaseOnly = Action.Equals(TEXT("release"), ESearchCase::IgnoreCase);
	bool bClick = Action.Equals(TEXT("click"), ESearchCase::IgnoreCase) || 
				  (!bPressOnly && !bReleaseOnly);

	UPlayerInput* PlayerInput = PC->PlayerInput;
	if (!PlayerInput)
	{
		return ClawMakeError(TEXT("Player input not available"));
	}

	// Set mouse position first
	PC->SetMouseLocation(FMath::RoundToInt(X), FMath::RoundToInt(Y));

	// Execute mouse input events
	if (bClick || bPressOnly)
	{
		PlayerInput->InputKey(FInputKeyParams(MouseKey, IE_Pressed, 1.0, false));
	}
	if (bClick || bReleaseOnly)
	{
		PlayerInput->InputKey(FInputKeyParams(MouseKey, IE_Released, 0.0, false));
	}

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("button"), Button);
	Result->SetNumberField(TEXT("x"), X);
	Result->SetNumberField(TEXT("y"), Y);
	Result->SetStringField(TEXT("event"), 
		bPressOnly ? TEXT("pressed") : 
		(bReleaseOnly ? TEXT("released") : TEXT("clicked")));

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("TriggerMouseInput: %s button %s at (%.1f,%.1f) successfully"), 
		*Button, *Result->GetStringField(TEXT("event")), X, Y);

	return ClawJsonToString(Result);
}

FString UInputInjectionAPI::TriggerAxisInput(const FString& AxisName, float Value)
{
	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("TriggerAxisInput: axis=%s, value=%.3f"), *AxisName, Value);

	if (AxisName.IsEmpty())
	{
		return ClawMakeError(TEXT("AxisName is required"));
	}

	UWorld* World = FindGameWorld();
	if (!World)
	{
		return ClawMakeError(TEXT("No game world found. Start a PIE session or run a packaged build."));
	}

	APlayerController* PC = GetPlayerController(World, 0);
	if (!PC)
	{
		return ClawMakeError(TEXT("Player controller not found"));
	}

	FKey AxisKey(*AxisName);
	if (!AxisKey.IsValid())
	{
		// Try common axis mappings
		if (AxisName.Equals(TEXT("MoveForward"), ESearchCase::IgnoreCase))
		{
			AxisKey = EKeys::W; // Approximate
		}
		else if (AxisName.Equals(TEXT("MoveRight"), ESearchCase::IgnoreCase))
		{
			AxisKey = EKeys::D; // Approximate
		}
		else if (AxisName.Equals(TEXT("Turn"), ESearchCase::IgnoreCase))
		{
			AxisKey = EKeys::MouseX;
		}
		else if (AxisName.Equals(TEXT("LookUp"), ESearchCase::IgnoreCase))
		{
			AxisKey = EKeys::MouseY;
		}
		else
		{
			return ClawMakeError(FString::Printf(TEXT("Invalid axis: %s"), *AxisName));
		}
	}

	UPlayerInput* PlayerInput = PC->PlayerInput;
	if (!PlayerInput)
	{
		return ClawMakeError(TEXT("Player input not available"));
	}

	// Send axis input via InputKey with axis delta
	PlayerInput->InputKey(FInputKeyParams(AxisKey, (double)Value, FApp::GetDeltaTime(), 1, false));

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("axis_name"), AxisName);
	Result->SetNumberField(TEXT("value"), Value);

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("TriggerAxisInput: Axis %s set to %.3f successfully"), 
		*AxisName, Value);

	return ClawJsonToString(Result);
}

UWorld* UInputInjectionAPI::FindGameWorld()
{
	// Prefer a standalone Game world, then fall back to PIE
	for (const FWorldContext& WorldContext : GEngine->GetWorldContexts())
	{
		if (WorldContext.WorldType == EWorldType::Game && WorldContext.World())
		{
			return WorldContext.World();
		}
	}
	
	// Fallback to PIE
	for (const FWorldContext& WorldContext : GEngine->GetWorldContexts())
	{
		if (WorldContext.WorldType == EWorldType::PIE && WorldContext.World())
		{
			return WorldContext.World();
		}
	}
	
	return nullptr;
}

APlayerController* UInputInjectionAPI::GetPlayerController(UWorld* World, int32 PlayerIndex)
{
	if (!World)
	{
		return nullptr;
	}

	int32 Idx = 0;
	for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
	{
		if (Idx == PlayerIndex)
		{
			return It->Get();
		}
		Idx++;
	}
	return nullptr;
}