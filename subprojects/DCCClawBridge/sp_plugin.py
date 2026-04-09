"""
sp_plugin.py - Substance Painter Plugin 入口
==============================================

SP plugin 约定导出 start_plugin() 和 close_plugin()。

安装方式:
    1. 将 DCCClawBridge 目录放到 SP 的 python/plugins/ 路径下
    2. 或将此文件所在目录添加到 SP 的 Python Plugins 路径
    3. SP 菜单 → Python → 勾选 sp_plugin 启用

启动后通过菜单 Window → ArtClaw Chat 打开面板。

环境变量 (可选):
    ARTCLAW_BRIDGE_PATH: artclaw_bridge 项目根目录
"""

from __future__ import annotations

import atexit
import logging
import os
import sys

logging.basicConfig(level=logging.INFO)

# SP renders stderr as red — route logging to stdout
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
logging.root.handlers = [_handler]

logger = logging.getLogger("artclaw.substance_painter")

# 全局状态
_global_state = {
    "adapter": None,
    "running": False,
    "menu_action": None,    # QAction in Window menu
    "dock_widget": None,    # QDockWidget returned by SP
    "atexit_registered": False,
}


def _setup_paths() -> bool:
    """将 DCCClawBridge 目录加入 sys.path"""
    # sp_plugin.py 位于 DCCClawBridge/ 根目录
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    dcc_bridge_dir = plugin_dir

    # 检查 adapters/ 子目录是否存在来验证路径
    if os.path.isdir(os.path.join(dcc_bridge_dir, "adapters")):
        if dcc_bridge_dir not in sys.path:
            sys.path.insert(0, dcc_bridge_dir)
        logger.info("ArtClaw: DCCClawBridge path = %s", dcc_bridge_dir)
        return True

    # Fallback: 从环境变量获取
    env_path = os.environ.get("ARTCLAW_BRIDGE_PATH", "")
    if env_path and os.path.isdir(env_path):
        dcc_bridge_dir = os.path.join(
            env_path, "subprojects", "DCCClawBridge"
        )
        if os.path.isdir(dcc_bridge_dir):
            if dcc_bridge_dir not in sys.path:
                sys.path.insert(0, dcc_bridge_dir)
            logger.info("ArtClaw: DCCClawBridge path = %s", dcc_bridge_dir)
            return True

    logger.warning(
        "ArtClaw: DCCClawBridge not found. "
        "Set ARTCLAW_BRIDGE_PATH or place plugin in DCCClawBridge/."
    )
    return False


def _deferred_startup():
    """延迟启动：创建 adapter + 注册菜单（不自动打开面板）"""
    if _global_state["running"]:
        logger.warning("ArtClaw: Already running, skip startup")
        return

    try:
        # 共享模块完整性检查
        try:
            core_dir = None
            for p in sys.path:
                candidate = os.path.join(p, "core")
                if (
                    os.path.isdir(candidate)
                    and os.path.exists(os.path.join(candidate, "__init__.py"))
                ):
                    core_dir = candidate
                    break

            if core_dir:
                try:
                    from core.integrity_check import check_and_repair
                except ImportError:
                    try:
                        from integrity_check import check_and_repair
                    except ImportError:
                        check_and_repair = None

                if check_and_repair:
                    integrity = check_and_repair(core_dir, auto_repair=True)
                    if integrity.repaired:
                        logger.info(
                            "ArtClaw: 共享模块自动修复: %s",
                            ", ".join(integrity.repaired),
                        )
                    if not integrity.ok:
                        logger.error(
                            "ArtClaw: 共享模块缺失: %s",
                            ", ".join(integrity.failed),
                        )
        except Exception as e:
            logger.warning("ArtClaw: 完整性检查跳过: %s", e)

        # 检查依赖
        try:
            from core.dependency_manager import ensure_dependencies

            def _on_deps(success, message):
                level = logging.INFO if success else logging.WARNING
                logger.log(level, "ArtClaw: %s", message)

            ensure_dependencies(callback=_on_deps)
        except Exception as e:
            logger.warning("ArtClaw: 依赖检查跳过: %s", e)

        # 创建 adapter 并启动（MCP Server 等后台服务）
        from adapters.substance_painter_adapter import (
            SubstancePainterAdapter,
        )

        adapter = SubstancePainterAdapter()
        adapter.on_startup()

        _global_state["adapter"] = adapter
        _global_state["running"] = True

        # 保存全局引用
        import builtins
        builtins._artclaw_adapter = adapter

        # 注册菜单入口（Window 菜单 → ArtClaw Chat）
        _register_menu_action()

        # 注册 atexit 兜底清理
        if not _global_state["atexit_registered"]:
            atexit.register(_atexit_cleanup)
            _global_state["atexit_registered"] = True

        logger.info(
            "ArtClaw: Substance Painter adapter initialized "
            "(use Window > ArtClaw Chat to open panel)"
        )

    except Exception as e:
        logger.error("ArtClaw: Startup failed: %s", e)
        import traceback
        traceback.print_exc()


def _register_menu_action():
    """在 SP 的 Window 菜单中添加 'ArtClaw Chat' 入口"""
    try:
        import substance_painter.ui as sp_ui
        try:
            from PySide6 import QtWidgets, QtGui
        except ImportError:
            from PySide2 import QtWidgets, QtGui

        action = QtGui.QAction("ArtClaw Chat", None)
        action.triggered.connect(lambda: show_panel())
        sp_ui.add_action(sp_ui.ApplicationMenu.Window, action)
        _global_state["menu_action"] = action
        logger.info("ArtClaw: Menu action registered (Window > ArtClaw Chat)")
    except Exception as e:
        logger.warning("ArtClaw: Failed to register menu action: %s", e)


def _atexit_cleanup():
    """atexit 兜底：确保后台线程正常关闭"""
    try:
        adapter = _global_state.get("adapter")
        if adapter:
            adapter.on_shutdown()
    except Exception:
        pass
    _global_state["adapter"] = None
    _global_state["running"] = False


def start_plugin():
    """SP plugin 入口 — SP 启动或启用插件时调用"""
    logger.info("ArtClaw: sp_plugin start_plugin() called")

    if not _setup_paths():
        return

    # 延迟启动，等 SP 完全就绪
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

    通过 SP 内置 add_dock_widget 注册为 dock panel，
    关闭后可随时通过菜单重新打开。

    关键设计：
    - SP 关闭 dock 只是隐藏（不销毁）
    - 再次打开时查找已有 QDockWidget 并 show
    - 只在第一次创建新 dock
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
            from PySide6 import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets

        # ---- 查找已有的 ArtClaw dock widget ----
        # SP 的 add_dock_widget 返回的 dock 关闭后只是隐藏
        dock = _global_state.get("dock_widget")
        if dock is not None:
            try:
                if not dock.isVisible():
                    dock.setVisible(True)
                    dock.raise_()
                    logger.info("ArtClaw: Re-shown existing dock")
                return
            except RuntimeError:
                # C++ 对象已销毁
                _global_state["dock_widget"] = None
                _cp_mod._panel_instance = None

        # Fallback: 在主窗口中搜索
        main_win = None
        for w in QtWidgets.QApplication.topLevelWidgets():
            if isinstance(w, QtWidgets.QMainWindow):
                main_win = w
                break

        if main_win:
            for d in main_win.findChildren(QtWidgets.QDockWidget):
                if "ArtClaw" in (d.windowTitle() or ""):
                    if not d.isVisible():
                        d.setVisible(True)
                        d.raise_()
                        logger.info("ArtClaw: Re-shown found dock (%s)", d.objectName())
                    _global_state["dock_widget"] = d
                    return

        # ---- 没有已有 dock，创建新的 ----
        panel = ChatPanel(parent=None, adapter=adapter)
        panel.setObjectName("ArtClawChatPanel")
        panel.setWindowTitle("ArtClaw Chat")

        try:
            import substance_painter.ui as sp_ui
            dock = sp_ui.add_dock_widget(panel)
            _global_state["dock_widget"] = dock
            logger.info("ArtClaw: Chat Panel registered as dock widget")
        except Exception as e:
            logger.warning(
                "ArtClaw: add_dock_widget failed (%s), "
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


def close_plugin():
    """SP plugin 退出 — SP 关闭或禁用插件时调用"""
    logger.info("ArtClaw: sp_plugin close_plugin() called")

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

    # 关闭 adapter（MCP Server + Bridge）
    adapter = _global_state.get("adapter")
    if adapter:
        try:
            adapter.on_shutdown()
        except Exception as e:
            logger.error("ArtClaw: Shutdown error: %s", e)

    # 清理菜单
    if _global_state.get("menu_action"):
        try:
            import substance_painter.ui as sp_ui
            sp_ui.delete_ui_element(_global_state["menu_action"])
        except Exception:
            pass
        _global_state["menu_action"] = None

    _global_state["adapter"] = None
    _global_state["running"] = False
    _global_state["dock_widget"] = None

    # 清理全局引用
    import builtins
    if hasattr(builtins, "_artclaw_adapter"):
        del builtins._artclaw_adapter

    logger.info("ArtClaw: Substance Painter plugin closed")
