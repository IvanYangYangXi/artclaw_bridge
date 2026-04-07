"""
sd_plugin.py - Substance Designer 插件入口
=============================================

放置到 SD 的用户插件目录:
  %USERPROFILE%\\Documents\\Adobe\\Adobe Substance 3D Designer\\python\\sduserplugins\\artclaw\\

SD 约定导出:
  - initializeSDPlugin()   — SD 加载插件时调用
  - uninitializeSDPlugin() — SD 卸载插件时调用
"""

from __future__ import annotations

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
    """延迟启动：创建 adapter + 打开 Chat Panel"""
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

        # 创建 adapter
        from adapters.substance_designer_adapter import SubstanceDesignerAdapter

        adapter = SubstanceDesignerAdapter()
        adapter.on_startup()

        _global_state["adapter"] = adapter
        _global_state["running"] = True

        # 注入全局引用（方便调试）
        import builtins
        builtins._artclaw_adapter = adapter

        # 打开 Chat Panel（延迟一下等 UI 就绪）
        try:
            try:
                from PySide2.QtCore import QTimer
            except ImportError:
                from PySide6.QtCore import QTimer
            QTimer.singleShot(1000, adapter._open_chat_panel)
        except ImportError:
            adapter._open_chat_panel()

        logger.info("ArtClaw: Substance Designer adapter initialized")

    except Exception as e:
        logger.error("ArtClaw: Startup failed: %s", e)
        import traceback
        traceback.print_exc()


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

    如果 Panel 已被关闭，重新创建并显示。
    如果 ArtClaw 未运行，则先启动。
    """
    if not _global_state["running"]:
        logger.info("ArtClaw: Not running, starting first...")
        initializeSDPlugin()
        return

    adapter = _global_state.get("adapter")
    if adapter is not None:
        try:
            adapter._open_chat_panel()
            logger.info("ArtClaw: Chat Panel reopened")
        except Exception as e:
            logger.error("ArtClaw: Failed to reopen Chat Panel: %s", e)


def uninitializeSDPlugin() -> None:
    """SD 插件卸载入口"""
    logger.info("ArtClaw: uninitializeSDPlugin called")

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

    logger.info("ArtClaw: Substance Designer adapter cleaned up")
