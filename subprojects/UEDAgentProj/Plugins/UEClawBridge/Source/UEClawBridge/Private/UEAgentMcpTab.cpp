// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentMcpTab.h"
#include "UEAgentManageUtils.h"
#include "UEAgentLocalization.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSeparator.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SWidgetSwitcher.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/STableRow.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

#define LOCTEXT_NAMESPACE "UEAgentMcpTab"

// ==================================================================
// Construct / Refresh
// ==================================================================

void SUEAgentMcpTab::Construct(const FArguments& InArgs)
{
	ChildSlot[ SAssignNew(ContentBox, SVerticalBox) ];
	Refresh();
}

void SUEAgentMcpTab::Refresh()
{
	RefreshData();
	if (!ContentBox.IsValid()) return;
	ContentBox->ClearChildren();
	ContentBox->AddSlot().FillHeight(1.0f)[ BuildContent() ];
}

// ==================================================================
// Data
// ==================================================================

void SUEAgentMcpTab::RefreshData()
{
	Servers.Empty();

	FString ConfigJson;
	if (FUEAgentManageUtils::ReadFileToString(
			FUEAgentManageUtils::GetOpenClawConfigPath(), ConfigJson))
	{
		ParseMcpConfig(ConfigJson);
	}

	// 探测端口
	FString PyCode = TEXT(
		"import json, socket\n"
		"from mcp_server import get_mcp_server\n"
		"local_server = get_mcp_server()\n"
		"local_tools = len(local_server._tools) if local_server else 0\n"
		"\n"
		"def probe(port, timeout=0.3):\n"
		"    try:\n"
		"        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
		"        s.settimeout(timeout)\n"
		"        s.connect(('127.0.0.1', port))\n"
		"        s.close()\n"
		"        return True\n"
		"    except:\n"
		"        return False\n"
		"\n"
		"ps = {}\n"
		"for p in [8080, 8081, 8082, 8083, 8084, 8085]:\n"
		"    ps[str(p)] = probe(p)\n"
		"\n"
		"_result = {'local_tools': local_tools, 'port_status': ps}\n"
	);

	FString JsonStr = FUEAgentManageUtils::RunPythonAndCapture(PyCode);

	TSharedPtr<FJsonObject> ProbeObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
	if (FJsonSerializer::Deserialize(Reader, ProbeObj) && ProbeObj.IsValid())
	{
		const TSharedPtr<FJsonObject>* PS;
		if (ProbeObj->TryGetObjectField(TEXT("port_status"), PS))
		{
			for (auto& Srv : Servers)
			{
				// 从 URL 提取端口
				int32 LastColon;
				if (Srv->Url.FindLastChar(TEXT(':'), LastColon))
				{
					FString Port = Srv->Url.Mid(LastColon + 1);
					int32 Slash;
					if (Port.FindChar(TEXT('/'), Slash)) Port = Port.Left(Slash);
					bool bOpen = false;
					if ((*PS)->TryGetBoolField(Port, bOpen))
						Srv->bConnected = bOpen;
				}
			}
		}

		int32 LT = 0;
		if (ProbeObj->TryGetNumberField(TEXT("local_tools"), LT))
		{
			for (auto& Srv : Servers)
				if (Srv->ServerId == TEXT("ue-editor-agent"))
					Srv->ToolCount = LT;
		}
	}
}

void SUEAgentMcpTab::ParseMcpConfig(const FString& JsonStr)
{
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> R = TJsonReaderFactory<>::Create(JsonStr);
	if (!FJsonSerializer::Deserialize(R, Root) || !Root.IsValid()) return;

	const TSharedPtr<FJsonObject>* P, *E, *M, *C, *S;
	if (!Root->TryGetObjectField(TEXT("plugins"), P)) return;
	if (!(*P)->TryGetObjectField(TEXT("entries"), E)) return;
	if (!(*E)->TryGetObjectField(TEXT("mcp-bridge"), M)) return;
	if (!(*M)->TryGetObjectField(TEXT("config"), C)) return;
	if (!(*C)->TryGetObjectField(TEXT("servers"), S)) return;

	TMap<FString, FString> Names;
	Names.Add(TEXT("ue-editor-agent"), TEXT("UE Claw Bridge"));
	Names.Add(TEXT("maya-primary"),    TEXT("Maya Claw Bridge"));
	Names.Add(TEXT("max-primary"),     TEXT("3ds Max Claw Bridge"));

	for (const auto& Pair : (*S)->Values)
	{
		const TSharedPtr<FJsonObject>* Obj;
		if (!(*S)->TryGetObjectField(Pair.Key, Obj)) continue;

		auto Entry = MakeShared<FMcpServerEntry>();
		Entry->ServerId = Pair.Key;
		const FString* DN = Names.Find(Pair.Key);
		Entry->DisplayName = DN ? *DN : Pair.Key;
		Entry->Type = (*Obj)->GetStringField(TEXT("type"));

		if (Entry->Type == TEXT("stdio"))
		{
			Entry->Command = (*Obj)->GetStringField(TEXT("command"));
			Entry->Url = Entry->Command;  // 显示用
		}
		else
		{
			Entry->Url = (*Obj)->GetStringField(TEXT("url"));
		}

		bool bEn = true;
		(*Obj)->TryGetBoolField(TEXT("enabled"), bEn);
		Entry->bEnabled = bEn;

		Servers.Add(Entry);
	}
}

// ==================================================================
// UI
// ==================================================================

TSharedRef<SWidget> SUEAgentMcpTab::BuildContent()
{
	int32 Total = Servers.Num(), Conn = 0, En = 0;
	for (auto& S : Servers) { if (S->bConnected) Conn++; if (S->bEnabled) En++; }

	return SNew(SVerticalBox)

	+ SVerticalBox::Slot().AutoHeight().Padding(8, 6)
	[
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth()
		[
			SNew(STextBlock)
			.Text(FText::Format(
				FUEAgentL10n::Get(TEXT("ManageMcpSummary")),
				FText::AsNumber(Total), FText::AsNumber(Conn), FText::AsNumber(En)))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
		]
		+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]
		+ SHorizontalBox::Slot().AutoWidth()
		[
			SNew(SButton)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageMcpAddBtn")); })
			.OnClicked(this, &SUEAgentMcpTab::OnAddServerClicked)
			.ContentPadding(FMargin(6, 3))
		]
	]

	+ SVerticalBox::Slot().AutoHeight()[ SNew(SSeparator) ]

	+ SVerticalBox::Slot().FillHeight(1.0f).Padding(4)
	[
		SNew(SScrollBox)
		+ SScrollBox::Slot()
		[
			SAssignNew(ServerListView, SListView<FMcpServerEntryPtr>)
			.ListItemsSource(&Servers)
			.OnGenerateRow(this, &SUEAgentMcpTab::GenerateRow)
			.SelectionMode(ESelectionMode::None)
		]
	];
}

TSharedRef<ITableRow> SUEAgentMcpTab::GenerateRow(
	FMcpServerEntryPtr Item, const TSharedRef<STableViewBase>& Owner)
{
	FLinearColor SC = Item->bConnected
		? FLinearColor(0.2f, 0.8f, 0.3f)
		: FLinearColor(0.6f, 0.3f, 0.3f);
	float Op = Item->bEnabled ? 1.0f : 0.45f;

	// stdio 类型显示 command，其他显示 URL
	FString SubLine = (Item->Type == TEXT("stdio"))
		? FString::Printf(TEXT("$ %s  (stdio)"), *Item->Command)
		: FString::Printf(TEXT("%s  (%s)"), *Item->Url, *Item->Type);

	return SNew(STableRow<FMcpServerEntryPtr>, Owner)
	[
		SNew(SBorder)
		.BorderBackgroundColor(FSlateColor(FLinearColor(0.08f, 0.08f, 0.08f)))
		.Padding(FMargin(6, 4))
		[
			SNew(SHorizontalBox)

			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2)
			[
				SNew(SCheckBox)
				.IsChecked(Item->bEnabled ? ECheckBoxState::Checked : ECheckBoxState::Unchecked)
				.OnCheckStateChanged(FOnCheckStateChanged::CreateSP(
					this, &SUEAgentMcpTab::OnEnableChanged, Item))
				.ToolTipText_Lambda([Item]() {
					return Item->bEnabled
						? FUEAgentL10n::Get(TEXT("ManageMcpDisableTip"))
						: FUEAgentL10n::Get(TEXT("ManageMcpEnableTip"));
				})
			]

			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4, 0)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Item->bConnected ? TEXT("\x25CF") : TEXT("\x25CB")))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
				.ColorAndOpacity(FSlateColor(SC))
			]

			+ SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(4, 2)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(STextBlock)
					.Text(FText::FromString(Item->DisplayName))
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
					.ColorAndOpacity(FSlateColor(FLinearColor(0.9f*Op, 0.9f*Op, 0.9f*Op)))
				]
				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(STextBlock)
					.Text(FText::FromString(SubLine))
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
					.ColorAndOpacity(FSlateColor(FLinearColor(0.45f*Op, 0.45f*Op, 0.45f*Op)))
				]
			]

			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(8, 0)
			[
				SNew(STextBlock)
				.Text_Lambda([Item]() {
					if (Item->Type == TEXT("stdio"))
						return FUEAgentL10n::Get(TEXT("ManageMcpStdio"));
					return Item->bConnected
						? FUEAgentL10n::Get(TEXT("Connected"))
						: FUEAgentL10n::Get(TEXT("Disconnected"));
				})
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
				.ColorAndOpacity(FSlateColor(Item->Type == TEXT("stdio")
					? FLinearColor(0.5f, 0.65f, 0.8f) : SC))
			]

			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(4, 0)
			[
				SNew(STextBlock)
				.Text_Lambda([Item]() {
					return Item->ToolCount > 0
						? FText::Format(FUEAgentL10n::Get(TEXT("ManageMcpToolCount")),
							FText::AsNumber(Item->ToolCount))
						: FText::GetEmpty();
				})
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
				.ColorAndOpacity(FSlateColor(FLinearColor(0.5f, 0.5f, 0.5f)))
			]
		]
	];
}

// ==================================================================
// Actions
// ==================================================================

void SUEAgentMcpTab::OnEnableChanged(ECheckBoxState NewState, FMcpServerEntryPtr Item)
{
	Item->bEnabled = (NewState == ECheckBoxState::Checked);
	SetServerEnabled(Item->ServerId, Item->bEnabled);
	Refresh();
}

void SUEAgentMcpTab::SetServerEnabled(const FString& ServerId, bool bEnabled)
{
	FString ConfigPath = FUEAgentManageUtils::GetOpenClawConfigPath();
	FString JsonStr;
	if (!FUEAgentManageUtils::ReadFileToString(ConfigPath, JsonStr)) return;

	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> R = TJsonReaderFactory<>::Create(JsonStr);
	if (!FJsonSerializer::Deserialize(R, Root) || !Root.IsValid()) return;

	auto Plug = Root->GetObjectField(TEXT("plugins"));
	auto Ent = Plug ? Plug->GetObjectField(TEXT("entries")) : nullptr;
	auto Mcp = Ent ? Ent->GetObjectField(TEXT("mcp-bridge")) : nullptr;
	auto Cfg = Mcp ? Mcp->GetObjectField(TEXT("config")) : nullptr;
	auto Srvs = Cfg ? Cfg->GetObjectField(TEXT("servers")) : nullptr;
	auto Srv = Srvs ? Srvs->GetObjectField(ServerId) : nullptr;
	if (!Srv) return;

	if (bEnabled) Srv->RemoveField(TEXT("enabled"));
	else Srv->SetBoolField(TEXT("enabled"), false);

	FString Out;
	TSharedRef<TJsonWriter<>> W = TJsonWriterFactory<>::Create(&Out);
	FJsonSerializer::Serialize(Root.ToSharedRef(), W);
	FUEAgentManageUtils::WriteStringToFile(ConfigPath, Out);
}

void SUEAgentMcpTab::WriteNewServer(const FString& Id, const FString& Type,
	const FString& Url, const FString& Command)
{
	FString ConfigPath = FUEAgentManageUtils::GetOpenClawConfigPath();
	FString JsonStr;
	if (!FUEAgentManageUtils::ReadFileToString(ConfigPath, JsonStr)) return;

	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> R = TJsonReaderFactory<>::Create(JsonStr);
	if (!FJsonSerializer::Deserialize(R, Root) || !Root.IsValid()) return;

	auto Plug = Root->GetObjectField(TEXT("plugins"));
	auto Ent = Plug ? Plug->GetObjectField(TEXT("entries")) : nullptr;
	auto Mcp = Ent ? Ent->GetObjectField(TEXT("mcp-bridge")) : nullptr;
	auto Cfg = Mcp ? Mcp->GetObjectField(TEXT("config")) : nullptr;
	auto Srvs = Cfg ? Cfg->GetObjectField(TEXT("servers")) : nullptr;
	if (!Srvs) return;

	TSharedPtr<FJsonObject> NewSrv = MakeShared<FJsonObject>();
	NewSrv->SetStringField(TEXT("type"), Type);

	if (Type == TEXT("stdio"))
	{
		NewSrv->SetStringField(TEXT("command"), Command);
		// 解析 args（按空格分割，保留引号内的部分）
		// 简化处理：URL 字段留空
	}
	else
	{
		NewSrv->SetStringField(TEXT("url"), Url);
	}

	Srvs->SetObjectField(Id, NewSrv);

	FString Out;
	TSharedRef<TJsonWriter<>> W = TJsonWriterFactory<>::Create(&Out);
	FJsonSerializer::Serialize(Root.ToSharedRef(), W);
	FUEAgentManageUtils::WriteStringToFile(ConfigPath, Out);
}

FReply SUEAgentMcpTab::OnAddServerClicked()
{
	TSharedRef<SWindow> Win = SNew(SWindow)
		.Title(FUEAgentL10n::Get(TEXT("ManageMcpAddTitle")))
		.ClientSize(FVector2D(500.0f, 360.0f))
		.SupportsMinimize(false)
		.SupportsMaximize(false);

	// State: which type is selected (0=websocket, 1=stdio)
	TSharedPtr<int32> SelectedType = MakeShared<int32>(0);

	TSharedPtr<SEditableTextBox> IdInput;
	// WebSocket fields
	TSharedPtr<SEditableTextBox> WsUrlInput;
	// stdio fields
	TSharedPtr<SEditableTextBox> StdioCommandInput;

	TWeakPtr<SWindow> WeakWin = Win;

	Win->SetContent(
		SNew(SVerticalBox)

		// Title
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 8)
		[
			SNew(STextBlock)
			.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageMcpAddDesc")); })
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
			.AutoWrapText(true)
		]

		// Server ID
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 4)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageMcpAddIdLabel")); })
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0, 2, 0, 0)
			[
				SAssignNew(IdInput, SEditableTextBox)
				.HintText(FText::FromString(TEXT("my-dcc-agent")))
			]
		]

		// Type selection buttons
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 6, 12, 2)
		[
			SNew(SHorizontalBox)

			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageMcpAddTypeLabel")); })
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
			]

			+ SHorizontalBox::Slot().AutoWidth().Padding(8, 0, 0, 0)
			[
				SNew(SButton)
				.Text(FText::FromString(TEXT("WebSocket")))
				.OnClicked_Lambda([SelectedType]() {
					*SelectedType = 0;
					return FReply::Handled();
				})
				.ContentPadding(FMargin(6, 2))
			]

			+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0, 0, 0)
			[
				SNew(SButton)
				.Text(FText::FromString(TEXT("stdio")))
				.OnClicked_Lambda([SelectedType]() {
					*SelectedType = 1;
					return FReply::Handled();
				})
				.ContentPadding(FMargin(6, 2))
			]
		]

		// Type-specific fields (switcher)
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 4)
		[
			SNew(SWidgetSwitcher)
			.WidgetIndex_Lambda([SelectedType]() { return *SelectedType; })

			// Index 0: WebSocket
			+ SWidgetSwitcher::Slot()
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(STextBlock)
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageMcpAddUrlLabel")); })
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0, 2, 0, 0)
				[
					SAssignNew(WsUrlInput, SEditableTextBox)
					.HintText(FText::FromString(TEXT("ws://127.0.0.1:8083")))
				]
			]

			// Index 1: stdio
			+ SWidgetSwitcher::Slot()
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(STextBlock)
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageMcpAddCmdLabel")); })
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0, 2, 0, 0)
				[
					SAssignNew(StdioCommandInput, SEditableTextBox)
					.HintText(FText::FromString(TEXT("npx -y @modelcontextprotocol/server-xxx")))
				]
			]
		]

		+ SVerticalBox::Slot().FillHeight(1.0f)[ SNew(SSpacer) ]

		// Buttons
		+ SVerticalBox::Slot().AutoHeight().Padding(12, 8)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.0f)[ SNew(SSpacer) ]

			+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("ManageMcpAddConfirm")); })
				.OnClicked_Lambda([this, SelectedType, IdInput, WsUrlInput,
					StdioCommandInput, WeakWin]()
				{
					FString Id = IdInput->GetText().ToString().TrimStartAndEnd();
					if (Id.IsEmpty()) return FReply::Handled();

					if (*SelectedType == 0)
					{
						FString Url = WsUrlInput->GetText().ToString().TrimStartAndEnd();
						if (Url.IsEmpty()) return FReply::Handled();
						FString Type = Url.StartsWith(TEXT("ws")) ? TEXT("websocket") : TEXT("sse");
						WriteNewServer(Id, Type, Url, TEXT(""));
					}
					else
					{
						FString Cmd = StdioCommandInput->GetText().ToString().TrimStartAndEnd();
						if (Cmd.IsEmpty()) return FReply::Handled();
						WriteNewServer(Id, TEXT("stdio"), TEXT(""), Cmd);
					}

					if (WeakWin.IsValid()) WeakWin.Pin()->RequestDestroyWindow();
					Refresh();
					return FReply::Handled();
				})
				.ContentPadding(FMargin(8, 4))
			]

			+ SHorizontalBox::Slot().AutoWidth().Padding(4, 0)
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QICancelBtn")); })
				.OnClicked_Lambda([WeakWin]() {
					if (WeakWin.IsValid()) WeakWin.Pin()->RequestDestroyWindow();
					return FReply::Handled();
				})
				.ContentPadding(FMargin(8, 4))
			]
		]
	);

	FSlateApplication::Get().AddWindow(Win);
	return FReply::Handled();
}

#undef LOCTEXT_NAMESPACE
