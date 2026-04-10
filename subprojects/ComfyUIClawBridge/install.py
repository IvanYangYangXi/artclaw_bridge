"""
install.py - ComfyUI-Manager 兼容安装脚本
============================================

ComfyUI-Manager 在安装自定义节点时会执行此脚本。
安装 ArtClaw Bridge 所需的 Python 依赖。

依赖:
  - websockets: MCP WebSocket Server 需要（ComfyUI 自身不包含）
"""

import subprocess
import sys


def install_dependencies():
    """安装必要的 Python 依赖"""
    dependencies = [
        "websockets>=12.0",
    ]

    for dep in dependencies:
        try:
            # 尝试 import 检查是否已安装
            pkg_name = dep.split(">=")[0].split("==")[0].split("<")[0]
            __import__(pkg_name)
            print(f"[ArtClaw] {pkg_name} 已安装，跳过")
        except ImportError:
            print(f"[ArtClaw] 安装 {dep}...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install",
                    dep, "--no-cache-dir",
                ])
                print(f"[ArtClaw] {dep} 安装成功")
            except subprocess.CalledProcessError as e:
                print(f"[ArtClaw] 警告: {dep} 安装失败: {e}")
                print(f"[ArtClaw] 请手动安装: pip install {dep}")


if __name__ == "__main__":
    install_dependencies()

# ComfyUI-Manager 直接 exec 此文件时也会执行
install_dependencies()
