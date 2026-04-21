// UEAgentLocalization.cpp — 中英文本注册与运行时切换
#include "UEAgentLocalization.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/PlatformProcess.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/Culture.h"

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

	// --- 先决定语言：加载用户偏好 > 检测系统语言 ---
	EUEAgentLanguage UserPref;
	if (LoadLanguagePreference(UserPref))
	{
		CurrentLanguage = UserPref;
	}
	else
	{
		CurrentLanguage = DetectSystemLanguage();
	}

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
	Reg(TEXT("StatsFormat"),        TEXT("活跃连接: {0}  |  消息: {1}"), TEXT("Active Connections: {0}  |  Messages: {1}"));
	Reg(TEXT("MsgCountLabel"),      TEXT("消息: "),                    TEXT("Messages: "));

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
	Reg(TEXT("LoadingHistory"),     TEXT("正在加载历史消息..."),       TEXT("Loading conversation history..."));
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
	// 发送按钮等待态 / 停止按钮 / 会话标签 (阶段 5)
	// ==================================================================
	Reg(TEXT("SendBtnWaiting"),     TEXT("等待中..."),                 TEXT("Waiting..."));
	Reg(TEXT("StopBtn"),            TEXT("停止"),                      TEXT("Stop"));
	Reg(TEXT("StopTip"),            TEXT("停止 AI 回答"),              TEXT("Stop AI response"));
	Reg(TEXT("ResumeBtn"),          TEXT("恢复"),                      TEXT("Resume"));
	Reg(TEXT("ResumeTip"),          TEXT("恢复接收中断的 AI 回复"),    TEXT("Resume receiving interrupted AI response"));
	Reg(TEXT("AIStopped"),          TEXT("已停止 AI 回答"),            TEXT("AI response stopped"));
	Reg(TEXT("ResumeReceiving"),    TEXT("正在恢复接收..."),            TEXT("Resuming reception..."));
	Reg(TEXT("ResumeComplete"),     TEXT("已恢复接收完毕。"),           TEXT("Reception resumed and completed."));
	Reg(TEXT("ResumeNoData"),       TEXT("没有未接收的数据。"),         TEXT("No pending data to resume."));
	Reg(TEXT("ResumeContinuing"),   TEXT("已恢复接收，AI 仍在回复中..."), TEXT("Reception resumed, AI still responding..."));
	Reg(TEXT("SessionLabel"),       TEXT("对话"),                      TEXT("Chat"));
	Reg(TEXT("ContextUsage"),       TEXT("上下文"),                    TEXT("Context"));

	// ==================================================================
	// 多会话管理 (任务 5.8)
	// ==================================================================
	Reg(TEXT("SessionMenuTip"),     TEXT("切换会话"),                  TEXT("Switch Session"));
	Reg(TEXT("SessionDeleteTip"),   TEXT("删除会话"),                  TEXT("Delete Session"));
	Reg(TEXT("SessionLoading"),     TEXT("加载中..."),                 TEXT("Loading..."));
	Reg(TEXT("SessionEmpty"),       TEXT("无历史消息"),                TEXT("No history"));
	Reg(TEXT("SessionDeleteConfirm"), TEXT("确定要删除这个会话吗?"),   TEXT("Delete this session?"));
	Reg(TEXT("SessionSwitched"),    TEXT("已切换到会话: {0}"),         TEXT("Switched to session: {0}"));
	Reg(TEXT("SessionDeleted"),     TEXT("会话已删除"),                TEXT("Session deleted"));
	Reg(TEXT("SessionHistoryLoaded"), TEXT("已加载 {0} 条历史消息"),   TEXT("Loaded {0} history messages"));

	// ==================================================================
	// Tool 调用卡片
	// ==================================================================
	Reg(TEXT("ToolParams"),         TEXT("参数:"),                     TEXT("Params:"));
	Reg(TEXT("ToolResult"),         TEXT("结果:"),                     TEXT("Result:"));
	Reg(TEXT("ToolError"),          TEXT("错误:"),                     TEXT("Error:"));

	// ==================================================================
	// 语言切换
	// ==================================================================
	Reg(TEXT("LangToggleTip"),      TEXT("切换到 English"),            TEXT("Switch to 中文"));
	Reg(TEXT("LangZh"),             TEXT("中"),                        TEXT("中"));
	Reg(TEXT("LangEn"),             TEXT("En"),                        TEXT("En"));

	// ==================================================================
	// 附件 (剪贴板图片/文件)
	// ==================================================================
	Reg(TEXT("AttachBtn"),          TEXT("Attach"),                    TEXT("Attach"));
	Reg(TEXT("AttachTip"),          TEXT("添加图片或文件附件 (也可 Ctrl+V 粘贴)"), TEXT("Add image or file attachment (or Ctrl+V to paste)"));
	Reg(TEXT("AttachRemoveTip"),    TEXT("移除此附件"),                TEXT("Remove this attachment"));
	Reg(TEXT("AttachTooLarge"),     TEXT("文件太大 (超过 10MB 限制)"), TEXT("File too large (exceeds 10MB limit)"));
	Reg(TEXT("AttachFileTitle"),    TEXT("选择文件"),                  TEXT("Select File"));

	// ==================================================================
	// ChatPanel (旧面板兼容)
	// ==================================================================
	Reg(TEXT("ClearBtn"),           TEXT("清空"),                      TEXT("Clear"));
	Reg(TEXT("InputHint"),          TEXT("输入消息... (Enter 发送)"),  TEXT("Type a message... (Enter to send)"));
	Reg(TEXT("ChatWelcomeMsg"),     TEXT("你好！我是 UE Claw Bridge AI 助手。\n\n输入 / 查看可用命令，或直接向我提问。"),
	                                TEXT("Hello! I'm the UE Claw Bridge AI Assistant. I can help you with level editing, asset management, and more.\n\nTry asking me to:\n  - List selected actors\n  - Create objects in the scene\n  - Modify material properties\n\nNote: Connect an MCP client to enable AI responses."));
	Reg(TEXT("ChatMsgReceived"),    TEXT("(已收到消息: \"{0}\")\n\n连接 MCP 客户端后，AI 回复将在此显示。"),
	                                TEXT("(Message received: \"{0}\")\n\nAI responses will appear here when an MCP client is connected."));
	Reg(TEXT("ChatMcpConnected"),   TEXT("MCP 客户端已连接。AI 回复现已可用。"), TEXT("MCP client connected. AI responses are now available."));
	Reg(TEXT("ChatMcpDisconnected"),TEXT("MCP 客户端已断开。"),        TEXT("MCP client disconnected."));

	// ==================================================================
	// /help 命令文本
	// ==================================================================
	Reg(TEXT("HelpTitle"),          TEXT("可用命令:"),                 TEXT("Available commands:"));
	Reg(TEXT("HelpSectionConnect"), TEXT("\n  连接:"),                 TEXT("\n  Connection:"));
	Reg(TEXT("HelpSectionChat"),    TEXT("\n  会话:"),                 TEXT("\n  Chat:"));
	Reg(TEXT("HelpSectionAI"),      TEXT("\n  AI 命令:"),              TEXT("\n  AI Commands:"));

	// ==================================================================
	// Slash 命令描述
	// ==================================================================
	Reg(TEXT("SlashConnect"),       TEXT("连接 OpenClaw 网关"),        TEXT("Connect to OpenClaw Gateway"));
	Reg(TEXT("SlashDisconnect"),    TEXT("断开 OpenClaw 网关连接"),    TEXT("Disconnect from OpenClaw Gateway"));
	Reg(TEXT("SlashDiagnose"),      TEXT("运行连接诊断"),              TEXT("Run connection diagnostics"));
	Reg(TEXT("SlashStatus"),        TEXT("显示连接状态"),              TEXT("Show connection status"));
	Reg(TEXT("SlashClear"),         TEXT("清空聊天记录"),              TEXT("Clear chat history"));
	Reg(TEXT("SlashCancel"),        TEXT("取消等待 AI 响应"),          TEXT("Cancel pending AI response"));
	Reg(TEXT("SlashResume"),        TEXT("恢复接收中断的 AI 回复"),    TEXT("Resume receiving interrupted AI response"));
	Reg(TEXT("SlashHelp"),          TEXT("显示所有可用命令"),          TEXT("Show all available commands"));
	Reg(TEXT("SlashNew"),           TEXT("开始新会话"),                TEXT("Start new conversation"));
	Reg(TEXT("SlashCompact"),       TEXT("压缩上下文 (释放 token 空间)"), TEXT("Compact context (free up token space)"));
	Reg(TEXT("SlashReview"),        TEXT("审查选中 Actor / 当前场景"),  TEXT("Review selected Actors / current scene"));
	Reg(TEXT("SlashUndo"),          TEXT("撤销上一步 AI 操作"),        TEXT("Undo last AI operation"));

	// ==================================================================
	// Tab 标题
	// ==================================================================
	Reg(TEXT("DashboardTabTitle"),  TEXT("UE Claw Bridge"),            TEXT("UE Claw Bridge"));

	// ==================================================================
	// 管理面板 (Phase 2-3)
	// ==================================================================
	Reg(TEXT("ManageBtn"),           TEXT("Skills"),                     TEXT("Skills"));
	Reg(TEXT("ManageTip"),           TEXT("打开 Skill 与 MCP 管理面板"), TEXT("Open Skill & MCP management panel"));
	Reg(TEXT("ManageWindowTitle"),   TEXT("Skill 与 MCP 管理"),         TEXT("Skill & MCP Management"));
	Reg(TEXT("ManageTabSkill"),      TEXT("Skill"),                     TEXT("Skills"));
	Reg(TEXT("ManageTabMcp"),        TEXT("MCP"),                       TEXT("MCP"));
	Reg(TEXT("ManageRefreshBtn"),    TEXT("刷新"),                      TEXT("Refresh"));
	Reg(TEXT("ManageMcpStatus"),     TEXT("MCP 服务器: {0}  |  工具: {1}"), TEXT("MCP Server: {0}  |  Tools: {1}"));
	Reg(TEXT("ManageSkillCount"),    TEXT("显示 {0} / {1} 个 Skill"),   TEXT("Showing {0} / {1} Skills"));
	Reg(TEXT("ManagePinTip"),        TEXT("钉选此 Skill (强制注入 AI 上下文)"), TEXT("Pin this Skill (force-inject into AI context)"));
	Reg(TEXT("ManageUnpinTip"),      TEXT("取消钉选"),                  TEXT("Unpin"));
	Reg(TEXT("ManageDetailTip"),     TEXT("查看详情"),                  TEXT("View details"));
	Reg(TEXT("ManageDetailLayer"),   TEXT("层级"),                      TEXT("Layer"));
	Reg(TEXT("ManageDetailSoftware"),TEXT("软件"),                      TEXT("Software"));
	Reg(TEXT("ManageDetailCategory"),TEXT("分类"),                      TEXT("Category"));
	Reg(TEXT("ManageDetailRisk"),    TEXT("风险级别"),                  TEXT("Risk Level"));
	Reg(TEXT("ManageDetailCode"),    TEXT("代码"),                      TEXT("Code"));
	Reg(TEXT("ManageDetailSkillMd"), TEXT("SKILL.md"),                  TEXT("SKILL.md"));
	Reg(TEXT("ManageDetailPath"),    TEXT("文件路径"),                  TEXT("File Path"));
	Reg(TEXT("ManageDetailAuthor"),  TEXT("作者"),                      TEXT("Author"));
	Reg(TEXT("ManageDetailInstalledPath"), TEXT("安装路径"),            TEXT("Installed Path"));
	Reg(TEXT("ManageDetailSourcePath"),    TEXT("源码路径"),            TEXT("Source Path"));
	Reg(TEXT("ManageDetailSourceVer"),     TEXT("源码"),                TEXT("source"));
	Reg(TEXT("ManageOpenInstalledDir"),    TEXT("打开安装目录"),        TEXT("Open Installed Dir"));
	Reg(TEXT("ManageOpenSourceDir"),       TEXT("打开源码目录"),        TEXT("Open Source Dir"));
	Reg(TEXT("ManageOpenPath"),      TEXT("打开所在目录"),              TEXT("Open in Explorer"));
	Reg(TEXT("ManageDetailInstall"), TEXT("安装类型"),                  TEXT("Install Type"));
	Reg(TEXT("ManageFilterLayer"),   TEXT("层级: "),                    TEXT("Layer: "));
	Reg(TEXT("ManageFilterInstall"), TEXT("安装: "),                    TEXT("Install: "));
	Reg(TEXT("ManageFilterDcc"),     TEXT("软件: "),                    TEXT("Software: "));
	Reg(TEXT("ManageFilterDccAll"),  TEXT("全部"),                      TEXT("All"));
	Reg(TEXT("ManageFilterDccUE"),   TEXT("UE"),                        TEXT("UE"));
	Reg(TEXT("ManageFilterDccMaya"), TEXT("Maya"),                      TEXT("Maya"));
	Reg(TEXT("ManageFilterDccMax"),  TEXT("Max"),                       TEXT("Max"));
	Reg(TEXT("ManageFilterDccUniversal"), TEXT("通用"),                 TEXT("Universal"));
	Reg(TEXT("ManageFilterInstalled"),    TEXT("已安装"),               TEXT("Installed"));
	Reg(TEXT("ManageFilterNotInstalled"), TEXT("未安装"),               TEXT("Not Installed"));

	// ==================================================================
	// MCP 管理 (Phase 2 增强)
	// ==================================================================
	Reg(TEXT("ManageMcpSummary"),    TEXT("MCP Server: {0} 个  |  已连接: {1}  |  已启用: {2}"),
	                                 TEXT("MCP Servers: {0}  |  Connected: {1}  |  Enabled: {2}"));
	Reg(TEXT("ManageMcpToolCount"),  TEXT("{0} 个工具"),                TEXT("{0} tools"));
	Reg(TEXT("ManageMcpAddBtn"),     TEXT("+ 添加"),                    TEXT("+ Add"));
	Reg(TEXT("ManageMcpAddTitle"),   TEXT("添加 MCP Server 连接"),      TEXT("Add MCP Server Connection"));
	Reg(TEXT("ManageMcpAddDesc"),    TEXT("添加一个 MCP Server 的连接配置。如需安装新的 MCP Server，请直接在聊天中告诉 AI 你下载的 MCP 地址，AI 会自动完成安装和配置。"),
	                                 TEXT("Add an MCP Server connection. To install a new MCP Server, just tell the AI the download URL in chat — it will handle installation and configuration automatically."));
	Reg(TEXT("ManageMcpAddIdLabel"), TEXT("Server ID (唯一标识):"),     TEXT("Server ID (unique key):"));
	Reg(TEXT("ManageMcpAddUrlLabel"),TEXT("WebSocket URL:"),            TEXT("WebSocket URL:"));
	Reg(TEXT("ManageMcpAddConfirm"), TEXT("添加"),                      TEXT("Add"));
	Reg(TEXT("ManageMcpEnableTip"),  TEXT("启用此 MCP Server"),         TEXT("Enable this MCP Server"));
	Reg(TEXT("ManageMcpDisableTip"), TEXT("禁用此 MCP Server"),         TEXT("Disable this MCP Server"));
	Reg(TEXT("ManageMcpStdio"),      TEXT("stdio 模式"),                TEXT("stdio mode"));
	Reg(TEXT("ManageMcpAddTypeLabel"), TEXT("连接类型:"),               TEXT("Connection type:"));
	Reg(TEXT("ManageMcpAddCmdLabel"), TEXT("启动命令 (stdio):"),        TEXT("Launch command (stdio):"));

	Reg(TEXT("ManageFilterLayerAll"), TEXT("全部"),                    TEXT("All"));
	Reg(TEXT("ManageFilterLayerOfficial"), TEXT("官方"),              TEXT("Official"));
	Reg(TEXT("ManageFilterLayerMarket"), TEXT("市集"),                TEXT("Market"));
	Reg(TEXT("ManageFilterLayerUser"), TEXT("用户"),                  TEXT("User"));
	Reg(TEXT("ManageFilterLayerOpenClaw"), TEXT("OC"),                TEXT("OC"));
	Reg(TEXT("ManageFilterLayerPlatform"), TEXT("其他平台"),           TEXT("Platform"));
	Reg(TEXT("ManageSearchHint"),    TEXT("搜索 Skill 名称/描述..."), TEXT("Search skills..."));
	Reg(TEXT("ManageMcpStatus"),     TEXT("MCP: {0}"),                TEXT("MCP: {0}"));

	// Skill 安装状态
	Reg(TEXT("ManageInstallFull"),    TEXT("运行时"),                    TEXT("Runtime"));
	Reg(TEXT("ManageInstallDoc"),     TEXT("文档"),                      TEXT("Guide"));
	Reg(TEXT("ManageInstallFilterAll"), TEXT("全部"),                    TEXT("All"));

	// Phase 4: 安装/卸载/同步/发布
	Reg(TEXT("ManageInstallNotInstalled"), TEXT("未装"),                TEXT("New"));
	Reg(TEXT("ManageInstallBtn"),    TEXT("安装"),                      TEXT("Install"));
	Reg(TEXT("ManageUninstallBtn"),  TEXT("卸载"),                      TEXT("Del"));
	Reg(TEXT("ManageUpdateBtn"),     TEXT("更新"),                      TEXT("Up"));
	Reg(TEXT("ManageSyncBtn"),       TEXT("全量更新 ({0})"),            TEXT("Update All ({0})"));
	Reg(TEXT("ManagePublishBtn"),    TEXT("发布"),                      TEXT("Pub"));
	Reg(TEXT("ManagePublishTitle"),  TEXT("发布 Skill: {0}"),           TEXT("Publish Skill: {0}"));
	Reg(TEXT("ManagePublishDesc"),   TEXT("将 {0} (v{1}) 发布到项目源码。选择目标层级、软件目录和版本号递增方式。"),
	                                 TEXT("Publish {0} (v{1}) to project source. Choose target layer, software directory and version bump."));
	Reg(TEXT("ManagePublishLayerLabel"), TEXT("目标层级:"),             TEXT("Target Layer:"));
	Reg(TEXT("ManagePublishDccLabel"),   TEXT("软件目录:"),             TEXT("Software Directory:"));
	Reg(TEXT("ManagePublishChangelogLabel"), TEXT("变更说明:"),         TEXT("Changelog:"));

	// ==================================================================
	// Plan 模式 (任务 5.9)
	// ==================================================================
	Reg(TEXT("PlanModeOn"),          TEXT("Plan: ON"),                  TEXT("Plan: ON"));
	Reg(TEXT("PlanModeOff"),         TEXT("Plan: OFF"),                 TEXT("Plan: OFF"));
	Reg(TEXT("PlanModeTip"),         TEXT("Plan 模式: AI 先制定计划再执行"), TEXT("Plan mode: AI creates a plan before executing"));
	Reg(TEXT("PlanTitle"),           TEXT("执行计划"),                  TEXT("Execution Plan"));
	Reg(TEXT("PlanStepPending"),     TEXT("--"),                        TEXT("--"));
	Reg(TEXT("PlanStepRunning"),     TEXT(">>"),                        TEXT(">>"));
	Reg(TEXT("PlanStepDone"),        TEXT("OK"),                        TEXT("OK"));
	Reg(TEXT("PlanStepFailed"),      TEXT("!!"),                        TEXT("!!"));
	Reg(TEXT("PlanStepSkipped"),     TEXT("跳"),                        TEXT("Skip"));
	Reg(TEXT("PlanExecuteAll"),      TEXT("执行全部"),                  TEXT("Execute All"));
	Reg(TEXT("PlanPause"),           TEXT("暂停"),                      TEXT("Pause"));
	Reg(TEXT("PlanResume"),          TEXT("继续"),                      TEXT("Resume"));
	Reg(TEXT("PlanCancel"),          TEXT("取消计划"),                  TEXT("Cancel"));
	Reg(TEXT("PlanDeleteStep"),      TEXT("删除"),                      TEXT("Del"));
	Reg(TEXT("PlanCompleted"),       TEXT("计划执行完毕"),              TEXT("Plan completed"));
	Reg(TEXT("PlanPaused"),          TEXT("计划已暂停"),                TEXT("Plan paused"));
	Reg(TEXT("PlanCancelled"),       TEXT("计划已取消"),                TEXT("Plan cancelled"));
	Reg(TEXT("PlanStepFailedMsg"),   TEXT("步骤执行失败，已暂停"),      TEXT("Step failed, plan paused"));
	Reg(TEXT("PlanParseFailed"),     TEXT("Plan 解析失败，已作为普通回复显示"), TEXT("Failed to parse plan, showing as normal reply"));
	Reg(TEXT("PlanProgressFmt"),     TEXT("步完成"),                    TEXT("steps done"));
	Reg(TEXT("PlanModeEnabled"),     TEXT("Plan 模式已开启"),           TEXT("Plan mode enabled"));
	Reg(TEXT("PlanModeDisabled"),    TEXT("Plan 模式已关闭"),           TEXT("Plan mode disabled"));
	Reg(TEXT("SlashPlan"),           TEXT("切换 Plan 模式"),            TEXT("Toggle Plan mode"));

	// ==================================================================
	// 文件操作确认弹窗 (阶段 5.6)
	// ==================================================================
	Reg(TEXT("ConfirmTitle"),           TEXT("操作确认"),                    TEXT("Confirm Operation"));
	Reg(TEXT("ConfirmRiskHigh"),        TEXT("⚠ 高风险操作"),               TEXT("⚠ High Risk"));
	Reg(TEXT("ConfirmRiskMedium"),      TEXT("中风险操作"),                  TEXT("Medium Risk"));
	Reg(TEXT("RiskHigh"),               TEXT("⚠ 高风险"),                   TEXT("⚠ High Risk"));
	Reg(TEXT("RiskMedium"),             TEXT("中风险"),                      TEXT("Medium Risk"));
	Reg(TEXT("ConfirmMessage"),         TEXT("AI 请求执行以下操作，是否允许？"), TEXT("AI is requesting to perform the following operations. Allow?"));
	Reg(TEXT("ConfirmOperations"),      TEXT("将执行以下操作:"),             TEXT("The following operations will be performed:"));
	Reg(TEXT("ConfirmCodePreview"),     TEXT("代码预览:"),                   TEXT("Code preview:"));
	Reg(TEXT("ConfirmBatchWarning"),    TEXT("⚠ 包含循环批量操作!"),         TEXT("⚠ Contains batch loop operations!"));
	Reg(TEXT("ConfirmApprove"),         TEXT("允许"),                        TEXT("Approve"));
	Reg(TEXT("ConfirmAllow"),           TEXT("允许执行"),                    TEXT("Allow"));
	Reg(TEXT("ConfirmDeny"),            TEXT("拒绝"),                        TEXT("Deny"));
	Reg(TEXT("ConfirmDontAsk"),         TEXT("不再提示此风险级别"),           TEXT("Don't ask again for this risk level"));
	Reg(TEXT("ConfirmSilentEnabled"),   TEXT("已启用静默模式，后续同级别操作将自动批准"), TEXT("Silent mode enabled, future operations of this risk level will be auto-approved"));
	Reg(TEXT("ConfirmSessionSilent"),   TEXT("静默通过"),                    TEXT("Auto-approved (silent)"));

	// ==================================================================
	// 静默模式 (阶段 5.7) — 中/高风险分开控制
	// ==================================================================
	Reg(TEXT("SilentMediumOn"),         TEXT("中风险静默: 开"),              TEXT("Med Silent: On"));
	Reg(TEXT("SilentMediumOff"),        TEXT("中风险静默: 关"),              TEXT("Med Silent: Off"));
	Reg(TEXT("SilentMediumTip"),        TEXT("中风险静默: 文件修改/移动操作自动通过"), TEXT("Medium risk silent: auto-approve file modify/move operations"));
	Reg(TEXT("SilentHighOn"),           TEXT("高风险静默: 开"),              TEXT("High Silent: On"));
	Reg(TEXT("SilentHighOff"),          TEXT("高风险静默: 关"),              TEXT("High Silent: Off"));
	Reg(TEXT("SilentHighTip"),          TEXT("高风险静默: 文件删除/批量操作自动通过"), TEXT("High risk silent: auto-approve file delete/batch operations"));

	// ==================================================================
	// 设置面板
	// ==================================================================
	Reg(TEXT("SettingsBtn"),            TEXT("设置"),                      TEXT("Settings"));
	Reg(TEXT("SettingsTip"),            TEXT("打开设置面板"),               TEXT("Open settings panel"));
	Reg(TEXT("ToolManagerBtn"),         TEXT("工具"),                      TEXT("Tools"));
	Reg(TEXT("ToolManagerTip"),         TEXT("打开 ArtClaw Tool Manager"), TEXT("Open ArtClaw Tool Manager"));
	Reg(TEXT("SettingsTitle"),          TEXT("设置"),                      TEXT("Settings"));
	Reg(TEXT("SettingsLanguage"),       TEXT("语言 / Language"),           TEXT("Language"));
	Reg(TEXT("SettingsSendMode"),       TEXT("Enter 发送"),                TEXT("Enter to Send"));
	Reg(TEXT("SettingsSilentMode"),     TEXT("静默模式"),                   TEXT("Silent Mode"));
	Reg(TEXT("SettingsPlanMode"),       TEXT("Plan 模式"),                  TEXT("Plan Mode"));
	Reg(TEXT("SettingsSkillsManage"),   TEXT("Skills 管理"),                TEXT("Skills Management"));
	Reg(TEXT("SettingsCloseBtn"),       TEXT("关闭"),                      TEXT("Close"));

	// 上下文窗口大小
	Reg(TEXT("SettingsContextWindow"),  TEXT("最大上下文窗口"),             TEXT("Max Context Window"));

	// 平台切换
	Reg(TEXT("SettingsPlatform"),        TEXT("AI 平台"),                    TEXT("AI Platform"));
	Reg(TEXT("PlatformSwitched"),        TEXT("已切换到平台: "),              TEXT("Switched to platform: "));

	// Agent 切换
	Reg(TEXT("SettingsAgent"),          TEXT("当前 Agent"),                 TEXT("Current Agent"));
	Reg(TEXT("AgentRefreshBtn"),        TEXT("刷新列表"),                   TEXT("Refresh List"));
	Reg(TEXT("AgentRefreshTip"),        TEXT("从 Gateway 获取最新 Agent 列表"), TEXT("Fetch latest Agent list from Gateway"));
	Reg(TEXT("AgentCurrent"),           TEXT("[当前]"),                     TEXT("[Current]"));
	Reg(TEXT("AgentSwitched"),          TEXT("已切换到 Agent: "),            TEXT("Switched to Agent: "));
	Reg(TEXT("AgentRefreshing"),        TEXT("正在刷新 Agent 列表..."),      TEXT("Refreshing Agent list..."));
	Reg(TEXT("AgentRefreshDone"),       TEXT("Agent 列表已刷新。"),          TEXT("Agent list refreshed."));
	Reg(TEXT("AgentRefreshFail"),       TEXT("Agent 列表刷新失败。"),        TEXT("Failed to refresh Agent list."));
	Reg(TEXT("AgentNone"),              TEXT("(无缓存列表，请点击刷新)"),    TEXT("(No cached list, click Refresh)"));
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
	SaveLanguagePreference();
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
	SaveLanguagePreference();
}

FText FUEAgentL10n::GetLanguageDisplayName()
{
	// 显示目标语言名：当前中文则显示"English"（表示可切换到英文），反之亦然
	return (CurrentLanguage == EUEAgentLanguage::Chinese)
		? FText::FromString(TEXT("English"))
		: FText::FromString(TEXT("中文"));
}

// ==================================================================
// 系统语言检测
// ==================================================================

EUEAgentLanguage FUEAgentL10n::DetectSystemLanguage()
{
	// 使用 UE 的国际化系统检测当前 culture
	FString Culture = FInternationalization::Get().GetCurrentCulture()->GetName();

	// 匹配中文系列: zh, zh-CN, zh-TW, zh-Hans, zh-Hant 等
	if (Culture.StartsWith(TEXT("zh")))
	{
		return EUEAgentLanguage::Chinese;
	}

	// 默认英文
	return EUEAgentLanguage::English;
}

// ==================================================================
// 语言配置持久化
// ==================================================================

FString FUEAgentL10n::GetConfigFilePath()
{
	// 保存在 ProjectSaved/UEAgent/language_pref.txt
	return FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()) / TEXT("ClawBridge") / TEXT("language_pref.txt");
}

bool FUEAgentL10n::LoadLanguagePreference(EUEAgentLanguage& OutLang)
{
	FString ConfigPath = GetConfigFilePath();
	if (!FPaths::FileExists(ConfigPath))
	{
		return false;
	}

	FString Content;
	if (!FFileHelper::LoadFileToString(Content, *ConfigPath))
	{
		return false;
	}

	Content.TrimStartAndEndInline();

	if (Content == TEXT("zh") || Content == TEXT("Chinese"))
	{
		OutLang = EUEAgentLanguage::Chinese;
		return true;
	}
	else if (Content == TEXT("en") || Content == TEXT("English"))
	{
		OutLang = EUEAgentLanguage::English;
		return true;
	}

	return false;
}

void FUEAgentL10n::SaveLanguagePreference()
{
	FString ConfigPath = GetConfigFilePath();

	// 确保目录存在
	FString Dir = FPaths::GetPath(ConfigPath);
	IFileManager::Get().MakeDirectory(*Dir, true);

	FString LangStr = (CurrentLanguage == EUEAgentLanguage::Chinese) ? TEXT("zh") : TEXT("en");
	FFileHelper::SaveStringToFile(LangStr, *ConfigPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}
