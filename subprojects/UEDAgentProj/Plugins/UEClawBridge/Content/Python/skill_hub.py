"""
skill_hub.py - Skill 热加载器与统一管理中心 (Phase B Enhanced)
================================================================

阶段 3.1 + Phase B: Dynamic Skill Hub with Layered Loading

Phase B 增强:
  B1: 分层加载机制 (00_official/01_team/02_user/99_custom)
  B2: manifest.json 解析与验证
  B3: 软件版本匹配
  B4: Skill 冲突检测

宪法约束:
  - 系统架构设计 §1.3: Skill Hub 统一加载/卸载/热重载所有 Skill
  - 系统架构设计 §1.5: Core Tool / Skill 二层体系
  - 核心机制 §1.2: @ue_agent.tool 装饰器 + 自动发现
  - 核心机制 §2: importlib.reload + DirectoryWatcher
  - 开发路线图 §3.1: Skills/ 目录实时文件监控
  - skill-management-system.md §5: 分层加载优先级
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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import unreal

from init_unreal import UELogger

# Phase B 模块
from skill_manifest import (
    SkillManifest, parse_manifest, validate_manifest, scan_skill_dir,
    ManifestValidationError,
)
from skill_version import (
    matches_software_version, select_best_match, version_distance,
)
from skill_conflict import (
    ConflictDetector, ConflictReport, SkillConflict, ToolConflict,
    LAYER_PRIORITY, LAYER_DISPLAY,
)

# ============================================================================
# 1.5 SKILL.md Frontmatter 解析 + AST Tool 扫描
# ============================================================================

def _parse_yaml_frontmatter(content: str) -> Optional[dict]:
    """从 SKILL.md 内容中解析 YAML frontmatter。

    支持标准 '---' 分隔的 frontmatter 块。
    仅做简单 key: value 解析，不依赖 PyYAML（UE Python 环境不一定有）。
    支持多行值（用 > 或 | 标记）。
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None

    # 找到结束的 ---
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx < 0:
        return None

    fm_lines = lines[1:end_idx]

    result: dict = {}
    current_key = None
    current_value_lines: list = []
    is_multiline = False

    for line in fm_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # 检查是否是新的 key: value 行
        if ":" in line and not line[0].isspace():
            # 保存之前的多行值
            if current_key and is_multiline:
                result[current_key] = " ".join(current_value_lines).strip()

            colon_idx = line.index(":")
            current_key = line[:colon_idx].strip()
            raw_value = line[colon_idx + 1:].strip()

            if raw_value in (">", "|", ">-", "|-"):
                # 多行值标记
                is_multiline = True
                current_value_lines = []
            elif raw_value.startswith('"') and raw_value.endswith('"'):
                result[current_key] = raw_value[1:-1]
                is_multiline = False
            elif raw_value.startswith("'") and raw_value.endswith("'"):
                result[current_key] = raw_value[1:-1]
                is_multiline = False
            elif raw_value:
                result[current_key] = raw_value
                is_multiline = False
            else:
                # 空值，可能是 dict 或后续缩进的多行
                is_multiline = True
                current_value_lines = []
        elif current_key and is_multiline:
            current_value_lines.append(stripped)

    # 处理最后一个多行值
    if current_key and is_multiline and current_value_lines:
        result[current_key] = " ".join(current_value_lines).strip()

    return result


def _scan_ue_tools_ast(init_py: Path) -> List[dict]:
    """通过 AST 静态分析 __init__.py 发现 @ue_tool 装饰器声明的工具。

    不执行代码，仅解析语法树提取 name 和 description。
    """
    try:
        source = init_py.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(init_py))
    except Exception:
        return []

    tools = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for deco in node.decorator_list:
            # 匹配 @ue_tool(...) 或 @tool(...)
            if isinstance(deco, ast.Call):
                func_name = ""
                if isinstance(deco.func, ast.Name):
                    func_name = deco.func.id
                elif isinstance(deco.func, ast.Attribute):
                    func_name = deco.func.attr
                if func_name not in ("ue_tool", "tool"):
                    continue

                # 提取 keyword arguments
                tool_name = node.name
                tool_desc = ""
                for kw in deco.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                        tool_name = kw.value.value
                    elif kw.arg == "description" and isinstance(kw.value, ast.Constant):
                        tool_desc = kw.value.value

                tools.append({"name": tool_name, "description": tool_desc})
    return tools


# ============================================================================
# ============================================================================
# 2. @ue_agent.tool 装饰器
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
    """从函数签名的 type hints 生成 JSON Schema。"""
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
# 2. 分层加载配置
# ============================================================================

# 层级目录名称 → 来源标识
# v2.6: 去掉数字前缀，改用语义目录名
LAYER_DIRS = {
    "official": "official",
    "marketplace": "marketplace",
    "user": "user",
    "custom": "custom",
}

# 向后兼容：旧目录名映射到新目录名
_LEGACY_LAYER_MAP = {
    "00_official": "official",
    "01_team": "marketplace",
    "02_user": "user",
    "99_custom": "custom",
}

# 层级加载顺序（优先级从高到低）
LAYER_ORDER = ["official", "marketplace", "user", "custom"]


# ============================================================================
# 3. Skill Hub 核心（Phase B 增强版）
# ============================================================================

# Skill 改名兼容映射：旧名 → 新名 (v2.6 改名迁移)
_NAME_ALIAS_MAP = {
    "artclaw_material": "ue54_material_node_edit",
    "ue54_artclaw_material": "ue54_material_node_edit",
    "get_material_nodes": "ue54_get_material_nodes",
    "generate_material_documentation": "ue54_generate_material_documentation",
}


class SkillHub:
    """
    Skill 管理中心 (Phase B Enhanced)。

    职责:
      - 分层扫描 Skills/ 目录 (official → marketplace → user → custom)
      - 支持 DCC 子目录 (official/unreal/, official/universal/ 等)
      - 解析并验证每个 Skill 的 manifest.json
      - 检测软件版本兼容性
      - 检测 Skill/Tool 冲突并按优先级解决
      - 注册到内部字典（v2.6: 仅 legacy 模式注册 MCP）
      - 监控文件变更，热重载
      - 变更后通知所有 MCP 客户端

    宪法约束:
      - 系统架构设计 §1.3: Skill Hub (统一管理)
      - 系统架构设计 §1.5.4: Skill Hub 扫描与注册流程
      - skill-management-system.md §5: 分层加载
      - Skill与MCP管理面板设计 §9: Phase 1 目录重构
    """

    def __init__(self, mcp_server, skills_dir: Optional[str] = None):
        self._mcp_server = mcp_server
        self._loaded_modules: Dict[str, Any] = {}  # module_name -> module object
        self._registered_skills: Dict[str, dict] = {}  # skill_name -> info
        self._watcher_handle = None

        # Phase B: 增强状态
        self._manifests: Dict[str, SkillManifest] = {}  # skill_name -> manifest
        self._all_manifests: List[SkillManifest] = []  # 所有发现的 manifest (含冲突)
        self._conflict_report: Optional[ConflictReport] = None
        self._disabled_skills: Set[str] = self._load_disabled_skills()
        self._conflict_detector = ConflictDetector(self._disabled_skills)

        # 软件环境信息
        self._current_software = "unreal_engine"
        self._current_version = self._detect_ue_version()

        # MCP Tool 排除列表（v2.6 遗留，保留用于过滤旧装饰器声明）
        self._excluded_tools: Set[str] = set()

        # 确定 Skills 目录：配置驱动，统一使用平台已安装目录
        if skills_dir:
            self._skills_dir = Path(skills_dir)
        else:
            self._skills_dir = self._resolve_skills_dir()

        # 确保分层目录存在
        self._ensure_layer_dirs()

        # 将 Skills 目录加入 sys.path
        skills_str = str(self._skills_dir)
        if skills_str not in sys.path:
            sys.path.insert(0, skills_str)

        UELogger.info(f"SkillHub initialized: {self._skills_dir} (UE {self._current_version})")

    # ------------------------------------------------------------------
    # 初始化辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _load_disabled_skills() -> Set[str]:
        """从 ~/.artclaw/config.json 读取 disabled_skills 列表。

        启动时恢复上次禁用的 Skill，确保禁用状态跨重启持久化。
        """
        try:
            config_path = Path.home() / ".artclaw" / "config.json"
            if not config_path.exists():
                return set()
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            disabled = cfg.get("disabled_skills", [])
            if isinstance(disabled, list):
                result = set(disabled)
                if result:
                    UELogger.info(f"SkillHub: loaded {len(result)} disabled skill(s) from config: {sorted(result)}")
                return result
        except Exception as e:
            UELogger.info(f"SkillHub: failed to load disabled_skills from config: {e}")
        return set()

    def _detect_ue_version(self) -> str:
        """检测当前 UE 版本"""
        try:
            version = unreal.SystemLibrary.get_engine_version()
            # 格式如 "5.4.1-0+++UE5+Release-5.4" → 提取 "5.4.1"
            import re
            match = re.match(r"(\d+\.\d+(?:\.\d+)?)", str(version))
            if match:
                return match.group(1)
            return str(version)
        except Exception:
            return "5.4"  # fallback

    @staticmethod
    def _resolve_skills_dir() -> Path:
        """
        从 ~/.artclaw/config.json 读取已安装 Skill 目录。
        回退到平台默认值，最终回退到 ~/.openclaw/skills。
        """
        import json as _json
        config_path = Path.home() / ".artclaw" / "config.json"
        if config_path.exists():
            try:
                cfg = _json.loads(config_path.read_text(encoding="utf-8"))
                installed = cfg.get("skills", {}).get("installed_path", "")
                if installed:
                    return Path(os.path.expanduser(installed))
                platform_type = cfg.get("platform", {}).get("type", "openclaw")
                defaults = {
                    "openclaw": "~/.openclaw/skills",
                    "workbuddy": "~/.workbuddy/skills",
                    "claude": "~/.claude/skills",
                }
                return Path(os.path.expanduser(defaults.get(platform_type, "~/.openclaw/skills")))
            except Exception:
                pass
        return Path(os.path.expanduser("~/.openclaw/skills"))

    def _ensure_layer_dirs(self) -> None:
        """确保分层目录存在，并迁移旧目录名"""
        self._skills_dir.mkdir(parents=True, exist_ok=True)

        # 迁移旧目录名到新目录名（如 00_official → official）
        for old_name, new_name in _LEGACY_LAYER_MAP.items():
            old_path = self._skills_dir / old_name
            new_path = self._skills_dir / new_name
            if old_path.exists() and not new_path.exists():
                old_path.rename(new_path)
                UELogger.info(f"SkillHub: migrated layer dir {old_name} → {new_name}")
            elif old_path.exists() and new_path.exists():
                # 两个都存在：把旧目录内容合并到新目录
                import shutil
                for item in old_path.iterdir():
                    dest = new_path / item.name
                    if not dest.exists():
                        if item.is_dir():
                            shutil.copytree(str(item), str(dest))
                        else:
                            shutil.copy2(str(item), str(dest))
                shutil.rmtree(str(old_path))
                UELogger.info(f"SkillHub: merged {old_name} into {new_name}, removed {old_name}")

        for layer_dir_name in LAYER_DIRS.keys():
            layer_path = self._skills_dir / layer_dir_name
            layer_path.mkdir(exist_ok=True)
    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def scan_and_register(self, metadata_only: bool = False) -> int:
        """
        分层扫描 Skills/ 目录，发现、验证并注册所有 Skill。

        Phase B 增强流程:
          1. 按层级顺序扫描 00_official → 01_team → 02_user → 99_custom
          2. 解析每个 Skill 的 manifest.json
          3. 验证软件版本兼容性
          4. 检测冲突并按优先级解决
          5. 加载 Python 模块并注册到 MCP Server

        Args:
            metadata_only: 仅扫描 manifest 不加载 Python 模块（管理面板刷新用）

        Returns:
            注册的 Skill 数量
        """
        UELogger.info(f"SkillHub: scanning skills in {self._skills_dir}")

        # 清空之前的状态
        _DECORATED_SKILLS.clear()
        self._all_manifests.clear()
        self._manifests.clear()

        # 阶段 1a: 按层级扫描 (兼容旧分层目录结构)
        for layer_dir_name in LAYER_ORDER:
            layer_path = self._skills_dir / layer_dir_name
            layer_id = LAYER_DIRS[layer_dir_name]

            if not layer_path.exists():
                continue

            self._scan_layer(layer_path, layer_id)

        # 阶段 1b: 扁平扫描 (install.py 安装的扁平目录结构)
        self._scan_flat_skills()

        UELogger.info(
            f"SkillHub: discovered {len(self._all_manifests)} skill(s) across layers"
        )

        # 阶段 2: 冲突检测与解决
        self._conflict_report = self._conflict_detector.detect(self._all_manifests)
        if self._conflict_report.has_conflicts:
            UELogger.info(f"SkillHub: {self._conflict_report.summary()}")

        resolved = self._conflict_detector.resolve(self._all_manifests)

        # 阶段 3: 版本过滤
        compatible = []
        for m in resolved:
            if m.software == "universal" or m.software == self._current_software:
                if matches_software_version(m.software_version, self._current_version):
                    compatible.append(m)
                else:
                    UELogger.info(
                        f"SkillHub: skipping {m.name} "
                        f"(requires {m.software} {m.software_version.min_version or '*'}"
                        f"-{m.software_version.max_version or '*'}, "
                        f"current: {self._current_version})"
                    )
            else:
                UELogger.info(
                    f"SkillHub: skipping {m.name} "
                    f"(for {m.software}, current: {self._current_software})"
                )

        # 阶段 4: 加载 Python 模块并注册（metadata_only 模式跳过）
        if metadata_only:
            UELogger.info(
                f"SkillHub: metadata-only scan complete, "
                f"{len(self._all_manifests)} skill(s) discovered"
            )
            return len(self._all_manifests)

        new_skills = 0
        for manifest in compatible:
            try:
                self._load_and_register_skill(manifest)
                self._manifests[manifest.name] = manifest
                new_skills += 1
            except Exception as e:
                UELogger.mcp_error(
                    f"Failed to load skill {manifest.name}: {e}"
                )
                traceback.print_exc()

        UELogger.info(
            f"SkillHub: registered {new_skills} skills "
            f"(total tools: {len(self._registered_skills)})"
        )

        return new_skills

    def _scan_layer(self, layer_path: Path, layer_id: str) -> None:
        """
        扫描一个层级目录，查找所有 Skill 包。

        支持两种结构:
          1. 直接子目录: official/my_skill/ (manifest.json or SKILL.md)
          2. DCC 子目录: official/unreal/my_skill/, official/universal/my_skill/

        DCC 子目录名: universal, unreal, maya, max
        """
        if not layer_path.is_dir():
            return

        # 已知 DCC 子目录名
        DCC_SUBDIRS = {"universal", "unreal", "maya", "max"}

        for entry in sorted(layer_path.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith("_") or entry.name.startswith("."):
                continue

            has_manifest = (entry / "manifest.json").exists()
            has_skill_md = (entry / "SKILL.md").exists()

            if has_manifest or has_skill_md:
                # 直接是 Skill 包
                self._parse_and_collect(entry, layer_id)
            elif entry.name in DCC_SUBDIRS:
                # DCC 子目录：扫描其下的 Skill 包
                for sub_entry in sorted(entry.iterdir()):
                    if not sub_entry.is_dir():
                        continue
                    if sub_entry.name.startswith("_") or sub_entry.name.startswith("."):
                        continue
                    sub_has_manifest = (sub_entry / "manifest.json").exists()
                    sub_has_skill_md = (sub_entry / "SKILL.md").exists()
                    if sub_has_manifest or sub_has_skill_md:
                        self._parse_and_collect(sub_entry, layer_id)
            else:
                # 可能是 category 分组目录 (material/, scene/ 等)
                for sub_entry in sorted(entry.iterdir()):
                    if sub_entry.is_dir() and (
                        (sub_entry / "manifest.json").exists()
                        or (sub_entry / "SKILL.md").exists()
                    ):
                        self._parse_and_collect(sub_entry, layer_id)

    def _scan_flat_skills(self) -> None:
        """
        扫描 Skills 目录下直接存在的 Skill 包（扁平结构）。
        install.py 安装后的目录: skills_dir/skill_name/ (无层级子目录)
        跳过已知层级目录和 DCC 子目录名。
        """
        if not self._skills_dir.is_dir():
            return

        SKIP_DIRS = set(LAYER_DIRS.keys()) | set(_LEGACY_LAYER_MAP.keys()) | {
            "universal", "unreal", "maya", "max", "templates",
        }
        # 已收集的 Skill 名
        seen_names = {m.name for m in self._all_manifests}

        for entry in sorted(self._skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith("_") or entry.name.startswith("."):
                continue
            if entry.name in SKIP_DIRS:
                continue

            has_manifest = (entry / "manifest.json").exists()
            has_skill_md = (entry / "SKILL.md").exists()

            if (has_manifest or has_skill_md) and entry.name not in seen_names:
                self._parse_and_collect(entry, "installed")

    def _parse_and_collect(self, skill_dir: Path, layer_id: str) -> None:
        """解析一个 Skill 目录的 manifest 并收集。

        优先读取 manifest.json；如果不存在但有 SKILL.md，
        则从 SKILL.md frontmatter + @ue_tool 装饰器自动构建 manifest（兼容 OpenClaw 格式）。
        """
        manifest_path = skill_dir / "manifest.json"
        skill_md_path = skill_dir / "SKILL.md"

        if manifest_path.exists():
            manifest, errors = parse_manifest(str(manifest_path))

            has_errors = any(e.severity == "error" for e in errors)
            if has_errors:
                if skill_md_path.exists():
                    # manifest.json 不完整但 SKILL.md 存在 → 从 SKILL.md 构建
                    # 常见于 publish_skill 只写了 version 字段的情况
                    UELogger.info(
                        f"SkillHub: {skill_dir.name}: manifest.json incomplete, "
                        f"falling back to SKILL.md"
                    )
                    manifest = self._manifest_from_skill_md(skill_dir, skill_md_path)
                    if manifest is not None:
                        # 从 manifest.json 补充 version（SKILL.md 可能没有）
                        try:
                            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
                            if raw.get("version"):
                                manifest.version = raw["version"]
                        except Exception:
                            pass
                else:
                    for e in errors:
                        if e.severity == "error":
                            UELogger.mcp_error(f"SkillHub: {skill_dir.name}: {e}")
                    return

            if manifest is None:
                return

            # 记录警告
            for e in errors:
                if e.severity == "warning":
                    UELogger.info(f"SkillHub: {manifest.name}: {e}")

        elif skill_md_path.exists():
            # Fallback: 从 SKILL.md frontmatter 构建 manifest
            manifest = self._manifest_from_skill_md(skill_dir, skill_md_path)
            if manifest is None:
                return
            UELogger.info(
                f"SkillHub: {skill_dir.name}: loaded from SKILL.md (no manifest.json)"
            )
        else:
            return

        manifest.source_layer = layer_id
        manifest.source_dir = str(skill_dir)
        self._all_manifests.append(manifest)

    def _manifest_from_skill_md(self, skill_dir: Path, skill_md_path: Path) -> Optional[SkillManifest]:
        """从 SKILL.md YAML frontmatter 构建 SkillManifest。

        读取 frontmatter 中的 name/description，然后预加载 __init__.py
        扫描 @ue_tool 装饰器以发现 tools 列表。
        """
        try:
            content = skill_md_path.read_text(encoding="utf-8")
        except Exception as e:
            UELogger.mcp_error(f"SkillHub: cannot read {skill_md_path}: {e}")
            return None

        # 解析 YAML frontmatter
        fm = _parse_yaml_frontmatter(content)
        if not fm or not fm.get("name"):
            UELogger.info(
                f"SkillHub: {skill_dir.name}: SKILL.md missing name in frontmatter"
            )
            return None

        fm_name = fm["name"].replace("-", "_")  # OpenClaw 用 kebab-case，我们用 snake_case
        # 优先使用目录名作为规范名（frontmatter name 可能和目录名不同，如 get_material_nodes vs ue54_get_material_nodes）
        # 这样 seen_names 去重能正确匹配目录名，避免同一 Skill 出现两条
        canonical_name = skill_dir.name
        if _NAME_ALIAS_MAP.get(fm_name) == canonical_name or fm_name != canonical_name:
            fm_name = canonical_name
        fm_desc = fm.get("description", "")

        # 扫描 __init__.py 中的 @ue_tool 装饰器（AST 静态分析，不执行）
        init_py = skill_dir / "__init__.py"
        tools_from_ast = []
        if init_py.exists():
            tools_from_ast = _scan_ue_tools_ast(init_py)

        if not tools_from_ast:
            # 没有发现工具，用 skill name 作为默认 tool
            tools_from_ast = [{"name": fm_name, "description": fm_desc}]

        # 从 frontmatter metadata 提取额外字段（如果有）
        metadata = fm.get("metadata", {})
        oc_meta = metadata.get("openclaw", {}) if isinstance(metadata, dict) else {}

        # 推断 software: frontmatter > 名称前缀 > 默认 universal
        _software = fm.get("software", "")
        if not _software:
            if fm_name.startswith("ue") and len(fm_name) > 2 and fm_name[2:3].isdigit():
                _software = "unreal_engine"
            elif fm_name.startswith("maya"):
                _software = "maya"
            elif fm_name.startswith("max"):
                _software = "max"
            else:
                _software = "universal"

        # 构建 SkillManifest
        from skill_manifest import SkillManifest, ToolEntry, SoftwareVersion
        manifest = SkillManifest(
            manifest_version="1.0",
            name=fm_name,
            display_name=fm.get("display_name", fm_name.replace("_", " ").title()),
            description=fm_desc,
            version=fm.get("version", "1.0.0"),
            author=fm.get("author", ""),
            license=fm.get("license", "MIT"),
            software=_software,
            category=fm.get("category", "utils"),
            risk_level=fm.get("risk_level", "low"),
            dependencies=[],
            tags=fm.get("tags", []),
            entry_point="__init__.py",
            tools=[ToolEntry(name=t["name"], description=t["description"]) for t in tools_from_ast],
            software_version=SoftwareVersion(),
        )
        return manifest

    def _load_and_register_skill(self, manifest: SkillManifest) -> None:
        """
        加载一个 Skill 的 Python 模块并注册所有 Tool 到 MCP。

        纯 SKILL.md 格式的 Skill（无 __init__.py）会跳过 Python 模块加载，
        仅保留 manifest 用于管理面板展示。这类 Skill 通过 OpenClaw SKILL.md
        按需指导 AI 调用 run_python，不需要本地 Python 代码。

        Args:
            manifest: 已验证的 SkillManifest
        """
        skill_dir = Path(manifest.source_dir)
        entry_file = skill_dir / manifest.entry_point

        if not entry_file.exists():
            # 纯 SKILL.md 格式：无 Python 代码，跳过模块加载
            UELogger.info(
                f"  Skill {manifest.name}: no entry point, "
                f"SKILL.md-only (skipping Python load)"
            )
            return

        module_name = f"ue_skill_{manifest.name}"

        # 确保 Skill 目录在 sys.path 中
        skill_dir_str = str(skill_dir.parent)
        if skill_dir_str not in sys.path:
            sys.path.insert(0, skill_dir_str)

        # 加载模块
        spec = importlib.util.spec_from_file_location(module_name, str(entry_file))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {entry_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        self._loaded_modules[module_name] = module

        # 注册装饰器声明的 Tool
        for tool_entry in manifest.tools:
            tool_name = tool_entry.name
            if tool_name in _DECORATED_SKILLS:
                info = _DECORATED_SKILLS[tool_name]
                info["manifest"] = manifest
                info["source_layer"] = manifest.source_layer
                self._register_skill_to_mcp(tool_name, info)
            else:
                UELogger.info(
                    f"SkillHub: tool '{tool_name}' declared in manifest "
                    f"but not found via @ue_tool decorator in {manifest.name}"
                )

        UELogger.info(
            f"  Loaded skill: {manifest.name} v{manifest.version} "
            f"[{manifest.source_layer}] ({len(manifest.tools)} tools)"
        )

    # ------------------------------------------------------------------
    # 文件监控
    # ------------------------------------------------------------------

    def start_watching(self) -> None:
        """
        启动文件监控，检测 Skills/ 目录变更。

        宪法约束:
          - 核心机制 §2: unreal.DirectoryWatcher 监控 Skills 文件夹
          - 开发路线图 §3.1: 实时文件监控
        """
        try:
            dir_watcher = unreal.DirectoryWatcher()
            self._watcher_handle = dir_watcher.watch(
                str(self._skills_dir),
                self._on_directory_changed,
            )
            UELogger.info(f"SkillHub: watching {self._skills_dir}")
        except Exception as e:
            UELogger.info(
                f"DirectoryWatcher unavailable ({e}), using polling fallback"
            )
            self._start_polling_watcher()

    def stop_watching(self) -> None:
        """停止文件监控"""
        self._watcher_handle = None
        UELogger.info("SkillHub: stopped watching")

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    def get_skill_list(self) -> List[dict]:
        """
        获取已注册的所有 Skill 信息（不含 handler）。

        用于 unreal://skills/list Resource。
        """
        result = []
        for skill_name, info in self._registered_skills.items():
            manifest = self._manifests.get(info.get("manifest_name", ""))
            entry = {
                "name": info["name"],
                "description": info.get("description", ""),
                "category": info.get("category", "general"),
                "risk_level": info.get("risk_level", "low"),
                "source_file": info.get("source_file", ""),
                "source_layer": info.get("source_layer", "custom"),
            }
            if manifest:
                entry["version"] = manifest.version
                entry["display_name"] = manifest.display_name
                entry["author"] = manifest.author
                entry["software"] = manifest.software
                entry["tags"] = manifest.tags
            result.append(entry)
        return result

    def get_skill_info(self, skill_name: str) -> Optional[dict]:
        """获取单个 Skill 的详细信息"""
        manifest = self._manifests.get(skill_name)
        if manifest:
            return manifest.to_dict()

        info = self._registered_skills.get(skill_name)
        if info:
            return {k: v for k, v in info.items()
                    if not k.startswith("_") and k != "handler"}
        return None

    def get_skills_by_layer(self, layer: str) -> List[dict]:
        """按层级获取 Skill 列表"""
        result = []
        for m in self._all_manifests:
            if m.source_layer == layer:
                result.append(m.to_dict())
        return result

    def get_skills_by_category(self, category: str) -> List[dict]:
        """按分类获取 Skill 列表"""
        result = []
        for m in self._manifests.values():
            if m.category == category:
                result.append(m.to_dict())
        return result

    def get_conflict_report(self) -> Optional[dict]:
        """获取冲突检测报告"""
        if self._conflict_report:
            return self._conflict_report.to_dict()
        return None

    def get_disabled_skills(self) -> List[str]:
        """获取被禁用的 Skill 列表"""
        return list(self._disabled_skills)

    # ------------------------------------------------------------------
    # Skill 执行接口（供 run_ue_python 内部调用）
    # ------------------------------------------------------------------

    def execute_skill(self, skill_name: str, params: dict = None) -> dict:
        """
        统一 Skill 执行入口，供 run_ue_python 调用。

        支持旧名自动映射（如 "artclaw_material" → "ue54_artclaw_material"）。

        用法 (AI 通过 run_ue_python 执行):
            from skill_hub import get_skill_hub
            hub = get_skill_hub()
            result = hub.execute_skill("batch_rename_actors", {"prefix": "SM_"})

        Returns:
            {"success": True, "result": ...} 或 {"success": False, "error": "..."}
        """
        if params is None:
            params = {}

        # 旧名兼容映射
        resolved_name = _NAME_ALIAS_MAP.get(skill_name, skill_name)
        if resolved_name != skill_name:
            UELogger.info(f"SkillHub: alias '{skill_name}' → '{resolved_name}' (deprecated, use new name)")

        if resolved_name not in self._registered_skills:
            return {"success": False, "error": f"Skill 未找到: {skill_name}"}

        info = self._registered_skills[resolved_name]
        handler = info.get("handler")
        if not handler:
            return {"success": False, "error": f"Skill '{skill_name}' 没有 handler"}

        try:
            result = handler(params)
            return {"success": True, "result": result}
        except Exception as e:
            UELogger.exception(f"Skill execution error ({skill_name}): {e}")
            return {"success": False, "error": str(e)}

    def list_skills(self, category: str = None, software: str = None) -> list:
        """
        列出已注册的 Skill，供 run_ue_python 调用。

        用法:
            from skill_hub import get_skill_hub
            hub = get_skill_hub()
            skills = hub.list_skills(category="material")

        Returns:
            [{"name": "...", "description": "...", "category": "...", ...}, ...]
        """
        results = []
        for name, info in self._registered_skills.items():
            manifest = info.get("manifest")
            entry = {
                "name": name,
                "description": info.get("description", ""),
            }
            if manifest:
                entry["category"] = getattr(manifest, "category", "")
                entry["software"] = getattr(manifest, "software", "")
                entry["version"] = getattr(manifest, "version", "")
                entry["display_name"] = getattr(manifest, "display_name", name)

            # 过滤
            if category and entry.get("category") != category:
                continue
            if software and entry.get("software") != software:
                continue

            results.append(entry)
        return results

    # ------------------------------------------------------------------
    # Skill 命名工具
    # ------------------------------------------------------------------

    def auto_name(self, description: str, software: str = None) -> str:
        """
        根据描述和当前 DCC 环境自动生成 Skill 名称。

        命名规范: {dcc}{major_version}_{skill_name}
        - UE 5.4 → ue54_
        - Maya 2023 → maya23_
        - Max 2024 → max24_
        - 通用 → 无前缀

        用法 (AI 通过 run_ue_python 调用):
            from skill_hub import get_skill_hub
            hub = get_skill_hub()
            name = hub.auto_name("batch rename actors in level")
            # → "ue54_batch_rename_actors"

        Args:
            description: Skill 功能的自然语言描述（英文或中文）
            software: 覆盖 DCC 标识（默认用当前环境检测）

        Returns:
            符合命名规范的 skill_name (snake_case)
        """
        import re

        sw = software or self._current_software
        ver = self._current_version

        # 构建前缀
        prefix = ""
        if sw == "unreal_engine":
            # "5.4.1" → "54"
            major_minor = ver.replace(".", "")[:2] if ver else "54"
            prefix = f"ue{major_minor}_"
        elif sw == "maya":
            major = ver.split(".")[0][:2] if ver else "23"
            prefix = f"maya{major}_"
        elif sw == "3ds_max":
            major = ver.split(".")[0][:2] if ver else "24"
            prefix = f"max{major}_"
        # universal → no prefix

        # 从描述提取 snake_case 名称
        # 移除中文字符，保留英文+数字
        desc_ascii = re.sub(r'[^\w\s]', '', description.lower())
        # 常见停用词
        stop_words = {'a', 'an', 'the', 'in', 'on', 'for', 'to', 'of', 'and', 'or', 'with', 'this', 'that'}
        words = [w for w in desc_ascii.split() if w and w not in stop_words]
        # 截断到 4 个词
        name_part = "_".join(words[:4])
        if not name_part:
            name_part = "unnamed_skill"

        # 确保不重名
        candidate = f"{prefix}{name_part}"
        if candidate not in self._registered_skills:
            return candidate

        # 加数字后缀
        for i in range(2, 100):
            suffixed = f"{candidate}_{i}"
            if suffixed not in self._registered_skills:
                return suffixed

        return candidate

    # ------------------------------------------------------------------
    # Skill 管理操作
    # ------------------------------------------------------------------

    def enable_skill(self, skill_name: str) -> bool:
        """启用一个被禁用的 Skill"""
        if skill_name in self._disabled_skills:
            self._disabled_skills.discard(skill_name)
            self._conflict_detector = ConflictDetector(self._disabled_skills)
            UELogger.info(f"SkillHub: enabled skill '{skill_name}'")
            self.scan_and_register()  # 重新扫描
            return True
        return False

    def disable_skill(self, skill_name: str) -> bool:
        """禁用一个 Skill"""
        if skill_name in self._manifests or skill_name in self._registered_skills:
            self._disabled_skills.add(skill_name)
            self._conflict_detector = ConflictDetector(self._disabled_skills)

            # 注销该 Skill 的所有 Tool
            manifest = self._manifests.get(skill_name)
            if manifest:
                for t in manifest.tools:
                    if os.environ.get("ARTCLAW_LEGACY_MCP", "").lower() == "true":
                        self._mcp_server.unregister_tool(t.name)
                    self._registered_skills.pop(t.name, None)
                del self._manifests[skill_name]

            UELogger.info(f"SkillHub: disabled skill '{skill_name}'")
            self._notify_tools_changed(f"disabled:{skill_name}")
            return True
        return False

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
                if os.environ.get("ARTCLAW_LEGACY_MCP", "").lower() == "true":
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

            self._notify_tools_changed(module_name)
            return True

        except Exception as e:
            UELogger.mcp_error(f"Failed to reload {module_name}: {e}")
            traceback.print_exc()
            return False

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _register_skill_to_mcp(self, skill_name: str, info: dict) -> None:
        """将 Skill 注册到内部 API（v2.6: 不再注册 MCP 工具）"""
        # 排除列表过滤
        if skill_name in self._excluded_tools:
            UELogger.info(f"  Skipped tool (excluded): {skill_name}")
            return

        # 记录 manifest 关联
        manifest = info.get("manifest")
        if manifest:
            info["manifest_name"] = manifest.name

        # v2.6: 仅在 legacy 模式下注册 MCP 工具
        if os.environ.get("ARTCLAW_LEGACY_MCP", "").lower() == "true":
            self._mcp_server.register_tool(
                name=skill_name,
                description=info["description"],
                input_schema=info["input_schema"],
                handler=info["handler"],
            )

        # 无论是否注册 MCP，都注册到内部字典（供 execute_skill 使用）
        self._registered_skills[skill_name] = info
    def _on_directory_changed(self, changes):
        """DirectoryWatcher 回调"""
        for change in changes:
            file_path = Path(str(change.filename))
            if file_path.suffix not in (".py", ".json"):
                continue

            UELogger.info(f"SkillHub: detected change in {file_path.name}")

            if file_path.name == "manifest.json":
                # manifest 变更 → 完全重新扫描
                self.scan_and_register()
                self._notify_tools_changed("manifest_changed")
                return

            if file_path.suffix == ".py":
                module_name = f"ue_skill_{file_path.stem}"
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
                        UELogger.mcp_error(
                            f"Failed to load new skill {file_path.name}: {e}"
                        )

    def _start_polling_watcher(self):
        """轮询方式的文件监控（fallback）"""
        self._file_mtimes: Dict[str, float] = {}

        # 记录初始状态 — 递归扫描所有层级
        for py_file in self._skills_dir.rglob("*.py"):
            self._file_mtimes[str(py_file)] = py_file.stat().st_mtime
        for json_file in self._skills_dir.rglob("manifest.json"):
            self._file_mtimes[str(json_file)] = json_file.stat().st_mtime

        self._poll_counter = 0
        self._poll_interval = 60  # 每 60 tick 检查一次

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
        for py_file in self._skills_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            current_files[str(py_file)] = py_file.stat().st_mtime
        for json_file in self._skills_dir.rglob("manifest.json"):
            current_files[str(json_file)] = json_file.stat().st_mtime

        changed = False
        for fpath, mtime in current_files.items():
            old_mtime = self._file_mtimes.get(fpath)
            if old_mtime is None or mtime > old_mtime:
                changed = True
                UELogger.info(f"SkillHub: file changed: {Path(fpath).name}")

        if changed:
            # 重新完整扫描
            self.scan_and_register()
            self._notify_tools_changed("polling_refresh")

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
        """在 Skills/99_custom/ 目录创建示例 Skill 文件"""
        custom_dir = self._skills_dir / "99_custom"
        example_dir = custom_dir / "example_skill"
        example_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = example_dir / "manifest.json"
        if manifest_path.exists():
            return

        manifest = {
            "manifest_version": "1.0",
            "name": "example_skill",
            "display_name": "示例技能",
            "description": "Example skill demonstrating ArtClaw skill structure",
            "version": "1.0.0",
            "author": "Ivan(杨己力)",
            "license": "MIT",
            "software": "unreal_engine",
            "category": "utils",
            "risk_level": "low",
            "tags": ["example"],
            "entry_point": "__init__.py",
            "tools": [
                {
                    "name": "example_hello",
                    "description": "A simple hello world skill for testing"
                }
            ]
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        init_path = example_dir / "__init__.py"
        init_code = '''"""Example Skill - demonstrates ArtClaw skill structure"""
from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None

@ue_tool(
    name="example_hello",
    description="A simple hello world skill for testing. Returns a greeting.",
    category="utils",
    risk_level="low",
)
def example_hello(arguments: dict) -> str:
    """示例技能: 返回问候语"""
    name = arguments.get("name", "World")
    return json.dumps({
        "success": True,
        "message": f"Hello, {name}! ArtClaw Skill Hub is working.",
    })
'''
        init_path.write_text(init_code, encoding="utf-8")
        UELogger.info(f"SkillHub: created example skill at {example_dir}")

# ============================================================================
# 4. 模块级便捷接口
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
    if hasattr(mcp_server, 'register_resource'):
        mcp_server.register_resource(
            uri="unreal://skills/list",
            name="Available Skills",
            description="List all registered skills (Core Tools + dynamic Skills)",
            handler=lambda: json.dumps({
                "core_tools": len(mcp_server._tools) - len(_skill_hub_instance._registered_skills),
                "skills": _skill_hub_instance.get_skill_list(),
                "total": len(mcp_server._tools),
            }),
        )

    return _skill_hub_instance


def get_skill_hub() -> Optional[SkillHub]:
    """获取 Skill Hub 单例"""
    return _skill_hub_instance