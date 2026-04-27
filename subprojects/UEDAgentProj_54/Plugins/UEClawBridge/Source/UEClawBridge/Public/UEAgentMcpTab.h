// Copyright ArtClaw Project. All Rights Reserved.
// MCP Tab — 全局 MCP Server 管理（状态/连接/启用/禁用/安装）

#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "Widgets/Views/SListView.h"

class SUEAgentMcpTab : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SUEAgentMcpTab) {}
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	void Refresh();

private:
	struct FMcpServerEntry
	{
		FString ServerId;
		FString DisplayName;
		FString Type;           // websocket / sse / stdio
		FString Url;            // ws://... or command string
		FString Command;        // stdio command (e.g. "npx @mcp/xxx")
		TArray<FString> Args;   // stdio args
		bool bEnabled = true;
		bool bConnected = false;
		int32 ToolCount = 0;
	};
	typedef TSharedPtr<FMcpServerEntry> FMcpServerEntryPtr;

	void RefreshData();
	TSharedRef<SWidget> BuildContent();
	TSharedRef<ITableRow> GenerateRow(
		FMcpServerEntryPtr Item, const TSharedRef<STableViewBase>& OwnerTable);

	void ParseMcpConfig(const FString& JsonStr, const FString& ConfigKey);

	/** 按 dot-separated key 路径遍历 JSON 对象树，返回目标节点 */
	static TSharedPtr<FJsonObject> TraverseJsonPath(
		TSharedPtr<FJsonObject> Root, const FString& DotPath);

	void OnEnableChanged(ECheckBoxState NewState, FMcpServerEntryPtr Item);
	void SetServerEnabled(const FString& ServerId, bool bEnabled);
	FReply OnAddServerClicked();

	/** 将新 server 写入平台配置文件 */
	void WriteNewServer(const FString& Id, const FString& Type,
		const FString& Url, const FString& Command);

	TArray<FMcpServerEntryPtr> Servers;
	TSharedPtr<SListView<FMcpServerEntryPtr>> ServerListView;
	TSharedPtr<SVerticalBox> ContentBox;

	/** MCP Server 配置在 JSON 文件中的 key 路径 (dot-separated) */
	FString CachedConfigKey;
};
