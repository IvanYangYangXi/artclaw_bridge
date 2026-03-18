#!/usr/bin/env python3
"""
skill_test.py - ArtClaw Skill 本地测试工具
=============================================

用法:
    python skill_test.py                     # 测试所有 Skill
    python skill_test.py scene_ops           # 测试指定模块
    python skill_test.py --skill spawn_actor # 测试指定 Skill
    python skill_test.py --list              # 列出所有已发现的 Skill
    python skill_test.py --validate          # 仅验证不执行
    python skill_test.py --dry-run           # 干运行模式

说明:
    - 在 UE 外部运行，不需要 OpenClaw 或 MCP 连接
    - 自动发现 Skills/ 目录中所有通过 @ue_tool 装饰器注册的 Skill
    - 验证 Skill 声明规范（name、description、category、risk_level）
    - 执行干运行测试（unreal=None 路径）
    - 可集成到 CI/CD 或 artclaw skill test 命令
"""

import argparse
import importlib
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================================
# UE Mock（允许在 UE 外部运行）
# ============================================================================

class _MockModule:
    """轻量级 Mock 模块，返回 None 或空字符串给所有属性访问"""
    def __getattr__(self, name):
        return _MockModule()
    def __call__(self, *args, **kwargs):
        return _MockModule()
    def __bool__(self):
        return False
    def __str__(self):
        return ""
    def __repr__(self):
        return "<Mock>"


def _setup_ue_mocks():
    """
    注入 UE 相关模块的 mock，使 skill_hub.py 可在 UE 外部导入。
    
    skill_hub.py 在顶层导入了 unreal 和 init_unreal，
    这些模块只在 UE Python 环境中存在。
    
    注意：Skill 文件中使用 `try: import unreal / except: unreal = None` 模式，
    所以这里的 mock 只是为了让 skill_hub.py 能导入。
    Skill 函数内会走 `unreal is None` 的保护分支（因为 Skill 自己 import 时会
    catch 到 ImportError 并设为 None）。
    
    为确保 Skill 文件也走 None 分支，我们在 mock 注入后加载 skill_hub，
    但不预注入 unreal 给 Skill 文件 — Skill 文件自己的 try/except 会生效。
    """
    if "unreal" not in sys.modules:
        sys.modules["unreal"] = _MockModule()
    if "init_unreal" not in sys.modules:
        # init_unreal 导出 UELogger, log_mcp_call, sync_connection_state
        mock_init = _MockModule()
        mock_init.UELogger = _MockModule()
        mock_init.log_mcp_call = lambda f: f  # 装饰器直接返回原函数
        mock_init.sync_connection_state = lambda *a: None
        sys.modules["init_unreal"] = mock_init


# ============================================================================
# 配置
# ============================================================================

# Skill 文件目录（相对于本脚本）
SCRIPT_DIR = Path(__file__).parent
SKILLS_DIR = SCRIPT_DIR.parent / "Skills"  # Content/Python/Skills/
SKILL_HUB_DIR = SCRIPT_DIR.parent          # Content/Python/ (skill_hub.py 所在)

# 有效的 category 枚举
VALID_CATEGORIES = {
    "scene", "asset", "material", "level", "lighting",
    "render", "blueprint", "animation", "utils", "ui",
    "workflow", "integration", "general",
}

# 有效的 risk_level 枚举
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}

# 颜色输出
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def colored(text: str, color: str) -> str:
    """添加终端颜色"""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{Colors.RESET}"


# ============================================================================
# Skill 发现
# ============================================================================

def discover_skills(skills_dir: Path, module_filter: Optional[str] = None) -> Dict[str, dict]:
    """
    扫描 Skills/ 目录，发现所有通过 @ue_tool 装饰器注册的 Skill。
    
    Returns:
        dict: {skill_name: {name, description, category, risk_level, handler, module, source_file}}
    """
    # skill_hub.py 位于 Skills/ 的父目录（Content/Python/）
    skills_dir = skills_dir.resolve()
    skill_hub_dir = skills_dir.parent  # Content/Python/
    
    # 同时保留 SKILL_HUB_DIR 作为 fallback
    for d in [str(skill_hub_dir), str(SKILL_HUB_DIR)]:
        if d not in sys.path:
            sys.path.insert(0, d)
    if str(skills_dir) not in sys.path:
        sys.path.insert(0, str(skills_dir))

    # Mock UE 模块，允许在 UE 外部导入 skill_hub
    _setup_ue_mocks()

    # 导入 skill_hub 以获取装饰器注册表
    try:
        import skill_hub
        skill_hub._DECORATED_SKILLS.clear()
    except ImportError as e:
        print(colored(f"ERROR: Cannot import skill_hub.py: {e}", Colors.RED))
        print(f"  Expected at: {skill_hub_dir / 'skill_hub.py'}")
        sys.exit(1)

    # skill_hub 导入完成后，移除 unreal mock，
    # 让 Skill 文件的 `try: import unreal / except: unreal = None` 走 None 分支
    sys.modules.pop("unreal", None)

    # 查找 Skill 源文件
    # 支持两种结构:
    #   1. 扁平文件: Skills/my_skill.py
    #   2. 包目录:   Skills/my_skill/__init__.py 或 skills/ue/core/scene/my_skill/__init__.py
    skill_entries = []

    # 扁平 .py 文件
    for py_file in sorted(skills_dir.glob("*.py")):
        if py_file.name != "__init__.py" and "__pycache__" not in str(py_file):
            skill_entries.append(("file", py_file.stem, py_file))

    # 包目录（直接子目录，含 __init__.py）
    for d in sorted(skills_dir.iterdir()):
        if d.is_dir() and (d / "__init__.py").exists() and "__pycache__" not in str(d):
            skill_entries.append(("pkg", d.name, d / "__init__.py"))

    # 递归搜索深层包目录（适配 skills/unreal_engine/core/scene/my_skill/ 结构）
    for init_file in sorted(skills_dir.rglob("*/__init__.py")):
        pkg_dir = init_file.parent
        if "__pycache__" in str(pkg_dir):
            continue
        # 避免与直接子目录重复
        rel = pkg_dir.relative_to(skills_dir)
        if len(rel.parts) > 1:  # 深层目录
            skill_entries.append(("pkg", pkg_dir.name, init_file))

    # 去重（按文件路径）
    seen = set()
    unique_entries = []
    for kind, name, path in skill_entries:
        if str(path) not in seen:
            seen.add(str(path))
            unique_entries.append((kind, name, path))
    skill_entries = unique_entries

    if module_filter:
        skill_entries = [(k, n, p) for k, n, p in skill_entries if n == module_filter]

    if not skill_entries:
        print(colored("No skill files found.", Colors.YELLOW))
        return {}

    # 加载每个模块
    for kind, name, py_file in skill_entries:
        module_name = f"ue_skill_{name}"
        try:
            # 确保包目录的父路径在 sys.path 中
            parent_dir = str(py_file.parent.parent if kind == "pkg" else py_file.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            spec = importlib.util.spec_from_file_location(module_name, str(py_file))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                display = f"{name}/" if kind == "pkg" else py_file.name
                print(f"  {colored('LOADED', Colors.GREEN)} {display}")
        except Exception as e:
            display = f"{name}/" if kind == "pkg" else py_file.name
            print(f"  {colored('FAILED', Colors.RED)} {display}: {e}")

    return dict(skill_hub._DECORATED_SKILLS)


# ============================================================================
# 验证规则
# ============================================================================

class ValidationResult:
    def __init__(self, skill_name: str):
        self.skill_name = skill_name
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)


def validate_skill(name: str, info: dict) -> ValidationResult:
    """验证单个 Skill 的声明规范"""
    result = ValidationResult(name)

    # 1. name 规范
    if not name:
        result.add_error("name is empty")
    elif name != name.lower():
        result.add_error(f"name must be lowercase: '{name}'")
    elif " " in name:
        result.add_error(f"name must not contain spaces: '{name}'")
    elif not name.replace("_", "").isalnum():
        result.add_error(f"name must be alphanumeric with underscores: '{name}'")
    if len(name) > 40:
        result.add_warning(f"name is long ({len(name)} chars), recommend < 40")

    # 2. description 规范
    desc = info.get("description", "")
    if not desc:
        result.add_error("description is empty")
    elif len(desc) < 10:
        result.add_warning(f"description is very short ({len(desc)} chars)")
    # 检测是否包含中文（应使用英文）
    if desc and any('\u4e00' <= c <= '\u9fff' for c in desc):
        result.add_warning("description contains Chinese characters; prefer English for AI consumption")

    # 3. category 规范
    category = info.get("category", "")
    if not category:
        result.add_error("category is empty")
    elif category not in VALID_CATEGORIES:
        result.add_warning(f"category '{category}' is not in standard set: {VALID_CATEGORIES}")

    # 4. risk_level 规范
    risk = info.get("risk_level", "")
    if not risk:
        result.add_error("risk_level is empty")
    elif risk not in VALID_RISK_LEVELS:
        result.add_error(f"risk_level must be one of {VALID_RISK_LEVELS}, got: '{risk}'")

    # 5. handler 检查
    handler = info.get("handler")
    if handler is None:
        result.add_error("handler function is missing")
    elif not callable(handler):
        result.add_error("handler is not callable")

    # 6. input_schema 检查
    schema = info.get("input_schema", {})
    if not schema:
        result.add_warning("input_schema is empty")
    elif schema.get("type") != "object":
        result.add_warning("input_schema should have type='object'")

    return result


def validate_manifest(skill_dir: Path) -> Optional[ValidationResult]:
    """验证 Skill 包目录中的 manifest.json"""
    manifest_path = skill_dir / "manifest.json"
    if not manifest_path.exists():
        return None  # 不是包结构，跳过

    result = ValidationResult(f"{skill_dir.name}/manifest.json")

    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        result.add_error(f"Invalid JSON: {e}")
        return result

    # 必填字段
    required_fields = ["manifest_version", "name", "description", "version",
                       "software", "category", "risk_level", "entry_point"]
    for field in required_fields:
        if field not in manifest:
            result.add_error(f"Missing required field: {field}")

    # name 与目录名匹配
    if manifest.get("name") and manifest["name"] != skill_dir.name:
        result.add_warning(
            f"manifest name '{manifest['name']}' doesn't match directory name '{skill_dir.name}'"
        )

    # entry_point 文件存在
    entry = manifest.get("entry_point", "__init__.py")
    if not (skill_dir / entry).exists():
        result.add_error(f"entry_point file not found: {entry}")

    # software 有效值
    valid_software = {"universal", "unreal_engine", "maya", "3ds_max"}
    if manifest.get("software") and manifest["software"] not in valid_software:
        result.add_warning(f"Unusual software value: {manifest['software']}")

    # risk_level
    if manifest.get("risk_level") and manifest["risk_level"] not in VALID_RISK_LEVELS:
        result.add_error(f"Invalid risk_level: {manifest['risk_level']}")

    # category
    if manifest.get("category") and manifest["category"] not in VALID_CATEGORIES:
        result.add_warning(f"Unusual category: {manifest['category']}")

    # tools 数组
    tools = manifest.get("tools", [])
    if not tools:
        result.add_warning("No tools declared in manifest")

    return result


# ============================================================================
# 干运行测试
# ============================================================================

def dry_run_skill(name: str, info: dict, test_args: Optional[dict] = None) -> Tuple[bool, str]:
    """
    干运行 Skill（在 unreal=None 环境下测试）。
    
    Returns:
        (success, output_or_error)
    """
    handler = info.get("handler")
    if handler is None:
        return False, "No handler"

    args = test_args or {}

    try:
        start = time.perf_counter()
        result_str = handler(args)
        elapsed = time.perf_counter() - start

        # 验证返回值是有效 JSON
        if not isinstance(result_str, str):
            return False, f"Handler returned {type(result_str).__name__}, expected str"

        try:
            result = json.loads(result_str)
        except json.JSONDecodeError as e:
            return False, f"Handler returned invalid JSON: {e}"

        # 验证返回值包含 success 字段
        if "success" not in result and "error" not in result:
            return False, f"Response missing 'success' field: {list(result.keys())}"

        return True, f"OK ({elapsed:.3f}s) → {result_str[:200]}"

    except Exception as e:
        return False, f"Exception: {type(e).__name__}: {e}"


# ============================================================================
# 报告生成
# ============================================================================

def print_report(skills: Dict[str, dict], validations: List[ValidationResult],
                 dry_runs: Optional[List[Tuple[str, bool, str]]] = None,
                 manifest_validations: Optional[List[ValidationResult]] = None):
    """打印测试报告"""
    print()
    print(colored("=" * 60, Colors.BOLD))
    print(colored("  ArtClaw Skill Test Report", Colors.BOLD))
    print(colored("=" * 60, Colors.BOLD))
    print()

    # 总览
    total = len(validations)
    passed = sum(1 for v in validations if v.passed)
    warnings = sum(len(v.warnings) for v in validations)
    errors = sum(len(v.errors) for v in validations)

    print(f"  Skills found:   {colored(str(total), Colors.CYAN)}")
    print(f"  Validation:     {colored(f'{passed}/{total} passed', Colors.GREEN if passed == total else Colors.YELLOW)}")
    print(f"  Errors:         {colored(str(errors), Colors.RED if errors > 0 else Colors.GREEN)}")
    print(f"  Warnings:       {colored(str(warnings), Colors.YELLOW if warnings > 0 else Colors.GREEN)}")
    print()

    # 详细结果
    for v in validations:
        status = colored("✓ PASS", Colors.GREEN) if v.passed else colored("✗ FAIL", Colors.RED)
        info = skills.get(v.skill_name, {})
        cat = info.get("category", "?")
        risk = info.get("risk_level", "?")
        print(f"  {status}  {v.skill_name}  [{cat}] [{risk}]")

        for err in v.errors:
            print(f"         {colored('ERROR', Colors.RED)}: {err}")
        for warn in v.warnings:
            print(f"         {colored('WARN', Colors.YELLOW)}: {warn}")

    # 干运行结果
    if dry_runs:
        print()
        print(colored("  --- Dry Run Results ---", Colors.BOLD))
        print()
        dr_passed = sum(1 for _, ok, _ in dry_runs if ok)
        for name, ok, msg in dry_runs:
            status = colored("✓", Colors.GREEN) if ok else colored("✗", Colors.RED)
            print(f"  {status}  {name}: {msg}")
        print()
        print(f"  Dry run: {colored(f'{dr_passed}/{len(dry_runs)} passed', Colors.GREEN if dr_passed == len(dry_runs) else Colors.YELLOW)}")

    # manifest.json 验证结果
    if manifest_validations:
        print()
        print(colored("  --- Manifest Validation ---", Colors.BOLD))
        print()
        m_passed = sum(1 for v in manifest_validations if v.passed)
        m_total = len(manifest_validations)
        for v in manifest_validations:
            status = colored("✓ PASS", Colors.GREEN) if v.passed else colored("✗ FAIL", Colors.RED)
            print(f"  {status}  {v.skill_name}")
            for err in v.errors:
                print(f"         {colored('ERROR', Colors.RED)}: {err}")
            for warn in v.warnings:
                print(f"         {colored('WARN', Colors.YELLOW)}: {warn}")
        print()
        print(f"  Manifests: {colored(f'{m_passed}/{m_total} passed', Colors.GREEN if m_passed == m_total else Colors.YELLOW)}")
        # manifest errors also count
        errors += sum(len(v.errors) for v in manifest_validations)

    print()
    print(colored("=" * 60, Colors.BOLD))

    # 退出码
    if errors > 0:
        return 1
    return 0


# ============================================================================
# Skill 列表显示
# ============================================================================

def print_skill_list(skills: Dict[str, dict]):
    """打印已发现的 Skill 列表"""
    print()
    print(colored("  Discovered Skills", Colors.BOLD))
    print(colored("  " + "-" * 50, Colors.DIM))

    # 按 category 分组
    by_category: Dict[str, list] = {}
    for name, info in skills.items():
        cat = info.get("category", "general")
        by_category.setdefault(cat, []).append((name, info))

    for cat in sorted(by_category.keys()):
        print()
        print(f"  {colored(f'[{cat}]', Colors.CYAN)}")
        for name, info in sorted(by_category[cat], key=lambda x: x[0]):
            risk = info.get("risk_level", "?")
            desc = (info.get("description", "")[:60] + "...") if len(info.get("description", "")) > 60 else info.get("description", "")
            risk_color = {
                "low": Colors.GREEN,
                "medium": Colors.YELLOW,
                "high": Colors.RED,
                "critical": Colors.RED,
            }.get(risk, Colors.DIM)
            print(f"    {name:35s} {colored(risk, risk_color):8s}  {desc}")

    print()
    print(f"  Total: {colored(str(len(skills)), Colors.CYAN)} skills")
    print()


# ============================================================================
# 主入口
# ============================================================================

def main():
    # 确保 stdout 使用 utf-8 编码（Windows 兼容）
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        description="ArtClaw Skill 本地测试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python skill_test.py                       # 测试所有 Skill
  python skill_test.py scene_ops             # 测试 scene_ops 模块
  python skill_test.py --skill spawn_actor   # 测试指定 Skill
  python skill_test.py --list                # 列出所有 Skill
  python skill_test.py --validate            # 仅验证声明规范
  python skill_test.py --dry-run             # 执行干运行测试
  python skill_test.py --skills-dir /path    # 指定 Skills 目录
        """,
    )
    parser.add_argument("module", nargs="?", help="指定要测试的模块名（不含 .py）")
    parser.add_argument("--skill", help="指定要测试的 Skill 名称")
    parser.add_argument("--list", action="store_true", help="列出所有已发现的 Skill")
    parser.add_argument("--validate", action="store_true", help="仅验证声明规范，不执行")
    parser.add_argument("--dry-run", action="store_true", help="执行干运行测试")
    parser.add_argument("--skills-dir", help="Skills 目录路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 确定 Skills 目录
    skills_dir = Path(args.skills_dir) if args.skills_dir else SKILLS_DIR
    if not skills_dir.exists():
        print(colored(f"Skills directory not found: {skills_dir}", Colors.RED))
        sys.exit(1)

    print()
    print(colored(f"  ArtClaw Skill Tester v1.0", Colors.BOLD))
    print(f"  Skills dir: {skills_dir}")
    print()
    print("  Discovering skills...")

    # 发现 Skill
    skills = discover_skills(skills_dir, module_filter=args.module)

    if not skills:
        print(colored("\n  No skills discovered.", Colors.YELLOW))
        sys.exit(0)

    # 过滤指定 Skill
    if args.skill:
        if args.skill in skills:
            skills = {args.skill: skills[args.skill]}
        else:
            print(colored(f"\n  Skill not found: {args.skill}", Colors.RED))
            print(f"  Available: {', '.join(sorted(skills.keys()))}")
            sys.exit(1)

    # 列表模式
    if args.list:
        print_skill_list(skills)
        sys.exit(0)

    # 验证
    print()
    print("  Validating skills...")
    validations = [validate_skill(name, info) for name, info in skills.items()]

    # 验证 manifest.json（包结构的 Skill）
    manifest_validations = []
    for init_file in skills_dir.rglob("*/__init__.py"):
        pkg_dir = init_file.parent
        if "__pycache__" in str(pkg_dir):
            continue
        mv = validate_manifest(pkg_dir)
        if mv is not None:
            manifest_validations.append(mv)

    # 干运行
    dry_runs = None
    if args.dry_run or (not args.validate):
        # 默认行为：验证 + 干运行
        print("  Running dry-run tests...")
        dry_runs = []
        for name, info in skills.items():
            ok, msg = dry_run_skill(name, info)
            dry_runs.append((name, ok, msg))

    # 报告
    exit_code = print_report(skills, validations, dry_runs, manifest_validations)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
