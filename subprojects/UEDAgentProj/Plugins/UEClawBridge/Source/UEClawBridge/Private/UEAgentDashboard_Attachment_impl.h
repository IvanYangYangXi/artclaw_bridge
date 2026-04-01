// Copyright ArtClaw Project. All Rights Reserved.
// 附件模块 - 剪贴板图片/文件粘贴、预览、发送
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// 附件辅助方法
// ==================================================================

FString SUEAgentDashboard::GetAttachmentTempDir() const
{
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent") / TEXT("attachments");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	return TempDir;
}

bool SUEAgentDashboard::IsImageFile(const FString& FilePath)
{
	FString Ext = FPaths::GetExtension(FilePath).ToLower();
	return Ext == TEXT("png") || Ext == TEXT("jpg") || Ext == TEXT("jpeg")
		|| Ext == TEXT("bmp") || Ext == TEXT("gif") || Ext == TEXT("webp")
		|| Ext == TEXT("tga");
}

FString SUEAgentDashboard::GetMimeType(const FString& FilePath)
{
	FString Ext = FPaths::GetExtension(FilePath).ToLower();
	if (Ext == TEXT("png"))  return TEXT("image/png");
	if (Ext == TEXT("jpg") || Ext == TEXT("jpeg")) return TEXT("image/jpeg");
	if (Ext == TEXT("bmp"))  return TEXT("image/bmp");
	if (Ext == TEXT("gif"))  return TEXT("image/gif");
	if (Ext == TEXT("webp")) return TEXT("image/webp");
	if (Ext == TEXT("tga"))  return TEXT("image/tga");
	if (Ext == TEXT("txt") || Ext == TEXT("log") || Ext == TEXT("md")) return TEXT("text/plain");
	if (Ext == TEXT("json")) return TEXT("application/json");
	if (Ext == TEXT("py"))   return TEXT("text/x-python");
	if (Ext == TEXT("cpp") || Ext == TEXT("h")) return TEXT("text/x-c++");
	return TEXT("application/octet-stream");
}

FString SUEAgentDashboard::FormatFileSize(int64 Bytes)
{
	if (Bytes < 1024)
	{
		return FString::Printf(TEXT("%lld B"), Bytes);
	}
	if (Bytes < 1024 * 1024)
	{
		return FString::Printf(TEXT("%.1f KB"), Bytes / 1024.0);
	}
	return FString::Printf(TEXT("%.1f MB"), Bytes / (1024.0 * 1024.0));
}

// ==================================================================
// Windows 剪贴板图片读取
// ==================================================================

bool SUEAgentDashboard::SaveClipboardImageToFile(const FString& OutPath)
{
#if PLATFORM_WINDOWS
	if (!::OpenClipboard(nullptr))
	{
		return false;
	}

	bool bSuccess = false;

	// 尝试读取 CF_DIBV5 或 CF_DIB
	HANDLE hDib = ::GetClipboardData(CF_DIBV5);
	if (!hDib)
	{
		hDib = ::GetClipboardData(CF_DIB);
	}

	if (hDib)
	{
		void* pDib = ::GlobalLock(hDib);
		if (pDib)
		{
			BITMAPINFOHEADER* pBIH = reinterpret_cast<BITMAPINFOHEADER*>(pDib);
			int32 Width  = FMath::Abs((int32)pBIH->biWidth);
			int32 Height = FMath::Abs((int32)pBIH->biHeight);
			int32 BitCount = pBIH->biBitCount;

			if (Width > 0 && Height > 0 && (BitCount == 24 || BitCount == 32))
			{
				// 计算像素数据偏移（跳过 header + color table）
				int32 HeaderSize = pBIH->biSize;

				// Color table size
				int32 ColorTableSize = 0;
				if (BitCount <= 8)
				{
					int32 ClrUsed = pBIH->biClrUsed ? pBIH->biClrUsed : (1 << BitCount);
					ColorTableSize = ClrUsed * 4;
				}

				uint8* pPixels = reinterpret_cast<uint8*>(pDib) + HeaderSize + ColorTableSize;
				int32 SrcStride = ((Width * BitCount + 31) / 32) * 4; // 4-byte aligned
				bool bBottomUp = ((int32)pBIH->biHeight > 0);

				// 转换为 BGRA 数组 (UE 的 IImageWrapper 需要)
				TArray<FColor> Pixels;
				Pixels.SetNum(Width * Height);

				for (int32 Y = 0; Y < Height; Y++)
				{
					int32 SrcY = bBottomUp ? (Height - 1 - Y) : Y;
					uint8* SrcRow = pPixels + SrcY * SrcStride;

					for (int32 X = 0; X < Width; X++)
					{
						FColor& Dst = Pixels[Y * Width + X];
						if (BitCount == 32)
						{
							Dst.B = SrcRow[X * 4 + 0];
							Dst.G = SrcRow[X * 4 + 1];
							Dst.R = SrcRow[X * 4 + 2];
							Dst.A = SrcRow[X * 4 + 3];
							// CF_DIB 的 alpha 通道可能全是 0，修正为 255
							if (Dst.A == 0) Dst.A = 255;
						}
						else // 24-bit
						{
							Dst.B = SrcRow[X * 3 + 0];
							Dst.G = SrcRow[X * 3 + 1];
							Dst.R = SrcRow[X * 3 + 2];
							Dst.A = 255;
						}
					}
				}

				// 使用 IImageWrapper 编码为 PNG
				IImageWrapperModule& ImageModule = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
				TSharedPtr<IImageWrapper> PngWriter = ImageModule.CreateImageWrapper(EImageFormat::PNG);

				if (PngWriter.IsValid())
				{
					PngWriter->SetRaw(Pixels.GetData(), Pixels.Num() * sizeof(FColor),
						Width, Height, ERGBFormat::BGRA, 8);

					const TArray64<uint8>& PngData = PngWriter->GetCompressed();
					if (PngData.Num() > 0)
					{
						bSuccess = FFileHelper::SaveArrayToFile(PngData, *OutPath);
					}
				}
			}

			::GlobalUnlock(hDib);
		}
	}

	::CloseClipboard();
	return bSuccess;
#else
	return false;
#endif
}

// ==================================================================
// 剪贴板粘贴处理
// ==================================================================

bool SUEAgentDashboard::TryPasteFromClipboard()
{
	// 1) 尝试读取剪贴板图片 (CF_DIB/CF_DIBV5)
	{
		FDateTime Now = FDateTime::Now();
		FString FileName = FString::Printf(TEXT("clipboard_%04d%02d%02d_%02d%02d%02d.png"),
			Now.GetYear(), Now.GetMonth(), Now.GetDay(),
			Now.GetHour(), Now.GetMinute(), Now.GetSecond());
		FString TempPath = GetAttachmentTempDir() / FileName;

		if (SaveClipboardImageToFile(TempPath))
		{
			// 检查文件大小
			int64 FileSize = IFileManager::Get().FileSize(*TempPath);
			if (FileSize > MaxAttachmentBytes)
			{
				IFileManager::Get().Delete(*TempPath);
				AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("AttachTooLarge")));
				return true; // 已处理，不再粘贴文本
			}

			FPendingAttachment Att;
			Att.FilePath = TempPath;
			Att.DisplayName = FileName;
			Att.MimeType = TEXT("image/png");
			Att.FileSize = FileSize;
			Att.bIsImage = true;
			PendingAttachments.Add(MoveTemp(Att));

			RebuildAttachmentPreview();
			return true;
		}
	}

	// 2) 尝试读取 CF_HDROP (资源管理器复制的文件列表)
#if PLATFORM_WINDOWS
	{
		if (::OpenClipboard(nullptr))
		{
			HANDLE hDrop = ::GetClipboardData(CF_HDROP);
			if (hDrop)
			{
				HDROP hDropInfo = static_cast<HDROP>(hDrop);
				UINT FileCount = ::DragQueryFileW(hDropInfo, 0xFFFFFFFF, nullptr, 0);

				TArray<FString> DroppedFiles;
				for (UINT i = 0; i < FileCount; ++i)
				{
					WCHAR FilePath[MAX_PATH];
					if (::DragQueryFileW(hDropInfo, i, FilePath, MAX_PATH) > 0)
					{
						DroppedFiles.Add(FString(FilePath));
					}
				}

				::CloseClipboard();

				if (DroppedFiles.Num() > 0)
				{
					for (const FString& File : DroppedFiles)
					{
						int64 FileSize = IFileManager::Get().FileSize(*File);
						bool bIsImg = IsImageFile(File);

						if (bIsImg && FileSize > MaxAttachmentBytes)
						{
							AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("AttachTooLarge")));
							continue;
						}

						// 文件管理器复制的文件: 直接引用原路径，不复制副本
						FPendingAttachment Att;
						Att.FilePath = File;
						Att.DisplayName = FPaths::GetCleanFilename(File);
						Att.MimeType = GetMimeType(File);
						Att.FileSize = FileSize > 0 ? FileSize : 0;
						Att.bIsImage = bIsImg;
						PendingAttachments.Add(MoveTemp(Att));
					}

					RebuildAttachmentPreview();
					return true;
				}
			}
			else
			{
				::CloseClipboard();
			}
		}
	}
#endif

	// 3) 尝试检测剪贴板文本是否为文件路径
	{
		FString ClipText;
		FPlatformApplicationMisc::ClipboardPaste(ClipText);
		ClipText.TrimStartAndEndInline();

		// 去掉引号包裹
		if (ClipText.StartsWith(TEXT("\"")) && ClipText.EndsWith(TEXT("\"")))
		{
			ClipText = ClipText.Mid(1, ClipText.Len() - 2);
		}

		// 检查是否为有效文件路径
		if (!ClipText.IsEmpty() && !ClipText.Contains(TEXT("\n"))
			&& FPaths::FileExists(ClipText))
		{
			int64 FileSize = IFileManager::Get().FileSize(*ClipText);
			bool bIsImg = IsImageFile(ClipText);

			if (bIsImg && FileSize > MaxAttachmentBytes)
			{
				AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("AttachTooLarge")));
				return true;
			}

			// 文件路径粘贴: 直接引用原路径，不复制副本
			FPendingAttachment Att;
			Att.FilePath = ClipText;
			Att.DisplayName = FPaths::GetCleanFilename(ClipText);
			Att.MimeType = GetMimeType(ClipText);
			Att.FileSize = FileSize > 0 ? FileSize : 0;
			Att.bIsImage = bIsImg;
			PendingAttachments.Add(MoveTemp(Att));

			RebuildAttachmentPreview();
			return true;
		}
	}

	// 4) 普通文本 — 不拦截，让 SMultiLineEditableTextBox 正常处理
	return false;
}

// ==================================================================
// 附件按钮: 打开文件选择器
// ==================================================================

FReply SUEAgentDashboard::OnAttachFileClicked()
{
	IDesktopPlatform* DesktopPlatform = FDesktopPlatformModule::Get();
	if (!DesktopPlatform)
	{
		return FReply::Handled();
	}

	TArray<FString> OutFiles;
	const FString DefaultPath = FPaths::ProjectDir();
	const FString FileTypes = TEXT("All Files (*.*)|*.*|Images (*.png;*.jpg;*.jpeg;*.bmp)|*.png;*.jpg;*.jpeg;*.bmp");

	TSharedPtr<SWindow> ParentWindow = FSlateApplication::Get().GetActiveTopLevelRegularWindow();
	void* ParentHandle = ParentWindow.IsValid() ? ParentWindow->GetNativeWindow()->GetOSWindowHandle() : nullptr;

	bool bOpened = DesktopPlatform->OpenFileDialog(
		ParentHandle,
		FUEAgentL10n::GetStr(TEXT("AttachFileTitle")),
		DefaultPath,
		TEXT(""),
		FileTypes,
		EFileDialogFlags::Multiple,
		OutFiles
	);

	if (bOpened)
	{
		for (const FString& File : OutFiles)
		{
			int64 FileSize = IFileManager::Get().FileSize(*File);
			bool bIsImg = IsImageFile(File);

			if (bIsImg && FileSize > MaxAttachmentBytes)
			{
				AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("AttachTooLarge")));
				continue;
			}

			if (bIsImg)
			{
				// 文件选择器: 直接引用原路径，不复制副本
				FPendingAttachment Att;
				Att.FilePath = File;
				Att.DisplayName = FPaths::GetCleanFilename(File);
				Att.MimeType = GetMimeType(File);
				Att.FileSize = FileSize;
				Att.bIsImage = true;
				PendingAttachments.Add(MoveTemp(Att));
			}
			else
			{
				FPendingAttachment Att;
				Att.FilePath = File;
				Att.DisplayName = FPaths::GetCleanFilename(File);
				Att.MimeType = GetMimeType(File);
				Att.FileSize = FileSize;
				Att.bIsImage = false;
				PendingAttachments.Add(MoveTemp(Att));
			}
		}

		RebuildAttachmentPreview();
	}

	return FReply::Handled();
}

// ==================================================================
// 附件移除与清空
// ==================================================================

FReply SUEAgentDashboard::OnRemoveAttachment(int32 Index)
{
	if (PendingAttachments.IsValidIndex(Index))
	{
		// 如果是临时目录中的文件（剪贴板图片），删除文件
		FString TempDir = GetAttachmentTempDir();
		if (PendingAttachments[Index].FilePath.StartsWith(TempDir))
		{
			IFileManager::Get().Delete(*PendingAttachments[Index].FilePath, false, false, true);
		}
		PendingAttachments.RemoveAt(Index);
		RebuildAttachmentPreview();
	}
	return FReply::Handled();
}

void SUEAgentDashboard::ClearAttachments()
{
	FString TempDir = GetAttachmentTempDir();
	for (const auto& Att : PendingAttachments)
	{
		if (Att.FilePath.StartsWith(TempDir))
		{
			IFileManager::Get().Delete(*Att.FilePath, false, false, true);
		}
	}
	PendingAttachments.Empty();
	RebuildAttachmentPreview();
}

// ==================================================================
// 附件预览 UI 重建
// ==================================================================

void SUEAgentDashboard::RebuildAttachmentPreview()
{
	if (!AttachmentPreviewBox.IsValid() || !AttachmentPreviewBorder.IsValid())
	{
		return;
	}

	AttachmentPreviewBox->ClearChildren();

	if (PendingAttachments.Num() == 0)
	{
		AttachmentPreviewBorder->SetVisibility(EVisibility::Collapsed);
		return;
	}

	AttachmentPreviewBorder->SetVisibility(EVisibility::Visible);

	for (int32 i = 0; i < PendingAttachments.Num(); i++)
	{
		const auto& Att = PendingAttachments[i];

		// 图标标识
		FString IconStr = Att.bIsImage ? TEXT("[IMG]") : TEXT("[FILE]");
		FLinearColor IconColor = Att.bIsImage
			? FLinearColor(0.3f, 0.7f, 0.3f)
			: FLinearColor(0.5f, 0.6f, 0.8f);

		// 每个附件卡片
		int32 CapturedIndex = i;
		AttachmentPreviewBox->AddSlot()
		.AutoWidth()
		.Padding(2.0f)
		[
			SNew(SBorder)
			.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.GroupBorder"))
			.Padding(FMargin(6.0f, 3.0f))
			[
				SNew(SHorizontalBox)
				// 图标
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(0.0f, 0.0f, 4.0f, 0.0f)
				[
					SNew(STextBlock)
					.Text(FText::FromString(IconStr))
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
					.ColorAndOpacity(FSlateColor(IconColor))
				]
				// 文件名 (超链接，点击打开) + 大小
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				.Padding(0.0f, 0.0f, 6.0f, 0.0f)
				[
					SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight()
					[
						SNew(SButton)
						.ButtonStyle(&FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("NoBorder"))
						.ContentPadding(FMargin(0.0f))
						.OnClicked_Lambda([CapturedPath = Att.FilePath]() -> FReply
						{
							FPlatformProcess::LaunchFileInDefaultExternalApplication(*CapturedPath);
							return FReply::Handled();
						})
						.ToolTipText(FText::FromString(Att.FilePath))
						.Cursor(EMouseCursor::Hand)
						[
							SNew(STextBlock)
							.Text(FText::FromString(Att.DisplayName))
							.Font(FCoreStyle::GetDefaultFontStyle("Regular", 9))
							.ColorAndOpacity(FSlateColor(FLinearColor(0.4f, 0.7f, 1.0f)))
						]
					]
					+ SVerticalBox::Slot().AutoHeight()
					[
						SNew(STextBlock)
						.Text(FText::FromString(FormatFileSize(Att.FileSize)))
						.Font(FCoreStyle::GetDefaultFontStyle("Regular", 7))
						.ColorAndOpacity(FSlateColor(FLinearColor(0.55f, 0.55f, 0.55f)))
					]
				]
				// 删除按钮
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.VAlign(VAlign_Center)
				[
					SNew(SButton)
					.ButtonStyle(&FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("NoBorder"))
					.ContentPadding(FMargin(2.0f, 0.0f))
					.OnClicked_Lambda([this, CapturedIndex]() { return OnRemoveAttachment(CapturedIndex); })
					.ToolTipText(FUEAgentL10n::Get(TEXT("AttachRemoveTip")))
					[
						SNew(STextBlock)
						.Text(FText::FromString(TEXT("x")))
						.Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
						.ColorAndOpacity(FSlateColor(FLinearColor(0.8f, 0.3f, 0.3f)))
					]
				]
			]
		];
	}
}
