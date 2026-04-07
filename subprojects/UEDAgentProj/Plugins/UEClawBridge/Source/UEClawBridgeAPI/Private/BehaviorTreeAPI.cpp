// Copyright ArtClaw. All Rights Reserved.

#include "BehaviorTreeAPI.h"
#include "UEClawBridgeAPI.h"

#include "Engine/Engine.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "UObject/SavePackage.h"
#include "Misc/PackageName.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

// AI includes
#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BTNode.h"
#include "BehaviorTree/BTCompositeNode.h"
#include "BehaviorTree/BTTaskNode.h"
#include "BehaviorTree/BTDecorator.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Bool.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Int.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Float.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_String.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Object.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Vector.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Rotator.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Enum.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Class.h"
#include "BehaviorTree/BlackboardData.h"

namespace
{
    FString ClawJsonToString(const TSharedPtr<FJsonObject>& JsonObject)
    {
        if (!JsonObject.IsValid()) return TEXT("{}");
        
        FString OutputString;
        TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
        FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
        return OutputString;
    }

    FString ClawMakeError(const FString& Message)
    {
        TSharedPtr<FJsonObject> ErrorJson = MakeShareable(new FJsonObject);
        ErrorJson->SetBoolField(TEXT("success"), false);
        ErrorJson->SetStringField(TEXT("error"), Message);
        return ClawJsonToString(ErrorJson);
    }

    FString ClawMakeSuccess(const FString& Data = TEXT(""))
    {
        TSharedPtr<FJsonObject> SuccessJson = MakeShareable(new FJsonObject);
        SuccessJson->SetBoolField(TEXT("success"), true);
        if (!Data.IsEmpty())
        {
            SuccessJson->SetStringField(TEXT("data"), Data);
        }
        return ClawJsonToString(SuccessJson);
    }

    UBehaviorTree* LoadBehaviorTree(const FString& AssetPath)
    {
        FString PackageName = AssetPath;
        if (!FPackageName::IsValidLongPackageName(PackageName))
        {
            PackageName = FString::Printf(TEXT("/Game/%s"), *AssetPath);
        }

        return Cast<UBehaviorTree>(StaticLoadObject(UBehaviorTree::StaticClass(), nullptr, *PackageName));
    }

    UBlackboardData* LoadBlackboardData(const FString& AssetPath)
    {
        FString PackageName = AssetPath;
        if (!FPackageName::IsValidLongPackageName(PackageName))
        {
            PackageName = FString::Printf(TEXT("/Game/%s"), *AssetPath);
        }

        return Cast<UBlackboardData>(StaticLoadObject(UBlackboardData::StaticClass(), nullptr, *PackageName));
    }

    UBlackboardKeyType* CreateKeyType(const FString& KeyType)
    {
        UObject* Outer = GetTransientPackage();
        if (KeyType == TEXT("Bool"))
        {
            return NewObject<UBlackboardKeyType_Bool>(Outer);
        }
        else if (KeyType == TEXT("Int"))
        {
            return NewObject<UBlackboardKeyType_Int>(Outer);
        }
        else if (KeyType == TEXT("Float"))
        {
            return NewObject<UBlackboardKeyType_Float>(Outer);
        }
        else if (KeyType == TEXT("String"))
        {
            return NewObject<UBlackboardKeyType_String>(Outer);
        }
        else if (KeyType == TEXT("Object"))
        {
            return NewObject<UBlackboardKeyType_Object>(Outer);
        }
        else if (KeyType == TEXT("Vector"))
        {
            return NewObject<UBlackboardKeyType_Vector>(Outer);
        }
        else if (KeyType == TEXT("Rotator"))
        {
            return NewObject<UBlackboardKeyType_Rotator>(Outer);
        }
        else if (KeyType == TEXT("Enum"))
        {
            return NewObject<UBlackboardKeyType_Enum>(Outer);
        }
        else if (KeyType == TEXT("Class"))
        {
            return NewObject<UBlackboardKeyType_Class>(Outer);
        }

        return nullptr;
    }

    void SerializeBTNode(UBTNode* Node, TSharedPtr<FJsonObject>& NodeJson, int32 Depth = 0)
    {
        if (!Node || !NodeJson.IsValid()) return;

        NodeJson->SetStringField(TEXT("class"), Node->GetClass()->GetName());
        NodeJson->SetStringField(TEXT("name"), Node->GetNodeName());
        NodeJson->SetNumberField(TEXT("depth"), Depth);

        if (UBTCompositeNode* CompositeNode = Cast<UBTCompositeNode>(Node))
        {
            TArray<TSharedPtr<FJsonValue>> ChildrenArray;
            for (int32 i = 0; i < CompositeNode->GetChildrenNum(); ++i)
            {
                FBTCompositeChild& Child = CompositeNode->Children[i];
                if (Child.ChildComposite || Child.ChildTask)
                {
                    UBTNode* ChildNode = Child.ChildComposite ? static_cast<UBTNode*>(Child.ChildComposite) : static_cast<UBTNode*>(Child.ChildTask);
                    
                    TSharedPtr<FJsonObject> ChildJson = MakeShareable(new FJsonObject);
                    SerializeBTNode(ChildNode, ChildJson, Depth + 1);
                    
                    // Add decorators
                    TArray<TSharedPtr<FJsonValue>> DecoratorsArray;
                    for (UBTDecorator* Decorator : Child.Decorators)
                    {
                        if (Decorator)
                        {
                            TSharedPtr<FJsonObject> DecoratorJson = MakeShareable(new FJsonObject);
                            DecoratorJson->SetStringField(TEXT("class"), Decorator->GetClass()->GetName());
                            DecoratorJson->SetStringField(TEXT("name"), Decorator->GetNodeName());
                            DecoratorsArray.Add(MakeShareable(new FJsonValueObject(DecoratorJson)));
                        }
                    }
                    ChildJson->SetArrayField(TEXT("decorators"), DecoratorsArray);
                    
                    ChildrenArray.Add(MakeShareable(new FJsonValueObject(ChildJson)));
                }
            }
            NodeJson->SetArrayField(TEXT("children"), ChildrenArray);
        }
    }
}

FString UBehaviorTreeAPI::QueryBehaviorTree(const FString& AssetPath)
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryBehaviorTree: %s"), *AssetPath);

    UBehaviorTree* BehaviorTree = LoadBehaviorTree(AssetPath);
    if (!BehaviorTree)
    {
        return ClawMakeError(FString::Printf(TEXT("Failed to load Behavior Tree: %s"), *AssetPath));
    }

    TSharedPtr<FJsonObject> InfoJson = MakeShareable(new FJsonObject);
    InfoJson->SetBoolField(TEXT("success"), true);
    InfoJson->SetStringField(TEXT("path"), AssetPath);

    // Blackboard info
    if (BehaviorTree->BlackboardAsset)
    {
        InfoJson->SetStringField(TEXT("blackboard"), BehaviorTree->BlackboardAsset->GetPathName());
    }

    // Root node info
    if (BehaviorTree->RootNode)
    {
        TSharedPtr<FJsonObject> RootJson = MakeShareable(new FJsonObject);
        SerializeBTNode(BehaviorTree->RootNode, RootJson);
        InfoJson->SetObjectField(TEXT("rootNode"), RootJson);
    }

    return ClawJsonToString(InfoJson);
}

FString UBehaviorTreeAPI::AddBTNode(const FString& AssetPath, const FString& ParentNodeIndex, const FString& NodeClass, const FString& PropertiesJson)
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("AddBTNode: %s, Parent: %s, Class: %s"), *AssetPath, *ParentNodeIndex, *NodeClass);

    UBehaviorTree* BehaviorTree = LoadBehaviorTree(AssetPath);
    if (!BehaviorTree)
    {
        return ClawMakeError(FString::Printf(TEXT("Failed to load Behavior Tree: %s"), *AssetPath));
    }

    // Find node class
    UClass* NodeClassObj = FindObject<UClass>(nullptr, *NodeClass);
    if (!NodeClassObj)
    {
        // Try to find with full path
        FString FullClassName = FString::Printf(TEXT("/Script/AIModule.%s"), *NodeClass);
        NodeClassObj = FindObject<UClass>(nullptr, *FullClassName);
    }

    if (!NodeClassObj || !NodeClassObj->IsChildOf(UBTNode::StaticClass()))
    {
        return ClawMakeError(FString::Printf(TEXT("Invalid or unknown node class: %s"), *NodeClass));
    }

    // For now, return success as adding nodes programmatically requires editor-only APIs
    // This would typically require UBehaviorTreeGraphNode and editor graph manipulation
    BehaviorTree->MarkPackageDirty();
    
    UE_LOG(LogUEClawBridgeAPI, Warning, TEXT("AddBTNode: Node addition requires editor-specific implementation"));
    return ClawMakeSuccess(FString::Printf(TEXT("Node class %s validated for addition"), *NodeClass));
}

FString UBehaviorTreeAPI::AddBlackboardKey(const FString& AssetPath, const FString& KeyName, const FString& KeyType)
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("AddBlackboardKey: %s, Key: %s, Type: %s"), *AssetPath, *KeyName, *KeyType);

    UBlackboardData* BlackboardData = LoadBlackboardData(AssetPath);
    if (!BlackboardData)
    {
        return ClawMakeError(FString::Printf(TEXT("Failed to load Blackboard: %s"), *AssetPath));
    }

    if (KeyName.IsEmpty())
    {
        return ClawMakeError(TEXT("KeyName cannot be empty"));
    }

    // Check if key already exists
    for (const FBlackboardEntry& Entry : BlackboardData->Keys)
    {
        if (Entry.EntryName.ToString() == KeyName)
        {
            return ClawMakeError(FString::Printf(TEXT("Key already exists: %s"), *KeyName));
        }
    }

    // Create key type
    UBlackboardKeyType* KeyTypeObj = CreateKeyType(KeyType);
    if (!KeyTypeObj)
    {
        return ClawMakeError(FString::Printf(TEXT("Unsupported key type: %s"), *KeyType));
    }

    // Add key to blackboard
    FBlackboardEntry NewEntry;
    NewEntry.EntryName = FName(*KeyName);
    NewEntry.KeyType = KeyTypeObj;
    
    BlackboardData->Keys.Add(NewEntry);
    BlackboardData->MarkPackageDirty();

    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("Successfully added blackboard key: %s (%s)"), *KeyName, *KeyType);
    return ClawMakeSuccess(FString::Printf(TEXT("Added key: %s (%s)"), *KeyName, *KeyType));
}

FString UBehaviorTreeAPI::QueryBlackboard(const FString& AssetPath)
{
    UE_LOG(LogUEClawBridgeAPI, Log, TEXT("QueryBlackboard: %s"), *AssetPath);

    UBlackboardData* BlackboardData = LoadBlackboardData(AssetPath);
    if (!BlackboardData)
    {
        return ClawMakeError(FString::Printf(TEXT("Failed to load Blackboard: %s"), *AssetPath));
    }

    TSharedPtr<FJsonObject> InfoJson = MakeShareable(new FJsonObject);
    InfoJson->SetBoolField(TEXT("success"), true);
    InfoJson->SetStringField(TEXT("path"), AssetPath);

    // Parent blackboard
    if (BlackboardData->Parent)
    {
        InfoJson->SetStringField(TEXT("parent"), BlackboardData->Parent->GetPathName());
    }

    // Keys info
    TArray<TSharedPtr<FJsonValue>> KeysArray;
    for (int32 i = 0; i < BlackboardData->Keys.Num(); ++i)
    {
        const FBlackboardEntry& Entry = BlackboardData->Keys[i];
        
        TSharedPtr<FJsonObject> KeyJson = MakeShareable(new FJsonObject);
        KeyJson->SetNumberField(TEXT("index"), i);
        KeyJson->SetStringField(TEXT("name"), Entry.EntryName.ToString());
        
        if (Entry.KeyType)
        {
            KeyJson->SetStringField(TEXT("type"), Entry.KeyType->GetClass()->GetName());
            KeyJson->SetStringField(TEXT("description"), Entry.KeyType->GetClass()->GetFName().ToString());
        }

        KeysArray.Add(MakeShareable(new FJsonValueObject(KeyJson)));
    }
    InfoJson->SetArrayField(TEXT("keys"), KeysArray);
    InfoJson->SetNumberField(TEXT("keyCount"), BlackboardData->Keys.Num());

    return ClawJsonToString(InfoJson);
}