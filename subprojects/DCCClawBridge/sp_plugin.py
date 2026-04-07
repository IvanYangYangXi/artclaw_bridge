"""
sp_plugin.py - Substance Painter Plugin 入口
==============================================

SP plugin 约定导出 start_plugin() 和 close_plugin()。

安装方式:
    1. 将 DCCClawBridge 目录放到 SP 的 python/plugins/ 路径下
    2. 或将此文件所在目录添加到 SP 的 Python Plugins 路径
    3. SP 菜单 → Python → 勾选 sp_plugin 启用

环境变量 (可选):
    ARTCLAW_BRIDGE_PATH: artclaw_bridge 项目根目录
"""

from __future__ import annotations

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
    """延迟启动：创建 adapter 并初始化"""
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

        # 创建 adapter 并启动
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

        # 打开 Chat Panel
        adapter._open_chat_panel()

        logger.info(
            "ArtClaw: Substance Painter adapter initialized successfully"
        )

    except Exception as e:
        logger.error("ArtClaw: Startup failed: %s", e)
        import traceback
        traceback.print_exc()


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

    如果 Panel 已被关闭，重新创建并显示。
    如果 ArtClaw 未运行，则先启动。
    """
    if not _global_state["running"]:
        logger.info("ArtClaw: Not running, starting first...")
        start_plugin()
        return

    adapter = _global_state.get("adapter")
    if adapter is not None:
        try:
            adapter._open_chat_panel()
            logger.info("ArtClaw: Chat Panel reopened")
        except Exception as e:
            logger.error("ArtClaw: Failed to reopen Chat Panel: %s", e)


def close_plugin():
    """SP plugin 退出 — SP 关闭或禁用插件时调用"""
    logger.info("ArtClaw: sp_plugin close_plugin() called")

    adapter = _global_state.get("adapter")
    if adapter:
        try:
            adapter.on_shutdown()
        except Exception as e:
            logger.error("ArtClaw: Shutdown error: %s", e)

    _global_state["adapter"] = None
    _global_state["running"] = False

    # 清理全局引用
    import builtins
    if hasattr(builtins, "_artclaw_adapter"):
        del builtins._artclaw_adapter

    logger.info("ArtClaw: Substance Painter plugin closed")
