"""
dependency_manager.py - 依赖检测与自动安装
==========================================

检测必需的 Python 包（如 websockets），缺失时自动安装到插件私有 Lib/ 目录。
"""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
import sys
import threading
from typing import List, Tuple

logger = logging.getLogger("artclaw.deps")

# 必需依赖列表: (import_name, pip_name, min_version)
REQUIRED_DEPS = [
    ("websockets", "websockets", "10.0"),
]


def get_lib_dir() -> str:
    """获取插件私有 Lib/ 目录路径"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lib_dir = os.path.join(base, "Lib")
    os.makedirs(lib_dir, exist_ok=True)
    # 确保在 sys.path 中
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    return lib_dir


def check_dependency(import_name: str) -> bool:
    """检查单个依赖是否可导入"""
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def check_all() -> List[Tuple[str, bool]]:
    """检查所有依赖，返回 [(name, available), ...]"""
    # 先确保 Lib/ 在 path 中
    get_lib_dir()

    results = []
    for import_name, _, _ in REQUIRED_DEPS:
        available = check_dependency(import_name)
        results.append((import_name, available))
        if available:
            logger.debug(f"Dependency OK: {import_name}")
        else:
            logger.warning(f"Dependency missing: {import_name}")

    return results


def install_missing(callback=None):
    """
    安装缺失的依赖到 Lib/ 目录。

    Args:
        callback: 安装完成回调 (success: bool, message: str)
    """
    missing = []
    for import_name, pip_name, _ in REQUIRED_DEPS:
        if not check_dependency(import_name):
            missing.append(pip_name)

    if not missing:
        logger.info("All dependencies satisfied")
        if callback:
            callback(True, "所有依赖已就绪")
        return

    lib_dir = get_lib_dir()
    logger.info(f"Installing missing deps to {lib_dir}: {missing}")

    def _install():
        try:
            python = sys.executable
            for pkg in missing:
                cmd = [
                    python, "-m", "pip", "install",
                    "--target", lib_dir,
                    "--no-user",
                    "--quiet",
                    pkg,
                ]
                logger.info(f"Running: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if result.returncode != 0:
                    error_msg = result.stderr.strip() or result.stdout.strip()
                    logger.error(f"Failed to install {pkg}: {error_msg}")
                    if callback:
                        callback(False, f"安装 {pkg} 失败: {error_msg}")
                    return

                logger.info(f"Installed: {pkg}")

            # 安装完成，重新加载
            importlib.invalidate_caches()

            # 验证
            all_ok = True
            for import_name, pip_name, _ in REQUIRED_DEPS:
                if not check_dependency(import_name):
                    all_ok = False
                    logger.error(f"Post-install check failed: {import_name}")

            if all_ok:
                logger.info("All dependencies installed successfully")
                if callback:
                    callback(True, "依赖安装完成")
            else:
                if callback:
                    callback(False, "部分依赖安装后仍无法导入")

        except Exception as e:
            logger.error(f"Dependency installation error: {e}")
            if callback:
                callback(False, f"安装异常: {e}")

    # 在后台线程安装，不阻塞 DCC 主线程
    thread = threading.Thread(target=_install, daemon=True, name="ArtClaw-DepInstall")
    thread.start()


def ensure_dependencies(callback=None) -> bool:
    """
    检查并安装依赖的便捷入口。

    Returns:
        True = 所有依赖已就绪, False = 需要安装（异步进行中）
    """
    results = check_all()
    all_ok = all(ok for _, ok in results)

    if all_ok:
        return True

    # 异步安装
    install_missing(callback=callback)
    return False
