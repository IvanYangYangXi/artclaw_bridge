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
	ExecPython(
		TEXT("import socket\n")
		TEXT("def _check_mcp_ready():\n")
		TEXT("    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n")
		TEXT("    s.settimeout(0.5)\n")
		TEXT("    try:\n")
		TEXT("        s.connect(('127.0.0.1', 8080))\n")
		TEXT("        s.close()\n")
		TEXT("        print('[LogUEAgent] MCP Server: OK')\n")
		TEXT("    except:\n")
		TEXT("        s.close()\n")
		TEXT("        print('[LogUEAgent] MCP Server: not ready yet (init_unreal will start it)')\n")
		TEXT("_check_mcp_ready()\n")
	);

	FString PythonCmd = FString::Printf(
		TEXT("import time\n")
		TEXT("from openclaw_chat import connect, is_connected\n")
		TEXT("connect()\n")
		TEXT("time.sleep(1.5)\n")
		TEXT("status = 'ok' if is_connected() else 'fail'\n")
		TEXT("with open(r'%s', 'w') as f:\n")
		TEXT("    f.write(status)\n"),
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
		TEXT("from openclaw_chat import cancel_current_request; cancel_current_request()")
	);
}

void FOpenClawPlatformBridge::CancelRequest()
{
	CancelCurrentRequest();
}

void FOpenClawPlatformBridge::SendMessageAsync(const FString& Message, const FString& ResponseFile)
{
	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import send_chat_async_to_file; send_chat_async_to_file('%s', r'%s')"),
		*Message, *ResponseFile
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
		TEXT("import socket\n")
		TEXT("_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n")
		TEXT("_s.settimeout(0.5)\n")
		TEXT("mcp_ok = False\n")
		TEXT("try:\n")
		TEXT("    _s.connect(('127.0.0.1', 8080))\n")
		TEXT("    mcp_ok = True\n")
		TEXT("except: pass\n")
		TEXT("finally: _s.close()\n")
		TEXT("from openclaw_chat import is_connected as _oc_connected\n")
		TEXT("oc_ok = _oc_connected()\n")
		TEXT("_mcp_s = 'OK' if mcp_ok else 'DOWN'\n")
		TEXT("_oc_s = 'Connected' if oc_ok else 'Disconnected'\n")
		TEXT("print(f'[LogUEAgent] Status: MCP Server={_mcp_s}, OpenClaw Bridge={_oc_s}')\n")
	);
}

void FOpenClawPlatformBridge::ResetSession()
{
	ExecPython(
		TEXT("try:\n")
		TEXT("    from openclaw_chat import reset_session\n")
		TEXT("    import openclaw_chat as _oc\n")
		TEXT("    reset_session()\n")
		TEXT("except: pass")
	);
}

void FOpenClawPlatformBridge::SetSessionKey(const FString& SessionKey)
{
	FString EscapedKey = SessionKey;
	EscapedKey.ReplaceInline(TEXT("'"), TEXT("\\'"));

	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import set_session_key; set_session_key('%s')"),
		*EscapedKey
	);
	ExecPython(PythonCmd);
}

FString FOpenClawPlatformBridge::GetSessionKey() const
{
	FString TempDir = FPaths::ProjectSavedDir() / TEXT("UEAgent");
	IFileManager::Get().MakeDirectory(*TempDir, true);
	FString KeyFile = TempDir / TEXT("_session_key.txt");
	IFileManager::Get().Delete(*KeyFile, false, false, true);

	FString PythonCmd = FString::Printf(
		TEXT("from openclaw_chat import get_session_key\n")
		TEXT("_key = get_session_key()\n")
		TEXT("with open(r'%s', 'w', encoding='utf-8') as f:\n")
		TEXT("    f.write(_key)\n"),
		*KeyFile
	);
	ExecPython(PythonCmd);

	FString Result;
	FFileHelper::LoadFileToString(Result, *KeyFile);
	IFileManager::Get().Delete(*KeyFile, false, false, true);
	return Result.TrimStartAndEnd();
}
