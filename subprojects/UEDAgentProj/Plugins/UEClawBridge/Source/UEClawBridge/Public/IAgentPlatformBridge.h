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
};
