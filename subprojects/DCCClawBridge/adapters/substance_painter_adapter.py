"""
substance_painter_adapter.py - Substance Painter 适配层实现
=============================================================

Substance Painter 2021+ (Python 3.7+, PySide2/Qt 5.15)

所有 substance_painter 调用集中在此文件。
其余模块（UI / Bridge / Skill）通过 adapter 接口访问 SP 功能。

注意：
    - SP 没有 undo group API，execute_code 不做 undo 包装
    - SP 没有传统的"选中物体"概念，get_selected_objects 返回 texture set 列表
    - 主线程调度通过 QTimer.singleShot(0, ...) 实现
"""

from __future__ import annotations

import io
import logging
import queue
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

from .base_adapter import BaseDCCAdapter

logger = logging.getLogger("artclaw.substance_painter")


def _require_sp():
    """延迟 import substance_painter 模块，仅在 SP 环境中可用"""
    import substance_painter as sp
    import substance_painter.project       # noqa: F401
    import substance_painter.textureset    # noqa: F401
    import substance_painter.layerstack    # noqa: F401
    import substance_painter.ui            # noqa: F401
    return sp


class SubstancePainterAdapter(BaseDCCAdapter):
    """Substance Painter DCC 适配层"""

    def __init__(self):
        self._panel = None
        self._main_queue: queue.Queue = queue.Queue()
        self._poll_timer = None

    # ── 基础信息 ──

    def get_software_name(self) -> str:
        return "substance_painter"

    def get_software_version(self) -> str:
        """返回 SP 版本号"""
        try:
            sp = _require_sp()
            # SP 2021+ 提供 application.version()
            if hasattr(sp, "application") and hasattr(sp.application, "version"):
                return str(sp.application.version())
        except Exception:
            pass
        try:
            sp = _require_sp()
            if hasattr(sp, "__version__"):
                return str(sp.__version__)
        except Exception:
            pass
        return "unknown"

    def get_python_version(self) -> str:
        return (
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )

    # ── 生命周期 ──

    def on_startup(self) -> None:
        """SP 启动时调用 — 设置 DCC 名称 + 启动 MCP Server"""
        logger.info("ArtClaw: Substance Painter adapter startup")

        # 设置 DCC 名称（影响 Gateway session key）
        try:
            from core.bridge_dcc import DCCBridgeManager
            DCCBridgeManager.set_dcc_name("substance_painter")
        except Exception:
            pass

        # 启动 MCP Server
        try:
            from core.mcp_server import start_mcp_server
            if start_mcp_server(adapter=self, port=8085):
                logger.info("ArtClaw: MCP Server started on port 8085")
            else:
                logger.warning(
                    "ArtClaw: MCP Server failed to start "
                    "(will retry on connect)"
                )
        except Exception as e:
            logger.error("ArtClaw: MCP Server startup error: %s", e)

        # 启动主线程队列轮询 timer
        self._start_poll_timer()

    def _start_poll_timer(self) -> None:
        """启动 QTimer 定期消费主线程队列（50ms 间隔）"""
        if self._poll_timer is not None:
            return
        try:
            try:
                from PySide2.QtCore import QTimer
            except ImportError:
                from PySide6.QtCore import QTimer

            self._poll_timer = QTimer()
            self._poll_timer.setInterval(50)
            self._poll_timer.timeout.connect(self._consume_main_queue)
            self._poll_timer.start()
            logger.info("ArtClaw: Main thread poll timer started (50ms)")
        except Exception as e:
            logger.warning("ArtClaw: Failed to start poll timer: %s", e)

    def _consume_main_queue(self) -> None:
        """消费主线程队列中的任务（每次 tick 最多 10 个）"""
        processed = 0
        while not self._main_queue.empty() and processed < 10:
            try:
                fn, args = self._main_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except Exception as e:
                logger.error("Main thread task failed: %s", e, exc_info=True)
            processed += 1

    def on_shutdown(self) -> None:
        """SP 关闭时调用 — 清理资源"""
        logger.info("ArtClaw: Substance Painter adapter shutdown")

        # 停止轮询 timer
        if self._poll_timer is not None:
            try:
                self._poll_timer.stop()
            except Exception:
                pass
            self._poll_timer = None

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

    # ── 主线程调度 ──

    def execute_on_main_thread(self, fn: Callable, *args) -> Any:
        """
        在 SP 主线程执行函数（场景 API 安全）。

        通过 _main_queue + QTimer 轮询调度，
        阻塞等待结果（超时 30s）。
        如果已在主线程则直接执行。
        """
        if threading.current_thread() is threading.main_thread():
            return fn(*args)

        result_queue: queue.Queue = queue.Queue()

        def _run():
            try:
                result_queue.put(("ok", fn(*args)))
            except Exception as e:
                result_queue.put(("error", e))

        self._main_queue.put((_run, ()))

        try:
            status, value = result_queue.get(timeout=30)
        except queue.Empty:
            raise TimeoutError(
                "execute_on_main_thread: 等待主线程执行超时 (30s)"
            )

        if status == "error":
            raise value
        return value

    def execute_deferred(self, fn: Callable, *args) -> None:
        """延迟到主线程空闲时执行（非阻塞），通过队列调度"""
        self._main_queue.put((fn, args))

    # ── 上下文采集 ──

    def get_selected_objects(self) -> List[Dict]:
        """
        获取当前 texture set 列表。

        SP 没有传统的"选中物体"概念，
        返回所有 texture set 作为等价物。
        """
        try:
            sp = _require_sp()
            if not sp.project.is_open():
                return []
            all_sets = sp.textureset.all_texture_sets()
            return [
                {
                    "name": ts.name(),
                    "long_name": ts.name(),
                    "type": "TextureSet",
                }
                for ts in all_sets
            ]
        except Exception as e:
            logger.warning("get_selected_objects 失败: %s", e)
            return []

    def get_scene_info(self) -> Dict:
        """获取当前项目基本信息"""
        try:
            sp = _require_sp()
            if not sp.project.is_open():
                return {
                    "scene_file": "no project open",
                    "texture_set_count": 0,
                    "texture_sets": [],
                    "has_unsaved_changes": False,
                }

            all_sets = sp.textureset.all_texture_sets()
            ts_names = [ts.name() for ts in all_sets]

            # file_path
            file_path = "untitled"
            try:
                fp = sp.project.file_path()
                if fp:
                    file_path = str(fp)
            except Exception:
                pass

            # unsaved changes
            has_unsaved = False
            if hasattr(sp.project, "needs_saving"):
                try:
                    has_unsaved = sp.project.needs_saving()
                except Exception:
                    pass

            return {
                "scene_file": file_path,
                "texture_set_count": len(all_sets),
                "texture_sets": ts_names,
                "has_unsaved_changes": has_unsaved,
            }
        except Exception as e:
            logger.warning("get_scene_info 失败: %s", e)
            return {
                "scene_file": "error",
                "texture_set_count": 0,
                "texture_sets": [],
                "has_unsaved_changes": False,
            }

    def get_current_file(self) -> Optional[str]:
        """获取当前项目文件路径"""
        try:
            sp = _require_sp()
            if sp.project.is_open():
                fp = sp.project.file_path()
                return str(fp) if fp else None
        except Exception:
            pass
        return None

    # ── UI 集成 ──

    def get_main_window(self) -> Any:
        """
        获取 SP 主窗口句柄。

        优先使用 sp.ui.get_main_window()，
        fallback 到 QApplication 顶级窗口。
        """
        try:
            sp = _require_sp()
            main_win = sp.ui.get_main_window()
            if main_win:
                return main_win
        except Exception:
            pass

        # Fallback: 通过 QApplication 查找
        try:
            try:
                from PySide2 import QtWidgets
            except ImportError:
                from PySide6 import QtWidgets
            app = QtWidgets.QApplication.instance()
            if app:
                for w in app.topLevelWidgets():
                    if isinstance(w, QtWidgets.QMainWindow):
                        return w
        except Exception:
            pass

        return None

    def register_menu(self, menu_name: str, callback: Callable) -> None:
        """
        注册菜单入口（占位）。

        SP plugin 的菜单/UI 通过 plugin 约定管理，
        不在 adapter 内直接创建。
        """
        logger.info(
            "ArtClaw: register_menu('%s') — "
            "SP 菜单由 plugin 管理，此处跳过",
            menu_name,
        )

    # ── 代码执行 ──

    def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict:
        """
        在 SP 环境中执行 Python 代码。

        上下文变量:
            S = texture set 列表 (list)
            W = 当前项目文件路径 (str)
            L = substance_painter 模块

        注意: SP 不支持 undo group API，不做 undo 包装。
        """
        sp = _require_sp()

        # 构建 texture set 列表
        texture_sets = []
        try:
            if sp.project.is_open():
                texture_sets = list(sp.textureset.all_texture_sets())
        except Exception:
            pass

        # 当前文件路径
        file_path = ""
        try:
            if sp.project.is_open():
                fp = sp.project.file_path()
                if fp:
                    file_path = str(fp)
        except Exception:
            pass

        exec_globals = {"__builtins__": __builtins__}
        exec_locals = {
            "sp": sp,
            "substance_painter": sp,
            "S": texture_sets,
            "W": file_path,
            "L": sp,
        }

        if context:
            exec_locals.update(context)

        # 捕获 stdout
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture

            # SP 没有 undo group API，直接执行
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
        """打开 ArtClaw Chat Panel"""
        try:
            from artclaw_ui.chat_panel import show_chat_panel
            self._panel = show_chat_panel(
                parent=self.get_main_window(),
                adapter=self,
            )
        except Exception as e:
            logger.error("ArtClaw: Failed to open Chat Panel: %s", e)
