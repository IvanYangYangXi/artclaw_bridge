"""
artclaw_bridge.commands.skill - Skill 子命令实现
==========================================

实现所有 artclaw_bridge skill <subcommand> 的命令逻辑。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Optional

# Windows 控制台 UTF-8 支持
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )

from artclaw_bridge.config import artclaw_bridgeConfig
from artclaw_bridge.manifest import ManifestValidator, load_manifest
from artclaw_bridge.skill_hub import SkillHub, SkillEntry

# VersionManager SDK（可选，找不到 core 目录时不崩溃）
try:
    import sys as _sys
    import os as _os
    _core_path = _os.path.normpath(
        _os.path.join(_os.path.dirname(__file__), '..', '..', '..', '..', 'core')
    )
    if _os.path.isdir(_core_path) and _core_path not in _sys.path:
        _sys.path.insert(0, _core_path)
    from version_manager import (  # noqa: F401
        VersionManager,
        compare_versions,
        matches_skill,
        SyncStatus,
        SyncState,
        ConflictInfo,
        parse_version,
        version_distance,
    )
    _VERSION_MANAGER_AVAILABLE = True
except ImportError:
    _VERSION_MANAGER_AVAILABLE = False


def dispatch(args: argparse.Namespace) -> None:
    """根据 subcommand 分发到对应处理函数。"""
    handlers = {
        "list": _cmd_list,
        "info": _cmd_info,
        "create": _cmd_create,
        "test": _cmd_test,
        "package": _cmd_package,
        "publish": _cmd_publish,
        "install": _cmd_install,
        "uninstall": _cmd_uninstall,
        "enable": _cmd_enable,
        "disable": _cmd_disable,
        "update": _cmd_update,
        "generate": _cmd_generate,
        "check-deps": _cmd_check_deps,
    }
    handler = handlers.get(args.subcommand)
    if handler is None:
        print(f"❌ 未知子命令: {args.subcommand}")
        sys.exit(1)
    try:
        handler(args)
    except KeyboardInterrupt:
        print("\n⚠️ 操作已取消")
        sys.exit(130)
    except Exception as exc:
        print(f"❌ 执行出错: {exc}")
        sys.exit(1)


# ============================================================================
# C6: list / info / enable / disable / uninstall / update
# ============================================================================

def _cmd_list(args: argparse.Namespace) -> None:
    """列出已安装的 Skill。"""
    config = artclaw_bridgeConfig()
    hub = SkillHub(config)
    print("🔍 正在扫描 Skill...")
    hub.scan_all_skills()

    category = args.category or None
    software = args.software or None
    source = args.source or None

    skills = hub.list_skills(category=category, software=software, source=source)

    if not skills:
        print("📦 未发现任何 Skill")
        if category or software or source:
            print("   提示: 尝试去掉筛选条件")
        return

    # 表头
    print(f"\n{'名称':<35} {'分类':<12} {'软件':<16} {'版本':<10} {'层级':<14}")
    print("-" * 87)
    for s in skills:
        print(f"{s.name:<35} {s.category:<12} {s.software:<16} {s.version:<10} {s.layer:<14}")

    print(f"\n✅ 共 {len(skills)} 个 Skill")

    # 冲突检测
    conflicts = hub.detect_conflicts()
    if conflicts:
        print(f"\n⚠️ 发现 {len(conflicts)} 个命名冲突:")
        for c in conflicts:
            overridden = ", ".join(e.layer for e in c.overridden)
            print(f"   {c.name}: {c.winner.layer} 覆盖 {overridden}")


def _cmd_info(args: argparse.Namespace) -> None:
    """显示 Skill 详细信息。"""
    config = artclaw_bridgeConfig()
    hub = SkillHub(config)
    hub.scan_all_skills()

    info = hub.get_skill_info(args.name)
    if info is None:
        print(f"❌ 未找到 Skill: {args.name}")
        sys.exit(1)

    print(f"\n📦 {info.get('display_name', args.name)}")
    print(f"   名称:     {info.get('name', '')}")
    print(f"   版本:     {info.get('version', '')}")
    print(f"   作者:     {info.get('author', '')}")
    print(f"   描述:     {info.get('description', '')}")
    print(f"   分类:     {info.get('category', '')}")
    print(f"   软件:     {info.get('software', '')}")
    print(f"   风险级别: {info.get('risk_level', '')}")
    print(f"   层级:     {info.get('_layer', '')}")
    print(f"   路径:     {info.get('_path', '')}")

    sv = info.get("software_version")
    if sv:
        print(f"   软件版本: {sv.get('min', '*')} ~ {sv.get('max', '*')}")

    tools = info.get("tools", [])
    if tools:
        print(f"\n   暴露工具 ({len(tools)}):")
        for t in tools:
            print(f"     - {t.get('name', '?')}: {t.get('description', '')}")

    tags = info.get("tags", [])
    if tags:
        print(f"\n   标签: {', '.join(tags)}")

    deps = info.get("dependencies", [])
    if deps:
        print(f"\n   依赖: {', '.join(deps)}")

    overridden = info.get("_overridden_by")
    if overridden:
        print(f"\n   ⚠️ 覆盖了以下同名 Skill:")
        for o in overridden:
            print(f"     - 层级 {o['layer']} (v{o['version']}) @ {o['path']}")


def _cmd_enable(args: argparse.Namespace) -> None:
    """启用 Skill（从 ~/.artclaw/config.json 的 disabled_skills 中移除）。"""
    skill_name: str = args.name

    cfg_path = Path.home() / ".artclaw" / "config.json"
    cfg: dict = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    disabled: list = cfg.get("disabled_skills", [])
    if skill_name in disabled:
        disabled.remove(skill_name)
        cfg["disabled_skills"] = disabled
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ Skill '{skill_name}' 已启用（重启 DCC 生效）")
    else:
        print(f"ℹ️  Skill '{skill_name}' 未在禁用列表中")


def _cmd_disable(args: argparse.Namespace) -> None:
    """禁用 Skill（写入 ~/.artclaw/config.json 的 disabled_skills）。"""
    skill_name: str = args.name

    # 检查 skill 是否存在
    config = artclaw_bridgeConfig()
    hub = SkillHub(config)
    hub.scan_all_skills()
    entry = hub.get_skill(skill_name)
    if entry is None:
        print(f"❌ Skill '{skill_name}' 未找到")
        return

    cfg_path = Path.home() / ".artclaw" / "config.json"
    cfg: dict = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    disabled: list = cfg.get("disabled_skills", [])
    if skill_name not in disabled:
        disabled.append(skill_name)
        cfg["disabled_skills"] = disabled
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ Skill '{skill_name}' 已禁用（重启 DCC 生效）")
    else:
        print(f"ℹ️  Skill '{skill_name}' 已经是禁用状态")


def _cmd_uninstall(args: argparse.Namespace) -> None:
    """卸载 Skill。"""
    config = artclaw_bridgeConfig()
    hub = SkillHub(config)
    hub.scan_all_skills()

    entry = hub.get_skill(args.name)
    if entry is None:
        print(f"❌ 未找到 Skill: {args.name}")
        sys.exit(1)

    print(f"📦 将卸载 Skill: {entry.name}")
    print(f"   路径: {entry.path}")
    print(f"   层级: {entry.layer}")

    confirm = input("\n确认卸载？此操作不可撤销 (y/N): ").strip().lower()
    if confirm != "y":
        print("⚠️ 已取消")
        return

    try:
        shutil.rmtree(entry.path)
        print(f"✅ Skill '{args.name}' 已卸载")
    except OSError as exc:
        print(f"❌ 卸载失败: {exc}")
        sys.exit(1)


def _cmd_update(args: argparse.Namespace) -> None:
    """检查并更新 Skill（对比团队库/官方库的版本）。"""
    config = artclaw_bridgeConfig()
    hub = SkillHub(config)
    hub.scan_all_skills()

    name: str = args.name

    # 查找 Skill 在所有层级中的实例
    from artclaw_bridge.skill_hub import LAYER_OFFICIAL, LAYER_TEAM, LAYER_USER

    entries = hub._skills.get(name, [])
    if not entries:
        print(f"❌ 未找到 Skill: {name}")
        sys.exit(1)

    current = entries[0]  # 当前生效的（最高优先级）

    if len(entries) < 2:
        print(f"📦 Skill '{name}' (v{current.version}) 位于 {current.layer}")
        print(f"   没有其他层级的版本可供更新")
        print(f"   如需从远程更新，请手动 Git pull 团队库")
        return

    # 显示所有层级的版本
    print(f"📦 Skill '{name}' 各层级版本:")
    for e in entries:
        marker = " ← 当前生效" if e is current else ""
        print(f"   {e.layer}: v{e.version} ({e.path}){marker}")

    # 检查是否有更高版本
    from artclaw_bridge.skill_hub import _parse_version_tuple
    current_ver = _parse_version_tuple(current.version)
    newer = [e for e in entries[1:] if _parse_version_tuple(e.version) > current_ver]

    if newer:
        print(f"\n⚠️ 发现更高版本:")
        for n in newer:
            print(f"   {n.layer} v{n.version} > 当前 v{current.version}")
        print(f"   注意: 更高版本在低优先级层级，不会自动生效")
        print(f"   如需使用，请将其发布到更高优先级层级:")
        print(f"   artclaw_bridge skill publish {name} --target 00_official")
    else:
        print(f"\n✅ 当前版本 v{current.version} 是最新")


# ============================================================================
# C1: create
# ============================================================================

def _cmd_create(args: argparse.Namespace) -> None:
    """从模板创建新 Skill 脚手架。"""
    config = artclaw_bridgeConfig()
    name: str = args.name
    category: str = args.category
    software: str = args.software
    template: str = args.template
    description: str = args.description or f"{name} skill"
    layer: str = args.layer
    target_dir_str: str = args.target_dir

    # 验证名称
    import re
    if not re.match(r"^[a-z][a-z0-9_]{0,63}$", name):
        print(f"❌ 名称不合法: '{name}'")
        print("   要求: 小写字母开头，仅含小写字母/数字/下划线，最长 64 字符")
        sys.exit(1)

    # 查找模板
    if config.templates_dir is None:
        print("❌ 未找到模板目录")
        sys.exit(1)

    template_dir = config.templates_dir / template
    if not template_dir.is_dir():
        available = [d.name for d in config.templates_dir.iterdir() if d.is_dir()]
        print(f"❌ 模板不存在: '{template}'")
        print(f"   可用模板: {', '.join(available)}")
        sys.exit(1)

    # 确定目标目录
    if target_dir_str:
        target_dir = Path(target_dir_str) / name
    elif layer == "01_team":
        if config.team_skills_dir is None:
            print("❌ 未找到团队 Skill 目录 (team_skills/)")
            sys.exit(1)
        target_dir = config.team_skills_dir / name
    elif layer == "02_user":
        target_dir = config.user_skills_dir / name
    else:
        # 默认: 放到官方库对应的 software/category/ 下
        if config.skills_dir is None:
            print("❌ 未找到 Skill 库目录 (skills/)")
            sys.exit(1)
        target_dir = config.skills_dir / software / category / name

    if target_dir.exists():
        print(f"❌ 目标目录已存在: {target_dir}")
        sys.exit(1)

    # 复制模板
    print(f"📦 从模板 '{template}' 创建 Skill '{name}'...")
    try:
        shutil.copytree(template_dir, target_dir)
    except OSError as exc:
        print(f"❌ 复制模板失败: {exc}")
        sys.exit(1)

    # 替换 manifest.json
    manifest_path = target_dir / "manifest.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["name"] = name
            data["display_name"] = name.replace("_", " ").title()
            data["description"] = description
            data["author"] = "Ivan(杨己力)"
            data["software"] = software
            data["category"] = category
            # 清理 tags 中的 TODO 占位符
            tags = data.get("tags", [])
            data["tags"] = [t for t in tags if not t.startswith("TODO")]
            if not data["tags"]:
                data["tags"] = [category]
            # 替换 tools 中的 TODO 名称
            for tool in data.get("tools", []):
                tool_name = tool.get("name", "")
                if tool_name.startswith("TODO"):
                    tool["name"] = name
                    tool["description"] = description
            manifest_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"⚠️ manifest.json 替换失败: {exc}")

    # 替换 .py 和 .md 文件中的占位符
    replacements = {
        "TODO_skill_name": name,
        "TODO_primary_tool": name,
        "TODO_secondary_tool": f"{name}_query",
        "TODO_tool_name": name,
        "TODO: 技能显示名称": name.replace("_", " ").title(),
        "TODO: 技能描述": description,
        "TODO: 一句话描述这个 Skill 的作用": description,
        "TODO: 一句话描述这个 Skill 的作用，包含使用场景和触发条件": description,
        "TODO: 一句话描述": description,
        "TODO: 详细描述 Skill 的功能和用途。": description,
        "TODO: 作者名": "artclaw_bridge",
        "TODO: 工具描述": description,
        "TODO: 工具的详细描述，说明输入输出和用途": description,
        "TODO: 主工具描述": description,
        "TODO: 辅助工具描述": f"Query helper for {name}",
        '"TODO"': f'"{category}"',
        "TODO: scene|asset|material|lighting|render|blueprint|animation|ui|utils|integration|workflow": category,
    }

    for file_path in target_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix not in (".py", ".md"):
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
            for old, new in replacements.items():
                content = content.replace(old, new)
            file_path.write_text(content, encoding="utf-8")
        except Exception:
            pass  # 非关键文件替换失败不影响整体

    print(f"✅ Skill '{name}' 已创建")
    print(f"   📂 路径: {target_dir}")
    print(f"   📝 分类: {category}")
    print(f"   💻 软件: {software}")
    print(f"\n   下一步:")
    print(f"   1. 编辑 {target_dir / '__init__.py'} 实现 Skill 逻辑")
    print(f"   2. 运行 artclaw_bridge skill test {name} 验证")


# ============================================================================
# C3: test
# ============================================================================

def _cmd_test(args: argparse.Namespace) -> None:
    """测试 Skill 合规性（manifest 验证 + 结构检查）。"""
    config = artclaw_bridgeConfig()
    hub = SkillHub(config)
    validator = ManifestValidator()

    name: str = args.name
    scan_dir: str = args.dir
    dry_run: bool = args.dry_run
    verbose: bool = getattr(args, "verbose", False)

    # 确定要测试的 Skill
    if name:
        hub.scan_all_skills()
        entry = hub.get_skill(name)
        if entry is None:
            # 尝试作为路径处理
            name_path = Path(name)
            if name_path.is_dir() and (name_path / "manifest.json").exists():
                targets = [name_path]
            else:
                print(f"❌ 未找到 Skill: {name}")
                sys.exit(1)
            targets = [name_path]
        else:
            targets = [entry.path]
    elif scan_dir:
        targets = _find_skill_dirs(Path(scan_dir))
    else:
        hub.scan_all_skills()
        all_skills = hub.list_skills()
        targets = [s.path for s in all_skills]

    if not targets:
        print("📦 没有找到需要测试的 Skill")
        return

    if dry_run:
        print(f"🔍 Dry-run: 将测试以下 {len(targets)} 个 Skill:")
        for t in targets:
            print(f"   📦 {t}")
        return

    print(f"🔍 测试 {len(targets)} 个 Skill...\n")

    passed = 0
    failed = 0

    for skill_dir in targets:
        skill_name = skill_dir.name
        errors: list[str] = []

        # 检查 manifest.json（或 SKILL.md 作为 fallback）
        manifest_path = skill_dir / "manifest.json"
        skill_md_path = skill_dir / "SKILL.md"
        if not manifest_path.exists():
            if skill_md_path.exists():
                # SKILL.md 模式 — 只做基本检查
                pass  # 允许仅有 SKILL.md 的 OpenClaw 兼容包
            else:
                errors.append("缺少 manifest.json 或 SKILL.md")
        else:
            result = validator.validate_file(manifest_path)
            if not result.success:
                errors.extend(result.errors)
            else:
                # 读取 manifest 检查 entry_point
                try:
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    entry_point = data.get("entry_point", "__init__.py")
                    ep_path = skill_dir / entry_point
                    if not ep_path.exists():
                        errors.append(f"入口文件不存在: {entry_point}")
                    skill_name = data.get("name", skill_name)
                except Exception as exc:
                    errors.append(f"读取 manifest 失败: {exc}")

        # 检查 __init__.py
        init_path = skill_dir / "__init__.py"
        if not init_path.exists():
            errors.append("缺少 __init__.py")

        # 输出结果
        if errors:
            failed += 1
            print(f"❌ {skill_name} ({skill_dir})")
            for err in errors:
                print(f"   - {err}")
        else:
            passed += 1
            if verbose:
                print(f"✅ {skill_name} ({skill_dir})")
            else:
                print(f"✅ {skill_name}")

    print(f"\n{'=' * 40}")
    print(f"测试完成: ✅ {passed} 通过, ❌ {failed} 失败, 共 {passed + failed} 个")
    if failed > 0:
        sys.exit(1)


def _find_skill_dirs(root: Path) -> list[Path]:
    """递归查找包含 manifest.json 或 SKILL.md 的 Skill 目录。"""
    results: list[Path] = []
    seen: set[str] = set()
    try:
        for manifest in root.rglob("manifest.json"):
            d = str(manifest.parent)
            if d not in seen:
                results.append(manifest.parent)
                seen.add(d)
        for skill_md in root.rglob("SKILL.md"):
            d = str(skill_md.parent)
            if d not in seen:
                results.append(skill_md.parent)
                seen.add(d)
    except OSError:
        pass
    return results


# ============================================================================
# C4: package
# ============================================================================

def _cmd_package(args: argparse.Namespace) -> None:
    """将 Skill 打包为 zip 发布包。"""
    config = artclaw_bridgeConfig()
    hub = SkillHub(config)
    hub.scan_all_skills()

    entry = hub.get_skill(args.name)
    if entry is None:
        print(f"❌ 未找到 Skill: {args.name}")
        sys.exit(1)

    version = entry.version
    output_dir = Path(args.output) if args.output else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_name = f"{entry.name}-{version}.zip"
    zip_path = output_dir / zip_name

    print(f"📦 正在打包 Skill '{entry.name}' v{version}...")

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in entry.path.rglob("*"):
                if file_path.is_file():
                    # 跳过 __pycache__
                    if "__pycache__" in file_path.parts:
                        continue
                    arcname = file_path.relative_to(entry.path.parent)
                    zf.write(file_path, arcname)

        file_size = zip_path.stat().st_size
        size_str = _format_size(file_size)
        print(f"✅ 打包完成: {zip_path} ({size_str})")
    except Exception as exc:
        print(f"❌ 打包失败: {exc}")
        sys.exit(1)


def _format_size(size_bytes: int) -> str:
    """格式化文件大小。"""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ============================================================================
# C5: publish
# ============================================================================

def _cmd_publish(args: argparse.Namespace) -> None:
    """发布 Skill 到指定层级目录。"""
    config = artclaw_bridgeConfig()
    hub = SkillHub(config)
    hub.scan_all_skills()

    entry = hub.get_skill(args.name)
    if entry is None:
        print(f"❌ 未找到 Skill: {args.name}")
        sys.exit(1)

    target = args.target  # "01_team" or "00_official"

    if target == "01_team":
        if config.team_skills_dir is None:
            print("❌ 未找到团队 Skill 目录 (team_skills/)")
            sys.exit(1)
        dest_dir = config.team_skills_dir / entry.name
    elif target == "00_official":
        if config.skills_dir is None:
            print("❌ 未找到官方 Skill 目录 (skills/)")
            sys.exit(1)
        dest_dir = config.skills_dir / entry.software / entry.category / entry.name
    else:
        print(f"❌ 不支持的发布目标: {target}")
        print("   可选: 01_team, 00_official")
        sys.exit(1)

    if dest_dir.exists():
        confirm = input(f"⚠️ 目标已存在: {dest_dir}\n   覆盖？(y/N): ").strip().lower()
        if confirm != "y":
            print("⚠️ 已取消")
            return
        shutil.rmtree(dest_dir)

    print(f"📦 正在发布 '{entry.name}' 到 {target}...")
    try:
        shutil.copytree(
            entry.path, dest_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        msg = args.message or "(无)"
        print(f"✅ 发布完成")
        print(f"   目标: {dest_dir}")
        print(f"   版本: {entry.version}")
        print(f"   说明: {msg}")
    except OSError as exc:
        print(f"❌ 发布失败: {exc}")
        sys.exit(1)


# ============================================================================
# C2: install / generate
# ============================================================================

def _cmd_install(args: argparse.Namespace) -> None:
    """安装 Skill。"""
    source: str = args.source
    source_type: str = args.source_type
    layer: str = args.layer
    config = artclaw_bridgeConfig()

    if source_type == "git":
        print("⚠️ Git 安装方式尚未支持")
        print("   请手动 clone 后使用 --source-type local 安装")
        sys.exit(0)

    if source_type == "registry":
        print("⚠️ 远程注册表安装方式尚未支持")
        sys.exit(0)

    # local 安装
    source_path = Path(source)
    if not source_path.is_dir():
        # 尝试作为 zip 解压
        if source_path.is_file() and source_path.suffix == ".zip":
            _install_from_zip(source_path, layer, config)
            return
        print(f"❌ 源路径不存在或不是目录: {source}")
        sys.exit(1)

    manifest_path = source_path / "manifest.json"
    if not manifest_path.exists():
        print(f"❌ 源目录缺少 manifest.json: {source}")
        sys.exit(1)

    # 读取名称
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        name = data["name"]
    except Exception as exc:
        print(f"❌ 读取 manifest 失败: {exc}")
        sys.exit(1)

    # 确定目标
    if layer == "02_user":
        dest_dir = config.user_skills_dir / name
    elif layer == "01_team":
        if config.team_skills_dir is None:
            print("❌ 未找到团队目录")
            sys.exit(1)
        dest_dir = config.team_skills_dir / name
    else:
        if config.skills_dir is None:
            print("❌ 未找到 Skill 库目录")
            sys.exit(1)
        dest_dir = config.skills_dir / name

    if dest_dir.exists():
        confirm = input(f"⚠️ 目标已存在: {dest_dir}\n   覆盖？(y/N): ").strip().lower()
        if confirm != "y":
            print("⚠️ 已取消")
            return
        shutil.rmtree(dest_dir)

    print(f"📦 正在安装 '{name}' 到 {layer}...")
    try:
        shutil.copytree(
            source_path, dest_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        print(f"✅ 安装完成: {dest_dir}")

        # E3: 安装后检查依赖
        _resolve_dependencies_for_install(dest_dir, config)
    except OSError as exc:
        print(f"❌ 安装失败: {exc}")
        sys.exit(1)


def _install_from_zip(zip_path: Path, layer: str, config: artclaw_bridgeConfig) -> None:
    """从 zip 包安装 Skill。"""
    import tempfile

    print(f"📦 从 zip 安装: {zip_path}")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_path)

            # 查找 manifest.json
            manifests = list(tmp_path.rglob("manifest.json"))
            if not manifests:
                print("❌ zip 包中未找到 manifest.json")
                sys.exit(1)

            skill_dir = manifests[0].parent
            # 递归调用本地安装
            class FakeArgs:
                pass
            fake = FakeArgs()
            fake.source = str(skill_dir)
            fake.source_type = "local"
            fake.layer = layer
            _cmd_install(fake)
    except zipfile.BadZipFile:
        print(f"❌ 无效的 zip 文件: {zip_path}")
        sys.exit(1)


def _cmd_generate(args: argparse.Namespace) -> None:
    """通过自然语言描述生成 Skill (TODO: AI 生成待实现)。"""
    description: str = args.description
    category: str = args.category
    software: str = args.software
    dry_run: bool = args.dry_run

    print(f"🤖 自然语言生成 Skill")
    print(f"   描述: {description}")
    print(f"   分类: {category or '(自动检测)'}")
    print(f"   软件: {software}")

    if dry_run:
        print("\n   [Dry-run] 将生成以下文件:")
        print("   - manifest.json")
        print("   - __init__.py")
        print("   - README.md")
        print("\n   ⚠️ AI 生成功能需要配置 LLM 后端，当前为预览模式")
        return

    # TODO: 集成 AI 生成逻辑
    # 当前降级为从 basic 模板创建，用描述作为 skill 名
    print("\n⚠️ AI 自动生成功能尚在开发中")
    print("   当前降级为模板创建模式\n")

    # 从描述推断名称
    import re
    # 简单处理：取关键词拼接
    clean = re.sub(r"[^\w\s]", "", description.lower())
    words = clean.split()[:4]
    inferred_name = "_".join(words) if words else "generated_skill"
    # 确保合法
    inferred_name = re.sub(r"[^a-z0-9_]", "", inferred_name)
    if not inferred_name or not inferred_name[0].isalpha():
        inferred_name = "skill_" + inferred_name

    inferred_category = category or "utils"

    print(f"   推断名称: {inferred_name}")
    print(f"   推断分类: {inferred_category}")

    # 复用 create 逻辑
    class FakeArgs:
        pass
    fake = FakeArgs()
    fake.name = inferred_name
    fake.category = inferred_category
    fake.software = software
    fake.template = "basic"
    fake.description = description
    fake.target_dir = args.target_dir if hasattr(args, "target_dir") else ""
    fake.layer = args.layer if hasattr(args, "layer") else "02_user"
    _cmd_create(fake)


# ============================================================================
# E3: 依赖检查
# ============================================================================

def _check_dependencies(skill_dir: Path, config: artclaw_bridgeConfig) -> list[str]:
    """检查 Skill 的依赖是否已安装。

    读取 manifest.json 中的 dependencies 字段，
    检查每个依赖是否能在当前 Skill 库中找到。

    Returns:
        缺失的依赖列表（空列表表示全部满足）。
    """
    manifest_path = skill_dir / "manifest.json"
    if not manifest_path.exists():
        return []

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    deps = data.get("dependencies", [])
    if not deps:
        return []

    # 扫描所有可用 Skill
    hub = SkillHub(config)
    hub.scan_all_skills()

    missing = []
    for dep_str in deps:
        # 解析依赖格式: "artclaw_bridge.universal.utils>=1.0.0" 或 "skill_name"
        import re
        match = re.match(r"^(?:artclaw_bridge\.[\w.]+\.)?(\w+)(?:[><=!]+.*)?$", dep_str)
        if match:
            dep_name = match.group(1)
        else:
            dep_name = dep_str.split(">=")[0].split("<=")[0].split("==")[0].strip()

        entry = hub.get_skill(dep_name)
        if entry is None:
            missing.append(dep_str)

    return missing


def _resolve_dependencies_for_install(skill_dir: Path, config: artclaw_bridgeConfig, check_deps: bool = True) -> bool:
    """
    检查并自动安装缺失依赖。

    :param check_deps: 内部递归调用时传 False，避免无限循环
    :return: True 表示所有依赖满足（或已安装），False 表示有依赖安装失败
    """
    if not check_deps:
        return True

    missing = _check_dependencies(skill_dir, config)
    if not missing:
        return True

    import re as _re

    print(f"\n⚠️  发现 {len(missing)} 个缺失依赖:")
    for dep in missing:
        print(f"   - {dep}")

    print(f"\n🔍 正在从本地源码库查找依赖...")
    hub = SkillHub(config)
    hub.scan_all_skills()

    all_ok = True
    for dep_name_raw in missing:
        # 去掉版本约束，取 skill 名称部分
        clean_name = _re.split(r'[>=<]', dep_name_raw)[0].strip()
        # 如果是 "artclaw_bridge.layer.dcc.name" 格式，取最后一段
        if '.' in clean_name:
            clean_name = clean_name.split('.')[-1]

        dep_entry = hub.get_skill(clean_name)
        if dep_entry is None:
            print(f"   ❌ 依赖 '{clean_name}' 在本地源码库中未找到，请手动安装")
            all_ok = False
            continue

        print(f"   📦 正在安装依赖: {clean_name} (来自 {dep_entry.layer})")
        try:
            _install_skill_files(dep_entry.path, config, check_deps=False)
            print(f"   ✅ 依赖 '{clean_name}' 安装成功")
        except Exception as e:
            print(f"   ❌ 依赖 '{clean_name}' 安装失败: {e}")
            all_ok = False

    return all_ok


def _install_skill_files(src_dir: Path, config: artclaw_bridgeConfig, layer: str = "02_user", check_deps: bool = True) -> None:
    """
    将 src_dir 中的 Skill 复制到目标层级目录。
    提取自 _cmd_install，供依赖自动安装复用。

    :param src_dir: Skill 源目录（包含 manifest.json）
    :param config: 项目配置
    :param layer: 目标层级，默认 "02_user"
    :param check_deps: 是否递归检查并安装依赖（False 避免无限循环）
    :raises Exception: 目录不存在、manifest 缺失、复制失败等
    """
    manifest_path = src_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json 不存在: {src_dir}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = data["name"]

    if layer == "02_user":
        dest_dir = config.user_skills_dir / name
    elif layer == "01_team":
        if config.team_skills_dir is None:
            raise RuntimeError("未找到团队目录")
        dest_dir = config.team_skills_dir / name
    else:
        if config.skills_dir is None:
            raise RuntimeError("未找到 Skill 库目录")
        dest_dir = config.skills_dir / name

    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    shutil.copytree(
        src_dir, dest_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    if check_deps:
        _resolve_dependencies_for_install(dest_dir, config, check_deps=True)


def _cmd_check_deps(args: argparse.Namespace) -> None:
    """检查 Skill 依赖是否满足。"""
    config = artclaw_bridgeConfig()
    hub = SkillHub(config)
    hub.scan_all_skills()

    name: str = args.name

    if name:
        # 检查单个 Skill
        entry = hub.get_skill(name)
        if entry is None:
            print(f"❌ 未找到 Skill: {name}")
            sys.exit(1)
        skills_to_check = [entry]
    else:
        # 检查所有 Skill
        skills_to_check = hub.list_skills()

    if not skills_to_check:
        print("📦 没有找到需要检查的 Skill")
        return

    print(f"🔍 检查 {len(skills_to_check)} 个 Skill 的依赖...\n")

    all_ok = True
    for entry in skills_to_check:
        missing = _check_dependencies(entry.path, config)
        if missing:
            all_ok = False
            print(f"❌ {entry.name} (v{entry.version})")
            for dep in missing:
                print(f"   缺失: {dep}")
        else:
            deps = entry.manifest.get("dependencies", [])
            if deps:
                print(f"✅ {entry.name} — {len(deps)} 个依赖全部满足")

    if all_ok:
        print(f"\n✅ 所有依赖检查通过")
    else:
        print(f"\n⚠️ 存在未满足的依赖，请安装后重试")
        sys.exit(1)
