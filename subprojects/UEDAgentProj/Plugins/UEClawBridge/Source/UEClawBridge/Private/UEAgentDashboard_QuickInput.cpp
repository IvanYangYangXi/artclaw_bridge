// Copyright ArtClaw Project. All Rights Reserved.
// 快捷输入面板模块 - 快捷短语管理、增删改查

#include "UEAgentDashboard.h"
#include "UEAgentLocalization.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"

// ==================================================================
// 快捷输入 (Quick Inputs)
// ==================================================================

void SUEAgentDashboard::LoadQuickInputs()
{
	FString ConfigPath = GetQuickInputConfigPath();
	if (!FPaths::FileExists(ConfigPath))
	{
		// 默认快捷输入
		QuickInputs.Empty();
		return;
	}

	FString JsonContent;
	TArray<uint8> RawBytes;
	if (!FFileHelper::LoadFileToArray(RawBytes, *ConfigPath))
	{
		return;
	}

	FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
	JsonContent = FString(Converter.Length(), Converter.Get());

	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
	{
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* InputsArray = nullptr;
	if (!JsonObj->TryGetArrayField(TEXT("quickInputs"), InputsArray) || !InputsArray)
	{
		return;
	}

	QuickInputs.Empty();
	for (const auto& InputVal : *InputsArray)
	{
		const TSharedPtr<FJsonObject>* InputObj = nullptr;
		if (!InputVal->TryGetObject(InputObj) || !InputObj)
		{
			continue;
		}

		FQuickInput Input;
		Input.Id = (*InputObj)->GetStringField(TEXT("id"));
		Input.Name = (*InputObj)->GetStringField(TEXT("name"));
		Input.Content = (*InputObj)->GetStringField(TEXT("content"));
		QuickInputs.Add(MoveTemp(Input));
	}
}

void SUEAgentDashboard::SaveQuickInputs()
{
	FString ConfigPath = GetQuickInputConfigPath();
	FString TempDir = FPaths::GetPath(ConfigPath);
	IFileManager::Get().MakeDirectory(*TempDir, true);

	TSharedPtr<FJsonObject> RootObj = MakeShared<FJsonObject>();
	TArray<TSharedPtr<FJsonValue>> InputsArray;

	for (const auto& Input : QuickInputs)
	{
		TSharedPtr<FJsonObject> InputObj = MakeShared<FJsonObject>();
		InputObj->SetStringField(TEXT("id"), Input.Id);
		InputObj->SetStringField(TEXT("name"), Input.Name);
		InputObj->SetStringField(TEXT("content"), Input.Content);
		InputsArray.Add(MakeShared<FJsonValue>(InputObj));
	}

	RootObj->SetArrayField(TEXT("quickInputs"), InputsArray);

	FString JsonStr;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonStr);
	FJsonSerializer::Serialize(RootObj.ToSharedRef(), Writer);

	FFileHelper::SaveStringToFile(JsonStr, *ConfigPath);
}

FString SUEAgentDashboard::GetQuickInputConfigPath() const
{
	return FPaths::ProjectSavedDir() / TEXT("UEAgent") / TEXT("quick_inputs.json");
}

void SUEAgentDashboard::RebuildQuickInputPanel()
{
	if (!QuickInputWrapBox.IsValid())
	{
		return;
	}

	QuickInputWrapBox->ClearChildren();

	for (int32 i = 0; i < QuickInputs.Num(); ++i)
	{
		const FQuickInput& Input = QuickInputs[i];
		const int32 CapturedIndex = i;

		QuickInputWrapBox->AddSlot()
		.Padding(4.0f)
		[
			SNew(SButton)
			.Text(FText::FromString(Input.Name))
			.OnClicked_Lambda([this, CapturedIndex]() -> FReply { return OnQuickInputClicked(CapturedIndex); })
			.ToolTipText(FText::FromString(Input.Content))
			.ContentPadding(FMargin(8.0f, 4.0f))
		];
	}
}

FReply SUEAgentDashboard::OnQuickInputClicked(int32 Index)
{
	if (!QuickInputs.IsValidIndex(Index) || !InputTextBox.IsValid())
	{
		return FReply::Handled();
	}

	FString Content = QuickInputs[Index].Content;
	InputTextBox->SetText(FText::FromString(Content));
	InputTextBox->SetFocus();

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnAddQuickInputClicked()
{
	FGuid NewId = FGuid::NewGuid();
	FQuickInput NewInput;
	NewInput.Id = NewId.ToString();
	NewInput.Name = TEXT("New");
	NewInput.Content = TEXT("");
	QuickInputs.Add(MoveTemp(NewInput));

	SaveQuickInputs();
	RebuildQuickInputPanel();

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnDeleteQuickInputClicked(int32 Index)
{
	if (!QuickInputs.IsValidIndex(Index))
	{
		return FReply::Handled();
	}

	QuickInputs.RemoveAt(Index);
	SaveQuickInputs();
	RebuildQuickInputPanel();

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnEditQuickInputClicked(int32 Index)
{
	// 编辑功能实现
	return FReply::Handled();
}

void SUEAgentDashboard::OnQuickInputNameCommitted(const FText& NewText, ETextCommit::Type CommitType, int32 Index)
{
	if (!QuickInputs.IsValidIndex(Index))
	{
		return;
	}

	QuickInputs[Index].Name = NewText.ToString();
	SaveQuickInputs();
	RebuildQuickInputPanel();
}

void SUEAgentDashboard::OnQuickInputContentCommitted(const FText& NewText, ETextCommit::Type CommitType, int32 Index)
{
	if (!QuickInputs.IsValidIndex(Index))
	{
		return;
	}

	QuickInputs[Index].Content = NewText.ToString();
	SaveQuickInputs();
}