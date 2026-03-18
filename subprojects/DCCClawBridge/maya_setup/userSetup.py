"""
userSetup.py - Maya 自动加载入口
==================================

放置到 ~/Documents/maya/20XX/scripts/ 目录下，
Maya 启动时自动执行。

功能:
  1. 将 DCCClawBridge 加入 sys.path
  2. 检测并安装依赖
  3. 注册 ArtClaw 菜单
  4. (可选) 自动连接 OpenClaw Gateway
"""

from __future__ import annotations

import logging
import os
import sys

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("artclaw")


def _setup_paths():
    """将 DCCClawBridge 目录加入 sys.path"""
    # userSetup.py 所在目录 → scripts/
    # DCCClawBridge 可能在:
    #   1. scripts/DCCClawBridge/ (直接部署)
    #   2. 项目目录/subprojects/DCCClawBridge/ (开发模式)

    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    # 情况 1: 直接部署
    dcc_bridge_dir = os.path.join(scripts_dir, "DCCClawBridge")

    # 情况 2: 开发模式 — 从环境变量获取
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
        logger.warning(
            "ArtClaw: DCCClawBridge not found. "
            "Place it in scripts/DCCClawBridge/ or set ARTCLAW_BRIDGE_PATH."
        )
        return False


def _deferred_startup():
    """延迟到 Maya 完全就绪后执行"""
    try:
        # 检查依赖
        from core.dependency_manager import ensure_dependencies

        def _on_deps_ready(success, message):
            if success:
                logger.info(f"ArtClaw: {message}")
            else:
                logger.warning(f"ArtClaw: {message}")

        deps_ok = ensure_dependencies(callback=_on_deps_ready)

        # 创建 adapter 并启动
        from adapters.maya_adapter import MayaAdapter

        adapter = MayaAdapter()
        adapter.on_startup()

        # 保存全局引用
        import builtins
        builtins._artclaw_adapter = adapter

        logger.info("ArtClaw: Maya adapter initialized successfully")

    except Exception as e:
        logger.error(f"ArtClaw: Startup failed: {e}")
        import traceback
        traceback.print_exc()


def _main():
    """入口"""
    if not _setup_paths():
        return

    # 延迟执行，等 Maya 完全启动
    try:
        import maya.utils
        maya.utils.executeDeferred(_deferred_startup)
        logger.info("ArtClaw: Deferred startup registered")
    except ImportError:
        logger.warning("ArtClaw: Not running inside Maya")


# Maya 启动时自动调用
_main()
