// Copyright ArtClaw Project. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"

/**
 * IAgentPlatformBridge
 *
 * AI Agent 平台通信抽象接口。
 * Dashboard 通过此接口与具体平台（OpenClaw / 未来平台）通信，
 * 不直接依赖任何平台特有的 Python 模块名或协议细节。
 *
 * 当前实现: FOpenClawPlatformBridge (通过 Python ExecCommand 调用 openclaw_bridge.py)
 * 未来扩展: 可添加其他平台实现而无需修改 Dashboard 代码
 */
class IAgentPlatformBridge
{
public:
	virtual ~IAgentPlatformBridge() = default;

	/** 获取平台显示名称 (用于日志和 UI 提示) */
	virtual FString GetPlatformName() const = 0;

	/**
	 * 连接到 AI 平台。
	 * @param StatusOutFile  写入连接结果的临时文件路径 (内容: "ok" 或 "fail")
	 */
	virtual void Connect(const FString& StatusOutFile) = 0;

	/** 断开连接 */
	virtual void Disconnect() = 0;

	/** 取消当前正在进行的 AI 请求 */
	virtual void CancelCurrentRequest() = 0;

	/** 取消当前请求 (停止按钮调用，与 CancelCurrentRequest 等价) */
	virtual void CancelRequest() = 0;

	/**
	 * 异步发送消息给 AI。
	 * 平台实现将 AI 响应写入 ResponseFile，流式内容写入 StreamFile。
	 * Dashboard 通过 FTSTicker 轮询这两个文件。
	 *
	 * @param Message       用户消息 (已转义，可安全嵌入 Python 字符串)
	 * @param ResponseFile  最终响应写入路径
	 */
	virtual void SendMessageAsync(const FString& Message, const FString& ResponseFile) = 0;

	/**
	 * 运行连接诊断。
	 * 结果写入 ReportOutFile。
	 *
	 * @param ReportOutFile  诊断报告写入路径
	 */
	virtual void RunDiagnostics(const FString& ReportOutFile) = 0;

	/**
	 * 收集环境上下文并写入文件。
	 * 连接成功后调用，内容会作为消息发送给 AI。
	 *
	 * @param ContextOutFile  上下文写入路径
	 */
	virtual void CollectEnvironmentContext(const FString& ContextOutFile) = 0;

	/**
	 * 查询连接状态 (发送 Python 检查命令)。
	 * 结果通过 ExecPythonCommand 打印到 Output Log。
	 */
	virtual void QueryStatus() = 0;

	/**
	 * 重置会话 (例如清除 session key)。
	 */
	virtual void ResetSession() = 0;

	/**
	 * 设置当前会话 key（用于会话切换）。
	 * @param SessionKey  新的 session key
	 */
	virtual void SetSessionKey(const FString& SessionKey) = 0;

	/**
	 * 获取当前会话 key。
	 * @return 当前活跃的 session key
	 */
	virtual FString GetSessionKey() const = 0;

	// --- Agent 切换 + 会话管理 (Phase 1+2) ---

	/**
	 * 获取当前 Agent ID。
	 * @return 当前 Agent ID 字符串
	 */
	virtual FString GetAgentId() const = 0;

	/**
	 * 设置当前 Agent ID（切换 Agent）。
	 * 实现应同时 reset session 和清除上下文注入标记。
	 * @param AgentId 新的 Agent ID
	 */
	virtual void SetAgentId(const FString& AgentId) = 0;

	/**
	 * 异步获取可用 Agent 列表。
	 * 结果以 JSON 写入 ResultFile: {"agents": [{"id":"...", "name":"...", "emoji":"..."}]}
	 * @param ResultFile 结果写入路径
	 */
	virtual void ListAgents(const FString& ResultFile) = 0;

	/**
	 * 异步获取指定 session 的聊天历史（从远端 Gateway 拉取）。
	 * 结果以 JSON 写入 HistoryFile: {"messages": [{"sender":"user/assistant", "content":"..."}]}
	 * @param SessionKey 目标 session key
	 * @param HistoryFile 历史写入路径
	 */
	virtual void FetchSessionHistory(const FString& SessionKey, const FString& HistoryFile) = 0;

	/**
	 * UE 启动时会话恢复: 中止 Gateway 上残留的运行 + 清理过期临时文件。
	 * UE 崩溃重启后调用，确保旧的 AI 运行被终止，不会干扰新消息。
	 * 结果写入 StatusOutFile: "ok" / "aborted" / "error:<msg>"
	 * @param StatusOutFile 恢复结果写入路径
	 */
	virtual void RecoverSession(const FString& StatusOutFile) = 0;
};
