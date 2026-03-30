// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentManageUtils.h"
#include "IPythonScriptPlugin.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformProcess.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"

FString FUEAgentManageUtils::RunPythonAndCapture(const FString& PythonCode)
{
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);

	FString CaptureFile = TempDir / TEXT("_manage_result.json");
	FString TempPyFile = TempDir / TEXT("_manage_cmd.py");
	IFileManager::Get().Delete(*CaptureFile, false, false, true);

	FString CleanScript;
	CleanScript += TEXT("import json, os\n");
	CleanScript += TEXT("_result = None\n");
	CleanScript += FString::Printf(TEXT("_capture_path = r'%s'\n"), *CaptureFile);
	CleanScript += TEXT("try:\n");

	TArray<FString> Lines;
	PythonCode.ParseIntoArrayLines(Lines);
	for (const FString& Line : Lines)
	{
		CleanScript += TEXT("    ") + Line + TEXT("\n");
	}

	CleanScript += TEXT("except Exception as _e:\n");
	CleanScript += TEXT("    _result = {'error': str(_e)}\n");
	CleanScript += TEXT("os.makedirs(os.path.dirname(_capture_path), exist_ok=True)\n");
	CleanScript += TEXT("with open(_capture_path, 'w', encoding='utf-8') as _f:\n");
	CleanScript += TEXT("    json.dump(_result if _result is not None else {}, _f, ensure_ascii=False)\n");

	FFileHelper::SaveStringToFile(CleanScript, *TempPyFile,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);

	FString ExecCmd = FString::Printf(
		TEXT("exec(open(r'%s', encoding='utf-8').read())"), *TempPyFile);
	IPythonScriptPlugin::Get()->ExecPythonCommand(*ExecCmd);

	FString Result;
	if (FFileHelper::LoadFileToString(Result, *CaptureFile))
	{
		IFileManager::Get().Delete(*CaptureFile, false, false, true);
		return Result;
	}
	return TEXT("{}");
}

bool FUEAgentManageUtils::ReadFileToString(const FString& FilePath, FString& OutContent)
{
	return FFileHelper::LoadFileToString(OutContent, *FilePath);
}

bool FUEAgentManageUtils::WriteStringToFile(const FString& FilePath, const FString& Content)
{
	FString Dir = FPaths::GetPath(FilePath);
	IFileManager::Get().MakeDirectory(*Dir, true);
	return FFileHelper::SaveStringToFile(Content, *FilePath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

// ---------------------------------------------------------------------------
// 内部辅助: 读取 artclaw config.json
// ---------------------------------------------------------------------------
static TSharedPtr<FJsonObject> LoadArtClawConfig()
{
	FString ConfigPath = FString(FPlatformProcess::UserHomeDir()) / TEXT(".artclaw") / TEXT("config.json");
	FString JsonStr;
	if (!FFileHelper::LoadFileToString(JsonStr, *ConfigPath))
		return nullptr;

	TSharedPtr<FJsonObject> Obj;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);
	if (!FJsonSerializer::Deserialize(Reader, Obj))
		return nullptr;
	return Obj;
}

// 平台默认路径
static const TCHAR* GetDefaultMcpConfigPath(const FString& PlatformType)
{
	if (PlatformType == TEXT("workbuddy")) return TEXT(".workbuddy/config.json");
	if (PlatformType == TEXT("claude"))    return TEXT(".claude/config.json");
	return TEXT(".openclaw/openclaw.json"); // openclaw 默认
}

static const TCHAR* GetDefaultSkillsDir(const FString& PlatformType)
{
	if (PlatformType == TEXT("workbuddy")) return TEXT(".workbuddy/skills");
	if (PlatformType == TEXT("claude"))    return TEXT(".claude/skills");
	return TEXT(".openclaw/skills"); // openclaw 默认
}

FString FUEAgentManageUtils::GetOpenClawConfigPath()
{
	auto Cfg = LoadArtClawConfig();
	if (Cfg.IsValid())
	{
		// 优先从 mcp.config_path 读取
		auto Mcp = Cfg->GetObjectField(TEXT("mcp"));
		if (Mcp.IsValid())
		{
			FString CfgPath;
			if (Mcp->TryGetStringField(TEXT("config_path"), CfgPath) && !CfgPath.IsEmpty())
			{
				CfgPath.ReplaceInline(TEXT("~"), *FString(FPlatformProcess::UserHomeDir()));
				return CfgPath;
			}
		}
		// 回退到平台默认
		auto Platform = Cfg->GetObjectField(TEXT("platform"));
		if (Platform.IsValid())
		{
			FString PlatformType;
			Platform->TryGetStringField(TEXT("type"), PlatformType);
			return FString(FPlatformProcess::UserHomeDir()) / GetDefaultMcpConfigPath(PlatformType);
		}
	}
	// 最终回退
	return FString(FPlatformProcess::UserHomeDir()) / TEXT(".openclaw") / TEXT("openclaw.json");
}

FString FUEAgentManageUtils::GetArtClawConfigPath()
{
	return FString(FPlatformProcess::UserHomeDir()) / TEXT(".artclaw") / TEXT("config.json");
}

FString FUEAgentManageUtils::GetOpenClawSkillsDir()
{
	auto Cfg = LoadArtClawConfig();
	if (Cfg.IsValid())
	{
		// 优先从 skills.installed_path 读取
		auto Skills = Cfg->GetObjectField(TEXT("skills"));
		if (Skills.IsValid())
		{
			FString Path;
			if (Skills->TryGetStringField(TEXT("installed_path"), Path) && !Path.IsEmpty())
			{
				Path.ReplaceInline(TEXT("~"), *FString(FPlatformProcess::UserHomeDir()));
				return Path;
			}
		}
		// 回退到平台默认
		auto Platform = Cfg->GetObjectField(TEXT("platform"));
		if (Platform.IsValid())
		{
			FString PlatformType;
			Platform->TryGetStringField(TEXT("type"), PlatformType);
			return FString(FPlatformProcess::UserHomeDir()) / GetDefaultSkillsDir(PlatformType);
		}
	}
	// 最终回退
	return FString(FPlatformProcess::UserHomeDir()) / TEXT(".openclaw") / TEXT("skills");
}
