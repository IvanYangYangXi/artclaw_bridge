"""
houdini_adapter.py - Houdini 适配层实现
=========================================

Houdini 19.5+ (Python 3.9+, PySide2/Qt 5.15)

所有 hou / hdefereval 调用集中在此文件。
其余模块（UI / Bridge / Skill）通过 adapter 接口访问 Houdini 功能。

坐标系: Y-up（Houdini 默认）
主线程调度: hdefereval
Undo: hou.undos.group() context manager
Qt: hou.qt.mainWindow() 原生支持
"""

from __future__ import annotations

import io
import logging
import sys
from typing import Any, Callable, Dict, List, Optional

from .base_adapter import BaseDCCAdapter

logger = logging.getLogger("artclaw.houdini")


# ── 延迟 import ──

def _require_houdini():
    """延迟 import hou 模块，仅在 Houdini 环境中可用"""
    import hou
    return hou


def _require_hdefereval():
    """延迟 import hdefereval 主线程调度模块"""
    import hdefereval
    return hdefereval


class HoudiniAdapter(BaseDCCAdapter):
    """Houdini DCC 适配层"""

    def __init__(self):
        super().__init__()  # 初始化持久化命名空间
        self._panel = None  # Chat Panel 实例引用

    # ── 基础信息 ──

    def get_software_name(self) -> str:
        return "houdini"

    def get_software_version(self) -> str:
        """返回 Houdini 版本字符串，如 '20.5.332'"""
        hou = _require_houdini()
        return hou.applicationVersionString()

    def get_python_version(self) -> str:
        return (
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )

    # ── 生命周期 ──

    def on_startup(self) -> None:
        """Houdini 启动时调用 — 设置 Bridge + 启动 MCP Server"""
        logger.info("ArtClaw: Houdini adapter startup")

        # 设置 DCC 名称（影响 Gateway session key）
        try:
            from core.bridge_dcc import DCCBridgeManager
            DCCBridgeManager.set_dcc_name("houdini")
        except Exception as exc:
            logger.warning(f"ArtClaw: Failed to set DCC name: {exc}")

        # 启动 MCP Server（独立线程，不阻塞 Houdini）
        try:
            from core.mcp_server import start_mcp_server
            if start_mcp_server(adapter=self, port=8084):
                logger.info("ArtClaw: MCP Server started on port 8084")
            else:
                logger.warning(
                    "ArtClaw: MCP Server failed to start "
                    "(will retry on connect)"
                )
        except Exception as exc:
            logger.error(f"ArtClaw: MCP Server startup error: {exc}")

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
        """Houdini 关闭时调用 — 停止 MCP Server + 断开 Bridge"""
        logger.info("ArtClaw: Houdini adapter shutdown")

        # Clean up event manager
        try:
            if hasattr(self, '_event_manager') and self._event_manager:
                self._event_manager.unregister_all()
        except Exception:
            pass

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

        # 清理 Chat Panel
        if self._panel is not None:
            try:
                self._panel.close()
            except Exception:
                pass
            self._panel = None

    # ── 主线程调度 ──

    def execute_on_main_thread(self, fn: Callable, *args) -> Any:
        """
        在 Houdini 主线程同步执行函数（场景 API 安全）。

        使用 hdefereval.executeInMainThreadWithResult，
        阻塞调用线程直到主线程完成执行并返回结果。
        """
        hdefereval = _require_hdefereval()
        return hdefereval.executeInMainThreadWithResult(fn, *args)

    def execute_deferred(self, fn: Callable, *args) -> None:
        """
        延迟到 Houdini 主线程空闲时执行（非阻塞）。

        hdefereval.executeDeferred 接收无参 callable，
        有参数时用 lambda 包装。
        """
        hdefereval = _require_hdefereval()
        if args:
            hdefereval.executeDeferred(lambda: fn(*args))
        else:
            hdefereval.executeDeferred(fn)

    # ── 上下文采集 ──

    def get_selected_objects(self) -> List[Dict]:
        """
        获取当前选中的 Houdini 节点列表。

        返回格式:
            [{"name": "geo1", "long_name": "/obj/geo1", "type": "geo"}, ...]
        """
        hou = _require_houdini()
        nodes = hou.selectedNodes()
        result = []
        for node in nodes:
            result.append({
                "name": node.name(),
                "long_name": node.path(),
                "type": node.type().name(),
            })
        return result

    def get_scene_info(self) -> Dict:
        """
        获取当前 Houdini 场景基本信息。

        包括: 场景文件、对象数、Geometry 数、帧范围、FPS、坐标轴朝向。
        """
        hou = _require_houdini()

        # 场景文件路径
        scene_file = hou.hipFile.path() or "untitled"

        # 统计 /obj 下的节点
        obj_context = hou.node("/obj")
        object_count = 0
        geometry_count = 0

        if obj_context is not None:
            children = obj_context.children()
            object_count = len(children)
            geometry_count = sum(
                1 for child in children
                if child.type().name() == "geo"
            )

        # 帧范围与 FPS
        frame_range_tuple = hou.playbar.frameRange()
        frame_range = [
            int(frame_range_tuple[0]),
            int(frame_range_tuple[1]),
        ]
        fps = hou.fps()

        return {
            "scene_file": scene_file,
            "object_count": object_count,
            "geometry_count": geometry_count,
            "frame_range": frame_range,
            "fps": fps,
            "up_axis": "Y",  # Houdini 默认 Y-up
        }

    def get_current_file(self) -> Optional[str]:
        """获取当前 hip 文件路径，未保存则返回 None"""
        hou = _require_houdini()
        path = hou.hipFile.path()
        if not path or "untitled" in path.lower():
            return None
        return path

    # ── UI 集成 ──

    def get_main_window(self) -> Any:
        """
        获取 Houdini 主窗口的 QMainWindow 实例。

        优先使用 hou.qt.mainWindow()（Houdini 原生 Qt 支持），
        失败时 fallback 到 QApplication 遍历查找。
        """
        try:
            hou = _require_houdini()
            return hou.qt.mainWindow()
        except Exception:
            pass

        # Fallback: 从 QApplication 顶层窗口中查找 QMainWindow
        try:
            try:
                from PySide2 import QtWidgets
            except ImportError:
                from PySide6 import QtWidgets
            app = QtWidgets.QApplication.instance()
            if app is not None:
                for widget in app.topLevelWidgets():
                    if isinstance(widget, QtWidgets.QMainWindow):
                        return widget
        except ImportError:
            pass

        logger.warning("ArtClaw: Failed to get Houdini main window")
        return None

    def register_menu(self, menu_name: str, callback: Callable) -> None:
        """
        注册菜单入口（占位实现）。

        Houdini 菜单通过 shelf tool 或 XML 定义注册，
        不支持运行时动态创建菜单栏入口。
        实际入口见 houdini_shelf.py。
        """
        logger.info(
            f"ArtClaw: Menu '{menu_name}' registered (via shelf tool). "
            f"Callback: {callback.__name__ if callable(callback) else callback}"
        )

    # ── 代码执行 ──

    def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict:
        """
        在 Houdini 环境中执行 Python 代码。

        使用持久化命名空间：跨调用保持用户定义的变量。
        每次调用时 DCC 上下文变量（S/W/L/hou）会刷新为最新值。

        上下文变量:
            S = 当前选中节点列表 (hou.selectedNodes())
            W = 当前 hip 文件路径
            L = hou 模块
            hou = hou 模块

        所有操作包裹在 hou.undos.group 中，支持 Ctrl+Z 撤销。

        Returns:
            {"success": bool, "result": Any, "error": str|None, "output": str}
        """
        hou = _require_houdini()

        # ── 持久化命名空间：刷新 DCC 上下文变量 ──
        ns = self._exec_namespace
        ns.update({
            "__builtins__": __builtins__,
            "hou": hou,
            "S": hou.selectedNodes(),
            "W": hou.hipFile.path() or "",
            "L": hou,
        })

        if context:
            ns.update(context)

        # 清除上次的 result
        ns.pop("result", None)

        # 捕获 stdout
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture

            # Undo 包装: Houdini 使用 context manager
            with hou.undos.group("ArtClaw AI"):
                exec(code, ns)

            output = stdout_capture.getvalue()
            result = ns.get("result")

            return {
                "success": True,
                "result": result,
                "error": None,
                "output": output,
            }

        except Exception as exc:
            output = stdout_capture.getvalue()
            return {
                "success": False,
                "result": None,
                "error": f"{type(exc).__name__}: {str(exc)}",
                "output": output,
            }

        finally:
            sys.stdout = old_stdout

    # ── 内部方法 ──

    def _open_chat_panel(self) -> None:
        """打开或显示 Chat Panel"""
        try:
            from artclaw_ui.chat_panel import show_chat_panel
            self._panel = show_chat_panel(
                parent=self.get_main_window(),
                adapter=self,
            )
        except Exception as exc:
            logger.error(f"ArtClaw: Failed to open Chat Panel: {exc}")
