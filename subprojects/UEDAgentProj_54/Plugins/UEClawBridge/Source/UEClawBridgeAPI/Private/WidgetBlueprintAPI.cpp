// Copyright ArtClaw. All Rights Reserved.
// Based on soft-ue-cli by softdaddy-o (MIT License)
// Ref: docs/UEClawBridge/features/UE全能力API开发清单.md

#include "WidgetBlueprintAPI.h"
#include "UEClawBridgeAPI.h"
#include "Utils/PropertySerializer.h"
#include "Utils/AssetModifier.h"

#include "WidgetBlueprint.h"
#include "Blueprint/WidgetTree.h"
#include "Blueprint/UserWidget.h"
#include "Components/Widget.h"
#include "Components/PanelWidget.h"
#include "Components/PanelSlot.h"
#include "Components/TextBlock.h"
#include "Components/Image.h"
#include "Components/Button.h"
#include "Animation/WidgetAnimation.h"
#include "MovieScene.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"
#include "ScopedTransaction.h"

FString UWidgetBlueprintAPI::ClawJsonObjectToString(const TSharedPtr<FJsonObject>& JsonObject)
{
	FString Output;
	auto Writer = TJsonWriterFactory<>::Create(&Output);
	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
	return Output;
}

FString UWidgetBlueprintAPI::ClawMakeError(const FString& ErrorMessage)
{
	TSharedPtr<FJsonObject> Obj = MakeShareable(new FJsonObject);
	Obj->SetBoolField(TEXT("success"), false);
	Obj->SetStringField(TEXT("error"), ErrorMessage);
	return ClawJsonObjectToString(Obj);
}

// ==================== Public API ====================

FString UWidgetBlueprintAPI::InspectWidgetBlueprint(const FString& AssetPath)
{
	FString LoadError;
	UObject* Asset = FAssetModifier::LoadAssetByPath(AssetPath, LoadError);
	if (!Asset) return ClawMakeError(LoadError);

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Asset);
	if (!WidgetBP) return ClawMakeError(FString::Printf(TEXT("Not a Widget Blueprint: %s"), *AssetPath));

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("asset"), AssetPath);
	Result->SetStringField(TEXT("parent_class"), WidgetBP->ParentClass ? WidgetBP->ParentClass->GetName() : TEXT("None"));

	// Widget hierarchy
	if (WidgetBP->WidgetTree && WidgetBP->WidgetTree->RootWidget)
	{
		Result->SetObjectField(TEXT("root_widget"), BuildWidgetNode(WidgetBP->WidgetTree->RootWidget, 0, 10, false));

		TArray<FString> Names;
		CollectWidgetNames(WidgetBP->WidgetTree->RootWidget, Names);
		Result->SetNumberField(TEXT("widget_count"), Names.Num());
	}
	else
	{
		Result->SetStringField(TEXT("root_widget"), TEXT("null"));
		Result->SetNumberField(TEXT("widget_count"), 0);
	}

	// Bindings & Animations
	Result->SetArrayField(TEXT("bindings"), ExtractBindings(WidgetBP));
	Result->SetArrayField(TEXT("animations"), ExtractAnimations(WidgetBP));

	return ClawJsonObjectToString(Result);
}

FString UWidgetBlueprintAPI::InspectRuntimeWidgets()
{
	if (!GEditor || !GEditor->IsPlaySessionInProgress())
	{
		return ClawMakeError(TEXT("No PIE session running"));
	}

	int32 TotalCount = 0;
	UWorld* PIEWorld = GetPIEWorldByIndex(0, TotalCount);
	if (!PIEWorld) return ClawMakeError(TEXT("PIE world not found"));

	TArray<UUserWidget*> Widgets = CollectPIEWidgets(PIEWorld);

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetNumberField(TEXT("widget_count"), Widgets.Num());

	TArray<TSharedPtr<FJsonValue>> WidgetArray;
	for (UUserWidget* W : Widgets)
	{
		if (!W) continue;
		auto Node = BuildRuntimeWidgetNode(W, 0, 5, true, true);
		if (Node.IsValid())
		{
			WidgetArray.Add(MakeShareable(new FJsonValueObject(Node)));
		}
	}
	Result->SetArrayField(TEXT("widgets"), WidgetArray);

	return ClawJsonObjectToString(Result);
}

FString UWidgetBlueprintAPI::AddWidget(
	const FString& AssetPath,
	const FString& ParentSlotName,
	const FString& WidgetClass,
	const FString& PropertiesJson)
{
	FString LoadError;
	UObject* Asset = FAssetModifier::LoadAssetByPath(AssetPath, LoadError);
	if (!Asset) return ClawMakeError(LoadError);

	UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Asset);
	if (!WidgetBP) return ClawMakeError(TEXT("Not a Widget Blueprint"));
	if (!WidgetBP->WidgetTree) return ClawMakeError(TEXT("Widget tree is null"));

	FString ClassError;
	UClass* WClass = ResolveWidgetClass(WidgetClass, ClassError);
	if (!WClass) return ClawMakeError(ClassError);

	auto Transaction = FAssetModifier::BeginTransaction(
		FString::Printf(TEXT("Add %s widget"), *WidgetClass));

	FAssetModifier::MarkModified(WidgetBP);

	UWidget* NewWidget = WidgetBP->WidgetTree->ConstructWidget<UWidget>(WClass);
	if (!NewWidget) return ClawMakeError(FString::Printf(TEXT("Failed to create widget: %s"), *WidgetClass));

	// Parent resolution
	bool bAdded = false;
	if (ParentSlotName.IsEmpty())
	{
		if (!WidgetBP->WidgetTree->RootWidget)
		{
			WidgetBP->WidgetTree->RootWidget = NewWidget;
			bAdded = true;
		}
		else if (UPanelWidget* RootPanel = Cast<UPanelWidget>(WidgetBP->WidgetTree->RootWidget))
		{
			bAdded = RootPanel->AddChild(NewWidget) != nullptr;
		}
	}
	else
	{
		UWidget* Parent = FindWidgetByName(WidgetBP->WidgetTree->RootWidget, ParentSlotName);
		if (UPanelWidget* Panel = Cast<UPanelWidget>(Parent))
		{
			bAdded = Panel->AddChild(NewWidget) != nullptr;
		}
		else if (Parent)
		{
			return ClawMakeError(FString::Printf(TEXT("Parent '%s' is not a panel widget"), *ParentSlotName));
		}
		else
		{
			return ClawMakeError(FString::Printf(TEXT("Parent widget not found: %s"), *ParentSlotName));
		}
	}

	if (!bAdded)
	{
		return ClawMakeError(TEXT("Failed to add widget to parent"));
	}

	// Apply properties
	if (!PropertiesJson.IsEmpty())
	{
		TSharedPtr<FJsonObject> Props;
		auto Reader = TJsonReaderFactory<>::Create(PropertiesJson);
		if (FJsonSerializer::Deserialize(Reader, Props) && Props.IsValid())
		{
			for (auto& Pair : Props->Values)
			{
				FProperty* Prop = NewWidget->GetClass()->FindPropertyByName(*Pair.Key);
				if (Prop)
				{
					FString SetErr;
					FPropertySerializer::DeserializePropertyValue(Prop, NewWidget, Pair.Value, SetErr);
				}
			}
		}
	}

	FAssetModifier::MarkPackageDirty(WidgetBP);

	TSharedPtr<FJsonObject> Result = MakeShareable(new FJsonObject);
	Result->SetBoolField(TEXT("success"), true);
	Result->SetStringField(TEXT("widget_name"), NewWidget->GetName());
	Result->SetStringField(TEXT("widget_class"), NewWidget->GetClass()->GetName());
	Result->SetBoolField(TEXT("needs_save"), true);
	return ClawJsonObjectToString(Result);
}

// ==================== Private Helpers ====================

TSharedPtr<FJsonObject> UWidgetBlueprintAPI::BuildWidgetNode(
	UWidget* Widget, int32 CurrentDepth, int32 MaxDepth, bool bIncludeDefaults)
{
	if (!Widget || CurrentDepth > MaxDepth) return nullptr;

	TSharedPtr<FJsonObject> Node = MakeShareable(new FJsonObject);
	Node->SetStringField(TEXT("name"), Widget->GetName());
	Node->SetStringField(TEXT("class"), Widget->GetClass()->GetName());
	Node->SetBoolField(TEXT("is_visible"), Widget->IsVisible());

	if (bIncludeDefaults)
	{
		Node->SetObjectField(TEXT("properties"), ExtractWidgetProperties(Widget, bIncludeDefaults));
	}

	if (UPanelWidget* Panel = Cast<UPanelWidget>(Widget))
	{
		TArray<TSharedPtr<FJsonValue>> Children;
		for (int32 i = 0; i < Panel->GetChildrenCount(); i++)
		{
			UWidget* Child = Panel->GetChildAt(i);
			auto ChildNode = BuildWidgetNode(Child, CurrentDepth + 1, MaxDepth, bIncludeDefaults);
			if (ChildNode.IsValid())
			{
				Children.Add(MakeShareable(new FJsonValueObject(ChildNode)));
			}
		}
		Node->SetArrayField(TEXT("children"), Children);
		Node->SetNumberField(TEXT("child_count"), Children.Num());
	}

	return Node;
}

TSharedPtr<FJsonObject> UWidgetBlueprintAPI::ExtractWidgetProperties(UWidget* Widget, bool bIncludeDefaults)
{
	TSharedPtr<FJsonObject> Props = MakeShareable(new FJsonObject);
	if (!Widget) return Props;

	UWidget* CDO = bIncludeDefaults ? nullptr : Cast<UWidget>(Widget->GetClass()->GetDefaultObject());

	for (TFieldIterator<FProperty> It(Widget->GetClass()); It; ++It)
	{
		FProperty* Prop = *It;
		if (Prop->HasAnyPropertyFlags(CPF_Transient | CPF_DuplicateTransient)) continue;
		if (!Prop->HasAnyPropertyFlags(CPF_Edit | CPF_BlueprintVisible)) continue;

		auto Val = FPropertySerializer::SerializePropertyValue(Prop, Widget, Widget, 0, 2);
		if (Val.IsValid()) Props->SetField(Prop->GetName(), Val);
	}
	return Props;
}

TArray<TSharedPtr<FJsonValue>> UWidgetBlueprintAPI::ExtractBindings(UWidgetBlueprint* WidgetBP)
{
	TArray<TSharedPtr<FJsonValue>> Arr;
	if (!WidgetBP) return Arr;

	for (const FDelegateEditorBinding& Binding : WidgetBP->Bindings)
	{
		TSharedPtr<FJsonObject> B = MakeShareable(new FJsonObject);
		B->SetStringField(TEXT("property"), Binding.PropertyName.ToString());
		B->SetStringField(TEXT("function"), Binding.FunctionName.ToString());
		B->SetStringField(TEXT("object"), Binding.ObjectName);
		Arr.Add(MakeShareable(new FJsonValueObject(B)));
	}
	return Arr;
}

TArray<TSharedPtr<FJsonValue>> UWidgetBlueprintAPI::ExtractAnimations(UWidgetBlueprint* WidgetBP)
{
	TArray<TSharedPtr<FJsonValue>> Arr;
	if (!WidgetBP) return Arr;

	for (UWidgetAnimation* Anim : WidgetBP->Animations)
	{
		if (!Anim) continue;
		TSharedPtr<FJsonObject> A = MakeShareable(new FJsonObject);
		A->SetStringField(TEXT("name"), Anim->GetName());
		if (Anim->MovieScene)
		{
			UMovieScene* MS = Anim->MovieScene.Get();
			int32 RangeFrames = MS->GetPlaybackRange().GetUpperBoundValue().Value - MS->GetPlaybackRange().GetLowerBoundValue().Value;
			A->SetNumberField(TEXT("duration"),
				(double)RangeFrames / MS->GetTickResolution().AsDecimal());
		}
		Arr.Add(MakeShareable(new FJsonValueObject(A)));
	}
	return Arr;
}

void UWidgetBlueprintAPI::CollectWidgetNames(UWidget* Widget, TArray<FString>& OutNames)
{
	if (!Widget) return;
	OutNames.Add(Widget->GetName());
	if (UPanelWidget* Panel = Cast<UPanelWidget>(Widget))
	{
		for (int32 i = 0; i < Panel->GetChildrenCount(); i++)
		{
			CollectWidgetNames(Panel->GetChildAt(i), OutNames);
		}
	}
}

UWorld* UWidgetBlueprintAPI::GetPIEWorldByIndex(int32 Index, int32& OutTotalCount)
{
	OutTotalCount = 0;
	for (const FWorldContext& Ctx : GEngine->GetWorldContexts())
	{
		if (Ctx.WorldType == EWorldType::PIE && Ctx.World())
		{
			if (OutTotalCount == Index) return Ctx.World();
			OutTotalCount++;
		}
	}
	return nullptr;
}

TArray<UUserWidget*> UWidgetBlueprintAPI::CollectPIEWidgets(UWorld* PIEWorld)
{
	TArray<UUserWidget*> Result;
	if (!PIEWorld) return Result;

	for (TObjectIterator<UUserWidget> It; It; ++It)
	{
		UUserWidget* W = *It;
		if (W && W->GetWorld() == PIEWorld && W->IsInViewport())
		{
			Result.Add(W);
		}
	}
	return Result;
}

UWidget* UWidgetBlueprintAPI::FindWidgetByName(UWidget* Root, const FString& Name)
{
	if (!Root) return nullptr;
	if (Root->GetName().Equals(Name, ESearchCase::IgnoreCase)) return Root;

	if (UPanelWidget* Panel = Cast<UPanelWidget>(Root))
	{
		for (int32 i = 0; i < Panel->GetChildrenCount(); i++)
		{
			if (UWidget* Found = FindWidgetByName(Panel->GetChildAt(i), Name))
				return Found;
		}
	}
	return nullptr;
}

TSharedPtr<FJsonObject> UWidgetBlueprintAPI::BuildRuntimeWidgetNode(
	UWidget* Widget, int32 CurrentDepth, int32 MaxDepth,
	bool bIncludeGeometry, bool bIncludeProperties)
{
	if (!Widget || CurrentDepth > MaxDepth) return nullptr;

	TSharedPtr<FJsonObject> Node = MakeShareable(new FJsonObject);
	Node->SetStringField(TEXT("name"), Widget->GetName());
	Node->SetStringField(TEXT("class"), Widget->GetClass()->GetName());
	Node->SetBoolField(TEXT("is_visible"), Widget->IsVisible());

	if (bIncludeGeometry) Node->SetObjectField(TEXT("geometry"), ExtractGeometry(Widget));
	if (bIncludeProperties) Node->SetObjectField(TEXT("runtime_props"), ExtractRuntimeProperties(Widget));

	if (UPanelWidget* Panel = Cast<UPanelWidget>(Widget))
	{
		TArray<TSharedPtr<FJsonValue>> Children;
		for (int32 i = 0; i < Panel->GetChildrenCount(); i++)
		{
			auto Child = BuildRuntimeWidgetNode(Panel->GetChildAt(i), CurrentDepth + 1, MaxDepth, bIncludeGeometry, bIncludeProperties);
			if (Child.IsValid()) Children.Add(MakeShareable(new FJsonValueObject(Child)));
		}
		Node->SetArrayField(TEXT("children"), Children);
	}
	return Node;
}

TSharedPtr<FJsonObject> UWidgetBlueprintAPI::ExtractGeometry(UWidget* Widget)
{
	TSharedPtr<FJsonObject> Geo = MakeShareable(new FJsonObject);
	if (!Widget) return Geo;

	auto CachedGeo = Widget->GetCachedGeometry();
	FVector2D AbsPos = CachedGeo.GetAbsolutePosition();
	FVector2D Size = CachedGeo.GetAbsoluteSize();

	Geo->SetNumberField(TEXT("abs_x"), AbsPos.X);
	Geo->SetNumberField(TEXT("abs_y"), AbsPos.Y);
	Geo->SetNumberField(TEXT("width"), Size.X);
	Geo->SetNumberField(TEXT("height"), Size.Y);
	return Geo;
}

TSharedPtr<FJsonObject> UWidgetBlueprintAPI::ExtractRuntimeProperties(UWidget* Widget)
{
	TSharedPtr<FJsonObject> Props = MakeShareable(new FJsonObject);
	if (!Widget) return Props;

	Props->SetBoolField(TEXT("is_visible"), Widget->IsVisible());
	Props->SetNumberField(TEXT("render_opacity"), Widget->GetRenderOpacity());

	if (UTextBlock* Text = Cast<UTextBlock>(Widget))
	{
		Props->SetStringField(TEXT("text"), Text->GetText().ToString());
	}
	return Props;
}

UClass* UWidgetBlueprintAPI::ResolveWidgetClass(const FString& WidgetClassName, FString& OutError)
{
	// Try direct resolve
	UClass* Found = FindFirstObject<UClass>(*WidgetClassName, EFindFirstObjectOptions::NativeFirst);
	if (Found && Found->IsChildOf<UWidget>()) return Found;

	// Try with U prefix
	Found = FindFirstObject<UClass>(*(TEXT("U") + WidgetClassName), EFindFirstObjectOptions::NativeFirst);
	if (Found && Found->IsChildOf<UWidget>()) return Found;

	// Try common UMG widget names
	static const TMap<FString, FString> CommonWidgets = {
		{TEXT("TextBlock"), TEXT("UTextBlock")},
		{TEXT("Image"), TEXT("UImage")},
		{TEXT("Button"), TEXT("UButton")},
		{TEXT("CheckBox"), TEXT("UCheckBox")},
		{TEXT("Slider"), TEXT("USlider")},
		{TEXT("ProgressBar"), TEXT("UProgressBar")},
		{TEXT("CanvasPanel"), TEXT("UCanvasPanel")},
		{TEXT("HorizontalBox"), TEXT("UHorizontalBox")},
		{TEXT("VerticalBox"), TEXT("UVerticalBox")},
		{TEXT("ScrollBox"), TEXT("UScrollBox")},
		{TEXT("GridPanel"), TEXT("UGridPanel")},
		{TEXT("Overlay"), TEXT("UOverlay")},
		{TEXT("Border"), TEXT("UBorder")},
		{TEXT("SizeBox"), TEXT("USizeBox")},
		{TEXT("Spacer"), TEXT("USpacer")},
	};

	if (const FString* Mapped = CommonWidgets.Find(WidgetClassName))
	{
		Found = FindFirstObject<UClass>(**Mapped, EFindFirstObjectOptions::NativeFirst);
		if (Found) return Found;
	}

	OutError = FString::Printf(TEXT("Widget class not found: %s"), *WidgetClassName);
	return nullptr;
}
