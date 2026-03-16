// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentChatPanel.h"
#include "UEAgentSubsystem.h"
#include "Editor.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"

#define LOCTEXT_NAMESPACE "UEAgentChatPanel"

void SUEAgentChatPanel::Construct(const FArguments& InArgs)
{
	// 获取 Subsystem
	if (GEditor)
	{
		CachedSubsystem = GEditor->GetEditorSubsystem<UUEAgentSubsystem>();
	}

	if (CachedSubsystem.IsValid())
	{
		bCachedIsConnected = CachedSubsystem->GetConnectionStatus();
		CachedSubsystem->OnConnectionStatusChangedNative.AddSP(
			this, &SUEAgentChatPanel::HandleConnectionStatusChanged);
	}

	// --- 构建 Slate 控件树 ---
	ChildSlot
	[
		SNew(SVerticalBox)

		// ========== 状态栏 ==========
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f, 4.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			[
				SNew(STextBlock)
				.Text(this, &SUEAgentChatPanel::GetStatusBarText)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			[
				SNew(SButton)
				.Text(LOCTEXT("ClearBtn", "Clear"))
				.OnClicked(this, &SUEAgentChatPanel::OnClearClicked)
			]
		]

		+ SVerticalBox::Slot()
		.AutoHeight()
		[
			SNew(SSeparator)
		]

		// ========== 消息区域 (可滚动) ==========
		+ SVerticalBox::Slot()
		.FillHeight(1.0f)
		.Padding(4.0f)
		[
			SAssignNew(MessageScrollBox, SScrollBox)
		]

		+ SVerticalBox::Slot()
		.AutoHeight()
		[
			SNew(SSeparator)
		]

		// ========== 输入区域 ==========
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(8.0f, 4.0f, 8.0f, 8.0f)
		[
			SNew(SHorizontalBox)

			// 输入框
			+ SHorizontalBox::Slot()
			.FillWidth(1.0f)
			.Padding(0.0f, 0.0f, 4.0f, 0.0f)
			[
				SAssignNew(InputTextBox, SEditableTextBox)
				.HintText(LOCTEXT("InputHint", "Type a message... (Enter to send)"))
				.OnTextCommitted(this, &SUEAgentChatPanel::OnInputTextCommitted)
			]

			// 发送按钮
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			[
				SNew(SButton)
				.Text(LOCTEXT("SendBtn", "Send"))
				.OnClicked(this, &SUEAgentChatPanel::OnSendClicked)
			]
		]
	];

	// 添加欢迎消息
	AddMessage(TEXT("assistant"),
		TEXT("Hello! I'm the UE Claw Bridge AI Assistant. I can help you with level editing, asset management, and more.\n\n")
		TEXT("Try asking me to:\n")
		TEXT("  - List selected actors\n")
		TEXT("  - Create objects in the scene\n")
		TEXT("  - Modify material properties\n\n")
		TEXT("Note: Connect an MCP client to enable AI responses."));
}

SUEAgentChatPanel::~SUEAgentChatPanel()
{
	if (CachedSubsystem.IsValid())
	{
		CachedSubsystem->OnConnectionStatusChangedNative.RemoveAll(this);
	}
}

// ------------------------------------------------------------------
// UI 回调
// ------------------------------------------------------------------

FReply SUEAgentChatPanel::OnSendClicked()
{
	if (!InputTextBox.IsValid())
	{
		return FReply::Handled();
	}

	FString InputText = InputTextBox->GetText().ToString().TrimStartAndEnd();
	if (InputText.IsEmpty())
	{
		return FReply::Handled();
	}

	// 添加用户消息
	AddMessage(TEXT("user"), InputText);

	// 清空输入框
	InputTextBox->SetText(FText::GetEmpty());

	// TODO: 阶段 3+ 连接 MCP 客户端，将消息发送给 AI
	// 当前仅作为 UI 展示，实际的 AI 通信通过外部 MCP 客户端完成
	AddMessage(TEXT("assistant"),
		FString::Printf(TEXT("(Message received: \"%s\")\n\nAI responses will appear here when an MCP client is connected."),
			*InputText.Left(100)));

	return FReply::Handled();
}

FReply SUEAgentChatPanel::OnClearClicked()
{
	Messages.Empty();
	RebuildMessageList();
	return FReply::Handled();
}

void SUEAgentChatPanel::OnInputTextCommitted(const FText& NewText, ETextCommit::Type CommitType)
{
	if (CommitType == ETextCommit::OnEnter)
	{
		OnSendClicked();
	}
}

void SUEAgentChatPanel::HandleConnectionStatusChanged(bool bNewStatus)
{
	bCachedIsConnected = bNewStatus;

	FString StatusMsg = bNewStatus
		? TEXT("MCP client connected. AI responses are now available.")
		: TEXT("MCP client disconnected.");
	AddMessage(TEXT("system"), StatusMsg);
}

// ------------------------------------------------------------------
// 辅助方法
// ------------------------------------------------------------------

void SUEAgentChatPanel::AddMessage(const FString& Sender, const FString& Content, bool bIsCode)
{
	// 限制消息历史
	if (Messages.Num() >= MaxMessages)
	{
		Messages.RemoveAt(0, Messages.Num() - MaxMessages + 1);
	}

	FChatMessage Msg;
	Msg.Sender = Sender;
	Msg.Content = Content;
	Msg.Timestamp = FDateTime::Now();
	Msg.bIsCode = bIsCode;
	Messages.Add(MoveTemp(Msg));

	RebuildMessageList();
}

void SUEAgentChatPanel::RebuildMessageList()
{
	if (!MessageScrollBox.IsValid())
	{
		return;
	}

	MessageScrollBox->ClearChildren();

	for (const FChatMessage& Msg : Messages)
	{
		// 时间戳
		FString TimeStr = Msg.Timestamp.ToString(TEXT("%H:%M"));

		// 发送者标签
		FString SenderLabel;
		if (Msg.Sender == TEXT("user"))
		{
			SenderLabel = TEXT("You");
		}
		else if (Msg.Sender == TEXT("assistant"))
		{
			SenderLabel = TEXT("AI Agent");
		}
		else
		{
			SenderLabel = TEXT("System");
		}

		// 消息气泡
		MessageScrollBox->AddSlot()
		.Padding(4.0f, 2.0f)
		[
			SNew(SVerticalBox)

			// 发送者 + 时间
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0.0f, 0.0f, 0.0f, 2.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(STextBlock)
					.Text(FText::FromString(SenderLabel))
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
					.ColorAndOpacity(GetSenderColor(Msg.Sender))
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(8.0f, 0.0f, 0.0f, 0.0f)
				[
					SNew(STextBlock)
					.Text(FText::FromString(TimeStr))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
					.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
				]
			]

			// 消息内容
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(8.0f, 0.0f, 0.0f, 4.0f)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Msg.Content))
				.Font(Msg.bIsCode
					? FCoreStyle::GetDefaultFontStyle("Mono", 9)
					: FCoreStyle::GetDefaultFontStyle("Regular", 10))
				.AutoWrapText(true)
			]
		];
	}

	// 滚动到底部
	MessageScrollBox->ScrollToEnd();
}

FSlateColor SUEAgentChatPanel::GetSenderColor(const FString& Sender) const
{
	if (Sender == TEXT("user"))
	{
		return FSlateColor(FLinearColor(0.3f, 0.7f, 1.0f));  // 蓝色
	}
	else if (Sender == TEXT("assistant"))
	{
		return FSlateColor(FLinearColor(0.4f, 0.9f, 0.4f));  // 绿色
	}
	else
	{
		return FSlateColor(FLinearColor(0.7f, 0.7f, 0.7f));  // 灰色
	}
}

FText SUEAgentChatPanel::GetStatusBarText() const
{
	FString Status = bCachedIsConnected
		? TEXT("● Connected")
		: TEXT("○ Disconnected");

	if (CachedSubsystem.IsValid())
	{
		FString Addr = CachedSubsystem->GetServerAddress();
		if (!Addr.IsEmpty())
		{
			Status += FString::Printf(TEXT("  |  %s"), *Addr);
		}
	}

	Status += FString::Printf(TEXT("  |  Messages: %d"), Messages.Num());

	return FText::FromString(Status);
}

#undef LOCTEXT_NAMESPACE