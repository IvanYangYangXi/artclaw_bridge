#!/usr/bin/env python3
"""
verify_sync.py — 共享模块同步校验工具
======================================

检查 core/ 和 platforms/ 源码是否与各 DCC 插件内的副本一致。
发现不一致时报告差异并可选自动修复。

用法:
    python verify_sync.py              # 检查模式（仅报告）
    python verify_sync.py --fix        # 自动修复（源码 → 副本）
    python verify_sync.py --reverse    # 反向修复（副本 → 源码，用于副本比源码新时）
    python verify_sync.py --ci         # CI 模式（不一致时退出码 1）
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

# 共享核心: core/ → DCC core/ + UE Content/Python/
CORE_DIR = PROJECT_ROOT / "core"
DCC_CORE_DIR = PROJECT_ROOT / "subprojects" / "DCCClawBridge" / "core"
UE_PYTHON_DIR = (
    PROJECT_ROOT / "subprojects" / "UEDAgentProj" / "Plugins"
    / "UEClawBridge" / "Content" / "Python"
)

# 核心共享模块列表（core/ 是唯一源码）
CORE_MODULES = [
    "bridge_core.py",
    "bridge_config.py",
    "bridge_diagnostics.py",
    "health_check.py",
    "integrity_check.py",
    "memory_core.py",
]

# 平台 Bridge: platforms/openclaw/ → UE Content/Python/
PLATFORM_DIR = PROJECT_ROOT / "platforms" / "openclaw"

# 平台模块列表（platforms/openclaw/ 是唯一源码）
PLATFORM_MODULES = [
    "openclaw_ws.py",
    "openclaw_chat.py",
    "openclaw_diagnose.py",
]

# DCC 源码: subprojects/DCCClawBridge/ → Maya 安装目录
DCC_SRC_DIR = PROJECT_ROOT / "subprojects" / "DCCClawBridge"

# Maya 安装目录（自动检测）
def _detect_maya_install_dirs() -> List[Path]:
    """检测 Maya 安装目录（scripts/ + 各 locale/scripts/）"""
    dirs: List[Path] = []
    maya_base = Path.home() / "Documents" / "maya"
    if not maya_base.exists():
        return dirs
    # 找最新的 Maya 版本目录
    version_dirs = sorted(
        [d for d in maya_base.iterdir() if d.is_dir() and d.name.isdigit()],
        key=lambda d: d.name,
        reverse=True,
    )
    if not version_dirs:
        return dirs
    maya_ver = version_dirs[0]
    # scripts/DCCClawBridge/
    scripts_dir = maya_ver / "scripts" / "DCCClawBridge"
    if scripts_dir.exists():
        dirs.append(scripts_dir)
    # locale/scripts/DCCClawBridge/ (zh_CN, ja_JP, etc.)
    for child in maya_ver.iterdir():
        if child.is_dir() and "_" in child.name and child.name[0].islower():
            locale_scripts = child / "scripts" / "DCCClawBridge"
            if locale_scripts.exists():
                dirs.append(locale_scripts)
    return dirs


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def file_hash(path: Path) -> str:
    """计算文件 MD5 hash（前 8 位）"""
    if not path.exists():
        return "--------"
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()[:8]


def _scan_dcc_source_files() -> List[Path]:
    """扫描 DCC 源码目录下所有 .py 文件（排除 __pycache__）"""
    if not DCC_SRC_DIR.exists():
        return []
    return sorted(
        p.relative_to(DCC_SRC_DIR)
        for p in DCC_SRC_DIR.rglob("*.py")
        if "__pycache__" not in str(p)
    )


def collect_sync_pairs() -> List[Tuple[Path, Path, str]]:
    """收集所有需要同步校验的 (源码, 副本, 说明) 三元组"""
    pairs = []

    # --- core/ → DCC core/ + UE Content/Python/ ---
    for mod in CORE_MODULES:
        src = CORE_DIR / mod
        pairs.append((src, DCC_CORE_DIR / mod, f"core->DCC  {mod}"))
        pairs.append((src, UE_PYTHON_DIR / mod, f"core->UE   {mod}"))

    # --- platforms/openclaw/ → UE Content/Python/ ---
    for mod in PLATFORM_MODULES:
        src = PLATFORM_DIR / mod
        pairs.append((src, UE_PYTHON_DIR / mod, f"plat->UE   {mod}"))

    # --- DCC source → Maya install dirs ---
    maya_dirs = _detect_maya_install_dirs()
    dcc_files = _scan_dcc_source_files()
    for maya_dir in maya_dirs:
        # 简短标签: scripts/ 或 zh_CN/
        label = maya_dir.parent.parent.name  # "2023" or locale like "zh_CN"
        if label.isdigit():
            tag = "Maya"
        else:
            tag = f"Maya/{label}"
        for rel in dcc_files:
            src = DCC_SRC_DIR / rel
            dst = maya_dir / rel
            pairs.append((src, dst, f"DCC->{tag}  {rel}"))

    return pairs


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------

def main():
    # Windows 终端 UTF-8 兼容
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="共享模块同步校验")
    parser.add_argument("--fix", action="store_true", help="自动修复：源码 → 副本")
    parser.add_argument("--reverse", action="store_true", help="反向修复：副本 → 源码")
    parser.add_argument("--ci", action="store_true", help="CI 模式：不一致时退出码 1")
    args = parser.parse_args()

    pairs = collect_sync_pairs()
    mismatches: List[Tuple[Path, Path, str]] = []
    missing_src: List[str] = []
    missing_dst: List[Tuple[Path, Path, str]] = []
    ok_count = 0

    print("=" * 60)
    print("ArtClaw Bridge -- Sync Verification")
    print("=" * 60)

    for src, dst, desc in pairs:
        if not src.exists():
            missing_src.append(desc)
            print(f"  [WARN] {desc} -- source missing!")
            continue
        if not dst.exists():
            missing_dst.append((src, dst, desc))
            print(f"  [WARN] {desc} -- dest missing!")
            continue

        h_src = file_hash(src)
        h_dst = file_hash(dst)

        if h_src == h_dst:
            ok_count += 1
            print(f"  [OK]   {desc}  ({h_src})")
        else:
            mismatches.append((src, dst, desc))
            src_t = os.path.getmtime(src)
            dst_t = os.path.getmtime(dst)
            newer = "src newer" if src_t > dst_t else "dst newer"
            print(f"  [DIFF] {desc}  src={h_src} dst={h_dst}  ({newer})")

    # --- Orphan detection: Maya install files not in DCC source ---
    maya_dirs = _detect_maya_install_dirs()
    orphans: List[Tuple[str, Path]] = []
    dcc_rels = set(str(r).replace(os.sep, "/") for r in _scan_dcc_source_files())
    for maya_dir in maya_dirs:
        label = maya_dir.parent.parent.name
        tag = "Maya" if label.isdigit() else f"Maya/{label}"
        for p in sorted(maya_dir.rglob("*.py")):
            if "__pycache__" in str(p):
                continue
            rel = str(p.relative_to(maya_dir)).replace(os.sep, "/")
            if rel not in dcc_rels:
                orphans.append((tag, p))

    if orphans:
        print()
        print(f"[WARN] {len(orphans)} orphan files in Maya (not in DCC source):")
        for tag, p in orphans:
            print(f"  {tag}: {p.name}")

    print()

    total = ok_count + len(mismatches) + len(missing_src) + len(missing_dst)
    print(f"Summary: {ok_count}/{total} OK", end="")
    if mismatches:
        print(f", {len(mismatches)} diff", end="")
    if missing_dst:
        print(f", {len(missing_dst)} dest missing", end="")
    if missing_src:
        print(f", {len(missing_src)} src missing", end="")
    if orphans:
        print(f", {len(orphans)} orphans", end="")
    print()

    print()

    if missing_src:
        print(f"⚠️  {len(missing_src)} 个源码文件缺失")
    if missing_dst:
        print(f"⚠️  {len(missing_dst)} 个副本文件缺失")

    if not mismatches and not missing_dst:
        print("[OK] All files in sync")
        return 0

    print(f"[FAIL] {len(mismatches)} diff, {len(missing_dst)} dest missing")

    if args.fix:
        print("\n--- Fix mode: source -> dest ---")
        for src, dst, desc in mismatches:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  FIXED {desc}")
        for src, dst, desc in missing_dst:
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  COPIED {desc}")
        print("\n[OK] Fix complete")
        return 0

    if args.reverse:
        print("\n--- Reverse fix: dest -> source ---")
        for src, dst, desc in mismatches:
            shutil.copy2(dst, src)
            print(f"  REVERSED {desc}")
        print("\n[OK] Reverse fix complete")
        return 0

    if args.ci:
        return 1

    print("\nUse --fix to overwrite dest from source, or --reverse to do the opposite")
    return 1


if __name__ == "__main__":
    sys.exit(main())
