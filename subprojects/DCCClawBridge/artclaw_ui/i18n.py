"""
i18n.py - ArtClaw DCC 国际化支持
=================================

简单的 key→text 翻译模块。
通过 T("key") 获取当前语言的文本。

用法:
    from artclaw_ui.i18n import T
    label.setText(T("connected"))  # → "已连接" 或 "Connected"
"""

from __future__ import annotations

_STRINGS: dict[str, dict[str, str]] = {
    # ── Status Bar ──
    "connected":       {"zh": "已连接",       "en": "Connected"},
    "disconnected":    {"zh": "未连接",       "en": "Disconnected"},
    "mcp_ready":       {"zh": "MCP就绪",     "en": "MCP Ready"},
    "mcp_not_ready":   {"zh": "MCP未就绪",   "en": "MCP Not Ready"},
    "context_usage":   {"zh": "上下文",       "en": "Context"},
    "connect":         {"zh": "连接",         "en": "Connect"},
    "disconnect":      {"zh": "断开",         "en": "Disconnect"},
    "diagnose":        {"zh": "诊断",         "en": "Diagnose"},
    "view_logs":       {"zh": "查看日志",     "en": "View Logs"},

    # ── Chat Panel ──
    "thinking":        {"zh": "思考中...",     "en": "Thinking..."},
    "ai_waiting":      {"zh": "AI 正在回复中，请等待或点击停止...",
                        "en": "AI is responding, please wait or click stop..."},
    "new_chat":        {"zh": "新对话已开始",  "en": "New chat started"},
    "chat_cleared":    {"zh": "聊天已清空",    "en": "Chat cleared"},
    "stopped":         {"zh": "已停止 AI 回复", "en": "AI response stopped"},
    "no_request":      {"zh": "没有正在执行的请求", "en": "No active request"},
    "connecting":      {"zh": "正在连接...",    "en": "Connecting..."},
    "connect_ok":      {"zh": "已连接到 OpenClaw", "en": "Connected to OpenClaw"},
    "connect_fail":    {"zh": "连接失败",      "en": "Connection failed"},
    "disconnected_msg": {"zh": "已断开连接",   "en": "Disconnected"},
    "running_diag":    {"zh": "正在运行诊断...", "en": "Running diagnostics..."},
    "bridge_not_init": {"zh": "[错误] Bridge 未初始化", "en": "[Error] Bridge not initialized"},
    "plan_on":         {"zh": "Plan 模式已开启", "en": "Plan mode enabled"},
    "plan_off":        {"zh": "Plan 模式已关闭", "en": "Plan mode disabled"},
    "no_session":      {"zh": "没有可恢复的会话", "en": "No session to resume"},
    "resuming":        {"zh": "正在恢复接收...", "en": "Resuming..."},
    "resume_done":     {"zh": "已恢复接收完毕", "en": "Resume complete"},
    "no_history":      {"zh": "未获取到会话历史", "en": "No history found"},
    "conn_lost":       {"zh": "连接断开",      "en": "Connection lost"},
    "lang_zh":         {"zh": "语言已切换为中文。重新打开面板后生效。",
                        "en": "Language changed to Chinese. Reopen panel to apply."},
    "lang_en":         {"zh": "Language changed to English. Reopen panel to apply.",
                        "en": "Language changed to English. Reopen panel to apply."},

    # ── Message Labels ──
    "sender_user":     {"zh": "用户",         "en": "User"},
    "sender_assistant": {"zh": "助手",        "en": "Assistant"},
    "sender_system":   {"zh": "系统",         "en": "System"},
    "sender_thinking": {"zh": "思考中",       "en": "Thinking"},
    "sender_streaming": {"zh": "助手",        "en": "Assistant"},
    "sender_tool_call": {"zh": "工具调用",    "en": "Tool Call"},
    "sender_tool_result": {"zh": "工具结果",  "en": "Tool Result"},
    "sender_tool_error": {"zh": "工具错误",   "en": "Tool Error"},
    "sender_tool_status": {"zh": "工具状态",  "en": "Tool Status"},
    "sender_plan":     {"zh": "执行计划",     "en": "Plan"},
    "tool_params":     {"zh": "参数：",       "en": "Parameters:"},
    "tool_result_lbl": {"zh": "结果：",       "en": "Result:"},
    "tool_error_lbl":  {"zh": "错误：",       "en": "Error:"},
    "tool_calls_count": {"zh": "次工具调用",  "en": "tool calls"},

    # ── Toolbar ──
    "send":            {"zh": "发送",         "en": "Send"},
    "stop":            {"zh": "停止",         "en": "Stop"},
    "new_chat_btn":    {"zh": "新对话",       "en": "New Chat"},
    "manage_btn":          {"zh": "技能",              "en": "Skills"},
    "tool_manager_btn":    {"zh": "工具",              "en": "Tools"},
    "attach_btn":          {"zh": "附件",              "en": "Attach"},
    "resume_btn":      {"zh": "恢复",         "en": "Resume"},
    "waiting_btn":     {"zh": "等待...",       "en": "Wait..."},

    # ── Quick Input ──
    "quick_input":     {"zh": "快捷输入",     "en": "Quick Input"},

    # ── Settings ──
    "settings_btn":    {"zh": "设置",         "en": "Settings"},
    "settings_title":  {"zh": "设置",         "en": "Settings"},
    "language_label":  {"zh": "语言 / Language", "en": "Language"},
    "send_mode":       {"zh": "发送方式",     "en": "Send Mode"},
    "enter_send":      {"zh": "Enter 发送",   "en": "Enter to Send"},
    "ctrl_enter_send": {"zh": "Ctrl+Enter 发送", "en": "Ctrl+Enter to Send"},
    "context_window":  {"zh": "上下文窗口",   "en": "Context Window"},
    "agent_switch":    {"zh": "Agent 切换",   "en": "Switch Agent"},
    "plan_mode":       {"zh": "Plan 模式",    "en": "Plan Mode"},
    "silent_mode":     {"zh": "静默模式",     "en": "Silent Mode"},
    "silent_medium":   {"zh": "中风险静默",   "en": "Silent Medium Risk"},
    "silent_high":     {"zh": "高风险静默",   "en": "Silent High Risk"},
    "manage_skills":   {"zh": "管理 Skill / MCP", "en": "Manage Skills / MCP"},

    # ── Manage Panel ──
    "manage_title":    {"zh": "ArtClaw 管理",  "en": "ArtClaw Manager"},
    "tab_skill":       {"zh": "Skill 管理",    "en": "Skill Manager"},
    "tab_mcp":         {"zh": "MCP 管理",      "en": "MCP Manager"},
    "refresh":         {"zh": "刷新",          "en": "Refresh"},

    # ── Skill Tab ──
    "layer_label":     {"zh": "层级:",         "en": "Layer:"},
    "software_label":  {"zh": "软件:",         "en": "Software:"},
    "search_skill":    {"zh": "搜索 Skill...", "en": "Search Skill..."},
    "sync_all":        {"zh": "全量更新",      "en": "Sync All"},
    "all":             {"zh": "全部",          "en": "All"},
    "not_installed":   {"zh": "未安装",        "en": "Not Installed"},
    "installed":       {"zh": "已安装",        "en": "Installed"},
    "install":         {"zh": "安装",          "en": "Install"},
    "uninstall":       {"zh": "卸载",          "en": "Uninstall"},
    "update":          {"zh": "更新",          "en": "Update"},
    "publish":         {"zh": "发布",          "en": "Publish"},
    "layer_official":  {"zh": "官方",          "en": "Official"},
    "layer_marketplace": {"zh": "市集",        "en": "Marketplace"},
    "layer_user":      {"zh": "用户",          "en": "User"},
    "layer_platform":  {"zh": "平台",          "en": "Platform"},
    "show_count":      {"zh": "显示",          "en": "Showing"},

    # ── Help ──
    "help_text":       {"zh": (
        "=== 帮助 ===\n"
        "连接管理:\n"
        "  /connect     连接到 OpenClaw\n"
        "  /disconnect  断开连接\n"
        "  /diagnose    运行连接诊断\n"
        "  /status      显示当前状态\n"
        "聊天:\n"
        "  /clear       清空聊天记录\n"
        "  /cancel      取消当前请求\n"
        "  /resume      恢复接收中断的 AI 回复\n"
        "  /help        显示帮助\n"
        "  /plan        切换 Plan 模式\n"
        "AI 命令:\n"
        "  /new         开始新对话\n"
        "  /compact     压缩上下文\n"
        "  /review      审查选中内容\n"
        "  /undo        撤销上次操作"
    ), "en": (
        "=== Help ===\n"
        "Connection:\n"
        "  /connect     Connect to OpenClaw\n"
        "  /disconnect  Disconnect\n"
        "  /diagnose    Run diagnostics\n"
        "  /status      Show status\n"
        "Chat:\n"
        "  /clear       Clear chat\n"
        "  /cancel      Cancel request\n"
        "  /resume      Resume AI response\n"
        "  /help        Show help\n"
        "  /plan        Toggle Plan mode\n"
        "AI:\n"
        "  /new         New conversation\n"
        "  /compact     Compact context\n"
        "  /review      Review selection\n"
        "  /undo        Undo last action"
    )},
}

_current_lang: str = "zh"


def init_language(lang: str = "") -> None:
    """初始化语言设置。未指定时从 config 读取。"""
    global _current_lang
    if lang:
        _current_lang = lang
        return
    try:
        from artclaw_ui.utils import get_artclaw_config
        cfg = get_artclaw_config()
        _current_lang = cfg.get("language", "zh")
    except Exception:
        _current_lang = "zh"


def get_lang() -> str:
    """获取当前语言代码"""
    return _current_lang


def T(key: str, **kwargs) -> str:
    """翻译函数。返回当前语言的文本，找不到则返回 key 本身。

    支持 format 参数:
        T("show_count", n=5, total=10) → "显示 5/10"
    """
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_current_lang, entry.get("zh", key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


# 启动时自动初始化
init_language()
