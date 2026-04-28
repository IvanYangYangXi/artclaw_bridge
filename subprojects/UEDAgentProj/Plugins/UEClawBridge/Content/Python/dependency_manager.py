"""
dependency_manager.py - 离线依赖包打包工具
============================================

阶段 0.5: 依赖隔离与自动安装 (Dependency Management)

此脚本在开发机器上运行（非 UE 内部），用于：
1. 下载所有依赖的 wheel 包到 Lib_bundle/ 目录
2. 打包为离线 bundle，供无网络环境部署

用法::

    # 在有网络的开发机器上运行
    python dependency_manager.py

    # 或指定 Python 版本和平台
    python dependency_manager.py --python-version 3.11 --platform win_amd64

输出::

    Content/Python/Lib_bundle/
    ├── websockets-12.0-py3-none-any.whl
    ├── pydantic-2.6.0-cp311-cp311-win_amd64.whl
    ├── PyYAML-6.0.1-cp311-cp311-win_amd64.whl
    └── ... (其他依赖)

宪法约束:
  - 开发路线图 §0.4: 依赖隔离管理机制
  - 项目概要 §五: dependency_manager 统一管理
  - 项目结构说明: tools/dependency_manager/ 跨项目工具
"""

import os
import sys
import subprocess
import argparse
import shutil


# 与 init_unreal.py 中的依赖列表保持同步
REQUIRED_PACKAGES = [
    "websockets>=12.0",
    "pydantic>=2.0",
    "cryptography>=46.0",
]

OPTIONAL_PACKAGES = [
    "PyYAML>=6.0",
    "cffi>=2.0",  # cryptography 的 C 扩展依赖，需要匹配 Python 版本
]

ALL_PACKAGES = REQUIRED_PACKAGES + OPTIONAL_PACKAGES


def get_bundle_dir():
    """获取离线 bundle 目录路径。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "Lib_bundle")


def download_wheels(
    output_dir: str,
    python_version: str = "3.11",
    platform: str = "win_amd64",
):
    """
    下载所有依赖的 wheel 包。

    Args:
        output_dir: 输出目录
        python_version: 目标 Python 版本 (如 "3.11")
        platform: 目标平台 (如 "win_amd64")
    """
    os.makedirs(output_dir, exist_ok=True)

    # 清空旧文件
    for f in os.listdir(output_dir):
        fp = os.path.join(output_dir, f)
        if f.endswith((".whl", ".tar.gz", ".zip")):
            os.remove(fp)
            print(f"  Removed old: {f}")

    print(f"\nDownloading wheels to: {output_dir}")
    print(f"  Python version: {python_version}")
    print(f"  Platform: {platform}")
    print(f"  Packages: {ALL_PACKAGES}")
    print()

    cmd = [
        sys.executable, "-m", "pip", "download",
        "--dest", output_dir,
        "--python-version", python_version,
        "--platform", platform,
        "--only-binary=:all:",
        "--no-deps",  # 先不解析依赖，逐个下载
    ]

    success_count = 0
    fail_count = 0

    for pkg in ALL_PACKAGES:
        pkg_cmd = cmd + [pkg]
        print(f"  Downloading: {pkg} ... ", end="", flush=True)
        try:
            result = subprocess.run(
                pkg_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                print("OK")
                success_count += 1
            else:
                # 尝试不限制 platform (pure python 包)
                fallback_cmd = [
                    sys.executable, "-m", "pip", "download",
                    "--dest", output_dir,
                    "--no-deps",
                    pkg,
                ]
                result2 = subprocess.run(
                    fallback_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result2.returncode == 0:
                    print("OK (pure Python)")
                    success_count += 1
                else:
                    print(f"FAILED\n    {result.stderr.strip()}")
                    fail_count += 1
        except Exception as e:
            print(f"ERROR: {e}")
            fail_count += 1

    # 同时下载依赖的子包
    print(f"\nDownloading sub-dependencies ...")
    for pkg in ALL_PACKAGES:
        deps_cmd = [
            sys.executable, "-m", "pip", "download",
            "--dest", output_dir,
            "--python-version", python_version,
            "--platform", platform,
            "--only-binary=:all:",
            pkg,
        ]
        try:
            subprocess.run(deps_cmd, capture_output=True, text=True, timeout=120)
        except Exception:
            pass

    # 统计结果
    wheel_files = [
        f for f in os.listdir(output_dir)
        if f.endswith((".whl", ".tar.gz", ".zip"))
    ]

    print(f"\n{'=' * 50}")
    print(f"Bundle created: {output_dir}")
    print(f"  Total packages: {len(wheel_files)}")
    print(f"  Direct downloads: {success_count} success, {fail_count} failed")
    print(f"\nFiles:")
    for f in sorted(wheel_files):
        size_kb = os.path.getsize(os.path.join(output_dir, f)) / 1024
        print(f"  {f} ({size_kb:.1f} KB)")

    return fail_count == 0


def verify_bundle(bundle_dir: str):
    """验证 bundle 是否包含所有必需包。"""
    if not os.path.isdir(bundle_dir):
        print(f"Bundle directory not found: {bundle_dir}")
        return False

    files = os.listdir(bundle_dir)
    wheel_files = [f for f in files if f.endswith((".whl", ".tar.gz", ".zip"))]

    print(f"\nVerifying bundle: {bundle_dir}")
    print(f"  Found {len(wheel_files)} packages")

    # 检查必需包
    all_ok = True
    for pkg_spec in REQUIRED_PACKAGES:
        pkg_name = pkg_spec.split(">=")[0].split("==")[0].lower().replace("-", "_")
        found = any(
            pkg_name in f.lower().replace("-", "_")
            for f in wheel_files
        )
        status = "OK" if found else "MISSING"
        print(f"  [{status}] {pkg_spec}")
        if not found:
            all_ok = False

    for pkg_spec in OPTIONAL_PACKAGES:
        pkg_name = pkg_spec.split(">=")[0].split("==")[0].lower().replace("-", "_")
        found = any(
            pkg_name in f.lower().replace("-", "_")
            for f in wheel_files
        )
        status = "OK" if found else "MISSING (optional)"
        print(f"  [{status}] {pkg_spec}")

    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="UE Claw Bridge - Dependency Bundle Manager"
    )
    parser.add_argument(
        "--python-version", default="3.11",
        help="Target Python version (default: 3.11)"
    )
    parser.add_argument(
        "--platform", default="win_amd64",
        help="Target platform (default: win_amd64)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output directory (default: Content/Python/Lib_bundle/)"
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Only verify existing bundle without downloading"
    )

    args = parser.parse_args()

    output_dir = args.output or get_bundle_dir()

    if args.verify_only:
        ok = verify_bundle(output_dir)
        sys.exit(0 if ok else 1)

    print("=" * 50)
    print("UE Claw Bridge - Dependency Bundle Creator")
    print("=" * 50)

    success = download_wheels(
        output_dir=output_dir,
        python_version=args.python_version,
        platform=args.platform,
    )

    verify_bundle(output_dir)

    if success:
        print(f"\nBundle ready for offline deployment!")
        print(f"Copy '{output_dir}' to the target machine.")
    else:
        print(f"\nSome packages failed to download. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
