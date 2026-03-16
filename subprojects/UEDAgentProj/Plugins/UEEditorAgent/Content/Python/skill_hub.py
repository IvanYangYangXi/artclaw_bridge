"""
skill_hub.py - Skill 热加载器与统一管理中心
=============================================

阶段 3.1: Dynamic Skill Hub

宪法约束:
  - 系统架构设计 §1.3: Skill Hub 统一加载/卸载/热重载所有 Skill
  - 系统架构设计 §1.5: Core Tool / Skill 二层体系
  - 核心机制 §1.2: @ue_agent.tool 装饰器 + 自动发现
  - 核心机制 §2: importlib.reload + DirectoryWatcher
  - 开发路线图 §3.1: Skills/ 目录实时文件监控

设计说明:
  - Core Tool 在各 tools/*.py 中硬编码注册（Phase 0~2 已完成）
  - Skill 在 Skills/ 目录下通过 @ue_agent.tool 装饰器声明
  - Skill Hub 负责扫描、注册、热重载、通知客户端
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import unreal

from init_unreal import UELogger

# ============================================================================
# 1. @ue_agent.tool 装饰器
# ============================================================================

# 全局注册表：所有通过装饰器声明的 Skill
_DECORATED_SKILLS: Dict[str, dict] = {}


def tool(
    name: Optional[str] = None,
    description: str = "",
    category: str = "general",
    risk_level: str = "low",
):
    """
    Skill 装饰器。将 Python 函数标记为 MCP Tool。

    用法:
        @ue_agent.tool(name="batch_rename", description="Batch rename actors")
        def batch_rename(arguments: dict) -> str:
            ...

    宪法约束:
      - 核心机制 §1.2: @ue_agent.tool 装饰器 + 自动发现
      - 系统架构设计 §1.5.1: Skill 注册方式

    Args:
        name: Tool 名称。默认使用函数名。
        description: Tool 描述，AI 可见。默认从 docstring 提取。
        category: 分类标签 (general, material, lighting, layout, asset, ...)
        risk_level: 风险级别 (low, medium, high, critical)
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or (inspect.getdoc(func) or "").split("\n")[0]

        # 尝试从 type hints 生成 input schema
        input_schema = _generate_schema_from_hints(func)

        # 注册到全局表
        _DECORATED_SKILLS[tool_name] = {
            "name": tool_name,
            "description": tool_desc,
            "category": category,
            "risk_level": risk_level,
            "input_schema": input_schema,
            "handler": func,
            "module": func.__module__,
            "source_file": inspect.getfile(func) if hasattr(func, "__code__") else None,
        }

        # 在函数上标记元数据
        func._ue_agent_tool = True
        func._ue_agent_tool_name = tool_name
        return func

    return decorator


def _generate_schema_from_hints(func: Callable) -> dict:
    """
    从函数签名的 type hints 生成 JSON Schema。

    宪法约束:
      - 核心机制 §1: inspect 提取签名 + docstring → Schema 转换
    """
    sig = inspect.signature(func)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls", "arguments"):
            continue

        prop: dict = {}
        annotation = param.annotation

        if annotation == str:
            prop["type"] = "string"
        elif annotation == int:
            prop["type"] = "integer"
        elif annotation == float:
            prop["type"] = "number"
        elif annotation == bool:
            prop["type"] = "boolean"
        elif annotation == list or annotation == List:
            prop["type"] = "array"
        elif annotation == dict or annotation == Dict:
            prop["type"] = "object"
        else:
            prop["type"] = "string"  # fallback

        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            prop["default"] = param.default

        properties[param_name] = prop

    schema = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


# ============================================================================
# 2. Skill Hub 核心
# ============================================================================

class SkillHub:
    """
    Skill 管理中心。

    职责:
      - 扫描 Skills/ 目录发现 @ue_agent.tool 装饰的函数
      - 注册到 MCP Server
      - 监控文件变更，热重载
      - 变更后通知所有 MCP 客户端

    宪法约束:
      - 系统架构设计 §1.3: Skill Hub (统一管理)
      - 系统架构设计 §1.5.4: Skill Hub 扫描与注册流程
    """

    def __init__(self, mcp_server, skills_dir: Optional[str] = None):
        self._mcp_server = mcp_server
        self._loaded_modules: Dict[str, Any] = {}  # module_name -> module object
        self._registered_skills: Dict[str, dict] = {}  # skill_name -> info
        self._watcher_handle = None

        # 确定 Skills 目录
        if skills_dir:
            self._skills_dir = Path(skills_dir)
        else:
            # 默认: 插件的 Content/Python/Skills/
            plugin_python_dir = Path(__file__).parent
            self._skills_dir = plugin_python_dir / "Skills"

        # 确保目录存在
        self._skills_dir.mkdir(parents=True, exist_ok=True)

        # 将 Skills 目录加入 sys.path
        skills_str = str(self._skills_dir)
        if skills_str not in sys.path:
            sys.path.insert(0, skills_str)

        UELogger.info(f"SkillHub initialized: {self._skills_dir}")

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def scan_and_register(self) -> int:
        """
        扫描 Skills/ 目录，发现并注册所有 Skill。

        Returns:
            注册的 Skill 数量

        宪法约束:
          - 系统架构设计 §1.5.4: 扫描 → 发现 → 注册 → 通知
        """
        UELogger.info(f"Scanning Skills directory: {self._skills_dir}")

        # 清空之前的装饰器注册表（保留 Core Tool 的注册）
        _DECORATED_SKILLS.clear()

        # 查找所有 .py 文件
        py_files = list(self._skills_dir.glob("*.py"))
        py_files.extend(self._skills_dir.glob("**/*.py"))
        # 去重
        py_files = list(set(py_files))

        # 排除 __init__.py 和 __pycache__
        py_files = [
            f for f in py_files
            if f.name != "__init__.py" and "__pycache__" not in str(f)
        ]

        if not py_files:
            UELogger.info("No skill files found in Skills/ directory")
            self._create_example_skill()
            # 重新扫描
            py_files = list(self._skills_dir.glob("*.py"))
            py_files = [f for f in py_files if f.name != "__init__.py"]

        # 加载每个模块
        loaded_count = 0
        for py_file in py_files:
            try:
                self._load_skill_module(py_file)
                loaded_count += 1
            except Exception as e:
                UELogger.mcp_error(f"Failed to load skill {py_file.name}: {e}")
                traceback.print_exc()

        # 将装饰器注册表中的 Skill 注册到 MCP Server
        new_skills = 0
        for skill_name, info in _DECORATED_SKILLS.items():
            if skill_name not in self._registered_skills:
                self._register_skill_to_mcp(skill_name, info)
                new_skills += 1

        UELogger.info(
            f"SkillHub: loaded {loaded_count} modules, "
            f"registered {new_skills} new skills "
            f"(total: {len(self._registered_skills)})"
        )

        return new_skills

    def start_watching(self) -> None:
        """
        启动文件监控，检测 Skills/ 目录变更。

        宪法约束:
          - 核心机制 §2: unreal.DirectoryWatcher 监控 Skills 文件夹
          - 开发路线图 §3.1: 实时文件监控
        """
        try:
            # 使用 UE 的 DirectoryWatcher
            dir_watcher = unreal.DirectoryWatcher()
            self._watcher_handle = dir_watcher.watch(
                str(self._skills_dir),
                self._on_directory_changed,
            )
            UELogger.info(f"SkillHub: watching {self._skills_dir}")
        except Exception as e:
            # fallback: 使用定时轮询
            UELogger.mcp_error(
                f"DirectoryWatcher unavailable ({e}), using polling fallback"
            )
            self._start_polling_watcher()

    def stop_watching(self) -> None:
        """停止文件监控"""
        self._watcher_handle = None
        UELogger.info("SkillHub: stopped watching")

    def get_skill_list(self) -> List[dict]:
        """
        获取已注册的所有 Skill 信息（不含 handler）。

        用于 unreal://skills/list Resource。
        """
        return [
            {
                "name": info["name"],
                "description": info.get("description", ""),
                "category": info.get("category", "general"),
                "risk_level": info.get("risk_level", "low"),
                "source_file": info.get("source_file", ""),
            }
            for info in self._registered_skills.values()
        ]

    def reload_skill(self, module_name: str) -> bool:
        """
        热重载指定模块。

        宪法约束:
          - 核心机制 §2: importlib.reload()
        """
        if module_name not in self._loaded_modules:
            UELogger.mcp_error(f"Module not loaded: {module_name}")
            return False

        try:
            old_module = self._loaded_modules[module_name]

            # 记录该模块之前注册的 Skill 名称
            old_skills = [
                name for name, info in self._registered_skills.items()
                if info.get("module") == module_name
            ]

            # 从 MCP Server 注销旧 Skill
            for skill_name in old_skills:
                self._mcp_server.unregister_tool(skill_name)
                del self._registered_skills[skill_name]

            # 清除装饰器注册表中该模块的条目
            to_remove = [
                k for k, v in _DECORATED_SKILLS.items()
                if v.get("module") == module_name
            ]
            for k in to_remove:
                del _DECORATED_SKILLS[k]

            # 重新加载模块
            importlib.reload(old_module)
            self._loaded_modules[module_name] = old_module

            # 注册新发现的 Skill
            new_skills = [
                (k, v) for k, v in _DECORATED_SKILLS.items()
                if v.get("module") == module_name
            ]
            for skill_name, info in new_skills:
                self._register_skill_to_mcp(skill_name, info)

            UELogger.info(
                f"SkillHub: reloaded {module_name} "
                f"(-{len(old_skills)} +{len(new_skills)} skills)"
            )

            # 通知所有客户端
            self._notify_tools_changed(module_name)

            return True

        except Exception as e:
            UELogger.mcp_error(f"Failed to reload {module_name}: {e}")
            traceback.print_exc()
            return False

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _load_skill_module(self, py_file: Path) -> None:
        """加载一个 Skill Python 文件为模块"""
        module_name = f"ue_skill_{py_file.stem}"

        spec = importlib.util.spec_from_file_location(module_name, str(py_file))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {py_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        self._loaded_modules[module_name] = module
        UELogger.info(f"  Loaded skill module: {py_file.name}")

    def _register_skill_to_mcp(self, skill_name: str, info: dict) -> None:
        """将 Skill 注册到 MCP Server"""
        self._mcp_server.register_tool(
            name=skill_name,
            description=info["description"],
            input_schema=info["input_schema"],
            handler=info["handler"],
        )
        self._registered_skills[skill_name] = info

    def _on_directory_changed(self, changes):
        """DirectoryWatcher 回调"""
        for change in changes:
            file_path = Path(str(change.filename))
            if file_path.suffix != ".py":
                continue

            UELogger.info(f"SkillHub: detected change in {file_path.name}")

            # 找到对应的模块名
            module_name = f"ue_skill_{file_path.stem}"
            if module_name in self._loaded_modules:
                self.reload_skill(module_name)
            else:
                # 新文件，加载并注册
                try:
                    self._load_skill_module(file_path)
                    new_skills = [
                        (k, v) for k, v in _DECORATED_SKILLS.items()
                        if v.get("module") == module_name
                    ]
                    for name, info in new_skills:
                        self._register_skill_to_mcp(name, info)

                    self._notify_tools_changed(module_name)
                except Exception as e:
                    UELogger.mcp_error(f"Failed to load new skill {file_path.name}: {e}")

    def _start_polling_watcher(self):
        """轮询方式的文件监控（fallback）"""
        self._file_mtimes: Dict[str, float] = {}

        # 记录初始状态
        for py_file in self._skills_dir.glob("*.py"):
            self._file_mtimes[str(py_file)] = py_file.stat().st_mtime

        # 注册 Slate tick 回调做定期检查
        self._poll_counter = 0
        self._poll_interval = 60  # 每 60 tick 检查一次 (约 1 秒)

        def _poll_tick(delta_time):
            self._poll_counter += 1
            if self._poll_counter < self._poll_interval:
                return
            self._poll_counter = 0
            self._check_file_changes()

        unreal.register_slate_post_tick_callback(_poll_tick)
        UELogger.info("SkillHub: using polling watcher (1s interval)")

    def _check_file_changes(self):
        """检查文件变更"""
        current_files = {}
        for py_file in self._skills_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            current_files[str(py_file)] = py_file.stat().st_mtime

        # 检查修改和新增
        for fpath, mtime in current_files.items():
            old_mtime = self._file_mtimes.get(fpath)
            if old_mtime is None or mtime > old_mtime:
                file_path = Path(fpath)
                module_name = f"ue_skill_{file_path.stem}"
                UELogger.info(f"SkillHub: file changed: {file_path.name}")

                if module_name in self._loaded_modules:
                    self.reload_skill(module_name)
                else:
                    try:
                        self._load_skill_module(file_path)
                        new_skills = [
                            (k, v) for k, v in _DECORATED_SKILLS.items()
                            if v.get("module") == module_name
                        ]
                        for name, info in new_skills:
                            self._register_skill_to_mcp(name, info)
                        self._notify_tools_changed(module_name)
                    except Exception as e:
                        UELogger.mcp_error(f"Failed to load {file_path.name}: {e}")

        self._file_mtimes = current_files

    def _notify_tools_changed(self, source: str):
        """通知所有客户端工具列表已变更"""
        import asyncio

        async def _send():
            await self._mcp_server.broadcast_notification(
                "notifications/tools/list_changed",
                {"source": source, "skill_count": len(self._registered_skills)},
            )

        loop = self._mcp_server._loop
        if loop and loop.is_running():
            asyncio.ensure_future(_send(), loop=loop)

    def _create_example_skill(self):
        """在 Skills/ 目录创建示例 Skill 文件"""
        example_path = self._skills_dir / "example_skills.py"
        if example_path.exists():
            return

        example_code = '''"""
Example Skills - UE Editor Agent
================================

示例 Skill 文件。将 .py 文件放入 Skills/ 目录即可自动发现。
使用 @ue_agent.tool 装饰器声明 MCP Tool。

保存文件后 Skill Hub 会自动热重载，无需重启 UE。
"""

# 导入装饰器 — 从 skill_hub 模块导入
from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None  # 允许在 UE 外部测试


@ue_tool(
    name="list_actor_classes",
    description="List all unique actor classes in the current level. "
                "Useful for understanding what types of objects exist.",
    category="level",
    risk_level="low",
)
def list_actor_classes(arguments: dict) -> str:
    """统计当前关卡中所有 Actor 的类别分布"""
    if unreal is None:
        return json.dumps({"error": "Not running in UE"})

    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    class_counts = {}
    for actor in actors:
        cls_name = actor.get_class().get_name()
        class_counts[cls_name] = class_counts.get(cls_name, 0) + 1

    # 按数量排序
    sorted_classes = sorted(class_counts.items(), key=lambda x: -x[1])

    return json.dumps({
        "total_actors": len(actors),
        "unique_classes": len(class_counts),
        "classes": [
            {"class": cls, "count": cnt}
            for cls, cnt in sorted_classes[:50]
        ],
    })


@ue_tool(
    name="find_actors_by_name",
    description="Find actors in the level by name pattern (case-insensitive substring match). "
                "Returns actor names, classes, and locations.",
    category="level",
    risk_level="low",
)
def find_actors_by_name(arguments: dict) -> str:
    """按名称模式搜索 Actor"""
    if unreal is None:
        return json.dumps({"error": "Not running in UE"})

    pattern = arguments.get("pattern", "").lower()
    if not pattern:
        return json.dumps({"error": "pattern is required"})

    limit = arguments.get("limit", 20)

    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    results = []

    for actor in actors:
        label = str(actor.get_actor_label())
        if pattern in label.lower():
            loc = actor.get_actor_location()
            results.append({
                "name": label,
                "class": actor.get_class().get_name(),
                "location": {"x": loc.x, "y": loc.y, "z": loc.z},
            })
            if len(results) >= limit:
                break

    return json.dumps({
        "pattern": pattern,
        "found": len(results),
        "actors": results,
    })


@ue_tool(
    name="get_level_stats",
    description="Get comprehensive statistics about the current level: "
                "actor counts, bounding box, memory estimates.",
    category="level",
    risk_level="low",
)
def get_level_stats(arguments: dict) -> str:
    """获取当前关卡的详细统计信息"""
    if unreal is None:
        return json.dumps({"error": "Not running in UE"})

    actors = unreal.EditorLevelLibrary.get_all_level_actors()

    stats = {
        "total_actors": len(actors),
        "static_meshes": 0,
        "lights": 0,
        "cameras": 0,
        "blueprints": 0,
        "other": 0,
    }

    for actor in actors:
        cls = actor.get_class().get_name()
        if "StaticMeshActor" in cls:
            stats["static_meshes"] += 1
        elif "Light" in cls:
            stats["lights"] += 1
        elif "Camera" in cls:
            stats["cameras"] += 1
        elif "Blueprint" in cls or cls.endswith("_C"):
            stats["blueprints"] += 1
        else:
            stats["other"] += 1

    return json.dumps(stats)
'''
        example_path.write_text(example_code, encoding="utf-8")
        UELogger.info(f"SkillHub: created example skill at {example_path}")


# ============================================================================
# 3. 模块级便捷接口
# ============================================================================

# 全局单例
_skill_hub_instance: Optional[SkillHub] = None


def init_skill_hub(mcp_server, skills_dir: Optional[str] = None) -> SkillHub:
    """
    初始化 Skill Hub 单例。应在 MCP Server 启动后调用。

    Returns:
        SkillHub 实例
    """
    global _skill_hub_instance
    _skill_hub_instance = SkillHub(mcp_server, skills_dir)
    _skill_hub_instance.scan_and_register()
    _skill_hub_instance.start_watching()

    # 注册 skills/list Resource
    mcp_server.register_resource(
        uri="unreal://skills/list",
        name="Available Skills",
        description="List all registered skills (Core Tools + dynamic Skills)",
        handler=lambda: json.dumps({
            "core_tools": len(mcp_server._tools) - len(_skill_hub_instance._registered_skills),
            "skills": _skill_hub_instance.get_skill_list(),
            "total": len(mcp_server._tools),
        }),
    ) if hasattr(mcp_server, 'register_resource') else None

    return _skill_hub_instance


def get_skill_hub() -> Optional[SkillHub]:
    """获取 Skill Hub 单例"""
    return _skill_hub_instance
