"""
startup.py - 3ds Max 自动加载入口
====================================

放置到 Max 的 startup scripts 目录:
  - %LOCALAPPDATA%/Autodesk/3dsMax/20XX/ENU/scripts/startup/

或通过 Max 的 Python 路径配置加载。
"""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("artclaw")


def _setup_paths():
    """将 DCCClawBridge 目录加入 sys.path"""
    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    # 情况 1: 直接部署到 startup 目录旁边
    dcc_bridge_dir = os.path.join(scripts_dir, "..", "DCCClawBridge")
    dcc_bridge_dir = os.path.normpath(dcc_bridge_dir)

    # 情况 2: 开发模式
    if not os.path.isdir(dcc_bridge_dir):
        env_path = os.environ.get("ARTCLAW_BRIDGE_PATH", "")
        if env_path and os.path.isdir(env_path):
            dcc_bridge_dir = os.path.join(env_path, "subprojects", "DCCClawBridge")

    if os.path.isdir(dcc_bridge_dir):
        if dcc_bridge_dir not in sys.path:
            sys.path.insert(0, dcc_bridge_dir)
        logger.info(f"ArtClaw: DCCClawBridge path = {dcc_bridge_dir}")
        return True
    else:
        logger.warning("ArtClaw: DCCClawBridge not found")
        return False


def _deferred_startup():
    """延迟启动"""
    try:
        # 共享模块完整性检查
        try:
            core_dir = None
            for p in sys.path:
                candidate = os.path.join(p, "core")
                if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "__init__.py")):
                    core_dir = candidate
                    break

            if core_dir:
                try:
                    from integrity_check import check_and_repair
                except ImportError:
                    _bridge_dir = os.path.normpath(
                        os.path.join(core_dir, "..", "..", "..", "core")
                    )
                    if os.path.isdir(_bridge_dir) and _bridge_dir not in sys.path:
                        sys.path.insert(0, _bridge_dir)
                    from integrity_check import check_and_repair

                integrity = check_and_repair(core_dir, auto_repair=True)
                if integrity.repaired:
                    logger.info(f"ArtClaw: 共享模块自动修复: {', '.join(integrity.repaired)}")
                if not integrity.ok:
                    logger.error(f"ArtClaw: 共享模块缺失: {', '.join(integrity.failed)}")
        except Exception as e:
            logger.warning(f"ArtClaw: 完整性检查跳过: {e}")

        from core.dependency_manager import ensure_dependencies

        def _on_deps(success, message):
            if success:
                logger.info(f"ArtClaw: {message}")
            else:
                logger.warning(f"ArtClaw: {message}")

        ensure_dependencies(callback=_on_deps)

        from adapters.max_adapter import MaxAdapter, _global_adapter
        import adapters.max_adapter as max_mod

        adapter = MaxAdapter()
        adapter.on_startup()

        max_mod._global_adapter = adapter

        import builtins
        builtins._artclaw_adapter = adapter

        logger.info("ArtClaw: Max adapter initialized")
    except Exception as e:
        logger.error(f"ArtClaw: Startup failed: {e}")
        import traceback
        traceback.print_exc()


def _main():
    if not _setup_paths():
        return

    try:
        from PySide2.QtCore import QTimer
        QTimer.singleShot(2000, _deferred_startup)
        logger.info("ArtClaw: Deferred startup scheduled (2s)")
    except ImportError:
        logger.warning("ArtClaw: PySide2 not available, starting directly")
        _deferred_startup()


_main()
