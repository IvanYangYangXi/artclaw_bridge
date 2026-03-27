// Copyright ArtClaw Project. All Rights Reserved.

#include "UEAgentManageUtils.h"
#include "IPythonScriptPlugin.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformProcess.h"
#include "Misc/Paths.h"

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

FString FUEAgentManageUtils::GetOpenClawConfigPath()
{
	return FString(FPlatformProcess::UserHomeDir()) / TEXT(".openclaw") / TEXT("openclaw.json");
}

FString FUEAgentManageUtils::GetArtClawConfigPath()
{
	return FString(FPlatformProcess::UserHomeDir()) / TEXT(".artclaw") / TEXT("config.json");
}

FString FUEAgentManageUtils::GetOpenClawSkillsDir()
{
	return FString(FPlatformProcess::UserHomeDir()) / TEXT(".openclaw") / TEXT("skills");
}
