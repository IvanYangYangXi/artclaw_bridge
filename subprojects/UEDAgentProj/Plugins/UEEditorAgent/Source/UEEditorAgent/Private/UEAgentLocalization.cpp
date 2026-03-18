// UEAgentLocalization.cpp — 中英文本注册与运行时切换
#include "UEAgentLocalization.h"

bool FUEAgentL10n::bInitialized = false;
EUEAgentLanguage FUEAgentL10n::CurrentLanguage = EUEAgentLanguage::Chinese;
TMap<FString, FString> FUEAgentL10n::ZhTexts;
TMap<FString, FString> FUEAgentL10n::EnTexts;

void FUEAgentL10n::Reg(const FString& Key, const FString& Zh, const FString& En)
{
	ZhTexts.Add(Key, Zh);
	EnTexts.Add(Key, En);
}

void FUEAgentL10n::Initialize()
{
	if (bInitialized) return;
	bInitialized = true;

	// ==================================================================
	// 状态栏
	// ==================================================================
	Reg(TEXT("VersionLabel"),        TEXT("版本: "),                    TEXT("Version: "));
	Reg(TEXT("ServerLabel"),         TEXT("服务器: "),                  TEXT("Server: "));
	Reg(TEXT("StatusAreaTitle"),     TEXT("Agent 状态"),                TEXT("Agent Status"));
	Reg(TEXT("Connected"),          TEXT("已连接"),                    TEXT("Connected"));
	Reg(TEXT("Disconnected"),       TEXT("未连接"),                    TEXT("Disconnected"));
	Reg(TEXT("ConnectedDot"),       TEXT("● 已连接"),                  TEXT("● Connected"));
	Reg(TEXT("DisconnectedDot"),    TEXT("○ 未连接"),                  TEXT("○ Disconnected"));
	Reg(TEXT("VersionUnknown"),     TEXT("未知"),                      TEXT("Unknown"));
	Reg(TEXT("ServerNotStarted"),   TEXT("未启动"),                    TEXT("Not started"));
	Reg(TEXT("StatsFormat"),        TEXT("活跃连接: %d  |  消息: %d"), TEXT("Active Connections: %d  |  Messages: %d"));

	// ==================================================================
	// 按钮
	// ==================================================================
	Reg(TEXT("ConnectBtn"),         TEXT("连接"),                      TEXT("Connect"));
	Reg(TEXT("ConnectTip"),         TEXT("连接到 OpenClaw 网关"),      TEXT("Connect to OpenClaw Gateway"));
	Reg(TEXT("DisconnectBtn"),      TEXT("断开"),                      TEXT("Disconnect"));
	Reg(TEXT("DisconnectTip"),      TEXT("断开 OpenClaw 网关连接"),    TEXT("Disconnect from OpenClaw Gateway"));
	Reg(TEXT("DiagnoseBtn"),        TEXT("诊断"),                      TEXT("Diagnose"));
	Reg(TEXT("DiagnoseTip"),        TEXT("运行连接诊断"),              TEXT("Run connection diagnostics"));
	Reg(TEXT("ViewLogsBtn"),        TEXT("日志"),                      TEXT("Logs"));
	Reg(TEXT("ViewLogsTip"),        TEXT("打开输出日志"),              TEXT("Open Output Log"));
	Reg(TEXT("SendBtn"),            TEXT("发送"),                      TEXT("Send"));
	Reg(TEXT("SendTip"),            TEXT("发送消息"),                  TEXT("Send message"));
	Reg(TEXT("NewChatBtn"),         TEXT("+ 新会话"),                  TEXT("+ New Chat"));
	Reg(TEXT("NewChatTip"),         TEXT("开始新会话 (/new)"),         TEXT("Start a new conversation (/new)"));
	Reg(TEXT("CreateSkillBtn"),     TEXT("创建 Skill"),                TEXT("Create Skill"));
	Reg(TEXT("CreateSkillTip"),     TEXT("通过自然语言描述创建 ArtClaw Skill"), TEXT("Create a new ArtClaw Skill via natural language description"));

	// ==================================================================
	// 快捷输入
	// ==================================================================
	Reg(TEXT("QuickInputTitle"),    TEXT("快捷输入"),                  TEXT("Quick Inputs"));
	Reg(TEXT("AddQuickInputBtn"),   TEXT("+ 添加"),                    TEXT("+ Add"));
	Reg(TEXT("AddQuickInputTip"),   TEXT("添加新的快捷输入"),          TEXT("Add a new quick input"));
	Reg(TEXT("NoQuickInputs"),      TEXT("暂无快捷输入，点击「+ 添加」创建一个。"), TEXT("No quick inputs yet. Click '+ Add' to create one."));
	Reg(TEXT("EditQuickInputBtn"),  TEXT("e"),                         TEXT("e"));
	Reg(TEXT("EditQuickInputTip"),  TEXT("编辑此快捷输入"),            TEXT("Edit this quick input"));
	Reg(TEXT("DeleteQuickInputBtn"),TEXT("x"),                         TEXT("x"));
	Reg(TEXT("DeleteQuickInputTip"),TEXT("删除此快捷输入"),            TEXT("Delete this quick input"));
	Reg(TEXT("EditQuickInputTitle"),TEXT("编辑快捷输入"),              TEXT("Edit Quick Input"));
	Reg(TEXT("QINameLabel"),        TEXT("名称（显示在按钮上）:"),     TEXT("Name (displayed on button):"));
	Reg(TEXT("QIContentLabel"),     TEXT("内容（填入聊天框）:"),       TEXT("Content (filled into chat):"));
	Reg(TEXT("QISaveBtn"),          TEXT("保存"),                      TEXT("Save"));
	Reg(TEXT("QICancelBtn"),        TEXT("取消"),                      TEXT("Cancel"));
	Reg(TEXT("ConfirmDeleteQI"),    TEXT("删除快捷输入 \"{0}\"？"),    TEXT("Delete quick input \"{0}\"?"));

	// ==================================================================
	// 输入框提示
	// ==================================================================
	Reg(TEXT("InputHintDefault"),   TEXT("向 AI 提问... (Enter 发送, / 查看命令)"),                          TEXT("Ask AI anything... (Enter to send, / for commands)"));
	Reg(TEXT("InputHintEnter"),     TEXT("向 AI 提问... (Enter 发送, Shift+Enter 换行, / 查看命令)"),        TEXT("Ask AI anything... (Enter to send, Shift+Enter for newline, / for commands)"));
	Reg(TEXT("InputHintCtrlEnter"), TEXT("向 AI 提问... (Ctrl+Enter 发送, Enter 换行, / 查看命令)"),         TEXT("Ask AI anything... (Ctrl+Enter to send, Enter for newline, / for commands)"));
	Reg(TEXT("EnterToSendLabel"),   TEXT("Enter 发送"),                TEXT("Enter to Send"));

	// ==================================================================
	// 聊天消息
	// ==================================================================
	Reg(TEXT("SenderYou"),          TEXT("你"),                        TEXT("You"));
	Reg(TEXT("SenderAI"),           TEXT("AI 助手"),                   TEXT("AI Agent"));
	Reg(TEXT("SenderSystem"),       TEXT("系统"),                      TEXT("System"));

	Reg(TEXT("WelcomeMsg"),         TEXT("你好！我是 UE Claw Bridge AI 助手。\n\n输入 / 查看可用命令，或直接向我提问。"),
	                                TEXT("Hello! I'm the UE Claw Bridge AI Assistant.\n\nType / to see available commands, or ask me anything."));

	Reg(TEXT("Thinking"),           TEXT("思考中..."),                 TEXT("Thinking..."));
	Reg(TEXT("EmptyResponse"),      TEXT("AI 返回了空回复。"),         TEXT("Empty response from AI."));
	Reg(TEXT("NewChatStarted"),     TEXT("已开始新会话。"),            TEXT("New conversation started."));
	Reg(TEXT("ChatCleared"),        TEXT("聊天已清空。"),              TEXT("Chat cleared."));
	Reg(TEXT("RequestCancelled"),   TEXT("请求已取消，可以继续聊天。"),TEXT("Request cancelled. You can continue chatting."));
	Reg(TEXT("NothingToCancel"),    TEXT("没有正在进行的请求。"),      TEXT("Nothing to cancel."));
	Reg(TEXT("StillWaiting"),       TEXT("仍在等待 AI 回复... (输入 /cancel 可取消)"), TEXT("Still waiting for AI response... (type /cancel to abort)"));
	Reg(TEXT("Connecting"),         TEXT("正在连接..."),               TEXT("Connecting..."));
	Reg(TEXT("RunningHealthCheck"), TEXT("正在运行环境健康检查..."),    TEXT("Running environment health check..."));
	Reg(TEXT("ConnectOK"),          TEXT("OpenClaw Bridge: 已连接。"), TEXT("OpenClaw Bridge: Connected."));
	Reg(TEXT("ConnectFail"),        TEXT("OpenClaw Bridge: 连接失败。\n检查: 1) OpenClaw 是否运行  2) 网关端口 18789  3) /diagnose"),
	                                TEXT("OpenClaw Bridge: Connection failed.\nCheck: 1) OpenClaw is running  2) Gateway port 18789  3) /diagnose"));
	Reg(TEXT("BridgeDisconnected"), TEXT("OpenClaw Bridge 已断开。"),  TEXT("OpenClaw Bridge disconnected."));
	Reg(TEXT("McpConnected"),       TEXT("MCP 客户端已连接。"),        TEXT("MCP client connected."));
	Reg(TEXT("McpDisconnected"),    TEXT("MCP 客户端已断开。"),        TEXT("MCP client disconnected."));
	Reg(TEXT("PleaseConnectFirst"), TEXT("请先连接 AI (/connect)"),    TEXT("Please connect to AI first (/connect)"));
	Reg(TEXT("CreateSkillPrompt"),  TEXT("Create an artclaw skill: "),  TEXT("Create an artclaw skill: "));  // 指令保持英文

	// ==================================================================
	// /status 输出
	// ==================================================================
	Reg(TEXT("StatusFormat"),       TEXT("MCP 客户端: {0}\nMCP 服务器: {1}\n消息数: {2}\n发送模式: {3}"),
	                                TEXT("MCP Client: {0}\nMCP Server: {1}\nMessages: {2}\nSend Mode: {3}"));
	Reg(TEXT("EnterToSend"),        TEXT("Enter 发送"),                TEXT("Enter to Send"));
	Reg(TEXT("CtrlEnterToSend"),    TEXT("Ctrl+Enter 发送"),           TEXT("Ctrl+Enter to Send"));

	// ==================================================================
	// 语言切换
	// ==================================================================
	Reg(TEXT("LangToggleTip"),      TEXT("切换到 English"),            TEXT("Switch to 中文"));
	Reg(TEXT("LangZh"),             TEXT("中"),                        TEXT("中"));
	Reg(TEXT("LangEn"),             TEXT("En"),                        TEXT("En"));
}

FText FUEAgentL10n::Get(const FString& Key)
{
	Initialize();
	const TMap<FString, FString>& Map = (CurrentLanguage == EUEAgentLanguage::Chinese) ? ZhTexts : EnTexts;
	const FString* Found = Map.Find(Key);
	if (Found)
	{
		return FText::FromString(*Found);
	}
	// Fallback: 返回 Key 本身（方便调试发现遗漏）
	return FText::FromString(Key);
}

FString FUEAgentL10n::GetStr(const FString& Key)
{
	Initialize();
	const TMap<FString, FString>& Map = (CurrentLanguage == EUEAgentLanguage::Chinese) ? ZhTexts : EnTexts;
	const FString* Found = Map.Find(Key);
	return Found ? *Found : Key;
}

void FUEAgentL10n::SetLanguage(EUEAgentLanguage Lang)
{
	CurrentLanguage = Lang;
}

EUEAgentLanguage FUEAgentL10n::GetLanguage()
{
	return CurrentLanguage;
}

void FUEAgentL10n::ToggleLanguage()
{
	CurrentLanguage = (CurrentLanguage == EUEAgentLanguage::Chinese)
		? EUEAgentLanguage::English
		: EUEAgentLanguage::Chinese;
}

FText FUEAgentL10n::GetLanguageDisplayName()
{
	return (CurrentLanguage == EUEAgentLanguage::Chinese)
		? FText::FromString(TEXT("中文"))
		: FText::FromString(TEXT("English"));
}
