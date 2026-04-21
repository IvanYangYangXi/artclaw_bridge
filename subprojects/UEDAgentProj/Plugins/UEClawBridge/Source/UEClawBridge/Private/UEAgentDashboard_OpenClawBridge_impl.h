// Copyright ArtClaw Project. All Rights Reserved. OpenClaw桥接模块 - 连接管理、环境上下文发送、流式响应处理
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// OpenClaw Bridge 连接管理
// ==================================================================

void SUEAgentDashboard::ConnectOpenClawBridge()
{
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("Connecting")));

	// 通过平台桥接连接
	FString TempDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString StatusFile = TempDir / TEXT("_connect_status.txt");
	IFileManager::Get().Delete(*StatusFile, false, false, true);

	PlatformBridge->Connect(StatusFile);

	// 轮询连接结果
	auto Self = SharedThis(this);
	FString CapturedFile = StatusFile;
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedFile](float) -> bool
		{
			if (!FPaths::FileExists(CapturedFile))
			{
				return true;
			}

			FString Status;
			FFileHelper::LoadFileToString(Status, *CapturedFile);
			IFileManager::Get().Delete(*CapturedFile, false, false, true);
			Status.TrimStartAndEndInline();

			if (Status == TEXT("ok"))
			{
				// 立即更新 Subsystem 状态（不等轮询）
				if (Self->CachedSubsystem.IsValid())
				{
					Self->CachedSubsystem->SetConnectionStatus(true);
				}

				// 防止 poll 里的 socket 探测因时序差覆盖刚设置的 connected 状态：
				// 设置宽限期，在此期间轮询跳过状态更新
				Self->ConnectGraceUntil = FPlatformTime::Seconds() + 5.0;

				Self->AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("ConnectOK")));
				// 环境上下文已由 Python 侧 openclaw_chat._enrich_with_context 注入，C++ 不再主动发送
			}
			else
			{
				// 连接失败也要确保状态为 disconnected
				if (Self->CachedSubsystem.IsValid())
				{
					Self->CachedSubsystem->SetConnectionStatus(false);
				}

				Self->AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("ConnectFail")));
			}
			return false;
		}),
		0.5f
	);
}

void SUEAgentDashboard::DisconnectOpenClawBridge()
{
	PlatformBridge->Disconnect();

	bEnvContextPending = false;
	ConnectGraceUntil = 0.0;

	// 立即更新 Subsystem 状态（不等轮询）
	if (CachedSubsystem.IsValid())
	{
		CachedSubsystem->SetConnectionStatus(false);
	}

	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("BridgeDisconnected")));
}

void SUEAgentDashboard::RunDiagnoseConnection()
{
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("RunningHealthCheck")));

	// 诊断结果写入临时文件，然后轮询读取
	FString TempDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString DiagFile = TempDir / TEXT("_diagnose_result.txt");

	// 清除上次结果
	IFileManager::Get().Delete(*DiagFile, false, false, true);

	// 优先使用完整 Health Check，fallback 到平台桥接诊断
	// 强制 reload 确保使用最新代码
	FString PythonCmd = FString::Printf(
		TEXT("import importlib\n"
			 "try:\n"
			 "    import health_check\n"
			 "    importlib.reload(health_check)\n"
			 "    result = health_check.run_health_check()\n"
			 "    with open(r'%s', 'w', encoding='utf-8') as f:\n"
			 "        f.write(result)\n"
			 "except ImportError:\n"
			 "    pass\n"),
		*DiagFile);
	IPythonScriptPlugin::Get()->ExecPythonCommand(*PythonCmd);

	// 如果 health_check 没有生成文件，走平台桥接诊断
	if (!FPaths::FileExists(DiagFile))
	{
		PlatformBridge->RunDiagnostics(DiagFile);
	}

	// 轮询诊断结果文件
	auto Self = SharedThis(this);
	FString CapturedFile = DiagFile;
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedFile](float) -> bool
		{
			if (!FPaths::FileExists(CapturedFile))
			{
				return true; // 继续等待
			}

			FString Content;
			TArray<uint8> DiagBytes;
			if (FFileHelper::LoadFileToArray(DiagBytes, *CapturedFile))
			{
				FUTF8ToTCHAR DiagConverter(reinterpret_cast<const ANSICHAR*>(DiagBytes.GetData()), DiagBytes.Num());
				Content = FString(DiagConverter.Length(), DiagConverter.Get());
				IFileManager::Get().Delete(*CapturedFile, false, false, true);
				Self->AddMessage(TEXT("system"), Content);
			}
			return false;
		}),
		0.5f
	);
}

// ==================================================================
// 连接成功后发送环境上下文
// ==================================================================

void SUEAgentDashboard::SendEnvironmentContext()
{
	// 收集静态环境信息并通过 Python 发送给 AI
	// 这些信息在会话期间不会变化，帮助 AI 了解当前工作环境
	FString TempDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString ContextFile = TempDir / TEXT("_env_context.txt");
	IFileManager::Get().Delete(*ContextFile, false, false, true);

	PlatformBridge->CollectEnvironmentContext(ContextFile);

	// 轮询等待 context 文件生成，然后作为消息发送给 AI
	auto Self = SharedThis(this);
	FString CapturedFile = ContextFile;
	FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedFile](float) -> bool
		{
			if (!FPaths::FileExists(CapturedFile))
			{
				return true; // 继续等待
			}

			FString ContextMsg;
			TArray<uint8> RawBytes;
			if (FFileHelper::LoadFileToArray(RawBytes, *CapturedFile))
			{
				FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
				ContextMsg = FString(Converter.Length(), Converter.Get());
			}
			IFileManager::Get().Delete(*CapturedFile, false, false, true);

			if (!ContextMsg.IsEmpty())
			{
				// 如果 AI 正在回复中，不要打断 — 环境上下文已由 Python _enrich_with_briefing 注入，跳过即可
				if (!Self->bIsWaitingForResponse)
				{
					Self->SendToOpenClaw(ContextMsg);
				}
			}
			return false;
		}),
		0.5f
	);
}

// ==================================================================
// 流式事件行解析 (供轮询和恢复接收共用)
// ==================================================================

void SUEAgentDashboard::ProcessStreamEventLine(const FString& Line)
{
	if (Line.IsEmpty()) return;

	TSharedPtr<FJsonObject> JsonObj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Line);
	if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
	{
		return;
	}

	FString EventType = JsonObj->GetStringField(TEXT("type"));

	if (EventType == TEXT("thinking"))
	{
		FString EventText = JsonObj->GetStringField(TEXT("text"));
		if (!EventText.IsEmpty())
		{
			UpdateStreamingMessage(TEXT("thinking"), EventText);
		}
	}
	else if (EventType == TEXT("delta"))
	{
		FString EventText = JsonObj->GetStringField(TEXT("text"));
		if (!EventText.IsEmpty())
		{
			UpdateStreamingMessage(TEXT("assistant"), EventText);
		}
	}
	else if (EventType == TEXT("tool_call"))
	{
		FString ToolName = JsonObj->GetStringField(TEXT("tool_name"));
		FString ToolId   = JsonObj->GetStringField(TEXT("tool_id"));

		// 序列化 arguments 对象为字符串
		FString ArgsStr;
		const TSharedPtr<FJsonObject>* ArgsObj = nullptr;
		if (JsonObj->TryGetObjectField(TEXT("arguments"), ArgsObj) && ArgsObj)
		{
			TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&ArgsStr);
			FJsonSerializer::Serialize(ArgsObj->ToSharedRef(), Writer);
		}

		if (!ToolName.IsEmpty())
		{
			AddToolCallMessage(ToolName, ToolId, ArgsStr);
		}
	}
	else if (EventType == TEXT("tool_result"))
	{
		FString ToolName = JsonObj->GetStringField(TEXT("tool_name"));
		FString ToolId   = JsonObj->GetStringField(TEXT("tool_id"));
		FString Content  = JsonObj->GetStringField(TEXT("content"));
		bool bIsError    = JsonObj->GetBoolField(TEXT("is_error"));

		if (!ToolId.IsEmpty())
		{
			AddToolResultMessage(ToolName, ToolId, Content, bIsError);
		}
	}
	else if (EventType == TEXT("usage"))
	{
		const TSharedPtr<FJsonObject>* UsageObj = nullptr;
		if (JsonObj->TryGetObjectField(TEXT("usage"), UsageObj) && UsageObj)
		{
			// 优先用 inputTokens（真实上下文大小），fallback 到 totalTokens
			int32 Tokens = 0;
			if (!(*UsageObj)->TryGetNumberField(TEXT("inputTokens"), Tokens) || Tokens <= 0)
			{
				(*UsageObj)->TryGetNumberField(TEXT("totalTokens"), Tokens);
			}
			if (Tokens > 0)
			{
				LastTotalTokens = Tokens;
			}
		}
	}
	else if (EventType == TEXT("tool_use_text"))
	{
		// 已有结构化 tool_call/tool_result 卡片，跳过旧文本摘要
	}
	else if (EventType == TEXT("session_key"))
	{
		FString Key = JsonObj->GetStringField(TEXT("key"));
		if (!Key.IsEmpty() && SessionEntries.IsValidIndex(ActiveSessionIndex))
		{
			SessionEntries[ActiveSessionIndex].SessionKey = Key;
			SaveLastSession();
		}
	}
}

// ==================================================================
// 读取 stream.jsonl 新增行并通过 ProcessStreamEventLine 分发
// ==================================================================

void SUEAgentDashboard::ReadAndProcessStreamLines(const FString& StreamFilePath)
{
	if (!FPaths::FileExists(StreamFilePath)) return;

	TArray<uint8> RawBytes;
	if (!FFileHelper::LoadFileToArray(RawBytes, *StreamFilePath)) return;

	FUTF8ToTCHAR Converter(reinterpret_cast<const ANSICHAR*>(RawBytes.GetData()), RawBytes.Num());
	FString StreamContent = FString(Converter.Length(), Converter.Get());
	TArray<FString> Lines;
	StreamContent.ParseIntoArrayLines(Lines);

	for (int32 i = StreamLinesRead; i < Lines.Num(); i++)
	{
		ProcessStreamEventLine(Lines[i]);
	}
	StreamLinesRead = Lines.Num();
}

// ==================================================================
// OpenClaw Gateway 通信 (阶段 3) — 通过 Python Bridge
// ==================================================================

void SUEAgentDashboard::SendToOpenClaw(const FString& UserMessage)
{
	// 如果上一个请求还在进行，先取消它（停止旧的轮询定时器）
	if (bIsWaitingForResponse)
	{
		// 停止旧的 poll timer
		if (PollTimerHandle.IsValid())
		{
			FTSTicker::GetCoreTicker().RemoveTicker(PollTimerHandle);
			PollTimerHandle.Reset();
		}
	}

	bIsWaitingForResponse = true;
	StreamLinesRead = 0;
	bHasStreamingMessage = false;
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("Thinking")));

	// 临时文件路径 — Python 写入响应，C++ 读取
	// 消息内容由 SendMessageAsync 通过临时文件传递（不在此处转义）
	FString TempDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString ResponseFile = TempDir / TEXT("_openclaw_response.txt");
	FString StreamFile   = TempDir / TEXT("_openclaw_response_stream.jsonl");

	// 清除上次响应文件
	IFileManager::Get().Delete(*ResponseFile, false, false, true);
	IFileManager::Get().Delete(*StreamFile,   false, false, true);

	// 通过平台桥接异步发送（消息通过临时文件传递，避免字符串拼接问题）
	PlatformBridge->SendMessageAsync(UserMessage, ResponseFile);

	// 启动定时器轮询临时文件
	auto Self = SharedThis(this);
	FString CapturedResponseFile = ResponseFile;
	FString CapturedStreamFile = StreamFile;
	PollTimerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateLambda([Self, CapturedResponseFile, CapturedStreamFile](float DeltaTime) -> bool
		{
			if (Self->bIsBeingDestroyed || !Self->bIsWaitingForResponse)
			{
				return false;
			}

			// --- 流式文件轮询: 读取新增行并实时显示 ---
			Self->ReadAndProcessStreamLines(CapturedStreamFile);

			// --- 最终响应文件轮询 ---
			if (!FPaths::FileExists(CapturedResponseFile))
			{
				return true; // 继续等待
			}

			// 读取响应（UTF-8）
			FString ResponseContent;
			TArray<uint8> RespBytes;
			if (FFileHelper::LoadFileToArray(RespBytes, *CapturedResponseFile))
			{
				FUTF8ToTCHAR RespConverter(reinterpret_cast<const ANSICHAR*>(RespBytes.GetData()), RespBytes.Num());
				ResponseContent = FString(RespConverter.Length(), RespConverter.Get());

				// 删除临时文件
				IFileManager::Get().Delete(*CapturedResponseFile, false, false, true);
				IFileManager::Get().Delete(*CapturedStreamFile, false, false, true);

				// 处理响应
				Self->HandlePythonResponse(ResponseContent);
			}

			return false; // 停止轮询
		}),
		0.25f // 每 0.25 秒检查一次（流式需要更快）
	);
}

void SUEAgentDashboard::UpdateStreamingMessage(const FString& Sender, const FString& Content)
{
	if (Content.IsEmpty()) return;

	// 流式消息统一用 "streaming" 标识，以区分最终回复的颜色
	FString StreamSender = (Sender == TEXT("thinking")) ? TEXT("thinking") : TEXT("streaming");

	if (!bHasStreamingMessage)
	{
		// 替换 "Thinking..." 消息 — 从末尾往前查找（跳过 tool 消息）
		for (int32 i = Messages.Num() - 1; i >= 0; --i)
		{
			if (Messages[i].Content == FUEAgentL10n::GetStr(TEXT("Thinking"))
				&& Messages[i].Sender == TEXT("system"))
			{
				Messages.RemoveAt(i);
				break;
			}
			// 只跳过 tool 消息，遇到其他类型就停止
			if (Messages[i].Sender != TEXT("tool_call")
				&& Messages[i].Sender != TEXT("tool_result"))
			{
				break;
			}
		}

		bHasStreamingMessage = true;
	}

	// 查找末尾的流式消息并追加内容
	for (int32 i = Messages.Num() - 1; i >= 0; --i)
	{
		if (Messages[i].Sender == StreamSender)
		{
			Messages[i].Content += Content;
			RebuildMessageList();
			return;
		}
		// 遇到其他非 tool 消息，停止查找
		if (Messages[i].Sender != TEXT("tool_call")
			&& Messages[i].Sender != TEXT("tool_result"))
		{
			break;
		}
	}

	// 没有找到现有流式消息，创建新消息
	FChatMessage Msg;
	Msg.Sender = StreamSender;
	Msg.Content = Content;
	Msg.Timestamp = FDateTime::Now();
	Messages.Add(MoveTemp(Msg));
	RebuildMessageList();
}

// ==================================================================
// 恢复接收中断的 AI 回复
// ==================================================================

void SUEAgentDashboard::ResumeReceiving()
{
	// 如果当前已经在正常轮询中，不需要恢复
	if (bIsWaitingForResponse && PollTimerHandle.IsValid())
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("StillWaiting")));
		return;
	}

	// 确保停止旧的轮询状态
	if (PollTimerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(PollTimerHandle);
		PollTimerHandle.Reset();
	}
	bIsWaitingForResponse = false;
	bHasStreamingMessage = false;
	StreamLinesRead = 0;

	FString TempDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge");
	FString StreamFile   = TempDir / TEXT("_openclaw_response_stream.jsonl");
	FString ResponseFile = TempDir / TEXT("_openclaw_response.txt");

	// --- 快速路径: response.txt 已存在 → AI 已回复完，直接读取 ---
	if (FPaths::FileExists(ResponseFile))
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("ResumeReceiving")));

		// 先读流式内容（tool 调用等中间信息）
		ReadAndProcessStreamLines(StreamFile);

		TArray<uint8> RespBytes;
		if (FFileHelper::LoadFileToArray(RespBytes, *ResponseFile))
		{
			FUTF8ToTCHAR RespConverter(reinterpret_cast<const ANSICHAR*>(RespBytes.GetData()), RespBytes.Num());
			FString ResponseContent = FString(RespConverter.Length(), RespConverter.Get());

			IFileManager::Get().Delete(*ResponseFile, false, false, true);
			IFileManager::Get().Delete(*StreamFile,   false, false, true);

			HandlePythonResponse(ResponseContent);
			AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("ResumeComplete")));
		}
		return;
	}

	// --- 通用路径: 从 Gateway 拉取完整会话历史 ---
	// 清理残留的临时文件（避免下次误判）
	IFileManager::Get().Delete(*StreamFile, false, false, true);

	FString SessionKey;
	if (SessionEntries.IsValidIndex(ActiveSessionIndex))
	{
		SessionKey = SessionEntries[ActiveSessionIndex].SessionKey;
	}
	if (SessionKey.IsEmpty())
	{
		SessionKey = PlatformBridge->GetSessionKey();
	}
	if (SessionKey.IsEmpty())
	{
		AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("ResumeNoData")));
		return;
	}

	// 清空当前消息，用 Gateway 完整历史替换
	Messages.Empty();
	RebuildMessageList();
	AddMessage(TEXT("system"), FUEAgentL10n::GetStr(TEXT("LoadingHistory")));
	LoadSessionHistory(SessionKey);
}
