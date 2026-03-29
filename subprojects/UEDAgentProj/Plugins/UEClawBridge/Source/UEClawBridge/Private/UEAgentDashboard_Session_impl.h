// Copyright ArtClaw Project. All Rights Reserved.
// 会话管理模块 - 多会话切换、 历史记录加载

#include "UEAgentDashboard.h"
#include "UEAgentSubsystem.h"
#include "UEAgentLocalization.h"
#include "IAgentPlatformBridge.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SMenuAnchor.h"
#include "Widgets/Text/STextBlock.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"

#define LOCTEXT_NAMESPACE "UEAgentDashboard"

// ==================================================================
// 多会话管理 (任务 5.8)
// ==================================================================

void SUEAgentDashboard::InitFirstSession()
{
	FDateTime Now = FDateTime::Now();
	CurrentSessionLabel = FString::Printf(TEXT("%s %02d-%02d %02d:%02d"),
		*FUEAgentL10n::GetStr(TEXT("SessionLabel")),
		Now.GetMonth(), Now.GetDay(), Now.GetHour(), Now.GetMinute());

	FSessionEntry FirstEntry;
	FirstEntry.Label = CurrentSessionLabel;
	FirstEntry.CreatedAt = Now;
	FirstEntry.bIsActive = true;

	SessionEntries.Add(MoveTemp(FirstEntry));
	ActiveSessionIndex = 0;
}

FReply SUEAgentDashboard::OnSessionMenuClicked()
{
	if (SessionMenuAnchor.IsValid())
	{
		SessionMenuAnchor->SetIsOpen(!SessionMenuAnchor->IsOpen());
	}
	return FReply::Handled();
}

TSharedRef<SWidget> SUEAgentDashboard::BuildSessionMenuContent()
{
	TSharedRef<SVerticalBox> MenuContent = SNew(SVerticalBox);

	// 会话列表（不含新建按钮，新建通过工具栏的 "+ 新会话" 按钮）
	for (int32 i = 0; i < SessionEntries.Num(); ++i)
	{
		const FSessionEntry& Entry = SessionEntries[i];
		const int32 CapturedIndex = i;

		MenuContent->AddSlot()
		.AutoHeight()
		.Padding(4.0f, 2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			[
				SNew(SButton)
				.Text(FText::FromString(Entry.Label))
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply { OnSessionSelected(CapturedIndex); return FReply::Handled(); })
				.ContentPadding(FMargin(8.0f, 4.0f))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(FUEAgentL10n::Get(TEXT("DeleteSession")))
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply { OnDeleteSession(CapturedIndex); return FReply::Handled(); })
				.ContentPadding(FMargin(4.0f, 4.0f))
				.ButtonColorAndOpacity(FLinearColor(0.8f, 0.3f, 0.3f))
			]
		];
	}

	return MenuContent;
}

void SUEAgentDashboard::OnSessionSelected(int32 Index)
{
	if (!SessionEntries.IsValidIndex(Index) || Index == ActiveSessionIndex)
	{
		return;
	}

	// 保存当前会话
	if (ActiveSessionIndex >= 0 && SessionEntries.IsValidIndex(ActiveSessionIndex))
	{
		FString CurrentKey = PlatformBridge->GetSessionKey();
		if (!CurrentKey.IsEmpty())
		{
			SessionEntries[ActiveSessionIndex].SessionKey = CurrentKey;
		}
		SessionEntries[ActiveSessionIndex].bIsActive = false;
	}

	// 切换到新会话
	ActiveSessionIndex = Index;
	SessionEntries[Index].bIsActive = true;
	CurrentSessionLabel = SessionEntries[Index].Label;

	// 加载会话历史
	FString SessionKey = SessionEntries[Index].SessionKey;
	if (!SessionKey.IsEmpty())
	{
		LoadSessionHistory(SessionKey);
	}
	else
	{
		// 新会话，清空消息
		Messages.Empty();
		RebuildMessageList();
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("NewChatStarted")));
	}

	// 关闭菜单
	if (SessionMenuAnchor.IsValid())
	{
		SessionMenuAnchor->SetIsOpen(false);
	}
}

void SUEAgentDashboard::OnDeleteSession(int32 Index)
{
	if (!SessionEntries.IsValidIndex(Index))
	{
		return;
	}

	// 如果删除的是当前活跃会话，切换到其他会话
	if (Index == ActiveSessionIndex)
	{
		if (SessionEntries.Num() > 1)
		{
			int32 NewIndex = (Index == 0) ? 1 : 0;
			OnSessionSelected(NewIndex);
		}
		else
		{
			// 只有一个会话，清空但不删除
			Messages.Empty();
			RebuildMessageList();
			InitFirstSession();
		}
	}

	SessionEntries.RemoveAt(Index);
}

void SUEAgentDashboard::LoadSessionHistory(const FString& SessionKey)
{
	// 从 Gateway transcript 加载会话历史
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	FString HistoryFile = TempDir / FString::Printf(TEXT("_session_%s.json"), *SessionKey);

	if (!FPaths::FileExists(HistoryFile))
	{
		return;
	}

	FString JsonContent;
	TArray<uint8> RawBytes;
	if (!FFileHelper::LoadFileToArray(RawBytes, *HistoryFile))
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

	// 解析消息历史
	const TArray<TSharedPtr<FJsonValue>>* MessagesArray = nullptr;
	if (!JsonObj->TryGetArrayField(TEXT("messages"), MessagesArray) || !MessagesArray)
	{
		return;
	}

	Messages.Empty();
	for (const auto& MsgVal : *MessagesArray)
	{
		const TSharedPtr<FJsonObject>* MsgObj = nullptr;
		if (!MsgVal->TryGetObject(MsgObj) || !MsgObj)
		{
			continue;
		}

		FChatMessage Msg;
		Msg.Sender = (*MsgObj)->GetStringField(TEXT("sender"));
		Msg.Content = (*MsgObj)->GetStringField(TEXT("content"));
		Msg.bIsCode = (*MsgObj)->GetBoolField(TEXT("isCode"));
		Messages.Add(MoveTemp(Msg));
	}

	RebuildMessageList();
}

FText SUEAgentDashboard::GetActiveSessionLabel() const
{
	return FText::FromString(CurrentSessionLabel);
}