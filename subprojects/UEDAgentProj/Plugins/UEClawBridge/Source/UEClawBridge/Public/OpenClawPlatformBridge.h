// Copyright ArtClaw Project. All Rights Reserved.

#pragma once

#include "IAgentPlatformBridge.h"

/**
 * FOpenClawPlatformBridge
 *
 * OpenClaw 平台的 IAgentPlatformBridge 实现。
 * 通过 IPythonScriptPlugin::ExecPythonCommand 调用 openclaw_bridge.py。
 *
 * 所有 Python 模块名和函数调用集中在此类中，
 * Dashboard 不再直接拼接 Python 字符串。
 */
class FOpenClawPlatformBridge : public IAgentPlatformBridge
{
public:
	virtual FString GetPlatformName() const override { return TEXT("OpenClaw"); }

	virtual void Connect(const FString& StatusOutFile) override;
	virtual void Disconnect() override;
	virtual void CancelCurrentRequest() override;
	virtual void CancelRequest() override;
	virtual void SendMessageAsync(const FString& Message, const FString& ResponseFile) override;
	virtual void RunDiagnostics(const FString& ReportOutFile) override;
	virtual void CollectEnvironmentContext(const FString& ContextOutFile) override;
	virtual void QueryStatus() override;
	virtual void ResetSession() override;
	virtual void SetSessionKey(const FString& SessionKey) override;
	virtual FString GetSessionKey() const override;

	// --- Agent 切换 + 会话管理 ---
	virtual FString GetAgentId() const override;
	virtual void SetAgentId(const FString& AgentId) override;
	virtual void ListAgents(const FString& ResultFile) override;
	virtual void FetchSessionHistory(const FString& SessionKey, const FString& HistoryFile) override;
	virtual void RecoverSession(const FString& StatusOutFile) override;

private:
	/** 执行 Python 命令的辅助方法 */
	void ExecPython(const FString& Code) const;
};
