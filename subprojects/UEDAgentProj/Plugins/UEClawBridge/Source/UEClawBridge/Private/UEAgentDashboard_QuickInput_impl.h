// Copyright ArtClaw Project. All Rights Reserved.
// 快捷输入面板模块 - 快捷短语管理、增删改查、模态对话框
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// 快捷输入 (Quick Inputs)
// ==================================================================

void SUEAgentDashboard::LoadQuickInputs()
{
	FString ConfigPath = GetQuickInputConfigPath();
	if (!FPaths::FileExists(ConfigPath))
	{
		QuickInputs.Empty();
		return;
	}

	FString JsonContent;
	if (!FFileHelper::LoadFileToString(JsonContent, *ConfigPath))
	{
		// FFileHelper 失败时，尝试原始字节方式读取
		TArray<uint8> RawBytes;
		if (!FFileHelper::LoadFileToArray(RawBytes, *ConfigPath))
		{
			QuickInputs.Empty();
			return;
		}
		// 跳过 UTF-8 BOM (EF BB BF)
		int32 Offset = 0;
		if (RawBytes.Num() >= 3 && RawBytes[0] == 0xEF && RawBytes[1] == 0xBB && RawBytes[2] == 0xBF)
		{
			Offset = 3;
		}
		FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData() + Offset), RawBytes.Num() - Offset);
		JsonContent = FString(Converter.Length(), Converter.Get());
	}

	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonContent);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
	{
		QuickInputs.Empty();
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* InputsArray = nullptr;
	if (!JsonObj->TryGetArrayField(TEXT("quickInputs"), InputsArray) || !InputsArray)
	{
		QuickInputs.Empty();
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

	// 加载成功后立即重新保存，确保文件编码为 UTF-8 (无 BOM)
	SaveQuickInputs();
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
		InputsArray.Add(MakeShared<FJsonValueObject>(InputObj));
	}

	RootObj->SetArrayField(TEXT("quickInputs"), InputsArray);

	FString JsonStr;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonStr);
	FJsonSerializer::Serialize(RootObj.ToSharedRef(), Writer);

	FFileHelper::SaveStringToFile(JsonStr, *ConfigPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
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

		// 每个快捷输入: [按钮名称] [e编辑] [x删除]
		QuickInputWrapBox->AddSlot()
		.Padding(2.0f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			[
				SNew(SButton)
				.Text(FText::FromString(Input.Name))
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply { return OnQuickInputClicked(CapturedIndex); })
				.ToolTipText(FText::FromString(Input.Content))
				.ContentPadding(FMargin(8.0f, 3.0f))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			.Padding(2.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("EditQuickInputBtn")); })
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply { return OnEditQuickInputClicked(CapturedIndex); })
				.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("EditQuickInputTip")); })
				.ContentPadding(FMargin(3.0f, 3.0f))
				.ButtonColorAndOpacity(FSlateColor(FLinearColor(0.35f, 0.35f, 0.45f)))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			.Padding(1.0f, 0.0f, 0.0f, 0.0f)
			[
				SNew(SButton)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("DeleteQuickInputBtn")); })
				.OnClicked_Lambda([this, CapturedIndex]() -> FReply { return OnDeleteQuickInputClicked(CapturedIndex); })
				.ToolTipText_Lambda([]() { return FUEAgentL10n::Get(TEXT("DeleteQuickInputTip")); })
				.ContentPadding(FMargin(3.0f, 3.0f))
				.ButtonColorAndOpacity(FSlateColor(FLinearColor(0.45f, 0.25f, 0.25f)))
			]
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
	FSlateApplication::Get().SetKeyboardFocus(InputTextBox);

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnAddQuickInputClicked()
{
	// 弹出模态对话框，新建快捷输入
	QuickInputEditIndex = -1; // -1 表示新建

	FString DefaultName = TEXT("New Command");
	FString DefaultContent = TEXT("");

	auto Self = SharedThis(this);

	QuickInputEditWindow = SNew(SWindow)
		.Title(FUEAgentL10n::Get(TEXT("EditQuickInputTitle")))
		.ClientSize(FVector2D(400.0f, 250.0f))
		.SupportsMinimize(false)
		.SupportsMaximize(false)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f)
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QINameLabel")); })
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f, 0.0f, 12.0f, 8.0f)
			[
				SAssignNew(QuickInputEditNameBox, SEditableTextBox)
				.Text(FText::FromString(DefaultName))
				.SelectAllTextWhenFocused(true)
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QIContentLabel")); })
			]
			+ SVerticalBox::Slot()
			.FillHeight(1.0f)
			.Padding(12.0f, 4.0f, 12.0f, 8.0f)
			[
				SAssignNew(QuickInputEditContentBox, SMultiLineEditableTextBox)
				.Text(FText::FromString(DefaultContent))
				.AutoWrapText(true)
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.HAlign(HAlign_Right)
			.Padding(12.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(0.0f, 0.0f, 8.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QICancelBtn")); })
					.OnClicked_Lambda([Self]() -> FReply { return Self->OnQuickInputEditCancelClicked(); })
					.ContentPadding(FMargin(12.0f, 4.0f))
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(SButton)
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QISaveBtn")); })
					.OnClicked_Lambda([Self]() -> FReply { return Self->OnQuickInputEditSaveClicked(); })
					.ContentPadding(FMargin(12.0f, 4.0f))
					.ButtonColorAndOpacity(FSlateColor(FLinearColor(0.15f, 0.45f, 0.75f)))
				]
			]
		];

	if (QuickInputEditWindow.IsValid())
	{
		FUEAgentManageUtils::AddChildWindow(QuickInputEditWindow.ToSharedRef());
	}

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnEditQuickInputClicked(int32 Index)
{
	if (!QuickInputs.IsValidIndex(Index))
	{
		return FReply::Handled();
	}

	// 弹出模态对话框，编辑现有快捷输入
	QuickInputEditIndex = Index;

	const FQuickInput& Input = QuickInputs[Index];
	auto Self = SharedThis(this);

	QuickInputEditWindow = SNew(SWindow)
		.Title(FUEAgentL10n::Get(TEXT("EditQuickInputTitle")))
		.ClientSize(FVector2D(400.0f, 250.0f))
		.SupportsMinimize(false)
		.SupportsMaximize(false)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f)
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QINameLabel")); })
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f, 0.0f, 12.0f, 8.0f)
			[
				SAssignNew(QuickInputEditNameBox, SEditableTextBox)
				.Text(FText::FromString(Input.Name))
				.SelectAllTextWhenFocused(true)
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(12.0f, 0.0f)
			[
				SNew(STextBlock)
				.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QIContentLabel")); })
			]
			+ SVerticalBox::Slot()
			.FillHeight(1.0f)
			.Padding(12.0f, 4.0f, 12.0f, 8.0f)
			[
				SAssignNew(QuickInputEditContentBox, SMultiLineEditableTextBox)
				.Text(FText::FromString(Input.Content))
				.AutoWrapText(true)
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.HAlign(HAlign_Right)
			.Padding(12.0f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(0.0f, 0.0f, 8.0f, 0.0f)
				[
					SNew(SButton)
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QICancelBtn")); })
					.OnClicked_Lambda([Self]() -> FReply { return Self->OnQuickInputEditCancelClicked(); })
					.ContentPadding(FMargin(12.0f, 4.0f))
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				[
					SNew(SButton)
					.Text_Lambda([]() { return FUEAgentL10n::Get(TEXT("QISaveBtn")); })
					.OnClicked_Lambda([Self]() -> FReply { return Self->OnQuickInputEditSaveClicked(); })
					.ContentPadding(FMargin(12.0f, 4.0f))
					.ButtonColorAndOpacity(FSlateColor(FLinearColor(0.15f, 0.45f, 0.75f)))
				]
			]
		];

	if (QuickInputEditWindow.IsValid())
	{
		FUEAgentManageUtils::AddChildWindow(QuickInputEditWindow.ToSharedRef());
	}

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnQuickInputEditSaveClicked()
{
	if (!QuickInputEditNameBox.IsValid() || !QuickInputEditContentBox.IsValid())
	{
		return FReply::Handled();
	}

	FString Name = QuickInputEditNameBox->GetText().ToString().TrimStartAndEnd();
	FString Content = QuickInputEditContentBox->GetText().ToString();

	if (Name.IsEmpty())
	{
		Name = TEXT("Unnamed");
	}

	if (QuickInputEditIndex < 0)
	{
		// 新增
		FGuid NewId = FGuid::NewGuid();
		FQuickInput NewInput;
		NewInput.Id = NewId.ToString();
		NewInput.Name = Name;
		NewInput.Content = Content;
		QuickInputs.Add(MoveTemp(NewInput));
	}
	else if (QuickInputs.IsValidIndex(QuickInputEditIndex))
	{
		// 编辑
		QuickInputs[QuickInputEditIndex].Name = Name;
		QuickInputs[QuickInputEditIndex].Content = Content;
	}

	SaveQuickInputs();
	RebuildQuickInputPanel();

	// 关闭对话框
	if (QuickInputEditWindow.IsValid())
	{
		QuickInputEditWindow->RequestDestroyWindow();
		QuickInputEditWindow.Reset();
	}

	return FReply::Handled();
}

FReply SUEAgentDashboard::OnQuickInputEditCancelClicked()
{
	// 关闭对话框
	if (QuickInputEditWindow.IsValid())
	{
		QuickInputEditWindow->RequestDestroyWindow();
		QuickInputEditWindow.Reset();
	}

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
