// Copyright ArtClaw Project. All Rights Reserved.

#include "OpenClawPlatformBridge.h"
#include "CoreMinimal.h"
#include "IPythonScriptPlugin.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"

void FOpenClawPlatformBridge::ExecPython(const FString& Code) const
{
	IPythonScriptPlugin::Get()->ExecPythonCommand(*Code);
}

void FOpenClawPlatformBridge::Connect(const FString& StatusOutFile)
{
	// 检查 MCP Server 端口（仅日志，不阻断）
	ExecPython(
		TEXT("import socket as _s\n")
		TEXT("from bridge_config import get_platform_defaults\n")
		TEXT("_mcp_port = get_platform_defaults().get('mcp_port', 8080)\n")
		TEXT("_sock = _s.socket(_s.AF_INET, _s.SOCK_STREAM)\n")
		TEXT("_sock.settimeout(0.5)\n")
		TEXT("try:\n")
		TEXT("    _sock.connect(('127.0.0.1', _mcp_port))\n")
		TEXT("    print(f'[LogUEAgent] MCP Server(:{_mcp_port}): OK')\n")
		TEXT("except:\n")
		TEXT("    print(f'[LogUEAgent] MCP Server(:{_mcp_port}): not ready')\n")
		TEXT("finally:\n")
		TEXT("    _sock.close()\n")
	);

	// connect() 直接返回 bool（socket 探测，不建立持久连接）
	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import connect as _oc_connect\n")
		TEXT("_ok = _oc_connect()\n")
		TEXT("with open(r'%s', 'w', encoding='utf-8') as _f:\n")
		TEXT("    _f.write('ok' if _ok else 'fail')\n"),
		*StatusOutFile
	);
	ExecPython(PythonCmd);
}

void FOpenClawPlatformBridge::Disconnect()
{
	ExecPython(
		TEXT("from openclaw_chat import shutdown\n")
		TEXT("shutdown()\n")
		TEXT("print('[LogUEAgent] OpenClaw Bridge disconnected')\n")
	);
}

void FOpenClawPlatformBridge::CancelCurrentRequest()
{
	ExecPython(
		TEXT("from openclaw_chat import cancel_current_request\n")
		TEXT("cancel_current_request()\n")
	);
}

void FOpenClawPlatformBridge::CancelRequest()
{
	CancelCurrentRequest();
}

void FOpenClawPlatformBridge::SendMessageAsync(const FString& Message, const FString& ResponseFile)
{
	// 消息内容通过临时文件传递，避免字符串拼接导致的引号/Unicode 问题
	FString MsgFile = FPaths::GetPath(ResponseFile) / TEXT("_openclaw_msg_input.txt");

	FFileHelper::SaveStringToFile(
		Message, *MsgFile,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM
	);

	// send_chat_async_to_file(msg_file, response_file) — 直接传文件路径
	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import send_chat_async_to_file\n")
		TEXT("send_chat_async_to_file(r'%s', r'%s')\n"),
		*MsgFile, *ResponseFile
	);
	ExecPython(PythonCmd);
}

void FOpenClawPlatformBridge::RunDiagnostics(const FString& ReportOutFile)
{
	FString PythonCmd = FString::Printf(
		TEXT("try:\n")
		TEXT("    from openclaw_chat import diagnose_connection\n")
		TEXT("    _report = diagnose_connection()\n")
		TEXT("    with open(r'%s', 'w', encoding='utf-8') as _f:\n")
		TEXT("        _f.write(_report)\n")
		TEXT("except Exception as _e:\n")
		TEXT("    with open(r'%s', 'w', encoding='utf-8') as _f:\n")
		TEXT("        _f.write(f'Diagnose error: {_e}')\n"),
		*ReportOutFile, *ReportOutFile
	);
	ExecPython(PythonCmd);
}

void FOpenClawPlatformBridge::CollectEnvironmentContext(const FString& ContextOutFile)
{
	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import _collect_and_save_context\n")
		TEXT("_collect_and_save_context(r'%s')\n"),
		*ContextOutFile
	);
	ExecPython(PythonCmd);
}

void FOpenClawPlatformBridge::QueryStatus()
{
	ExecPython(
		TEXT("import socket as _s\n")
		TEXT("from bridge_config import get_gateway_config, get_platform_defaults\n")
		TEXT("_mcp_port = get_platform_defaults().get('mcp_port', 8080)\n")
		TEXT("_sock = _s.socket(_s.AF_INET, _s.SOCK_STREAM)\n")
		TEXT("_sock.settimeout(0.5)\n")
		TEXT("_mcp_ok = False\n")
		TEXT("try:\n")
		TEXT("    _sock.connect(('127.0.0.1', _mcp_port))\n")
		TEXT("    _mcp_ok = True\n")
		TEXT("except: pass\n")
		TEXT("finally: _sock.close()\n")
		TEXT("from openclaw_chat import connect as _oc_connect\n")
		TEXT("_oc_ok = _oc_connect()\n")
		TEXT("_gw = get_gateway_config()\n")
		TEXT("_gw_port = _gw.get('port', 18789)\n")
		TEXT("print(f'[LogUEAgent] MCP Server(:{_mcp_port})={\"OK\" if _mcp_ok else \"DOWN\"}, "
		     "Gateway(:{_gw_port})={\"Connected\" if _oc_ok else \"Disconnected\"}')\n")
	);
}

void FOpenClawPlatformBridge::ResetSession()
{
	ExecPython(
		TEXT("from openclaw_chat import reset_session\n")
		TEXT("reset_session()\n")
	);
}

void FOpenClawPlatformBridge::SetSessionKey(const FString& SessionKey)
{
	FString EscapedKey = SessionKey;
	EscapedKey.ReplaceInline(TEXT("'"), TEXT("\\'"));

	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import set_session_key\n")
		TEXT("set_session_key('%s')\n"),
		*EscapedKey
	);
	ExecPython(PythonCmd);
}

FString FOpenClawPlatformBridge::GetSessionKey() const
{
	FString TempDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString KeyFile = TempDir / TEXT("_session_key.txt");
	IFileManager::Get().Delete(*KeyFile, false, false, true);

	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import get_session_key\n")
		TEXT("_key = get_session_key()\n")
		TEXT("with open(r'%s', 'w', encoding='utf-8') as _f:\n")
		TEXT("    _f.write(_key)\n"),
		*KeyFile
	);
	ExecPython(PythonCmd);

	FString Result;
	FFileHelper::LoadFileToString(Result, *KeyFile);
	IFileManager::Get().Delete(*KeyFile, false, false, true);
	return Result.TrimStartAndEnd();
}

// ==================================================================
// Agent 切换 + 会话管理
// ==================================================================

FString FOpenClawPlatformBridge::GetAgentId() const
{
	FString TempDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString AgentFile = TempDir / TEXT("_agent_id.txt");
	IFileManager::Get().Delete(*AgentFile, false, false, true);

	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import get_agent_id\n")
		TEXT("_aid = get_agent_id()\n")
		TEXT("with open(r'%s', 'w', encoding='utf-8') as _f:\n")
		TEXT("    _f.write(_aid)\n"),
		*AgentFile
	);
	ExecPython(PythonCmd);

	FString Result;
	FFileHelper::LoadFileToString(Result, *AgentFile);
	IFileManager::Get().Delete(*AgentFile, false, false, true);
	return Result.TrimStartAndEnd();
}

void FOpenClawPlatformBridge::SetAgentId(const FString& AgentId)
{
	FString EscapedId = AgentId;
	EscapedId.ReplaceInline(TEXT("'"), TEXT("\\'"));

	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import set_agent_id\n")
		TEXT("set_agent_id('%s')\n"),
		*EscapedId
	);
	ExecPython(PythonCmd);
}

void FOpenClawPlatformBridge::ListAgents(const FString& ResultFile)
{
	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import list_agents\n")
		TEXT("list_agents(r'%s')\n"),
		*ResultFile
	);
	ExecPython(PythonCmd);
}

void FOpenClawPlatformBridge::FetchSessionHistory(const FString& SessionKey, const FString& HistoryFile)
{
	FString EscapedKey = SessionKey;
	EscapedKey.ReplaceInline(TEXT("'"), TEXT("\\'"));

	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import fetch_history\n")
		TEXT("fetch_history('%s', r'%s')\n"),
		*EscapedKey, *HistoryFile
	);
	ExecPython(PythonCmd);
}
