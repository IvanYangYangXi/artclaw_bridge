// Copyright ArtClaw Project. All Rights Reserved.
// 状态栏模块 - 连接状态、版本号、服务器地址、诊断日志
// 所有 include 由 UEAgentDashboard.cpp 统一管理

// ==================================================================
// 状态栏辅助方法
// ==================================================================

FText SUEAgentDashboard::GetConnectionStatusText() const
{
	if (bCachedIsConnected)
	{
		return FUEAgentL10n::Get(TEXT("Connected"));
	}
	return FUEAgentL10n::Get(TEXT("Disconnected"));
}

FSlateColor SUEAgentDashboard::GetConnectionStatusColor() const
{
	return bCachedIsConnected
		? FSlateColor(FLinearColor(0.2f, 0.8f, 0.2f))
		: FSlateColor(FLinearColor(0.6f, 0.6f, 0.6f));
}

FText SUEAgentDashboard::GetVersionText() const
{
	if (CachedSubsystem.IsValid())
	{
		return FText::FromString(CachedSubsystem->GetPluginVersion());
	}
	return FUEAgentL10n::Get(TEXT("VersionUnknown"));
}

FText SUEAgentDashboard::GetServerAddressText() const
{
	if (CachedSubsystem.IsValid())
	{
		FString Address = CachedSubsystem->GetServerAddress();
		if (!Address.IsEmpty())
		{
			return FText::FromString(Address);
		}
	}
	return FUEAgentL10n::Get(TEXT("ServerNotStarted"));
}

FText SUEAgentDashboard::GetStatsText() const
{
	int32 Connections = 0;
	if (CachedSubsystem.IsValid())
	{
		Connections = CachedSubsystem->GetClientCount();
	}
	FString FormatStr = FUEAgentL10n::GetStr(TEXT("StatsFormat"));
	TArray<FStringFormatArg> Args;
	Args.Add(FStringFormatArg(Connections));
	Args.Add(FStringFormatArg(Messages.Num()));
	return FText::FromString(FString::Format(*FormatStr, Args));
}

FText SUEAgentDashboard::GetStatusSummaryText() const
{
	FString Summary = bCachedIsConnected
		? FUEAgentL10n::GetStr(TEXT("ConnectedDot"))
		: FUEAgentL10n::GetStr(TEXT("DisconnectedDot"));

	// MCP 连接状态
	FString McpState = bCachedMcpReady
		? TEXT("MCP ✓")
		: TEXT("MCP ✗");
	Summary += FString::Printf(TEXT("  |  %s"), *McpState);

	// 显示上下文使用百分比 (任务 5.5)
	if (LastTotalTokens > 0 && ContextWindowSize > 0)
	{
		int32 Pct = FMath::RoundToInt32(100.0f * LastTotalTokens / ContextWindowSize);
		Pct = FMath::Clamp(Pct, 0, 100);

		// 格式化 token 数为 K 单位
		auto FormatK = [](int32 Tokens) -> FString
		{
			if (Tokens >= 1000)
			{
				return FString::Printf(TEXT("%dK"), FMath::RoundToInt32(Tokens / 1000.0f));
			}
			return FString::Printf(TEXT("%d"), Tokens);
		};

		Summary += FString::Printf(TEXT("  |  %s: %d%% (%s/%s)"),
			*FUEAgentL10n::GetStr(TEXT("ContextUsage")),
			Pct,
			*FormatK(LastTotalTokens),
			*FormatK(ContextWindowSize));
	}

	// 显示当前会话名称 (任务 5.4)
	if (!CurrentSessionLabel.IsEmpty())
	{
		Summary += FString::Printf(TEXT("  |  %s"), *CurrentSessionLabel);
	}

	if (CachedSubsystem.IsValid())
	{
		FString Addr = CachedSubsystem->GetServerAddress();
		if (!Addr.IsEmpty())
		{
			Summary += FString::Printf(TEXT("  |  %s"), *Addr);
		}
	}
	return FText::FromString(Summary);
}

// ==================================================================
// 按钮回调 - 状态栏相关
// ==================================================================

FReply SUEAgentDashboard::OnToggleStatusClicked()
{
	bStatusExpanded = !bStatusExpanded;
	if (StatusDetailWidget.IsValid())
	{
		StatusDetailWidget->SetVisibility(
			bStatusExpanded ? EVisibility::Visible : EVisibility::Collapsed);
	}
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnConnectClicked()
{
	ConnectOpenClawBridge();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnDisconnectClicked()
{
	DisconnectOpenClawBridge();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnDiagnoseClicked()
{
	RunDiagnoseConnection();
	return FReply::Handled();
}

FReply SUEAgentDashboard::OnViewLogsClicked()
{
	// 打开日志目录
	FString LogDir = FPaths::ProjectLogDir();
	FPlatformProcess::LaunchFileInDefaultExternalApplication(*LogDir);
	return FReply::Handled();
}