"""
artclaw_bridge.manifest - manifest.json 解析与验证
=============================================

提供 ManifestValidator 类，按照 MANIFEST_SPEC.md 规范
验证 Skill 的 manifest.json 文件。

验证规则:
  - 所有必需字段存在且类型正确
  - name 匹配 ^[a-z][a-z0-9_]{0,63}$
  - version 符合 semver (MAJOR.MINOR.PATCH)
  - software / category / risk_level 为合法枚举值
  - tools 数组至少包含一个元素
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("artclaw_bridge.manifest")

# ---------------------------------------------------------------------------
# 可选依赖：jsonschema（安装后自动启用 JSON Schema 校验）
# ---------------------------------------------------------------------------
try:
    import jsonschema as _jsonschema          # noqa: F401
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    _jsonschema = None                         # type: ignore[assignment]
    _JSONSCHEMA_AVAILABLE = False

# skills/manifest.schema.json 相对于本文件的路径
_SCHEMA_PATH = Path(__file__).parent.parent.parent / "skills" / "manifest.schema.json"
_CACHED_SCHEMA: Optional[dict] = None


def _load_schema() -> Optional[dict]:
    """加载并缓存 skills/manifest.schema.json。"""
    global _CACHED_SCHEMA
    if _CACHED_SCHEMA is not None:
        return _CACHED_SCHEMA
    try:
        if _SCHEMA_PATH.exists():
            _CACHED_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
            return _CACHED_SCHEMA
    except Exception as exc:
        logger.debug("加载 manifest.schema.json 失败（非致命）: %s", exc)
    return None

# ── 枚举常量 ──────────────────────────────────────────────

VALID_SOFTWARE = {"universal", "unreal_engine", "maya", "3ds_max"}

VALID_CATEGORIES = {
    "scene", "asset", "material", "lighting", "render",
    "blueprint", "animation", "ui",
    "utils", "integration", "workflow",
}

VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}

# ── 正则 ──────────────────────────────────────────────────

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# ── 必需字段定义 ──────────────────────────────────────────

REQUIRED_FIELDS: dict[str, type | tuple[type, ...]] = {
    "manifest_version": str,
    "name": str,
    "display_name": str,
    "description": str,
    "version": str,
    "author": str,
    "software": str,
    "category": str,
    "risk_level": str,
    "entry_point": str,
    "tools": list,
}


# ── 验证结果 ──────────────────────────────────────────────

@dataclass
class ValidationResult:
    """manifest.json 验证结果。

    Attributes:
        success: 验证是否通过。
        errors: 错误信息列表（验证失败时非空）。
    """

    success: bool
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.success


# ── 验证器 ────────────────────────────────────────────────

class ManifestValidator:
    """manifest.json Schema 验证器。

    按照 MANIFEST_SPEC.md 定义的规则，验证 manifest 数据的
    完整性和合法性。
    """

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """验证 manifest 数据字典。

        验证顺序：
        1. （可选）若 jsonschema 已安装且 skills/manifest.schema.json 存在，
           先做 JSON Schema 校验（更严格，覆盖全量规则）。
        2. 手动规则校验（必选，向后兼容，不依赖 jsonschema）。

        Args:
            data: 从 manifest.json 解析出的字典。

        Returns:
            ValidationResult，包含 success 标志和 errors 列表。
        """
        errors: list[str] = []

        # ── 阶段 1：JSON Schema 校验（可选，jsonschema 可用时启用）──────
        if _JSONSCHEMA_AVAILABLE:
            schema = _load_schema()
            if schema is not None:
                try:
                    _jsonschema.validate(instance=data, schema=schema)
                    logger.debug("jsonschema 校验通过")
                except _jsonschema.ValidationError as exc:
                    # 将 jsonschema 错误转为与手动校验一致的格式
                    path_str = " → ".join(str(p) for p in exc.absolute_path) if exc.absolute_path else "root"
                    errors.append(f"[schema] {path_str}: {exc.message}")
                except _jsonschema.SchemaError as exc:
                    # Schema 文件本身有问题，记录警告后跳过 schema 校验
                    logger.warning("manifest.schema.json 有误（跳过 schema 校验）: %s", exc.message)
            else:
                logger.debug("skills/manifest.schema.json 未找到，跳过 JSON Schema 校验")
        else:
            logger.debug("jsonschema 未安装，使用手动规则校验（pip install jsonschema 可启用 schema 校验）")

        # ── 阶段 2：手动规则校验（始终执行，与 jsonschema 互补）─────────
        self._check_required_fields(data, errors)

        # 只有基础字段存在时才做深层校验
        if not any(e for e in errors if not e.startswith("[schema]")):
            self._check_manifest_version(data, errors)
            self._check_name(data, errors)
            self._check_version(data, errors)
            self._check_software(data, errors)
            self._check_category(data, errors)
            self._check_risk_level(data, errors)
            self._check_tools(data, errors)
            self._check_software_version(data, errors)
            self._check_dependencies(data, errors)
            self._check_tags(data, errors)

        return ValidationResult(success=len(errors) == 0, errors=errors)

    def validate_file(self, path: Path) -> ValidationResult:
        """从文件路径加载并验证 manifest.json。

        Args:
            path: manifest.json 文件路径。

        Returns:
            ValidationResult。
        """
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ValidationResult(success=False, errors=[f"文件不存在: {path}"])
        except OSError as exc:
            return ValidationResult(success=False, errors=[f"无法读取文件: {exc}"])

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return ValidationResult(success=False, errors=[f"JSON 解析失败: {exc}"])

        if not isinstance(data, dict):
            return ValidationResult(
                success=False, errors=["manifest.json 顶层必须是 JSON 对象"]
            )

        return self.validate(data)

    # ── 私有校验方法 ──────────────────────────────────────

    @staticmethod
    def _check_required_fields(
        data: dict[str, Any], errors: list[str]
    ) -> None:
        """检查所有必需字段是否存在且类型正确。"""
        for field_name, expected_type in REQUIRED_FIELDS.items():
            if field_name not in data:
                errors.append(f"缺少必需字段: {field_name}")
            elif not isinstance(data[field_name], expected_type):
                errors.append(
                    f"字段 '{field_name}' 类型错误: "
                    f"期望 {expected_type.__name__}, "
                    f"实际 {type(data[field_name]).__name__}"
                )

    @staticmethod
    def _check_manifest_version(
        data: dict[str, Any], errors: list[str]
    ) -> None:
        """manifest_version 必须为 '1.0'。"""
        if data.get("manifest_version") != "1.0":
            errors.append(
                f"manifest_version 必须为 '1.0', "
                f"实际为 '{data.get('manifest_version')}'"
            )

    @staticmethod
    def _check_name(data: dict[str, Any], errors: list[str]) -> None:
        """name 必须匹配 ^[a-z][a-z0-9_]{0,63}$。"""
        name = data.get("name", "")
        if not NAME_PATTERN.match(name):
            errors.append(
                f"name '{name}' 不合法: "
                "必须匹配 ^[a-z][a-z0-9_]{{0,63}}$"
            )

    @staticmethod
    def _check_version(data: dict[str, Any], errors: list[str]) -> None:
        """version 必须符合 semver。"""
        version = data.get("version", "")
        if not SEMVER_PATTERN.match(version):
            errors.append(
                f"version '{version}' 不符合 semver 格式 (MAJOR.MINOR.PATCH)"
            )

    @staticmethod
    def _check_software(data: dict[str, Any], errors: list[str]) -> None:
        """software 必须是合法枚举值。"""
        software = data.get("software", "")
        if software not in VALID_SOFTWARE:
            errors.append(
                f"software '{software}' 不合法, "
                f"可选值: {sorted(VALID_SOFTWARE)}"
            )

    @staticmethod
    def _check_category(data: dict[str, Any], errors: list[str]) -> None:
        """category 必须是合法枚举值。"""
        category = data.get("category", "")
        if category not in VALID_CATEGORIES:
            errors.append(
                f"category '{category}' 不合法, "
                f"可选值: {sorted(VALID_CATEGORIES)}"
            )

    @staticmethod
    def _check_risk_level(data: dict[str, Any], errors: list[str]) -> None:
        """risk_level 必须是合法枚举值。"""
        risk = data.get("risk_level", "")
        if risk not in VALID_RISK_LEVELS:
            errors.append(
                f"risk_level '{risk}' 不合法, "
                f"可选值: {sorted(VALID_RISK_LEVELS)}"
            )

    @staticmethod
    def _check_tools(data: dict[str, Any], errors: list[str]) -> None:
        """tools 数组至少包含一个元素，每个元素须有 name 和 description。"""
        tools = data.get("tools", [])
        if not isinstance(tools, list) or len(tools) == 0:
            errors.append("tools 数组至少包含一个元素")
            return

        for idx, tool in enumerate(tools):
            if not isinstance(tool, dict):
                errors.append(f"tools[{idx}] 必须是对象")
                continue
            if "name" not in tool:
                errors.append(f"tools[{idx}] 缺少 'name' 字段")
            if "description" not in tool:
                errors.append(f"tools[{idx}] 缺少 'description' 字段")

    @staticmethod
    def _check_software_version(
        data: dict[str, Any], errors: list[str]
    ) -> None:
        """software_version（可选）的 min/max 必须是字符串。"""
        sv = data.get("software_version")
        if sv is None:
            return
        if not isinstance(sv, dict):
            errors.append("software_version 必须是对象")
            return
        for key in ("min", "max"):
            if key in sv and not isinstance(sv[key], str):
                errors.append(f"software_version.{key} 必须是字符串")

    @staticmethod
    def _check_dependencies(
        data: dict[str, Any], errors: list[str]
    ) -> None:
        """dependencies（可选）必须是字符串数组。"""
        deps = data.get("dependencies")
        if deps is None:
            return
        if not isinstance(deps, list):
            errors.append("dependencies 必须是数组")
            return
        for idx, dep in enumerate(deps):
            if not isinstance(dep, str):
                errors.append(f"dependencies[{idx}] 必须是字符串")

    @staticmethod
    def _check_tags(data: dict[str, Any], errors: list[str]) -> None:
        """tags（可选）必须是字符串数组。"""
        tags = data.get("tags")
        if tags is None:
            return
        if not isinstance(tags, list):
            errors.append("tags 必须是数组")
            return
        for idx, tag in enumerate(tags):
            if not isinstance(tag, str):
                errors.append(f"tags[{idx}] 必须是字符串")


def check_skill_dependencies(
    skill_manifest: dict,
    available_skills: list[str],
) -> list[str]:
    """检查 skill 的依赖是否满足。

    读取 skill_manifest 中的 "dependencies" 字段，检查每个依赖名是否
    出现在 available_skills 中。

    Args:
        skill_manifest:   已解析的 manifest 字典。
        available_skills: 当前已注册的 Skill 名称列表。

    Returns:
        缺失的依赖名列表（空列表表示全部满足）。
    """
    deps = skill_manifest.get("dependencies")
    if not deps or not isinstance(deps, list):
        return []

    available_set = set(available_skills)
    return [dep for dep in deps if isinstance(dep, str) and dep not in available_set]


def load_manifest(path: Path) -> Optional[dict[str, Any]]:
    """加载并验证 manifest.json，返回数据字典或 None。

    加载成功且验证通过时返回字典；否则记录错误日志并返回 None。

    Args:
        path: manifest.json 文件路径。

    Returns:
        验证通过的 manifest 字典，或 None。
    """
    validator = ManifestValidator()
    result = validator.validate_file(path)
    if not result.success:
        for err in result.errors:
            logger.warning("manifest 验证失败 (%s): %s", path, err)
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("加载 manifest 失败 (%s): %s", path, exc)
        return None
