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
        super().__init__()  # 初始化持久化命名空间
        self._panel = None
        self._menu_name = "ArtClaw"

        # 主线程任务队列 + 轮询 timer
        import queue as _queue
        self._task_queue: _queue.Queue = _queue.Queue()
        self._poll_timer = None

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

        # 设置 DCC 名称（影响 Gateway session key）
        try:
            from core.bridge_dcc import DCCBridgeManager
            DCCBridgeManager.set_dcc_name("max")
        except Exception:
            pass

        # 启动 MCP Server
        try:
            from core.mcp_server import start_mcp_server
            if start_mcp_server(adapter=self, port=8082):
                logger.info("ArtClaw: MCP Server started")
        except Exception as e:
            logger.error(f"ArtClaw: MCP Server startup error: {e}")

        # 启动主线程轮询 timer（MCP 工具调用需要通过此 timer 调度到主线程）
        self._start_poll_timer()

        # Initialize event manager for Tool Manager triggers
        try:
            from core.dcc_event_manager import DCCEventManager, set_global_event_manager
            self._event_manager = DCCEventManager(self)
            set_global_event_manager(self._event_manager)
            self._event_manager.load_rules()
            self._event_manager.register_events()
            logger.info("ArtClaw: DCCEventManager initialized")
        except Exception as e:
            logger.warning(f"ArtClaw: DCCEventManager init failed (Tool Manager not running?): {e}")

    def on_shutdown(self) -> None:
        logger.info("ArtClaw: Max adapter shutdown")
        
        # Clean up event manager
        try:
            if hasattr(self, '_event_manager') and self._event_manager:
                self._event_manager.unregister_all()
        except Exception:
            pass
        
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

    def _start_poll_timer(self):
        """启动主线程轮询 timer（50ms 间隔，pump 任务队列）。

        QTimer.singleShot(0, fn) 在 Max 中不可靠（主线程可能不及时处理 Qt 事件），
        改用持久 QTimer 定期轮询任务队列，类似 Blender adapter 的方案。
        """
        if self._poll_timer is not None:
            return
        try:
            from PySide2.QtCore import QTimer
            self._poll_timer = QTimer()
            self._poll_timer.setInterval(50)
            self._poll_timer.timeout.connect(self._pump_tasks)
            self._poll_timer.start()
            logger.info("ArtClaw: Main-thread poll timer started (50ms)")
        except Exception as e:
            logger.warning(f"ArtClaw: Failed to start poll timer: {e}")

    def _pump_tasks(self):
        """在主线程中执行队列里的所有待处理任务。"""
        while not self._task_queue.empty():
            try:
                fn = self._task_queue.get_nowait()
                fn()
            except Exception as e:
                logger.error(f"ArtClaw: Task execution error: {e}")

    def execute_on_main_thread(self, fn: Callable, *args) -> Any:
        """在 Max 主线程执行函数并阻塞等待结果。

        pymxs 调用必须在主线程，通过任务队列 + 轮询 QTimer 实现跨线程调度。
        """
        import queue as _queue
        result_queue: _queue.Queue = _queue.Queue()

        def _run():
            try:
                result_queue.put(("ok", fn(*args)))
            except Exception as e:
                result_queue.put(("error", e))

        self._task_queue.put(_run)
        self._start_poll_timer()

        try:
            status, value = result_queue.get(timeout=60)
            if status == "error":
                raise value
            return value
        except _queue.Empty:
            raise TimeoutError("Max main thread execution timed out (60s)")

    def execute_deferred(self, fn: Callable, *args) -> None:
        """延迟到主线程执行（非阻塞）。"""
        if args:
            self._task_queue.put(lambda: fn(*args))
        else:
            self._task_queue.put(fn)
        self._start_poll_timer()

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
        """在 Max 中注册宏 + 主菜单项（幂等，不重复创建）"""
        try:
            pymxs = _require_max()
            rt = pymxs.runtime

            # 1. 注册 MacroScript
            rt.execute('''
                macroScript ArtClaw_OpenChat
                    category:"ArtClaw"
                    tooltip:"Open ArtClaw Chat Panel"
                (
                    python.execute "from adapters.max_adapter import _open_chat_panel_global; _open_chat_panel_global()"
                )
            ''')

            # 2. 添加到主菜单栏（幂等：先清理再创建）
            rt.execute('''
                -- 清理已有 ArtClaw 菜单
                for i = 1 to 5 do (
                    m = menuMan.findMenu "ArtClaw"
                    if m != undefined do menuMan.unRegisterMenu m
                )
                mainMenu = menuMan.getMainMenuBar()
                for i = mainMenu.numItems() to 1 by -1 do (
                    item = mainMenu.getItem i
                    if item != undefined and item.getTitle() == "ArtClaw" do
                        mainMenu.removeItemByPosition i
                )

                -- 创建新菜单
                artclawMenu = menuMan.createMenu "ArtClaw"
                chatAction = menuMan.createActionItem "ArtClaw_OpenChat" "ArtClaw"
                chatAction.setTitle "Chat Panel"
                chatAction.setUseCustomTitle true
                artclawMenu.addItem chatAction -1

                subItem = menuMan.createSubMenuItem "ArtClaw" artclawMenu
                mainMenu.addItem subItem (mainMenu.numItems())
                menuMan.updateMenuBar()
            ''')
            logger.info("ArtClaw: Max menu registered (menu bar + macro)")
        except Exception as e:
            logger.warning(f"ArtClaw: Menu registration failed: {e}")

    # ── 代码执行 ──

    def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict:
        """
        在 Max 环境中执行 Python 代码。

        使用持久化命名空间：跨调用保持用户定义的变量。
        每次调用时 DCC 上下文变量（S/W/L/rt/pymxs）会刷新为最新值。
        """
        pymxs = _require_max()
        rt = pymxs.runtime

        # ── 持久化命名空间：刷新 DCC 上下文变量 ──
        ns = self._exec_namespace
        ns.update({
            "__builtins__": __builtins__,
            "rt": rt,
            "pymxs": pymxs,
            "S": list(rt.getCurrentSelection()) if rt.getCurrentSelection() else [],
            "W": str(rt.maxFilePath) + str(rt.maxFileName) if rt.maxFileName else "",
            "L": rt,  # MaxScript runtime as the "library"
        })

        if context:
            ns.update(context)

        # 清除上次的 result
        ns.pop("result", None)

        import io
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture

            # Max undo 包装
            with pymxs.undo(True, "ArtClaw AI"):
                exec(code, ns)

            output = stdout_capture.getvalue()
            result = ns.get("result")

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
            # Max: 不传 parent（独立窗口），避免 shiboken2 wrapInstance 崩溃
            self._panel = show_chat_panel(parent=None, adapter=self)
        except Exception as e:
            logger.error(f"ArtClaw: Failed to open Chat Panel: {e}")
            import traceback
            traceback.print_exc()


# 全局引用（供 MaxScript 宏调用）
_global_adapter: Optional[MaxAdapter] = None


def _open_chat_panel_global():
    """MaxScript 宏调用入口"""
    global _global_adapter
    if _global_adapter:
        _global_adapter._open_chat_panel()
