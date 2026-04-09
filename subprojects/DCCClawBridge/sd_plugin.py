"""
sd_plugin.py - Substance Designer 插件入口
=============================================

放置到 SD 的用户插件目录:
  %USERPROFILE%\\Documents\\Adobe\\Adobe Substance 3D Designer\\python\\sduserplugins\\artclaw\\

SD 约定导出:
  - initializeSDPlugin()   — SD 加载插件时调用
  - uninitializeSDPlugin() — SD 卸载插件时调用

启动后通过菜单 ArtClaw → Open Chat 打开面板。
"""

from __future__ import annotations

import atexit
import logging
import os
import sys

logging.basicConfig(level=logging.INFO)

# SD renders stderr as red — route logging to stdout
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
logging.root.handlers = [_handler]

logger = logging.getLogger("artclaw.substance_designer")

# 全局状态：adapter 实例 + 运行标记
_global_state = {
    "adapter": None,
    "running": False,
    "menu_object_name": "artclaw_menu",  # SD menu objectName
    "atexit_registered": False,
}


def _setup_paths() -> bool:
    """将 DCCClawBridge 目录加入 sys.path"""
    plugin_dir = os.path.dirname(os.path.abspath(__file__))

    # 情况 1: sd_plugin.py 直接在 DCCClawBridge 根目录
    dcc_bridge_dir = plugin_dir

    # 检查 adapters 子目录是否存在作为验证
    if not os.path.isdir(os.path.join(dcc_bridge_dir, "adapters")):
        # 情况 2: 从环境变量获取
        env_path = os.environ.get("ARTCLAW_BRIDGE_PATH", "")
        if env_path and os.path.isdir(env_path):
            dcc_bridge_dir = os.path.join(env_path, "subprojects", "DCCClawBridge")

    if os.path.isdir(os.path.join(dcc_bridge_dir, "adapters")):
        if dcc_bridge_dir not in sys.path:
            sys.path.insert(0, dcc_bridge_dir)
        logger.info("ArtClaw: DCCClawBridge path = %s", dcc_bridge_dir)
        return True

    logger.warning("ArtClaw: DCCClawBridge not found")
    return False


def _check_integrity(dcc_bridge_dir: str) -> None:
    """共享模块完整性检查（非关键，失败跳过）"""
    try:
        core_dir = os.path.join(dcc_bridge_dir, "core")
        if not os.path.isdir(core_dir):
            return

        try:
            from integrity_check import check_and_repair
        except ImportError:
            bridge_dir = os.path.normpath(
                os.path.join(core_dir, "..", "..", "..", "core")
            )
            if os.path.isdir(bridge_dir) and bridge_dir not in sys.path:
                sys.path.insert(0, bridge_dir)
            from integrity_check import check_and_repair

        integrity = check_and_repair(core_dir, auto_repair=True)
        if integrity.repaired:
            logger.info("ArtClaw: 共享模块自动修复: %s", ", ".join(integrity.repaired))
        if not integrity.ok:
            logger.error("ArtClaw: 共享模块缺失: %s", ", ".join(integrity.failed))
    except Exception as e:
        logger.warning("ArtClaw: 完整性检查跳过: %s", e)


def _deferred_startup() -> None:
    """延迟启动：创建 adapter + 注册菜单（不自动打开面板）"""
    if _global_state["running"]:
        logger.warning("ArtClaw: already running, skip startup")
        return

    try:
        # 依赖安装
        from core.dependency_manager import ensure_dependencies

        def _on_deps(success, message):
            if success:
                logger.info("ArtClaw: %s", message)
            else:
                logger.warning("ArtClaw: %s", message)

        ensure_dependencies(callback=_on_deps)

        # 创建 adapter（MCP Server 等后台服务）
        from adapters.substance_designer_adapter import SubstanceDesignerAdapter

        adapter = SubstanceDesignerAdapter()
        adapter.on_startup()

        _global_state["adapter"] = adapter
        _global_state["running"] = True

        # 注入全局引用（方便调试）
        import builtins
        builtins._artclaw_adapter = adapter

        # 注册菜单入口
        _register_menu()

        # 注册 atexit 兜底清理
        if not _global_state["atexit_registered"]:
            atexit.register(_atexit_cleanup)
            _global_state["atexit_registered"] = True

        logger.info(
            "ArtClaw: Substance Designer adapter initialized "
            "(use ArtClaw > Open Chat to open panel)"
        )

    except Exception as e:
        logger.error("ArtClaw: Startup failed: %s", e)
        import traceback
        traceback.print_exc()


def _register_menu() -> None:
    """在 SD 菜单栏添加 'ArtClaw' 菜单 → 'Open Chat' 入口"""
    try:
        import sd
        from sd.api.qtforpythonuimgrwrapper import QtForPythonUIMgrWrapper

        ctx = sd.getContext()
        ui_mgr = QtForPythonUIMgrWrapper(ctx.getSDApplication().getUIMgr())

        menu = ui_mgr.newMenu("ArtClaw", _global_state["menu_object_name"])

        try:
            from PySide2 import QtWidgets
        except ImportError:
            from PySide6 import QtWidgets

        open_action = QtWidgets.QAction("Open Chat", None)
        open_action.triggered.connect(lambda: show_panel())
        menu.addAction(open_action)

        # 保存引用防止 GC
        _global_state["_menu_ref"] = menu
        _global_state["_action_ref"] = open_action

        logger.info("ArtClaw: Menu registered (ArtClaw > Open Chat)")
    except Exception as e:
        logger.warning("ArtClaw: Failed to register menu: %s", e)


def _atexit_cleanup() -> None:
    """atexit 兜底：确保后台线程正常关闭"""
    try:
        adapter = _global_state.get("adapter")
        if adapter:
            adapter.on_shutdown()
    except Exception:
        pass
    _global_state["adapter"] = None
    _global_state["running"] = False


def initializeSDPlugin() -> None:
    """SD 插件加载入口"""
    logger.info("ArtClaw: initializeSDPlugin called")

    if not _setup_paths():
        return

    # 完整性检查
    for p in sys.path:
        if os.path.isdir(os.path.join(p, "adapters")):
            _check_integrity(p)
            break

    # 延迟启动，等 SD 完成初始化
    try:
        try:
            from PySide2.QtCore import QTimer
        except ImportError:
            from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, _deferred_startup)
        logger.info("ArtClaw: Deferred startup scheduled (2s)")
    except ImportError:
        logger.warning("ArtClaw: Qt not available, starting directly")
        _deferred_startup()


def show_panel():
    """
    显示 / 重新打开 Chat Panel。

    通过 SD 内置 API 注册为 dock widget，
    关闭后可随时通过菜单重新打开。

    关键设计：
    - SD 关闭 dock 只是隐藏（不销毁），可通过 窗口 菜单重新显示
    - ArtClaw → Open Chat 做同样的事：找到已有 dock 并 show
    - 只在第一次（dock 不存在时）创建新的
    - 通过 QDockWidget objectName 前缀匹配查找
    """
    if not _global_state["running"]:
        logger.info("ArtClaw: Not running, starting first...")
        _deferred_startup()

    adapter = _global_state.get("adapter")
    if adapter is None:
        logger.error("ArtClaw: Adapter not available")
        return

    try:
        from artclaw_ui.chat_panel import ChatPanel, get_chat_panel
        import artclaw_ui.chat_panel as _cp_mod

        try:
            from PySide2 import QtWidgets
        except ImportError:
            from PySide6 import QtWidgets

        # ---- 查找已有的 ArtClaw dock widget ----
        main_win = None
        for w in QtWidgets.QApplication.topLevelWidgets():
            if isinstance(w, QtWidgets.QMainWindow):
                main_win = w
                break

        if main_win:
            for dock in main_win.findChildren(QtWidgets.QDockWidget):
                if dock.objectName().startswith("artclaw_chat_dock"):
                    if not dock.isVisible():
                        dock.setVisible(True)
                        dock.raise_()
                        logger.info(
                            "ArtClaw: Re-shown existing dock (%s)",
                            dock.objectName(),
                        )
                    return

        # ---- 没有已有 dock，创建新的 ----
        panel = ChatPanel(parent=None, adapter=adapter)
        panel.setObjectName("ArtClawChatPanel")
        panel.setWindowTitle("ArtClaw Chat")

        try:
            import sd
            from sd.api.qtforpythonuimgrwrapper import QtForPythonUIMgrWrapper

            ctx = sd.getContext()
            ui_mgr = QtForPythonUIMgrWrapper(ctx.getSDApplication().getUIMgr())
            dock = ui_mgr.newDockWidget("artclaw_chat_dock", "ArtClaw Chat")

            layout = QtWidgets.QVBoxLayout(dock)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(panel)
            dock.show()

            logger.info("ArtClaw: Chat Panel registered as dock widget")
        except Exception as e:
            logger.warning(
                "ArtClaw: newDockWidget failed (%s), "
                "falling back to standalone window", e
            )
            panel.resize(420, 700)
            panel.show()

        _cp_mod._panel_instance = panel
        adapter._panel = panel

    except Exception as e:
        logger.error("ArtClaw: Failed to open Chat Panel: %s", e)
        import traceback
        traceback.print_exc()


def uninitializeSDPlugin() -> None:
    """SD 插件卸载入口"""
    logger.info("ArtClaw: uninitializeSDPlugin called")

    # 先关闭面板（停止 QTimer 等资源）
    try:
        from artclaw_ui.chat_panel import get_chat_panel
        import artclaw_ui.chat_panel as _cp_mod
        panel = get_chat_panel()
        if panel is not None:
            try:
                panel.close()
            except Exception:
                pass
            _cp_mod._panel_instance = None
    except Exception:
        pass

    # 关闭 adapter
    adapter = _global_state.get("adapter")
    if adapter:
        try:
            adapter.on_shutdown()
        except Exception as e:
            logger.error("ArtClaw: Shutdown error: %s", e)

    # 清理菜单
    try:
        import sd
        from sd.api.qtforpythonuimgrwrapper import QtForPythonUIMgrWrapper
        ctx = sd.getContext()
        ui_mgr = QtForPythonUIMgrWrapper(ctx.getSDApplication().getUIMgr())
        ui_mgr.deleteMenu(_global_state["menu_object_name"])
    except Exception:
        pass

    _global_state["adapter"] = None
    _global_state["running"] = False
    _global_state.pop("_menu_ref", None)
    _global_state.pop("_action_ref", None)

    # 清理全局引用
    import builtins
    if hasattr(builtins, "_artclaw_adapter"):
        del builtins._artclaw_adapter

    logger.info("ArtClaw: Substance Designer adapter cleaned up")
