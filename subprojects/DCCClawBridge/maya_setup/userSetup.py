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

import logging
import os
import sys

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("artclaw")


def _setup_paths():
    """将 DCCClawBridge 目录加入 sys.path"""
    # DCCClawBridge 可能在:
    #   1. scripts/DCCClawBridge/ (直接部署)
    #   2. 项目目录/subprojects/DCCClawBridge/ (开发模式)
    #
    # 查找策略（按优先级）:
    #   a. __file__ 同目录（大多数情况可靠）
    #   b. MAYA_SCRIPT_PATH 中的各 scripts 目录
    #   c. maya.cmds.internalVar(userScriptDir=True)
    #   d. ARTCLAW_BRIDGE_PATH 环境变量（开发模式）

    candidate_dirs = []

    # a. __file__ 同目录
    try:
        candidate_dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass  # __file__ 未定义（极端情况）

    # b. MAYA_SCRIPT_PATH 中的 scripts 目录
    maya_script_path = os.environ.get("MAYA_SCRIPT_PATH", "")
    if maya_script_path:
        for p in maya_script_path.split(os.pathsep):
            p = p.strip()
            if p and os.path.isdir(p):
                candidate_dirs.append(p)

    # c. maya.cmds.internalVar（Maya 启动后可用）
    try:
        import maya.cmds as _cmds
        user_script_dir = _cmds.internalVar(userScriptDir=True)
        if user_script_dir:
            candidate_dirs.append(user_script_dir.rstrip("/\\"))
    except Exception:
        pass

    # 在候选目录中查找 DCCClawBridge/
    for scripts_dir in candidate_dirs:
        dcc_bridge_dir = os.path.join(scripts_dir, "DCCClawBridge")
        if os.path.isdir(dcc_bridge_dir):
            if dcc_bridge_dir not in sys.path:
                sys.path.insert(0, dcc_bridge_dir)
            logger.info(f"ArtClaw: DCCClawBridge path = {dcc_bridge_dir}")
            return True

    # d. 开发模式 — 从环境变量获取
    env_path = os.environ.get("ARTCLAW_BRIDGE_PATH", "")
    if env_path and os.path.isdir(env_path):
        dcc_bridge_dir = os.path.join(env_path, "subprojects", "DCCClawBridge")
        if os.path.isdir(dcc_bridge_dir):
            if dcc_bridge_dir not in sys.path:
                sys.path.insert(0, dcc_bridge_dir)
            logger.info(f"ArtClaw: DCCClawBridge path = {dcc_bridge_dir} (dev mode)")
            return True

    logger.warning(
        "ArtClaw: DCCClawBridge not found. "
        "Place it in scripts/DCCClawBridge/ or set ARTCLAW_BRIDGE_PATH."
    )
    return False


def _deferred_startup():
    """延迟到 Maya 完全就绪后执行"""
    try:
        # 共享模块完整性检查
        try:
            core_dir = None
            # 定位 core/ 目录
            for p in sys.path:
                candidate = os.path.join(p, "core")
                if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "__init__.py")):
                    core_dir = candidate
                    break

            if core_dir:
                try:
                    from integrity_check import check_and_repair
                except ImportError:
                    # integrity_check.py 不在 core/ 里，从 core/ 找
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
                    logger.error("ArtClaw: 请使用安装脚本重新安装，或查看 core/_integrity_issues.md")
        except Exception as e:
            logger.warning(f"ArtClaw: 完整性检查跳过: {e}")

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
