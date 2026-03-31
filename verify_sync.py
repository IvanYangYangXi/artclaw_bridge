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


def collect_sync_pairs() -> List[Tuple[Path, Path, str]]:
    """收集所有需要同步校验的 (源码, 副本, 说明) 三元组"""
    pairs = []

    for mod in CORE_MODULES:
        src = CORE_DIR / mod
        # core/ → DCC core/
        pairs.append((src, DCC_CORE_DIR / mod, f"core→DCC  {mod}"))
        # core/ → UE Content/Python/
        pairs.append((src, UE_PYTHON_DIR / mod, f"core→UE   {mod}"))

    for mod in PLATFORM_MODULES:
        src = PLATFORM_DIR / mod
        # platforms/openclaw/ → UE Content/Python/
        pairs.append((src, UE_PYTHON_DIR / mod, f"plat→UE   {mod}"))

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
    missing_dst: List[str] = []

    print("=" * 60)
    print("ArtClaw Bridge — 共享模块同步校验")
    print("=" * 60)

    for src, dst, desc in pairs:
        if not src.exists():
            missing_src.append(desc)
            print(f"  ⚠️  {desc} — 源码不存在!")
            continue
        if not dst.exists():
            missing_dst.append(desc)
            print(f"  ⚠️  {desc} — 副本不存在!")
            continue

        h_src = file_hash(src)
        h_dst = file_hash(dst)

        if h_src == h_dst:
            print(f"  ✅  {desc}  ({h_src})")
        else:
            mismatches.append((src, dst, desc))
            src_t = os.path.getmtime(src)
            dst_t = os.path.getmtime(dst)
            newer = "src newer" if src_t > dst_t else "dst newer"
            print(f"  ❌  {desc}  src={h_src} dst={h_dst}  ({newer})")

    print()

    if missing_src:
        print(f"⚠️  {len(missing_src)} 个源码文件缺失")
    if missing_dst:
        print(f"⚠️  {len(missing_dst)} 个副本文件缺失")

    if not mismatches and not missing_dst:
        print("✅ 所有共享模块同步一致")
        return 0

    print(f"❌ {len(mismatches)} 个文件不一致, {len(missing_dst)} 个副本缺失")

    if args.fix:
        print("\n--- 修复模式：源码 → 副本 ---")
        for src, dst, desc in mismatches:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  📝 {desc}  已覆盖")
        for desc in missing_dst:
            # 找到对应的 pair
            for src, dst, d in pairs:
                if d == desc and src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    print(f"  📝 {desc}  已复制")
                    break
        print("\n✅ 修复完成")
        return 0

    if args.reverse:
        print("\n--- 反向修复：副本 → 源码 ---")
        for src, dst, desc in mismatches:
            shutil.copy2(dst, src)
            print(f"  📝 {desc}  已回写")
        print("\n✅ 反向修复完成")
        return 0

    if args.ci:
        return 1

    print("\n💡 使用 --fix 自动修复（源码覆盖副本），或 --reverse 反向修复")
    return 1


if __name__ == "__main__":
    sys.exit(main())
