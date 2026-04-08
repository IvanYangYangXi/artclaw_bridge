"""
maya_adapter.py - Maya 适配层实现
==================================

Maya 2022+ (Python 3.9+, PySide2/Qt 5.15)

所有 maya.cmds / OpenMaya 调用集中在此文件。
其余模块（UI / Bridge / Skill）通过 adapter 接口访问 Maya 功能。
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Callable, Dict, List, Optional

from .base_adapter import BaseDCCAdapter

logger = logging.getLogger("artclaw.maya")


def _require_maya():
    """延迟 import maya 模块，仅在 Maya 环境中可用"""
    import maya.cmds as cmds
    import maya.utils
    import maya.OpenMayaUI as omui
    return cmds, maya.utils, omui


class MayaAdapter(BaseDCCAdapter):
    """Maya DCC 适配层"""

    def __init__(self):
        self._panel = None  # Chat Panel 实例引用
        self._menu_name = "ArtClawMenu"

    # ── 基础信息 ──

    def get_software_name(self) -> str:
        return "maya"

    def get_software_version(self) -> str:
        cmds, _, _ = _require_maya()
        return cmds.about(version=True)

    def get_python_version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # ── 生命周期 ──

    def on_startup(self) -> None:
        """Maya 启动时调用 — 注册菜单 + 启动 MCP Server"""
        logger.info("ArtClaw: Maya adapter startup")
        self.register_menu(self._menu_name, self._open_chat_panel)

        # 设置 DCC 名称（影响 Gateway session key）
        try:
            from core.bridge_dcc import DCCBridgeManager
            DCCBridgeManager.set_dcc_name("maya")
        except Exception:
            pass

        # 启动 MCP Server（独立线程，不阻塞 Maya）
        try:
            from core.mcp_server import start_mcp_server
            if start_mcp_server(adapter=self):
                logger.info("ArtClaw: MCP Server started")
            else:
                logger.warning("ArtClaw: MCP Server failed to start (will retry on connect)")
        except Exception as e:
            logger.error(f"ArtClaw: MCP Server startup error: {e}")

    def on_shutdown(self) -> None:
        """Maya 关闭时调用 — 清理"""
        logger.info("ArtClaw: Maya adapter shutdown")

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

        # 清理菜单
        try:
            cmds, _, _ = _require_maya()
            if cmds.menu(self._menu_name, exists=True):
                cmds.deleteUI(self._menu_name)
        except Exception:
            pass

    # ── 主线程调度 ──

    def execute_on_main_thread(self, fn: Callable, *args) -> Any:
        """在 Maya 主线程执行函数（场景 API 安全）"""
        _, utils, _ = _require_maya()
        return utils.executeInMainThreadWithResult(fn, *args)

    def execute_deferred(self, fn: Callable, *args) -> None:
        """延迟到主线程空闲时执行"""
        _, utils, _ = _require_maya()
        if args:
            utils.executeDeferred(lambda: fn(*args))
        else:
            utils.executeDeferred(fn)

    # ── 上下文采集 ──

    def get_selected_objects(self) -> List[Dict]:
        cmds, _, _ = _require_maya()
        sel = cmds.ls(selection=True, long=True) or []
        result = []
        for obj in sel:
            short_name = obj.split("|")[-1]
            try:
                obj_type = cmds.objectType(obj)
            except Exception:
                obj_type = "unknown"
            result.append({
                "name": short_name,
                "long_name": obj,
                "type": obj_type,
            })
        return result

    def get_scene_info(self) -> Dict:
        cmds, _, _ = _require_maya()
        scene_file = cmds.file(query=True, sceneName=True) or "untitled"
        all_transforms = cmds.ls(type="transform") or []
        all_meshes = cmds.ls(type="mesh") or []

        start_frame = cmds.playbackOptions(query=True, minTime=True)
        end_frame = cmds.playbackOptions(query=True, maxTime=True)

        return {
            "scene_file": scene_file,
            "object_count": len(all_transforms),
            "mesh_count": len(all_meshes),
            "frame_range": [int(start_frame), int(end_frame)],
            "fps": cmds.currentUnit(query=True, time=True),
            "up_axis": cmds.upAxis(query=True, axis=True),
        }

    def get_current_file(self) -> Optional[str]:
        cmds, _, _ = _require_maya()
        path = cmds.file(query=True, sceneName=True)
        return path if path else None

    # ── UI 集成 ──

    def get_main_window(self) -> Any:
        """获取 Maya 主窗口的 QMainWindow 实例"""
        _, _, omui = _require_maya()
        from shiboken2 import wrapInstance
        from PySide2 import QtWidgets

        ptr = omui.MQtUtil.mainWindow()
        if ptr is not None:
            return wrapInstance(int(ptr), QtWidgets.QMainWindow)
        return None

    def register_menu(self, menu_name: str, callback: Callable) -> None:
        """在 Maya 菜单栏注册 ArtClaw 入口"""
        cmds, _, _ = _require_maya()

        # 删除已有菜单（防止重复）
        if cmds.menu(menu_name, exists=True):
            cmds.deleteUI(menu_name)

        cmds.menu(menu_name, label="ArtClaw", parent="MayaWindow", tearOff=False)
        cmds.menuItem(label="打开 Chat Panel", command=lambda _: callback())
        cmds.menuItem(divider=True)
        cmds.menuItem(label="连接诊断", command=lambda _: self._run_diagnostics())
        cmds.menuItem(label="关于", command=lambda _: self._show_about())

    # ── 代码执行 ──

    def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict:
        """
        在 Maya 环境中执行 Python 代码。

        上下文变量:
            S = 选中对象列表
            W = 当前场景文件路径
            L = maya.cmds 模块
        """
        cmds, _, _ = _require_maya()

        # 构建执行环境
        # 预注入变量放 exec_globals，确保 def 内部也能访问（Python exec 的闭包规则）
        exec_globals = {
            "__builtins__": __builtins__,
            "cmds": cmds,
            "S": cmds.ls(selection=True, long=True) or [],
            "W": cmds.file(query=True, sceneName=True) or "",
            "L": cmds,
        }
        exec_locals: Dict = {}

        if context:
            exec_globals.update(context)

        # 捕获 stdout
        import io
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture

            # Undo 包装
            cmds.undoInfo(openChunk=True, chunkName="ArtClaw_AI")
            try:
                exec(code, exec_globals, exec_locals)
            finally:
                cmds.undoInfo(closeChunk=True)

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

    # ── 内部方法 ──

    def _open_chat_panel(self):
        """打开或显示 Chat Panel"""
        try:
            from artclaw_ui.chat_panel import show_chat_panel
            self._panel = show_chat_panel(parent=self.get_main_window(), adapter=self)
        except Exception as e:
            logger.error(f"ArtClaw: Failed to open Chat Panel: {e}")
            cmds, _, _ = _require_maya()
            cmds.warning(f"ArtClaw: 打开 Chat Panel 失败: {e}")

    def _run_diagnostics(self):
        """运行连接诊断"""
        try:
            from core.bridge_dcc import DCCBridgeManager
            report = DCCBridgeManager.instance().run_diagnostics()
            logger.info(report)
            # 也在 Script Editor 显示
            print(report)
        except Exception as e:
            logger.error(f"Diagnostics failed: {e}")

    def _show_about(self):
        """显示关于信息"""
        cmds, _, _ = _require_maya()
        cmds.confirmDialog(
            title="ArtClaw",
            message="ArtClaw DCC Bridge\nMaya Adapter\n\nhttps://github.com/IvanYangYangXi/artclaw_bridge",
            button=["OK"],
        )
