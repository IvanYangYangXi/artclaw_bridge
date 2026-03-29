// Copyright ArtClaw Project. All Rights Reserved. 
// 系统功能模块 - 技能创建、语言切换、确认对话框、静默模式

#include "UEAgentDashboard.h"
#include "UEAgentLocalization.h"
#include "UEAgentManagePanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/SWindow.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonWriter.h"
#include "Misc/MessageDialog.h"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"

// ==================================================================
// 阶段 D: Skill 创建集成 (v2 — 对话式，无弹窗)
// ==================================================================

FReply SUEAgentDashboard::OnCreateSkillClicked()
{
	// 在输入框填充引导文本
	if (InputTextBox.IsValid())
	{
		FString GuideText = TEXT("I want to create a new skill that can help me with UE editor tasks. Please guide me through the process.");
		InputTextBox->SetText(FText::FromString(GuideText));
		FSlateApplication::Get().SetKeyboardFocus(InputTextBox);
	}
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnManageClicked()
{
	// 打开 Skill/MCP 管理独立窗口
	if (ManageWindow.IsValid())
	{
		ManageWindow->BringToFront();
		return FReply::Handled();
	}

	ManageWindow = SNew(SWindow)
		.Title(FUEAgentL10n::Get(TEXT("ManageWindowTitle")))
		.ClientSize(FVector2D(600.0f, 500.0f))
		.SupportsMinimize(false)
		.SupportsMaximize(false)
		[
			SNew(SBorder)
			.BorderImage(FCoreStyle::Get().GetBrush("NoBorder"))
			.Padding(0.0f)
			[
				SAssignNew(ManagePanelWidget, SUEAgentManagePanel)
			]
		];

	FSlateApplication::Get().AddWindow(ManageWindow.ToSharedRef());
	return FReply::Handled();
}

// ==================================================================
// 语言切换
// ==================================================================

FReply SUEAgentDashboard::OnToggleLanguageClicked()
{
	// 切换语言
	if (FUEAgentL10n::GetLanguage() == EUEAgentLanguage::Chinese)
	{
		FUEAgentL10n::SetLanguage(EUEAgentLanguage::English);
	}
	else
	{
		FUEAgentL10n::SetLanguage(EUEAgentLanguage::Chinese);
	}

	// 重建整个 UI
	RebuildAfterLanguageChange();

	return FReply::Handled();
}

void SUEAgentDashboard::RebuildAfterLanguageChange()
{
	// 重建整个 UI（刷新所有文本）
	// 由于 Construct 方法包含大量 Slate 声明，这里简化处理
	// 实际项目中可能需要将 UI 构建逻辑提取为单独方法
	Messages.Empty();
	RebuildMessageList();
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("LanguageChanged")));
}

// ==================================================================
// 文件操作确认弹窗 (阶段 5.6)
// ==================================================================

void SUEAgentDashboard::PollConfirmationRequests()
{
	FString ConfirmFile = FPaths::ProjectSavedDir() / TEXT("UEAgent/_confirm_request.json");
	if (!FPaths::FileExists(ConfirmFile))
	{
		return;
	}

	FString JsonContent;
	TArray<uint8> RawBytes;
	if (!FFileHelper::LoadFileToArray(RawBytes, *ConfirmFile))
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

	FString RiskLevel = JsonObj->GetStringField(TEXT("riskLevel"));
	FString CodePreview = JsonObj->GetStringField(TEXT("codePreview"));

	const TArray<TSharedPtr<FJsonValue>>* OperationsArray = nullptr;
	JsonObj->TryGetArrayField(TEXT("operations"), OperationsArray);

	TArray<TSharedPtr<FJsonValue>> Operations;
	if (OperationsArray)
	{
		Operations = *OperationsArray;
	}

	// 显示确认对话框
	ShowConfirmationDialog(RiskLevel, Operations, CodePreview);

	// 删除请求文件
	IFileManager::Get().Delete(*ConfirmFile, false, false, true);
}

void SUEAgentDashboard::ShowConfirmationDialog(const FString& RiskLevel,
	const TArray<TSharedPtr<FJsonValue>>& Operations,
	const FString& CodePreview)
{
	FString Title = FUEAgentL10n::GetStr(TEXT("ConfirmTitle"));
	FString Message = FUEAgentL10n::GetStr(TEXT("ConfirmMessage"));
	Message += TEXT("\n\nRisk Level: ") + RiskLevel;

	if (!CodePreview.IsEmpty())
	{
		Message += TEXT("\n\nCode Preview:\n") + CodePreview.Left(500);
	}

	// 显示确认对话框
	EAppReturnType::Type Result = FMessageDialog::Open(EAppMsgType::YesNo, FText::FromString(Message), FText::FromString(Title));

	// 写入响应文件
	FString ResponseFile = FPaths::ProjectSavedDir() / TEXT("UEAgent/_confirm_response.json");
	FString Response = (Result == EAppReturnType::Yes) ? TEXT("yes") : TEXT("no");
	FFileHelper::SaveStringToFile(Response, *ResponseFile);
}

// ==================================================================
// 静默模式 (阶段 5.7)
// ==================================================================

void SUEAgentDashboard::LoadSilentModeFromConfig()
{
	// 读取 ~/.artclaw/config.json 中的静默模式配置
	FString ConfigPath = FPaths::ProjectSavedDir() / TEXT("UEAgent/config.json");
	if (!FPaths::FileExists(ConfigPath))
	{
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

	JsonObj->TryGetBoolField(TEXT("silentMedium"), bSilentMedium);
	JsonObj->TryGetBoolField(TEXT("silentHigh"), bSilentHigh);
}

void SUEAgentDashboard::SaveSilentModeToConfig()
{
	// 更新 ~/.artclaw/config.json 中的静默模式配置
	FString ConfigPath = FPaths::ProjectSavedDir() / TEXT("UEAgent/config.json");
	FString TempDir = FPaths::GetPath(ConfigPath);
	IFileManager::Get().MakeDirectory(*TempDir, true);

	TSharedPtr<FJsonObject> JsonObj = MakeShared<FJsonObject>();
	JsonObj->SetBoolField(TEXT("silentMedium"), bSilentMedium);
	JsonObj->SetBoolField(TEXT("silentHigh"), bSilentHigh);

	FString JsonStr;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonStr);
	FJsonSerializer::Serialize(JsonObj.ToSharedRef(), Writer);

	FFileHelper::SaveStringToFile(JsonStr, *ConfigPath);
}

FReply SUEAgentDashboard::OnToggleSilentMediumClicked()
{
	bSilentMedium = !bSilentMedium;
	SaveSilentModeToConfig();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnToggleSilentHighClicked()
{
	bSilentHigh = !bSilentHigh;
	SaveSilentModeToConfig();
	return FReply::Handled();
}