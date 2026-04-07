// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)

#include "ActorOpsAPI.h"
#include "UEClawBridgeAPI.h"
#include "Utils/JsonHelpers.h"
#include "Utils/PropertySerializer.h"
#include "Utils/AssetModifier.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Engine/Blueprint.h"
#include "GameFramework/Actor.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/PointLight.h"
#include "Engine/SpotLight.h"
#include "Engine/DirectionalLight.h"
#include "Camera/CameraActor.h"
#include "Engine/TriggerBox.h"
#include "Engine/TriggerSphere.h"
#include "ScopedTransaction.h"
#include "EngineUtils.h"
#include "Components/ActorComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"

FString UActorOpsAPI::SpawnActor(
	const FString& ClassName,
	float LocX, float LocY, float LocZ,
	float RotPitch, float RotYaw, float RotRoll,
	const FString& PropertiesJson,
	const FString& WorldType)
{
	UWorld* World = FindWorldByType(WorldType);
	if (!World)
	{
		return ClawJson::MakeError(FString::Printf(TEXT("World '%s' not found"), *WorldType));
	}

	FString ClassError;
	UClass* SpawnClass = ResolveActorClass(ClassName, ClassError);
	if (!SpawnClass)
	{
		return ClawJson::MakeError(ClassError);
	}

	FVector Location(LocX, LocY, LocZ);
	FRotator Rotation(RotPitch, RotYaw, RotRoll);

	TSharedPtr<FScopedTransaction> Transaction;
	if (WorldType.Equals(TEXT("editor"), ESearchCase::IgnoreCase))
	{
		Transaction = FAssetModifier::BeginTransaction(
			FString::Printf(TEXT("Spawn %s"), *ClassName));
	}

	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	AActor* SpawnedActor = World->SpawnActor<AActor>(SpawnClass, Location, Rotation, SpawnParams);
	if (!SpawnedActor)
	{
		return ClawJson::MakeError(TEXT("SpawnActor returned null"));
	}

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Spawned actor: %s at %s"), 
		*ClassName, *Location.ToString());

	// Apply properties if provided
	TArray<FString> PropertyErrors;
	if (!PropertiesJson.IsEmpty())
	{
		TSharedPtr<FJsonObject> JsonObject;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PropertiesJson);
		if (FJsonSerializer::Deserialize(Reader, JsonObject) && JsonObject.IsValid())
		{
			ApplyPropertiesFromJson(SpawnedActor, JsonObject, PropertyErrors);
		}
		else
		{
			PropertyErrors.Add(TEXT("Invalid JSON format"));
		}
	}

	// Build result
	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("actor_name"), GetActorLabelSafe(SpawnedActor));
	Result->SetStringField(TEXT("actor_class"), SpawnClass->GetName());
	Result->SetStringField(TEXT("location"), Location.ToString());
	Result->SetStringField(TEXT("rotation"), Rotation.ToString());

	if (PropertyErrors.Num() > 0)
	{
		TArray<TSharedPtr<FJsonValue>> ErrorArray;
		for (const FString& Error : PropertyErrors)
		{
			ErrorArray.Add(MakeShareable(new FJsonValueString(Error)));
		}
		Result->SetArrayField(TEXT("property_errors"), ErrorArray);
	}

	return ClawJson::ToString(Result);
}

FString UActorOpsAPI::AddComponent(
	const FString& ActorName,
	const FString& ComponentClass,
	const FString& PropertiesJson)
{
	UWorld* World = FindWorldByType(TEXT("editor"));
	if (!World)
	{
		return ClawJson::MakeError(TEXT("Editor world not found"));
	}

	AActor* Actor = FindActor(World, ActorName);
	if (!Actor)
	{
		return ClawJson::MakeError(FString::Printf(TEXT("Actor not found: %s"), *ActorName));
	}

	FString ClassError;
	UClass* CompClass = ResolveComponentClass(ComponentClass, ClassError);
	if (!CompClass)
	{
		return ClawJson::MakeError(ClassError);
	}

	TSharedPtr<FScopedTransaction> Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Add %s to %s"), *ComponentClass, *ActorName));

	FAssetModifier::MarkModified(Actor);

	UActorComponent* NewComponent = NewObject<UActorComponent>(Actor, CompClass);
	if (!NewComponent)
	{
		return ClawJson::MakeError(TEXT("Failed to create component"));
	}

	Actor->AddInstanceComponent(NewComponent);
	NewComponent->RegisterComponent();

	// If it's a scene component, try to attach to root
	if (USceneComponent* SceneComp = Cast<USceneComponent>(NewComponent))
	{
		if (USceneComponent* RootComp = Actor->GetRootComponent())
		{
			SceneComp->AttachToComponent(RootComp, FAttachmentTransformRules::KeepWorldTransform);
		}
		else
		{
			Actor->SetRootComponent(SceneComp);
		}
	}

	UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Added component: %s to actor: %s"), 
		*ComponentClass, *ActorName);

	// Apply properties if provided
	TArray<FString> PropertyErrors;
	if (!PropertiesJson.IsEmpty())
	{
		TSharedPtr<FJsonObject> JsonObject;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PropertiesJson);
		if (FJsonSerializer::Deserialize(Reader, JsonObject) && JsonObject.IsValid())
		{
			ApplyPropertiesFromJson(NewComponent, JsonObject, PropertyErrors);
		}
		else
		{
			PropertyErrors.Add(TEXT("Invalid JSON format"));
		}
	}

	auto Result = ClawJson::MakeSuccess();
	Result->SetStringField(TEXT("component_name"), NewComponent->GetName());
	Result->SetStringField(TEXT("component_class"), CompClass->GetName());
	Result->SetStringField(TEXT("actor_name"), GetActorLabelSafe(Actor));

	if (PropertyErrors.Num() > 0)
	{
		TArray<TSharedPtr<FJsonValue>> ErrorArray;
		for (const FString& Error : PropertyErrors)
		{
			ErrorArray.Add(MakeShareable(new FJsonValueString(Error)));
		}
		Result->SetArrayField(TEXT("property_errors"), ErrorArray);
	}

	return ClawJson::ToString(Result);
}

// === Private helpers ===

UWorld* UActorOpsAPI::FindWorldByType(const FString& WorldType)
{
	if (WorldType.Equals(TEXT("editor"), ESearchCase::IgnoreCase))
	{
		return GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	}
	else if (WorldType.Equals(TEXT("pie"), ESearchCase::IgnoreCase))
	{
		for (const FWorldContext& Context : GEngine->GetWorldContexts())
		{
			if (Context.WorldType == EWorldType::PIE)
			{
				return Context.World();
			}
		}
	}
	else if (WorldType.Equals(TEXT("game"), ESearchCase::IgnoreCase))
	{
		for (const FWorldContext& Context : GEngine->GetWorldContexts())
		{
			if (Context.WorldType == EWorldType::Game)
			{
				return Context.World();
			}
		}
	}

	// Default fallback - try editor first, then first available
	if (UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr)
	{
		return EditorWorld;
	}

	for (const FWorldContext& Context : GEngine->GetWorldContexts())
	{
		if (Context.World())
		{
			return Context.World();
		}
	}

	return nullptr;
}

AActor* UActorOpsAPI::FindActor(UWorld* World, const FString& ActorName)
{
	if (!World)
	{
		return nullptr;
	}

	for (TActorIterator<AActor> ActorItr(World); ActorItr; ++ActorItr)
	{
		AActor* Actor = *ActorItr;
		if (!Actor)
		{
			continue;
		}

		// Match by label (display name) first
		FString ActorLabel = GetActorLabelSafe(Actor);
		if (MatchesWildcard(ActorLabel, ActorName))
		{
			return Actor;
		}

		// Then by object name
		if (MatchesWildcard(Actor->GetName(), ActorName))
		{
			return Actor;
		}
	}

	return nullptr;
}

UClass* UActorOpsAPI::ResolveActorClass(const FString& ClassName, FString& OutError)
{
	if (ClassName.IsEmpty())
	{
		OutError = TEXT("Class name is empty");
		return nullptr;
	}

	// Blueprint path
	if (ClassName.StartsWith(TEXT("/")))
	{
		UBlueprint* Blueprint = FAssetModifier::LoadAssetByPath<UBlueprint>(ClassName, OutError);
		if (Blueprint && Blueprint->GeneratedClass)
		{
			if (Blueprint->GeneratedClass->IsChildOf(AActor::StaticClass()))
			{
				return Blueprint->GeneratedClass;
			}
			else
			{
				OutError = FString::Printf(TEXT("Blueprint class is not an Actor: %s"), *ClassName);
				return nullptr;
			}
		}
		return nullptr;
	}

	// Native class shortcuts
	static const TMap<FString, UClass*> NativeClasses = {
		{ TEXT("PointLight"),       APointLight::StaticClass()       },
		{ TEXT("SpotLight"),        ASpotLight::StaticClass()        },
		{ TEXT("DirectionalLight"), ADirectionalLight::StaticClass() },
		{ TEXT("StaticMeshActor"),  AStaticMeshActor::StaticClass()  },
		{ TEXT("CameraActor"),      ACameraActor::StaticClass()      },
		{ TEXT("TriggerBox"),       ATriggerBox::StaticClass()       },
		{ TEXT("TriggerSphere"),    ATriggerSphere::StaticClass()    },
	};

	if (UClass* const* Found = NativeClasses.Find(ClassName))
	{
		return *Found;
	}

	// Try direct class lookup
	UClass* FoundClass = FindFirstObject<UClass>(*ClassName, EFindFirstObjectOptions::ExactClass);
	if (FoundClass && FoundClass->IsChildOf(AActor::StaticClass()))
	{
		return FoundClass;
	}

	// Try with 'A' prefix
	FoundClass = FindFirstObject<UClass>(*(TEXT("A") + ClassName), EFindFirstObjectOptions::ExactClass);
	if (FoundClass && FoundClass->IsChildOf(AActor::StaticClass()))
	{
		return FoundClass;
	}

	OutError = FString::Printf(TEXT("Actor class not found: %s"), *ClassName);
	return nullptr;
}

UClass* UActorOpsAPI::ResolveComponentClass(const FString& ComponentClass, FString& OutError)
{
	if (ComponentClass.IsEmpty())
	{
		OutError = TEXT("Component class name is empty");
		return nullptr;
	}

	// Try direct lookup
	UClass* FoundClass = FindFirstObject<UClass>(*ComponentClass, EFindFirstObjectOptions::ExactClass);
	if (FoundClass && FoundClass->IsChildOf(UActorComponent::StaticClass()))
	{
		return FoundClass;
	}

	// Try with 'U' prefix
	FoundClass = FindFirstObject<UClass>(*(TEXT("U") + ComponentClass), EFindFirstObjectOptions::ExactClass);
	if (FoundClass && FoundClass->IsChildOf(UActorComponent::StaticClass()))
	{
		return FoundClass;
	}

	OutError = FString::Printf(TEXT("Component class not found: %s"), *ComponentClass);
	return nullptr;
}

bool UActorOpsAPI::ApplyPropertiesFromJson(
	UObject* Object, 
	const TSharedPtr<FJsonObject>& Properties, 
	TArray<FString>& OutErrors)
{
	if (!Object || !Properties.IsValid())
	{
		return false;
	}

	bool bAnySuccess = false;
	for (const auto& Pair : Properties->Values)
	{
		FString PropertyPath = Pair.Key;
		const TSharedPtr<FJsonValue>& Value = Pair.Value;

		void* Container = nullptr;
		FString PropertyError;
		FProperty* Property = FAssetModifier::FindPropertyByPath(Object, PropertyPath, Container, PropertyError);
		
		if (Property && Container)
		{
			FString DeserializeError;
			if (FPropertySerializer::DeserializePropertyValue(Property, Container, Value, DeserializeError))
			{
				bAnySuccess = true;
			}
			else
			{
				OutErrors.Add(FString::Printf(TEXT("Property '%s': %s"), *PropertyPath, *DeserializeError));
			}
		}
		else
		{
			OutErrors.Add(FString::Printf(TEXT("Property not found: %s"), *PropertyPath));
		}
	}

	return bAnySuccess;
}

bool UActorOpsAPI::MatchesWildcard(const FString& Text, const FString& Pattern)
{
	return Text.Equals(Pattern, ESearchCase::IgnoreCase);
}

FString UActorOpsAPI::GetActorLabelSafe(AActor* Actor)
{
	if (!Actor)
	{
		return TEXT("");
	}

#if WITH_EDITOR
	return Actor->GetActorLabel();
#else
	return Actor->GetName();
#endif
}
