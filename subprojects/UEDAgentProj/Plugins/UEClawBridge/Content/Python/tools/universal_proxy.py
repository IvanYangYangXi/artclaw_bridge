"""
universal_proxy.py - 万能执行器 (Universal Proxy)
===================================================

阶段 1.2 ~ 1.6 整合实现:
  1.2 万能执行器: exec() + try-except，返回 traceback 字符串
  1.3 静态指令预审: 执行前 AST 扫描
  1.4 事务保护: ScopedEditorTransaction 包装
  1.5 主线程调度: 所有代码在 Game Thread 上执行（slate_post_tick 已保证）
  1.6 上下文注入: S/W/L 自动注入 exec() globals

宪法约束:
  - 开发路线图 §1.2: exec() + try-except，将 Traceback 转为字符串返回
  - 开发路线图 §1.3: 执行前 ast 扫描黑名单
  - 开发路线图 §1.4: ScopedEditorTransaction 包装
  - 开发路线图 §1.5: 利用 slate_post_tick 确保 Game Thread
  - 开发路线图 §1.6: globals 中预置 S, W, L
  - 核心机制 §3: 安全可逆执行，原子化操作
"""

import os
import sys
import time
import traceback
import json
from io import StringIO
from typing import Any, Optional

import unreal

from claw_bridge_logger import UELogger
from tools.static_guard import StaticGuard, RiskLevel, ScanResult, detect_file_operations


# ============================================================================
# 1. 执行计数器（全局）
# ============================================================================

_execution_counter = 0


# ============================================================================
# 1b. 文件操作确认机制 (阶段 5.6 / 5.7)
# ============================================================================

# 会话级静默标记 (阶段 5.7)
_session_silent_mode = False


def _load_artclaw_config() -> dict:
    """加载 ~/.artclaw/config.json 配置"""
    try:
        home = os.path.expanduser("~")
        config_path = os.path.join(home, ".artclaw", "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _check_session_silent_flag() -> bool:
    """检查临时会话静默标记文件 (C++ 弹窗复选框写入)"""
    try:
        flag_file = os.path.join(
            unreal.Paths.project_saved_dir(), "ClawBridge", "_silent_session.flag")
        return os.path.exists(flag_file)
    except Exception:
        return False


def _request_file_confirmation(operations: list, risk_level: str, code_preview: str) -> bool:
    """
    请求用户确认文件操作 (阶段 5.6)。

    通过文件通信机制与 C++ 弹窗交互:
    1. 写入 _confirm_request.json
    2. 等待 C++ 写入 _confirm_response.json
    3. 读取并返回结果

    阶段 5.7: 静默模式检查
    """
    global _session_silent_mode

    # --- 阶段 5.7: 静默模式检查 (中/高风险分开控制) ---
    config = _load_artclaw_config()
    silent_medium = config.get("silent_mode_medium", False)
    silent_high = config.get("silent_mode_high", False)

    # 全局静默: 按风险等级独立判断
    if risk_level == "medium" and silent_medium:
        UELogger.info(f"[FileOp] Silent mode: auto-approved medium risk operation")
        return True
    if risk_level == "high" and silent_high:
        UELogger.info(f"[FileOp] Silent mode: auto-approved high risk operation")
        return True

    # 临时会话静默 (弹窗复选框 或 Python 内存标记)
    # 注意: C++ 侧 /new 会删除 _silent_session.flag，此处重新验证
    if _session_silent_mode:
        if _check_session_silent_flag():
            if risk_level == "medium":
                UELogger.info(f"[FileOp] Session silent: auto-approved medium risk operation")
                return True
        else:
            # flag 文件已被删除 (新会话)，重置内存标记
            _session_silent_mode = False
    elif _check_session_silent_flag():
        _session_silent_mode = True
        if risk_level == "medium":
            UELogger.info(f"[FileOp] Session silent (flag): auto-approved medium risk operation")
            return True

    # --- 正常弹窗确认流程 ---
    try:
        confirm_dir = os.path.join(unreal.Paths.project_saved_dir(), "ClawBridge")
        os.makedirs(confirm_dir, exist_ok=True)
        request_file = os.path.join(confirm_dir, "_confirm_request.json")
        response_file = os.path.join(confirm_dir, "_confirm_response.json")

        # 清理旧的响应文件
        if os.path.exists(response_file):
            os.remove(response_file)

        # 写入确认请求
        request_data = {
            "type": "confirm",
            "risk": risk_level,
            "operations": operations,
            "code_preview": code_preview[:500],
            "timestamp": time.time()
        }
        with open(request_file, 'w', encoding='utf-8') as f:
            json.dump(request_data, f, ensure_ascii=False, indent=2)

        UELogger.info(f"[FileOp] Confirmation requested: {risk_level} risk, {len(operations)} ops")

        # 等待 C++ 侧写入响应 (最多 60 秒)
        for _ in range(600):
            if os.path.exists(response_file):
                try:
                    with open(response_file, 'r', encoding='utf-8') as f:
                        response = json.load(f)
                    os.remove(response_file)
                    if os.path.exists(request_file):
                        os.remove(request_file)

                    approved = response.get("approved", False)

                    # 检查是否设置了会话静默标记
                    if response.get("session_silent", False):
                        _session_silent_mode = True
                        UELogger.info("[FileOp] Session silent mode activated via dialog checkbox")

                    UELogger.info(f"[FileOp] User {'APPROVED' if approved else 'REJECTED'} {risk_level} operation")
                    return approved
                except (json.JSONDecodeError, IOError):
                    pass  # 文件可能还在写入
            time.sleep(0.1)

        # 超时 = 拒绝
        UELogger.warning("[FileOp] Confirmation timeout (60s) — operation rejected")
        if os.path.exists(request_file):
            os.remove(request_file)
        return False

    except Exception as e:
        UELogger.error(f"[FileOp] Confirmation mechanism error: {e}")
        return False


# ============================================================================
# 2. 上下文注入 (阶段 1.6)
# ============================================================================

def _build_context() -> dict:
    """
    构建执行上下文，注入到 exec() 的 globals 中。

    宪法约束:
      - 开发路线图 §1.6: 预置 S (选中 Actor), W (当前世界), L (常用库简写)
      - 每次执行前动态获取，确保是最新状态

    预置变量:
      S : list[unreal.Actor]  - 当前选中的 Actor 列表
      W : unreal.World         - 当前编辑器世界
      L : module               - unreal 模块引用（常用库简写）
      ELL : class              - unreal.EditorLevelLibrary 快捷引用
      EAL : class              - unreal.EditorAssetLibrary 快捷引用
    """
    context = {
        # 核心模块
        "unreal": unreal,
        "L": unreal,  # 常用库简写

        # 辅助库
        "ELL": unreal.EditorLevelLibrary,
    }

    # 动态获取当前状态
    try:
        context["S"] = list(unreal.EditorLevelLibrary.get_selected_level_actors())
    except Exception:
        context["S"] = []

    try:
        context["W"] = unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        context["W"] = None

    # EditorAssetLibrary 可能不是所有版本都有
    try:
        context["EAL"] = unreal.EditorAssetLibrary
    except AttributeError:
        pass

    return context


# ============================================================================
# 3. 结果序列化
# ============================================================================

def _serialize_result(value: Any) -> Any:
    """
    将执行结果序列化为 JSON 安全类型。

    处理 Unreal UObject、列表、字典等复杂类型。
    """
    if value is None:
        return None

    # 基本类型
    if isinstance(value, (bool, int, float, str)):
        return value

    # Unreal 对象
    if hasattr(value, "get_name") and hasattr(value, "get_class"):
        try:
            result = {
                "_type": "UObject",
                "name": str(value.get_name()),
                "class": str(value.get_class().get_name()),
            }
            if hasattr(value, "get_actor_location"):
                loc = value.get_actor_location()
                result["location"] = {"x": loc.x, "y": loc.y, "z": loc.z}
            return result
        except Exception:
            return f"<UObject: {type(value).__name__}>"

    # Unreal 向量/旋转等
    if isinstance(value, (unreal.Vector, unreal.Rotator)):
        return str(value)

    # 列表/元组
    if isinstance(value, (list, tuple)):
        serialized = [_serialize_result(item) for item in value[:100]]  # 限制 100 项
        if len(value) > 100:
            serialized.append(f"... ({len(value) - 100} more items)")
        return serialized

    # 字典
    if isinstance(value, dict):
        return {str(k): _serialize_result(v) for k, v in list(value.items())[:50]}

    # 集合
    if isinstance(value, set):
        return _serialize_result(list(value))

    # 兜底：字符串化
    try:
        return str(value)
    except Exception:
        return f"<{type(value).__name__}>"


# ============================================================================
# 4. 核心执行函数
# ============================================================================

def run_ue_python(arguments: dict) -> str:
    """
    万能执行器核心函数 - 作为 MCP Tool handler 注册。

    接收 AI 发送的 Python 代码，经过安全检查后在 UE 编辑器中执行。

    Args:
        arguments: {"code": str, "inject_context": bool (可选)}

    Returns:
        JSON 字符串，包含 success/result/output/error/execution_time 等字段

    宪法约束:
      - 开发路线图 §1.2: exec() + try-except，Traceback 转字符串
      - 核心机制 §3: ScopedEditorTransaction 包装
    """
    global _execution_counter
    _execution_counter += 1
    exec_id = _execution_counter

    # 支持两种调用方式:
    #   1. MCP Tool: run_ue_python({"code": "...", "inject_context": True})
    #   2. 直接调用: run_ue_python("print('hello')")
    if isinstance(arguments, str):
        code = arguments
        inject_context = True
    else:
        # v2.6: get_context 快捷模式 — 直接返回编辑器上下文，无需写代码
        if arguments.get("get_context", False):
            try:
                from tools.context_provider import _read_editor_context
                ctx = _read_editor_context()
                return json.dumps({
                    "success": True,
                    "exec_id": _execution_counter + 1,
                    "context": ctx,
                    "output": "",
                    "result": ctx,
                    "execution_time": 0,
                })
            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": f"Failed to read editor context: {e}",
                })

        code = arguments.get("code", "")
        inject_context = arguments.get("inject_context", True)

    UELogger.info(f"[Exec #{exec_id}] Running code ({len(code)} chars)")

    # --- 阶段 1.3: 静态指令预审 ---
    guard = StaticGuard()
    scan_result = guard.check_code(code)

    if scan_result.blocked:
        UELogger.warning(f"[Exec #{exec_id}] BLOCKED by Static Guard")
        return json.dumps({
            "success": False,
            "exec_id": exec_id,
            "error": "Code blocked by security scanner",
            "security": scan_result.to_dict(),
            "output": "",
            "result": None,
            "execution_time": 0,
        })

    # --- 阶段 2.3: 风险分级确认 ---
    try:
        from tools.risk_confirmation import assess_operation_risk, request_confirmation
        risk_info = assess_operation_risk(code)
        if risk_info.get("requires_confirmation", False):
            confirmed = request_confirmation(risk_info, code_preview=code)
            if not confirmed:
                UELogger.info(f"[Exec #{exec_id}] REJECTED by user (risk: {risk_info['level']})")
                return json.dumps({
                    "success": False,
                    "exec_id": exec_id,
                    "error": f"Operation rejected by user (risk level: {risk_info['level']})",
                    "risk": risk_info,
                    "output": "",
                    "result": None,
                    "execution_time": 0,
                })
    except ImportError:
        pass  # risk_confirmation 模块可能尚未加载

    # --- 阶段 5.6: 文件操作弹窗确认 ---
    file_op_risk = detect_file_operations(code)
    if file_op_risk.needs_confirmation:
        UELogger.info(f"[Exec #{exec_id}] File operation detected: {file_op_risk.risk_level} risk, "
                      f"{len(file_op_risk.operations)} ops, batch={file_op_risk.is_batch}")
        confirmed = _request_file_confirmation(
            operations=file_op_risk.operations,
            risk_level=file_op_risk.risk_level,
            code_preview=file_op_risk.code_preview or code[:500],
        )
        if not confirmed:
            UELogger.info(f"[Exec #{exec_id}] REJECTED file operation (risk: {file_op_risk.risk_level})")
            return json.dumps({
                "success": False,
                "exec_id": exec_id,
                "error": f"File operation rejected by user (risk: {file_op_risk.risk_level})",
                "file_operations": file_op_risk.operations,
                "output": "",
                "result": None,
                "execution_time": 0,
            })

    # --- 准备执行环境 ---
    exec_globals = {"__builtins__": __builtins__}

    # 阶段 1.6: 上下文注入
    if inject_context:
        context = _build_context()
        exec_globals.update(context)

    exec_locals = {}

    # --- 捕获标准输出 ---
    output_buffer = StringIO()
    original_stdout = sys.stdout

    # --- 执行 ---
    start_time = time.perf_counter()
    success = False
    result_value = None
    error_msg = ""

    try:
        # 重定向 stdout 到缓冲区（捕获 print 输出）
        sys.stdout = output_buffer

        # --- 阶段 1.4: 事务保护 ---
        # 所有操作包裹在 ScopedEditorTransaction 中，支持 Ctrl+Z 撤销
        with unreal.ScopedEditorTransaction(f"AI Agent Exec #{exec_id}"):
            # --- 阶段 1.2: exec() 执行 ---
            # 对于单行表达式，尝试 eval() 获取返回值
            code_stripped = code.strip()
            if "\n" not in code_stripped and not _is_statement(code_stripped):
                try:
                    result_value = eval(code_stripped, exec_globals, exec_locals)
                except SyntaxError:
                    # 不是表达式，按语句执行
                    exec(code, exec_globals, exec_locals)
                    result_value = exec_locals.get("result", exec_locals.get("_result", None))
            else:
                exec(code, exec_globals, exec_locals)
                # 尝试获取 result 变量作为返回值
                result_value = exec_locals.get("result", exec_locals.get("_result", None))

        success = True

    except Exception as e:
        error_msg = traceback.format_exc()
        UELogger.error(f"[Exec #{exec_id}] Error: {type(e).__name__}: {e}")

    finally:
        sys.stdout = original_stdout

    elapsed = time.perf_counter() - start_time
    output_text = output_buffer.getvalue()

    # --- 组装结果 ---
    response = {
        "success": success,
        "exec_id": exec_id,
        "result": _serialize_result(result_value),
        "output": output_text[:10000],  # 限制输出长度
        "error": error_msg if error_msg else None,
        "execution_time": round(elapsed, 4),
    }

    # 附加安全扫描结果（如果有警告）
    if scan_result.issues:
        response["security"] = scan_result.to_dict()

    # --- 阶段 2.7: 自修复上下文 ---
    if not success and error_msg:
        try:
            from tools.self_healing import build_retry_context
            retry_ctx = build_retry_context(response, code)
            if retry_ctx:
                response["retry_context"] = retry_ctx
        except ImportError:
            pass  # self_healing 模块可能尚未加载

    UELogger.info(
        f"[Exec #{exec_id}] {'OK' if success else 'FAIL'} "
        f"({elapsed:.3f}s, output={len(output_text)} chars)"
    )

    return json.dumps(response, default=str)


def _is_statement(code: str) -> bool:
    """判断代码是否是语句（而非表达式）"""
    statement_keywords = (
        "import ", "from ", "class ", "def ", "if ", "for ", "while ",
        "with ", "try:", "except", "finally:", "raise ", "assert ",
        "del ", "pass", "break", "continue", "return ", "yield ",
        "global ", "nonlocal ",
    )
    return any(code.startswith(kw) for kw in statement_keywords) or "=" in code


# ============================================================================
# 5. MCP Tool 定义 & 注册
# ============================================================================

# MCP Tool Definition (JSON Schema)
TOOL_DEFINITION = {
    "name": "run_ue_python",
    "description": (
        "Execute Python code in the Unreal Editor environment. "
        "The code runs with full access to the `unreal` module and editor APIs. "
        "Pre-injected variables: S (selected actors), W (editor world), L (unreal module). "
        "All operations are wrapped in an undo transaction (Ctrl+Z to revert). "
        "Dangerous operations (os.system, subprocess, etc.) are blocked by the security scanner."
        "\n\nQuick context: set get_context=true (no code needed) to get editor state: "
        "active_panel (viewport/content_browser), selected (items from the active panel), "
        "selected_source, viewport_selection_count, content_browser_selection_count, "
        "mode, total_actors, level_name. "
        "The 'selected' field automatically contains viewport actors or content browser assets "
        "based on which panel the user was last interacting with."
        "\n\nAvailable internal APIs (import and call via this tool):\n"
        "- knowledge_base.get_knowledge_base().search(query, top_k) — search local knowledge base\n"
        "- memory_store.get_memory_store() — memory read/write (store/get/search/check_operation)\n"
        "- skill_hub.get_skill_hub().execute_skill(name, params) — execute a registered Skill\n"
        "- skill_hub.get_skill_hub().list_skills() — list available Skills"
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Python code to execute. Use `unreal` module for editor operations. "
                    "Pre-injected: S=selected actors, W=editor world, L=unreal module. "
                    "Store results in `result` variable to return them. "
                    "Example: 'result = [a.get_name() for a in S]'"
                ),
            },
            "inject_context": {
                "type": "boolean",
                "description": "Whether to inject S/W/L context variables (default: true)",
                "default": True,
            },
            "get_context": {
                "type": "boolean",
                "description": "If true, return editor context (mode, selection, actors, level) without executing any code. No 'code' parameter needed.",
                "default": False,
            },
        },
        "required": [],
    },
}


def register_tools(mcp_server) -> None:
    """
    将所有阶段 1 的工具注册到 MCP 服务器。

    宪法约束:
      - 核心机制 §1: 自动能力发现，Schema 转换
      - 开发路线图 §1.2: 注册 run_ue_python 到 MCP 工具列表
    """
    mcp_server.register_tool(
        name=TOOL_DEFINITION["name"],
        description=TOOL_DEFINITION["description"],
        input_schema=TOOL_DEFINITION["inputSchema"],
        handler=run_ue_python,
    )
    UELogger.info("Phase 1 tools registered: run_ue_python")
