// Copyright ArtClaw. All Rights Reserved.

// NOTE: Requires additional modules in UEClawBridgeAPI.Build.cs:
//   "LevelSequence", "MovieScene", "MovieSceneTracks"

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "SequencerAPI.generated.h"

/**
 * Sequencer API for Level Sequence creation, editing, and playback control
 */
UCLASS()
class UECLAWBRIDGEAPI_API USequencerAPI : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Create a new Level Sequence asset */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|Sequencer")
    static FString CreateLevelSequence(const FString& AssetPath);

    /** Get sequence info: tracks, sections, length */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|Sequencer")
    static FString GetSequenceInfo(const FString& AssetPath);

    /** Add a track to sequence (Transform, Skeletal, Audio, Event, etc.) */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|Sequencer")
    static FString AddTrack(
        const FString& SequencePath,
        const FString& TrackType,  // "Transform", "SkeletalAnimation", "Audio", "Event", "Float", "Bool"
        const FString& ActorName = TEXT(""),
        const FString& PropertyPath = TEXT(""));

    /** Add keyframe to a track */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|Sequencer")
    static FString AddKeyframe(
        const FString& SequencePath,
        const FString& TrackIdentifier,  // "ActorName.Transform" or track index
        float Time,
        const FString& ValueJson);

    /** Set sequence playback range */
    UFUNCTION(BlueprintCallable, Category="ArtClaw|Sequencer")
    static FString SetPlaybackRange(
        const FString& SequencePath,
        float StartTime,
        float EndTime);
};