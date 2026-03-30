// Copyright ArtClaw Project. All Rights Reserved.
// 管理面板共享工具 — Python IPC、文件 IO、JSON 解析

#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class FUEAgentManageUtils
{
public:
	/** 通过 IPythonScriptPlugin 执行 Python 并获取 JSON 结果 */
	static FString RunPythonAndCapture(const FString& PythonCode);

	/** 读取文件内容 */
	static bool ReadFileToString(const FString& FilePath, FString& OutContent);

	/** 写入文件内容（自动创建目录） */
	static bool WriteStringToFile(const FString& FilePath, const FString& Content);

	/** 获取平台配置文件路径（通过 artclaw config 驱动，回退到 ~/.openclaw/openclaw.json） */
	static FString GetOpenClawConfigPath();

	/** 获取 ~/.artclaw/config.json 路径 */
	static FString GetArtClawConfigPath();

	/** 获取平台已安装 Skills 目录（通过 artclaw config 驱动） */
	static FString GetOpenClawSkillsDir();

	/** 加载 ~/.artclaw/config.json 并返回 JSON 对象 */
	static TSharedPtr<FJsonObject> LoadArtClawConfig();
};
