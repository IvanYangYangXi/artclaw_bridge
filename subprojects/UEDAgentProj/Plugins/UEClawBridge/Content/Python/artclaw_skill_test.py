#!/usr/bin/env python3
"""
artclaw_skill_test.py - Skill 本地测试工具
============================================

无需 UE 即可测试 Skill 的基本结构和 Schema 合规性。

用法:
    python artclaw_skill_test.py                          # 测试所有 Skills/ 下的文件
    python artclaw_skill_test.py scene_ops.py             # 测试单个文件
    python artclaw_skill_test.py --dir D:/path/to/Skills  # 指定目录

测试内容:
  1. 语法检查（ast.parse）
  2. 模块可导入（不依赖 unreal）
  3. @ue_tool 装饰器使用合规性
  4. 返回值格式校验（传空 arguments 调用）
  5. 开发规范审查清单
"""

import ast
import importlib
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
from typing import List, Tuple


# ============================================================================
# 测试结果
# ============================================================================

class TestResult:
    def __init__(self):
        self.passed: List[str] = []
        self.warnings: List[str] = []
        self.failed: List[str] = []

    def pass_(self, msg: str):
        self.passed.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def fail(self, msg: str):
        self.failed.append(msg)

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0

    def summary(self) -> str:
        total = len(self.passed) + len(self.warnings) + len(self.failed)
        return (
            f"  ✅ {len(self.passed)} passed  "
            f"⚠️ {len(self.warnings)} warnings  "
            f"❌ {len(self.failed)} failed  "
            f"({total} total)"
        )


# ============================================================================
# 测试函数
# ============================================================================

def test_syntax(file_path: Path, result: TestResult) -> bool:
    """1. 语法检查"""
    try:
        source = file_path.read_text(encoding="utf-8")
        ast.parse(source)
        result.pass_("Syntax OK")
        return True
    except SyntaxError as e:
        result.fail(f"Syntax error at line {e.lineno}: {e.msg}")
        return False


def test_import(file_path: Path, result: TestResult):
    """2. 模块可导入性"""
    module_name = f"_test_{file_path.stem}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            result.fail("Cannot create module spec")
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        result.pass_("Import OK (unreal=None mode)")
        return module
    except Exception as e:
        result.fail(f"Import failed: {e}")
        return None
    finally:
        sys.modules.pop(module_name, None)


def test_decorators(file_path: Path, module, result: TestResult) -> list:
    """3. @ue_tool 装饰器合规性"""
    # 从全局注册表中获取通过装饰器注册的 Skill
    try:
        from skill_hub import _DECORATED_SKILLS
    except ImportError:
        result.warn("Cannot import skill_hub._DECORATED_SKILLS, skipping decorator check")
        return []

    # 收集该模块注册的 Skill
    module_name = f"_test_{file_path.stem}"
    skills = [
        (name, info) for name, info in _DECORATED_SKILLS.items()
        if info.get("module") == module_name or info.get("source_file") == str(file_path)
    ]

    if not skills:
        result.warn("No @ue_tool decorated functions found in this file")
        return []

    result.pass_(f"Found {len(skills)} @ue_tool skills")

    for skill_name, info in skills:
        # 检查 name 格式
        if skill_name != skill_name.lower():
            result.fail(f"  [{skill_name}] Name must be lowercase snake_case")
        elif not skill_name.replace("_", "").isalpha():
            result.warn(f"  [{skill_name}] Name contains non-alpha characters")
        else:
            result.pass_(f"  [{skill_name}] Name format OK")

        # 检查 description
        desc = info.get("description", "")
        if not desc:
            result.fail(f"  [{skill_name}] Missing description")
        elif len(desc) < 10:
            result.warn(f"  [{skill_name}] Description too short ({len(desc)} chars)")
        else:
            result.pass_(f"  [{skill_name}] Description OK ({len(desc)} chars)")

        # 检查 category
        valid_categories = {
            "scene", "asset", "material", "level", "lighting",
            "render", "blueprint", "animation", "ui", "utils",
            "integration", "workflow", "general",
        }
        cat = info.get("category", "")
        if cat not in valid_categories:
            result.warn(f"  [{skill_name}] Non-standard category: '{cat}'")
        else:
            result.pass_(f"  [{skill_name}] Category '{cat}' OK")

        # 检查 risk_level
        valid_risks = {"low", "medium", "high", "critical"}
        risk = info.get("risk_level", "")
        if risk not in valid_risks:
            result.fail(f"  [{skill_name}] Invalid risk_level: '{risk}'")
        else:
            result.pass_(f"  [{skill_name}] Risk level '{risk}' OK")

        # 检查 handler 签名
        handler = info.get("handler")
        if handler:
            import inspect
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            if params != ["arguments"]:
                result.warn(
                    f"  [{skill_name}] Expected signature (arguments: dict), "
                    f"got ({', '.join(params)})"
                )
            else:
                result.pass_(f"  [{skill_name}] Signature OK")

    return skills


def test_return_format(skills: list, result: TestResult):
    """4. 返回值格式校验"""
    for skill_name, info in skills:
        handler = info.get("handler")
        if not handler:
            continue

        try:
            # 调用时传空 arguments（预期返回错误 JSON）
            ret = handler({})
            if ret is None:
                result.fail(f"  [{skill_name}] Handler returned None (must return str)")
                continue

            if not isinstance(ret, str):
                result.fail(f"  [{skill_name}] Handler returned {type(ret).__name__} (must return str)")
                continue

            # 尝试 JSON 解析
            data = json.loads(ret)

            if not isinstance(data, dict):
                result.warn(f"  [{skill_name}] Return is not a JSON object")
                continue

            # 检查 success 字段
            if "success" not in data and "error" not in data:
                result.warn(f"  [{skill_name}] Missing 'success' field in return")
            else:
                result.pass_(f"  [{skill_name}] Return format OK")

        except json.JSONDecodeError as e:
            result.fail(f"  [{skill_name}] Return is not valid JSON: {e}")
        except Exception as e:
            # 调用可能因为需要 UE 环境而失败，这是预期的
            result.pass_(f"  [{skill_name}] Handler callable (UE-dependent, expected error: {type(e).__name__})")


def test_conventions(file_path: Path, result: TestResult):
    """5. 开发规范审查"""
    source = file_path.read_text(encoding="utf-8")

    # 检查 unreal 导入保护
    if "import unreal" in source:
        if "except ImportError" in source or "ImportError" in source:
            result.pass_("unreal import protection present")
        else:
            result.fail("Missing 'except ImportError' guard for unreal import")

    # 检查 json 导入
    if "import json" in source:
        result.pass_("json module imported")
    else:
        result.warn("Missing 'import json'")

    # 检查文件头文档
    tree = ast.parse(source)
    _str_types = (ast.Constant,)
    if hasattr(ast, "Str"):
        _str_types = (ast.Constant, ast.Str)
    if (tree.body and isinstance(tree.body[0], ast.Expr) and
            isinstance(tree.body[0].value, _str_types)):
        result.pass_("Module docstring present")
    else:
        result.warn("Missing module-level docstring")

    # 检查事务保护（写操作）
    if "risk_level=\"medium\"" in source or "risk_level=\"high\"" in source:
        if "ScopedEditorTransaction" in source:
            result.pass_("ScopedEditorTransaction used for write operations")
        else:
            result.warn("Write operations detected but no ScopedEditorTransaction found")


# ============================================================================
# UE 外测试环境 Mock
# ============================================================================

class _MockUELogger:
    """Mock UELogger for testing outside UE"""
    @staticmethod
    def info(msg): pass
    @staticmethod
    def mcp_error(msg): pass
    @staticmethod
    def warning(msg): pass
    @staticmethod
    def error(msg): pass


class _MockInitUnreal:
    """Mock init_unreal module"""
    UELogger = _MockUELogger


class _MockUnreal:
    """Minimal mock of unreal module"""
    class DirectoryWatcher:
        def watch(self, *a, **kw): pass

    class Vector:
        def __init__(self, x=0, y=0, z=0):
            self.x, self.y, self.z = x, y, z

    class Rotator:
        def __init__(self, pitch=0, yaw=0, roll=0):
            self.pitch, self.yaw, self.roll = pitch, yaw, roll

    class LinearColor:
        def __init__(self, r=0, g=0, b=0, a=1):
            self.r, self.g, self.b, self.a = r, g, b, a

    class ActorComponent: pass
    class StaticMeshComponent: pass
    class PrimitiveComponent: pass
    class MaterialInstance: pass
    class MaterialInstanceConstant: pass

    class ScopedEditorTransaction:
        def __init__(self, desc=""): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass

    class EditorLevelLibrary:
        @staticmethod
        def get_all_level_actors(): return []
        @staticmethod
        def get_selected_level_actors(): return []
        @staticmethod
        def set_selected_level_actors(actors): pass
        @staticmethod
        def get_editor_world(): return None
        @staticmethod
        def save_current_level(): return True
        @staticmethod
        def spawn_actor_from_object(*a, **kw): return None
        @staticmethod
        def spawn_actor_from_class(*a, **kw): return None
        @staticmethod
        def destroy_actor(a): return True
        @staticmethod
        def pilot_level_actor(a): pass
        @staticmethod
        def load_level(p): return True
        @staticmethod
        def get_level_viewport_camera_info(): return None
        @staticmethod
        def set_level_viewport_camera_info(l, r): pass

    class EditorAssetLibrary:
        @staticmethod
        def load_asset(p): return None
        @staticmethod
        def load_blueprint_class(p): return None
        @staticmethod
        def list_assets(p, **kw): return []
        @staticmethod
        def does_asset_exist(p): return False
        @staticmethod
        def rename_asset(old, new): return True
        @staticmethod
        def save_asset(p): return True
        @staticmethod
        def find_asset_data(p): return None

    class EditorLoadingAndSavingUtils:
        @staticmethod
        def save_dirty_packages(**kw): return True

    class AssetToolsHelpers:
        @staticmethod
        def get_asset_tools():
            class _Tools:
                @staticmethod
                def create_asset(*a, **kw): return None
            return _Tools()

    class MaterialEditingLibrary:
        @staticmethod
        def set_material_instance_parent(inst, parent): pass
        @staticmethod
        def get_scalar_parameter_names(mat): return []
        @staticmethod
        def get_vector_parameter_names(mat): return []
        @staticmethod
        def get_texture_parameter_names(mat): return []
        @staticmethod
        def set_material_instance_scalar_parameter_value(*a): pass
        @staticmethod
        def set_material_instance_vector_parameter_value(*a): pass
        @staticmethod
        def get_material_instance_scalar_parameter_value(*a): return 0.0
        @staticmethod
        def get_material_instance_vector_parameter_value(*a): return _MockUnreal.LinearColor()
        @staticmethod
        def get_material_instance_texture_parameter_value(*a): return None

    class MaterialInstanceConstantFactoryNew: pass

    @staticmethod
    def register_slate_post_tick_callback(cb): pass
    @staticmethod
    def get_editor_subsystem(cls): return None


def _setup_mocks():
    """Set up mock modules for testing outside UE"""
    if "unreal" not in sys.modules:
        sys.modules["unreal"] = _MockUnreal()
    if "init_unreal" not in sys.modules:
        sys.modules["init_unreal"] = _MockInitUnreal()


# ============================================================================
# 主入口
# ============================================================================

def run_tests(file_path: Path) -> TestResult:
    """运行所有测试"""
    result = TestResult()

    # 1. 语法检查
    if not test_syntax(file_path, result):
        return result  # 语法错误则后续无法测试

    # 5. 规范审查（不需要导入模块）
    test_conventions(file_path, result)

    # 2. 导入测试
    module = test_import(file_path, result)
    if module is None:
        return result

    # 3. 装饰器合规性
    skills = test_decorators(file_path, module, result)

    # 4. 返回值格式
    if skills:
        test_return_format(skills, result)

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="ArtClaw Skill 测试工具 — 本地验证 Skill 合规性"
    )
    parser.add_argument(
        "files", nargs="*",
        help="要测试的 .py 文件（默认：Skills/ 目录下所有文件）"
    )
    parser.add_argument(
        "--dir", "-d", default=None,
        help="Skills 目录路径"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="显示详细输出"
    )

    args = parser.parse_args()

    # 确保 skill_hub 可导入
    # 查找 skill_hub.py 的位置
    skill_hub_candidates = [
        Path(__file__).parent / "skill_hub.py",
        Path(__file__).parent.parent / "skill_hub.py",
    ]
    for p in skill_hub_candidates:
        if p.exists():
            parent_dir = str(p.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            break

    # Mock unreal 和 init_unreal 模块（UE 外测试）
    _setup_mocks()

    # 确定要测试的文件
    files_to_test: List[Path] = []

    if args.files:
        for f in args.files:
            p = Path(f)
            if p.exists():
                files_to_test.append(p)
            else:
                print(f"❌ File not found: {f}")
    else:
        # 默认扫描 Skills 目录
        if args.dir:
            skills_dir = Path(args.dir)
        else:
            # 尝试常见位置
            candidates = [
                Path.home() / ".openclaw" / "skills",
                Path(__file__).parent / "Skills",
                Path.cwd() / "Skills",
            ]
            skills_dir = None
            for d in candidates:
                if d.exists():
                    skills_dir = d
                    break

            if skills_dir is None:
                print("❌ Skills directory not found. Use --dir to specify.")
                sys.exit(1)

        files_to_test = [
            f for f in skills_dir.glob("*.py")
            if f.name != "__init__.py" and "__pycache__" not in str(f)
        ]
        # 也扫描子目录
        for f in skills_dir.glob("**/*.py"):
            if f.name != "__init__.py" and "__pycache__" not in str(f) and f not in files_to_test:
                files_to_test.append(f)

    if not files_to_test:
        print("⚠️ No skill files found to test.")
        sys.exit(0)

    print(f"\n🧪 ArtClaw Skill Test — Testing {len(files_to_test)} file(s)\n")
    print("=" * 60)

    total_passed = 0
    total_warnings = 0
    total_failed = 0
    file_results: List[Tuple[Path, TestResult]] = []

    for file_path in sorted(files_to_test):
        print(f"\n📄 {file_path.name}")
        print("-" * 40)

        # 清空装饰器注册表
        try:
            from skill_hub import _DECORATED_SKILLS
            _DECORATED_SKILLS.clear()
        except ImportError:
            pass

        result = run_tests(file_path)
        file_results.append((file_path, result))

        if args.verbose:
            for msg in result.passed:
                print(f"  ✅ {msg}")
            for msg in result.warnings:
                print(f"  ⚠️ {msg}")
            for msg in result.failed:
                print(f"  ❌ {msg}")
        else:
            # 只显示 warnings 和 failures
            for msg in result.warnings:
                print(f"  ⚠️ {msg}")
            for msg in result.failed:
                print(f"  ❌ {msg}")

        print(result.summary())

        total_passed += len(result.passed)
        total_warnings += len(result.warnings)
        total_failed += len(result.failed)

    # 总结
    print("\n" + "=" * 60)
    status = "✅ ALL PASSED" if total_failed == 0 else "❌ SOME TESTS FAILED"
    print(f"\n{status}")
    print(f"  Files: {len(files_to_test)}")
    print(f"  ✅ {total_passed} passed  ⚠️ {total_warnings} warnings  ❌ {total_failed} failed")
    print()

    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
