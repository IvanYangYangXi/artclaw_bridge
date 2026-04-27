#!/usr/bin/env python3
"""
verify_sync.py — 共享模块同步校验工具
======================================

检查 core/ 和 platforms/ 源码是否与各 DCC 插件内的副本一致。
发现不一致时报告差异并可选自动修复。

用法:
    python verify_sync.py              # 检查模式（仅报告）
    python verify_sync.py --fix        # 安全修复（源码 → 副本，dest 更新时需确认）
    python verify_sync.py --fix --force  # 强制修复（源码 → 副本，忽略时间戳）
    python verify_sync.py --reverse    # 反向修复（副本 → 源码，仅同步 dest 更新的文件）
    python verify_sync.py --ci         # CI 模式（不一致时退出码 1）

安全机制:
    --fix 检测到 dest 比 source 新时，会逐个提示确认，避免覆盖在副本上的改动。
    如果确定源码是正确的，用 --fix --force 跳过所有确认。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

# ---------------------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

# 共享核心: core/ → DCC core/（UE 不再复制，通过 sys.path 引用）
CORE_DIR = PROJECT_ROOT / "core"
DCC_CORE_DIR = PROJECT_ROOT / "subprojects" / "DCCClawBridge" / "core"

# 核心共享模块列表（core/ 是唯一源码）
CORE_MODULES = [
    "bridge_core.py",
    "bridge_config.py",
    "bridge_diagnostics.py",
    "device_auth.py",
    "health_check.py",
    "integrity_check.py",
    "memory_core.py",
    "retry_tracker.py",
    "skill_sync.py",
]

# 平台模块列表（platforms/openclaw/ 是唯一源码）
# 注: UE 不再复制这些模块，通过 sys.path 引用源码。
#     仅检查 DCC core/ 是否同步。
PLATFORM_MODULES = [
    "openclaw_ws.py",
    "openclaw_chat.py",
    "openclaw_diagnose.py",
]

# DCC 源码: subprojects/DCCClawBridge/ → Maya 安装目录
DCC_SRC_DIR = PROJECT_ROOT / "subprojects" / "DCCClawBridge"

# 平台 Bridge 源码
PLATFORM_DIR = PROJECT_ROOT / "platforms" / "openclaw"

# 各 DCC 需要的共享子目录（安装时 junction）
_DCC_SHARED_DIRS = ["adapters", "artclaw_ui", "core", "skills"]

# 各 DCC 特有的顶层文件/目录（安装时 symlink/junction）
_DCC_SPECIFIC_FILES: dict = {
    "maya":    ["maya_setup"],
    "max":     ["max_setup"],
    "blender": ["blender_addon.py", "blender_qt_bridge.py", "blender_event_intercept.py", "__init__.py"],
    "houdini": ["houdini_shelf.py"],
    "sp":      ["sp_plugin.py"],
    "sd":      ["sd_plugin.py"],
    "comfyui": [],
}

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


# Blender 安装目录（自动检测）
def _detect_blender_install_dirs() -> List[Path]:
    """检测 Blender 安装目录（addons/artclaw_bridge/）"""
    dirs: List[Path] = []
    blender_base = Path(os.environ.get("APPDATA", "")) / "Blender Foundation" / "Blender"
    if not blender_base.exists():
        return dirs
    for ver_dir in sorted(blender_base.iterdir(), reverse=True):
        if not ver_dir.is_dir():
            continue
        addon_dir = ver_dir / "scripts" / "addons" / "artclaw_bridge"
        if addon_dir.exists():
            dirs.append(addon_dir)
    return dirs


# Houdini 安装目录（自动检测）
def _detect_houdini_install_dirs() -> List[Path]:
    """检测 Houdini 安装目录（scripts/python/DCCClawBridge/）"""
    dirs: List[Path] = []
    houdini_base = Path.home() / "Documents"
    if not houdini_base.exists():
        return dirs
    for child in sorted(houdini_base.iterdir(), reverse=True):
        if child.is_dir() and child.name.startswith("houdini"):
            dcc_dir = child / "scripts" / "python" / "DCCClawBridge"
            if dcc_dir.exists():
                dirs.append(dcc_dir)
    return dirs


# Substance Painter 安装目录（自动检测）
def _detect_sp_install_dir() -> Path | None:
    """检测 Substance Painter 插件安装目录"""
    sp_dir = (
        Path.home() / "Documents" / "Adobe"
        / "Adobe Substance 3D Painter" / "python" / "plugins"
        / "artclaw_bridge"
    )
    return sp_dir if sp_dir.exists() else None


# Substance Designer 安装目录（自动检测）
def _detect_sd_install_dir() -> Path | None:
    """检测 Substance Designer 插件安装目录"""
    sd_dir = (
        Path.home() / "Documents" / "Adobe"
        / "Adobe Substance 3D Designer" / "python" / "sduserplugins"
        / "artclaw_bridge"
    )
    return sd_dir if sd_dir.exists() else None


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


def _get_expected_files_for_dcc(dcc_type: str) -> List[Path]:
    """获取某个 DCC 安装目录应该包含的文件列表（相对路径）。

    只返回共享子目录 + 该 DCC 特有的文件，不包含其他 DCC 的文件。
    """
    all_files = _scan_dcc_source_files()
    expected = []
    shared_dirs = set(_DCC_SHARED_DIRS)
    specific = set(_DCC_SPECIFIC_FILES.get(dcc_type, []))

    for rel in all_files:
        parts = rel.parts
        # 共享子目录内的文件
        if parts[0] in shared_dirs:
            expected.append(rel)
            continue
        # 该 DCC 特有的顶层文件/目录
        if parts[0] in specific:
            expected.append(rel)
            continue
        # 单文件匹配（如 blender_addon.py, __init__.py）
        if len(parts) == 1 and str(rel) in specific:
            expected.append(rel)

    return expected


def collect_sync_pairs() -> List[Tuple[Path, Path, str]]:
    """收集所有需要同步校验的 (源码, 副本, 说明) 三元组"""
    pairs = []

    # --- core/ → DCC core/ （不再检查 UE，UE 通过 sys.path 引用源码）---
    for mod in CORE_MODULES:
        src = CORE_DIR / mod
        pairs.append((src, DCC_CORE_DIR / mod, f"core->DCC  {mod}"))

    # --- DCC source → Maya install dirs ---
    maya_dirs = _detect_maya_install_dirs()
    maya_files = _get_expected_files_for_dcc("maya")
    for maya_dir in maya_dirs:
        label = maya_dir.parent.parent.name
        tag = "Maya" if label.isdigit() else f"Maya/{label}"
        for rel in maya_files:
            src = DCC_SRC_DIR / rel
            dst = maya_dir / rel
            pairs.append((src, dst, f"DCC->{tag}  {rel}"))

    # --- DCC source → Blender install dirs ---
    blender_dirs = _detect_blender_install_dirs()
    blender_files = _get_expected_files_for_dcc("blender")
    for blender_dir in blender_dirs:
        ver = blender_dir.parent.parent.parent.name
        for rel in blender_files:
            src = DCC_SRC_DIR / rel
            dst = blender_dir / rel
            pairs.append((src, dst, f"DCC->Blender/{ver}  {rel}"))

    # --- DCC source → Houdini install dirs ---
    houdini_dirs = _detect_houdini_install_dirs()
    houdini_files = _get_expected_files_for_dcc("houdini")
    for houdini_dir in houdini_dirs:
        ver = houdini_dir.parent.parent.parent.name
        for rel in houdini_files:
            src = DCC_SRC_DIR / rel
            dst = houdini_dir / rel
            pairs.append((src, dst, f"DCC->{ver}  {rel}"))

    # --- DCC source → Substance Painter install dir ---
    sp_dir = _detect_sp_install_dir()
    if sp_dir:
        sp_files = _get_expected_files_for_dcc("sp")
        for rel in sp_files:
            src = DCC_SRC_DIR / rel
            dst = sp_dir / rel
            pairs.append((src, dst, f"DCC->SP  {rel}"))

    # --- DCC source → Substance Designer install dir ---
    sd_dir = _detect_sd_install_dir()
    if sd_dir:
        sd_files = _get_expected_files_for_dcc("sd")
        for rel in sd_files:
            src = DCC_SRC_DIR / rel
            dst = sd_dir / rel
            pairs.append((src, dst, f"DCC->SD  {rel}"))

    return pairs

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
    parser.add_argument("--fix", action="store_true", help="安全修复：源码 → 副本（dest 更新时需确认）")
    parser.add_argument("--force", action="store_true", help="与 --fix 配合：跳过确认，强制源码覆盖副本")
    parser.add_argument("--reverse", action="store_true", help="反向修复：副本 → 源码（仅同步 dest 更新的文件）")
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
            src_time = datetime.fromtimestamp(src_t).strftime("%m-%d %H:%M")
            dst_time = datetime.fromtimestamp(dst_t).strftime("%m-%d %H:%M")
            direction = "⬅ dest NEWER" if dst_t > src_t else "➡ src newer"
            print(f"  [DIFF] {desc}  src={h_src}({src_time}) dst={h_dst}({dst_time})  {direction}")

    # --- Orphan detection: install files not in DCC source ---
    dcc_rels = set(str(r).replace(os.sep, "/") for r in _scan_dcc_source_files())

    # Maya
    maya_dirs = _detect_maya_install_dirs()
    orphans: List[Tuple[str, Path]] = []
    for maya_dir in maya_dirs:
        label = maya_dir.parent.parent.name
        tag = "Maya" if label.isdigit() else f"Maya/{label}"
        for p in sorted(maya_dir.rglob("*.py")):
            if "__pycache__" in str(p):
                continue
            rel = str(p.relative_to(maya_dir)).replace(os.sep, "/")
            if rel not in dcc_rels:
                orphans.append((tag, p))

    # Blender
    for blender_dir in _detect_blender_install_dirs():
        ver = blender_dir.parent.parent.parent.name
        for p in sorted(blender_dir.rglob("*.py")):
            if "__pycache__" in str(p):
                continue
            rel = str(p.relative_to(blender_dir)).replace(os.sep, "/")
            if rel not in dcc_rels:
                orphans.append((f"Blender/{ver}", p))

    # Houdini
    for houdini_dir in _detect_houdini_install_dirs():
        ver = houdini_dir.parent.parent.parent.name
        for p in sorted(houdini_dir.rglob("*.py")):
            if "__pycache__" in str(p):
                continue
            rel = str(p.relative_to(houdini_dir)).replace(os.sep, "/")
            if rel not in dcc_rels:
                orphans.append((ver, p))

    # SP
    sp_dir = _detect_sp_install_dir()
    if sp_dir:
        for p in sorted(sp_dir.rglob("*.py")):
            if "__pycache__" in str(p):
                continue
            rel = str(p.relative_to(sp_dir)).replace(os.sep, "/")
            if rel not in dcc_rels:
                orphans.append(("SP", p))

    # SD
    sd_dir = _detect_sd_install_dir()
    if sd_dir:
        for p in sorted(sd_dir.rglob("*.py")):
            if "__pycache__" in str(p):
                continue
            rel = str(p.relative_to(sd_dir)).replace(os.sep, "/")
            if rel not in dcc_rels:
                orphans.append(("SD", p))

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
        fixed = 0
        skipped = 0
        for src, dst, desc in mismatches:
            src_t = os.path.getmtime(src)
            dst_t = os.path.getmtime(dst)
            if dst_t > src_t and not args.force:
                # dest 比 source 新 — 可能有人直接改了副本
                src_time = datetime.fromtimestamp(src_t).strftime("%m-%d %H:%M:%S")
                dst_time = datetime.fromtimestamp(dst_t).strftime("%m-%d %H:%M:%S")
                print(f"\n  ⚠️  {desc}")
                print(f"      src: {src_time}  |  dest: {dst_time}  (dest is NEWER)")
                print(f"      src: {src}")
                print(f"      dst: {dst}")
                try:
                    ans = input("      Overwrite dest with source? [y/N/r=reverse] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    ans = ""
                if ans == "r":
                    # 反向: dest → source
                    shutil.copy2(dst, src)
                    print(f"      REVERSED (dest -> src)")
                    fixed += 1
                elif ans == "y":
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    print(f"      FIXED (src -> dest)")
                    fixed += 1
                else:
                    print(f"      SKIPPED")
                    skipped += 1
            else:
                # source 更新或 --force — 直接覆盖
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  FIXED {desc}")
                fixed += 1
        for src, dst, desc in missing_dst:
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  COPIED {desc}")
                fixed += 1
        print(f"\n[OK] Fix complete: {fixed} fixed", end="")
        if skipped:
            print(f", {skipped} skipped (use --force to override)")
        print()
        return 0

    if args.reverse:
        print("\n--- Reverse fix: dest -> source ---")
        reversed_count = 0
        skipped = 0
        for src, dst, desc in mismatches:
            src_t = os.path.getmtime(src)
            dst_t = os.path.getmtime(dst)
            if dst_t > src_t:
                # dest 更新 — 自动反向同步
                shutil.copy2(dst, src)
                print(f"  REVERSED {desc}  (dest was newer)")
                reversed_count += 1
            else:
                # source 更新 — 不反向，跳过
                print(f"  SKIPPED  {desc}  (source is newer, use --fix)")
                skipped += 1
        print(f"\n[OK] Reverse complete: {reversed_count} reversed", end="")
        if skipped:
            print(f", {skipped} skipped (source was newer)")
        print()
        return 0

    if args.ci:
        return 1

    print("\nUse --fix to sync source -> dest (safe, with confirmation)")
    print("    --fix --force to skip confirmation")
    print("    --reverse to sync dest -> source (only newer dest files)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
