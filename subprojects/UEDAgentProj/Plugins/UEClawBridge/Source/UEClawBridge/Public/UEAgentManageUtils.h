// Copyright ArtClaw Project. All Rights Reserved.
// 管理面板共享工具 — Python IPC、文件 IO、JSON 解析

#pragma once

#include "CoreMinimal.h"

class FUEAgentManageUtils
{
public:
	/** 通过 IPythonScriptPlugin 执行 Python 并获取 JSON 结果 */
	static FString RunPythonAndCapture(const FString& PythonCode);

	/** 读取文件内容 */
	static bool ReadFileToString(const FString& FilePath, FString& OutContent);

	/** 写入文件内容（自动创建目录） */
	static bool WriteStringToFile(const FString& FilePath, const FString& Content);

	/** 获取 ~/.openclaw/openclaw.json 路径 */
	static FString GetOpenClawConfigPath();

	/** 获取 ~/.artclaw/config.json 路径 */
	static FString GetArtClawConfigPath();

	/** 获取 ~/.openclaw/skills/ 路径 */
	static FString GetOpenClawSkillsDir();
};
