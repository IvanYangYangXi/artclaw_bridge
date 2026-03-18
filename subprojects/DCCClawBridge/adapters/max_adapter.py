"""
max_adapter.py - 3ds Max 适配层实现
=====================================

3ds Max 2024+ (Python 3.9+, PySide2/Qt 5.15)

所有 pymxs / MaxPlus 调用集中在此文件。
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Callable, Dict, List, Optional

from .base_adapter import BaseDCCAdapter

logger = logging.getLogger("artclaw.max")


def _require_max():
    """延迟 import pymxs 模块"""
    import pymxs
    return pymxs


class MaxAdapter(BaseDCCAdapter):
    """3ds Max DCC 适配层"""

    def __init__(self):
        self._panel = None
        self._menu_name = "ArtClaw"

    # ── 基础信息 ──

    def get_software_name(self) -> str:
        return "max"

    def get_software_version(self) -> str:
        pymxs = _require_max()
        # pymxs.runtime.maxVersion() 返回 tuple: (version_number, ...)
        try:
            ver = pymxs.runtime.maxVersion()
            # ver[0] 是如 26000 (Max 2024), 27000 (Max 2025)
            year = 1998 + (ver[0] // 1000)
            return str(year)
        except Exception:
            return "unknown"

    def get_python_version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # ── 生命周期 ──

    def on_startup(self) -> None:
        logger.info("ArtClaw: Max adapter startup")
        self.register_menu(self._menu_name, self._open_chat_panel)

        # 启动 MCP Server
        try:
            from core.mcp_server import start_mcp_server
            if start_mcp_server(adapter=self, port=8082):
                logger.info("ArtClaw: MCP Server started")
        except Exception as e:
            logger.error(f"ArtClaw: MCP Server startup error: {e}")

    def on_shutdown(self) -> None:
        logger.info("ArtClaw: Max adapter shutdown")
        try:
            from core.mcp_server import stop_mcp_server
            stop_mcp_server()
        except Exception:
            pass
        try:
            from core.bridge_dcc import DCCBridgeManager
            manager = DCCBridgeManager.instance()
            if manager.is_connected():
                manager.disconnect()
        except Exception:
            pass

    # ── 主线程调度 ──

    def execute_on_main_thread(self, fn: Callable, *args) -> Any:
        """在 Max 主线程执行"""
        # pymxs 本身在主线程调用是安全的
        # 但如果从其他线程调用，需要用 QTimer
        try:
            from PySide2.QtCore import QTimer
            import queue
            result_queue = queue.Queue()

            def _run():
                try:
                    result_queue.put(("ok", fn(*args)))
                except Exception as e:
                    result_queue.put(("error", e))

            QTimer.singleShot(0, _run)
            status, value = result_queue.get(timeout=30)
            if status == "error":
                raise value
            return value
        except ImportError:
            # 无 Qt，直接调用（假设已在主线程）
            return fn(*args)

    def execute_deferred(self, fn: Callable, *args) -> None:
        try:
            from PySide2.QtCore import QTimer
            if args:
                QTimer.singleShot(0, lambda: fn(*args))
            else:
                QTimer.singleShot(0, fn)
        except ImportError:
            fn(*args)

    # ── 上下文采集 ──

    def get_selected_objects(self) -> List[Dict]:
        pymxs = _require_max()
        rt = pymxs.runtime
        selection = rt.getCurrentSelection()
        result = []
        if selection:
            for obj in selection:
                try:
                    result.append({
                        "name": str(obj.name),
                        "long_name": str(obj.name),
                        "type": str(rt.classOf(obj)),
                    })
                except Exception:
                    pass
        return result

    def get_scene_info(self) -> Dict:
        pymxs = _require_max()
        rt = pymxs.runtime

        # 场景文件
        scene_file = str(rt.maxFilePath) + str(rt.maxFileName)
        if not rt.maxFileName:
            scene_file = "untitled"

        # 对象统计
        all_objects = list(rt.objects) if hasattr(rt, 'objects') else []
        geometry = [o for o in all_objects if str(rt.superClassOf(o)) == "GeometryClass"]

        # 帧范围
        start_frame = int(rt.animationRange.start)
        end_frame = int(rt.animationRange.end)

        # FPS
        fps = int(rt.frameRate)

        return {
            "scene_file": scene_file,
            "object_count": len(all_objects),
            "geometry_count": len(geometry),
            "frame_range": [start_frame, end_frame],
            "fps": fps,
        }

    def get_current_file(self) -> Optional[str]:
        pymxs = _require_max()
        rt = pymxs.runtime
        path = str(rt.maxFilePath) + str(rt.maxFileName)
        return path if rt.maxFileName else None

    # ── UI 集成 ──

    def get_main_window(self) -> Any:
        """获取 Max 主窗口"""
        try:
            from pymxs import runtime as rt
            import ctypes
            # GetQmaxMainWindow 在 Max 2020+
            main_window = rt.windows.getMAXHWND()
            if main_window:
                from PySide2 import QtWidgets
                from shiboken2 import wrapInstance
                return wrapInstance(int(main_window), QtWidgets.QMainWindow)
        except Exception:
            pass

        # Fallback: 通过 QApplication
        try:
            from PySide2 import QtWidgets
            app = QtWidgets.QApplication.instance()
            if app:
                for w in app.topLevelWidgets():
                    if isinstance(w, QtWidgets.QMainWindow):
                        return w
        except Exception:
            pass

        return None

    def register_menu(self, menu_name: str, callback: Callable) -> None:
        """在 Max 中注册菜单（通过 pymxs.runtime）"""
        try:
            pymxs = _require_max()
            rt = pymxs.runtime

            # 用 MaxScript 创建菜单
            rt.execute(f'''
                macroScript ArtClaw_OpenChat
                    category:"ArtClaw"
                    tooltip:"Open ArtClaw Chat Panel"
                (
                    python.execute "from adapters.max_adapter import _open_chat_panel_global; _open_chat_panel_global()"
                )
            ''')
            logger.info("ArtClaw: Max menu macro registered")
        except Exception as e:
            logger.warning(f"ArtClaw: Failed to register Max menu: {e}")

    # ── 代码执行 ──

    def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict:
        """在 Max 环境中执行 Python 代码"""
        pymxs = _require_max()
        rt = pymxs.runtime

        exec_globals = {"__builtins__": __builtins__}
        exec_locals = {
            "rt": rt,
            "pymxs": pymxs,
            "S": list(rt.getCurrentSelection()) if rt.getCurrentSelection() else [],
            "W": str(rt.maxFilePath) + str(rt.maxFileName) if rt.maxFileName else "",
            "L": rt,  # MaxScript runtime as the "library"
        }

        if context:
            exec_locals.update(context)

        import io
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture

            # Max undo 包装
            with pymxs.undo(True, "ArtClaw AI"):
                exec(code, exec_globals, exec_locals)

            output = stdout_capture.getvalue()
            result = exec_locals.get("result", None)

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

    # ── 内部方法 ──

    def _open_chat_panel(self):
        try:
            from artclaw_ui.chat_panel import show_chat_panel
            self._panel = show_chat_panel(parent=self.get_main_window(), adapter=self)
        except Exception as e:
            logger.error(f"ArtClaw: Failed to open Chat Panel: {e}")


# 全局引用（供 MaxScript 宏调用）
_global_adapter: Optional[MaxAdapter] = None


def _open_chat_panel_global():
    """MaxScript 宏调用入口"""
    global _global_adapter
    if _global_adapter:
        _global_adapter._open_chat_panel()
