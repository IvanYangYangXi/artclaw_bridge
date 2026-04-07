// Copyright ArtClaw. All Rights Reserved.
// Test file to verify PIE Control and Input Injection APIs

#pragma once

#include "CoreMinimal.h"
#include "PIEControlAPI.h"
#include "InputInjectionAPI.h"

/**
 * Simple test cases for the new APIs
 */
class FPIEAPITests
{
public:
    /**
     * Test basic PIE lifecycle: start -> get state -> stop
     */
    static void TestPIELifecycle()
    {
        // Start PIE in viewport mode
        FString StartResult = UPIEControlAPI::PIEStart(TEXT("viewport"), TEXT(""), 30.0f);
        UE_LOG(LogUEClawBridgeAPI, Log, TEXT("PIE Start Result: %s"), *StartResult);

        // Wait a moment
        FPlatformProcess::Sleep(2.0f);

        // Get PIE state
        FString StateResult = UPIEControlAPI::PIEGetState(TEXT("all"));
        UE_LOG(LogUEClawBridgeAPI, Log, TEXT("PIE State: %s"), *StateResult);

        // Stop PIE
        FString StopResult = UPIEControlAPI::PIEStop();
        UE_LOG(LogUEClawBridgeAPI, Log, TEXT("PIE Stop Result: %s"), *StopResult);
    }

    /**
     * Test input injection with common keys
     */
    static void TestInputInjection()
    {
        // Test key input - simulate WASD movement
        FString WResult = UInputInjectionAPI::TriggerKeyInput(TEXT("W"), TEXT("click"));
        UE_LOG(LogUEClawBridgeAPI, Log, TEXT("W Key Input: %s"), *WResult);

        // Test mouse input - left click at center screen
        FString MouseResult = UInputInjectionAPI::TriggerMouseInput(960.0f, 540.0f, TEXT("left"), TEXT("click"));
        UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Mouse Input: %s"), *MouseResult);

        // Test axis input - move forward
        FString AxisResult = UInputInjectionAPI::TriggerAxisInput(TEXT("MoveForward"), 1.0f);
        UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Axis Input: %s"), *AxisResult);
    }
};