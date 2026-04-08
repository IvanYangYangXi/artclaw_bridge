"""
blender_adapter.py - Blender 适配层实现
=========================================

Blender 3.0+ (Python 3.10+)

所有 bpy 调用集中在此文件。
其余模块（UI / Bridge / Skill）通过 adapter 接口访问 Blender 功能。

主线程调度：
    Blender 不提供像 Maya 的 executeInMainThreadWithResult，
    需要通过 queue.Queue + bpy.app.timers.register() 手动实现。
"""

from __future__ import annotations

import io
import logging
import queue
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

from .base_adapter import BaseDCCAdapter

logger = logging.getLogger("artclaw.blender")

# ── 主线程调度用的共享队列 ──
_main_thread_queue: queue.Queue = queue.Queue()
_timer_registered: bool = False


def _require_blender():
    """延迟 import bpy 模块，仅在 Blender 环境中可用"""
    import bpy
    return bpy


def _main_thread_consumer() -> Optional[float]:
    """
    bpy.app.timers 回调：消费主线程队列中的任务。

    每次 tick 最多处理 10 个任务，避免阻塞主线程。
    返回 0.05（50ms 轮询间隔）。
    """
    processed = 0
    while not _main_thread_queue.empty() and processed < 10:
        try:
            fn, args, result_event, result_container = _main_thread_queue.get_nowait()
        except queue.Empty:
            break

        try:
            ret = fn(*args)
            if result_container is not None:
                result_container[0] = ret
        except Exception as e:
            if result_container is not None:
                result_container[1] = e
            logger.error("主线程任务执行失败: %s", e, exc_info=True)
        finally:
            if result_event is not None:
                result_event.set()
            processed += 1

    return 0.05  # 继续轮询


def _ensure_timer_registered():
    """确保 bpy.app.timers 回调已注册（幂等）"""
    global _timer_registered
    if _timer_registered:
        return
    bpy = _require_blender()
    if not bpy.app.timers.is_registered(_main_thread_consumer):
        bpy.app.timers.register(
            _main_thread_consumer,
            first_interval=0.05,
            persistent=True,
        )
    _timer_registered = True


class BlenderAdapter(BaseDCCAdapter):
    """Blender DCC 适配层"""

    def __init__(self):
        self._panel = None  # Chat Panel 实例引用（由 BlenderQtBridge 管理）

    # ── 基础信息 ──

    def get_software_name(self) -> str:
        return "blender"

    def get_software_version(self) -> str:
        bpy = _require_blender()
        return bpy.app.version_string

    def get_python_version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # ── 生命周期 ──

    def on_startup(self) -> None:
        """Blender 启动时调用 — 注册 timer + 启动 MCP Server"""
        logger.info("ArtClaw: Blender adapter startup")

        # 确保主线程消费 timer 已注册
        _ensure_timer_registered()

        # 设置 DCC 名称（影响 Gateway session key）
        try:
            from core.bridge_dcc import DCCBridgeManager
            DCCBridgeManager.set_dcc_name("blender")
        except Exception:
            pass

        # 启动 MCP Server（独立线程，不阻塞 Blender）
        try:
            from core.mcp_server import start_mcp_server
            if start_mcp_server(adapter=self, port=8083):
                logger.info("ArtClaw: MCP Server started on port 8083")
            else:
                logger.warning(
                    "ArtClaw: MCP Server failed to start (will retry on connect)"
                )
        except Exception as e:
            logger.error("ArtClaw: MCP Server startup error: %s", e)

    def on_shutdown(self) -> None:
        """Blender 关闭时调用 — 清理资源"""
        global _timer_registered
        logger.info("ArtClaw: Blender adapter shutdown")

        # 停止 MCP Server
        try:
            from core.mcp_server import stop_mcp_server
            stop_mcp_server()
        except Exception:
            pass

        # 断开 Bridge 连接
        try:
            from core.bridge_dcc import DCCBridgeManager
            manager = DCCBridgeManager.instance()
            if manager.is_connected():
                manager.disconnect()
        except Exception:
            pass

        # 反注册 timer
        try:
            bpy = _require_blender()
            if bpy.app.timers.is_registered(_main_thread_consumer):
                bpy.app.timers.unregister(_main_thread_consumer)
            _timer_registered = False
        except Exception:
            pass

    # ── 主线程调度 ──

    def execute_on_main_thread(self, fn: Callable, *args) -> Any:
        """
        在 Blender 主线程执行函数（场景 API 安全）。

        通过 queue + bpy.app.timers 调度，阻塞等待结果（超时 30s）。
        如果已在主线程则直接执行。
        """
        # 快速路径：如果在主线程直接执行
        if threading.current_thread() is threading.main_thread():
            return fn(*args)

        _ensure_timer_registered()

        result_event = threading.Event()
        # result_container: [return_value, exception]
        result_container: list = [None, None]

        _main_thread_queue.put((fn, args, result_event, result_container))

        if not result_event.wait(timeout=30.0):
            raise TimeoutError(
                "execute_on_main_thread: 等待主线程执行超时 (30s)"
            )

        if result_container[1] is not None:
            raise result_container[1]

        return result_container[0]

    def execute_deferred(self, fn: Callable, *args) -> None:
        """
        延迟到主线程空闲时执行（非阻塞，不等待结果）。

        如果已在主线程则直接执行。
        """
        if threading.current_thread() is threading.main_thread():
            fn(*args)
            return

        _ensure_timer_registered()
        _main_thread_queue.put((fn, args, None, None))

    # ── 上下文采集 ──

    def get_selected_objects(self) -> List[Dict]:
        """获取当前选中对象列表"""
        bpy = _require_blender()
        result = []
        for obj in bpy.context.selected_objects:
            result.append({
                "name": obj.name,
                "long_name": obj.name,
                "type": obj.type,
            })
        return result

    def get_scene_info(self) -> Dict:
        """获取当前场景基本信息"""
        bpy = _require_blender()
        scene = bpy.context.scene

        scene_file = bpy.data.filepath or "untitled"
        object_count = len(bpy.data.objects)
        mesh_count = len([o for o in bpy.data.objects if o.type == "MESH"])

        return {
            "scene_file": scene_file,
            "object_count": object_count,
            "mesh_count": mesh_count,
            "frame_range": [scene.frame_start, scene.frame_end],
            "fps": scene.render.fps,
            "up_axis": "Z",
        }

    def get_current_file(self) -> Optional[str]:
        """获取当前文件路径"""
        bpy = _require_blender()
        path = bpy.data.filepath
        return path if path else None

    # ── UI 集成 ──

    def get_main_window(self) -> Any:
        """
        获取主窗口句柄。

        Blender 没有 Qt 主窗口，Qt UI 由 BlenderQtBridge 在子线程独立创建，
        因此此处返回 None。
        """
        return None

    def register_menu(self, menu_name: str, callback: Callable) -> None:
        """
        注册菜单入口。

        Blender 的菜单/面板通过 bpy.types.Panel + addon 的 register() 管理，
        不在 adapter 内创建。此处仅记录日志。
        """
        logger.info(
            "ArtClaw: register_menu('%s') — Blender 菜单由 addon 管理，跳过",
            menu_name,
        )

    # ── 代码执行 ──

    def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict:
        """
        在 Blender 环境中执行 Python 代码。

        上下文变量:
            S = 选中对象列表 (list[bpy.types.Object])
            W = 当前场景文件路径 (str)
            L = bpy 模块（类比 Maya 的 cmds）
            C = bpy.context（Blender 惯例快捷变量）
            D = bpy.data（Blender 惯例快捷变量）
        """
        bpy = _require_blender()

        # 构建执行环境
        # 预注入变量放 exec_globals，确保 def 内部也能访问（Python exec 的闭包规则）
        exec_globals = {
            "__builtins__": __builtins__,
            "bpy": bpy,
            "S": list(bpy.context.selected_objects),
            "W": bpy.data.filepath or "",
            "L": bpy,
            "C": bpy.context,
            "D": bpy.data,
        }
        exec_locals: Dict = {}

        if context:
            exec_globals.update(context)

        # 捕获 stdout
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture

            # Undo 包装：在执行前创建 undo 步骤
            bpy.ops.ed.undo_push(message="ArtClaw AI")
            exec(code, exec_globals, exec_locals)

            output = stdout_capture.getvalue()
            result = exec_locals.get("result") or exec_globals.get("result")

            return {
                "success": True,
                "result": result,
                "error": None,
                "output": output,
            }

        except Exception as e:
            output = stdout_capture.getvalue()
            return {
                "success": False,
                "result": None,
                "error": f"{type(e).__name__}: {str(e)}",
                "output": output,
            }

        finally:
            sys.stdout = old_stdout
