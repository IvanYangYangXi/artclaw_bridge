"""
skill_loader.py - 分层加载与 Manifest 解析
=============================================

阶段 B: Skill Hub 增强

实现:
  - B1: 分层加载机制 (00_official/01_team/02_user/99_custom)
  - B2: manifest.json 解析与 JSON Schema 验证
  - B3: 软件版本匹配
  - B4: Skill 冲突检测（同名覆盖 + 日志警告）

宪法约束:
  - skill-management-system.md §2.1: 分层加载，官方 > 团队 > 用户 > 临时
  - skill-management-system.md §4.2: manifest.json 规范
  - skill-management-system.md §5: 加载优先级与版本匹配
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import unreal
except ImportError:
    unreal = None

try:
    from init_unreal import UELogger
except ImportError:
    # Fallback logger for testing outside UE
    class UELogger:
        @staticmethod
        def info(msg): print(f"[INFO] {msg}")
        @staticmethod
        def mcp_error(msg): print(f"[ERROR] {msg}")
        @staticmethod
        def warning(msg): print(f"[WARN] {msg}")


# ============================================================================
# 常量
# ============================================================================

# 分层目录名 → 优先级 (数字越小优先级越高)
# v2.6: 去掉数字前缀，改用语义目录名
LAYER_DIRS = {
    "official": 0,
    "marketplace": 1,
    "user": 2,
    "custom": 99,
}

# 向后兼容：旧目录名映射到新目录名
_LEGACY_LAYER_MAP = {
    "00_official": "official",
    "01_team": "marketplace",
    "02_user": "user",
    "99_custom": "custom",
}

# 有效的软件标识
VALID_SOFTWARE = {"universal", "unreal_engine", "maya", "3ds_max", "blender", "houdini"}

# 有效的 category
VALID_CATEGORIES = {
    "scene", "asset", "material", "lighting", "render",
    "blueprint", "animation", "ui", "utils", "integration", "workflow",
    "general",
}

# 有效的 risk_level
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}

# Manifest 必需字段
MANIFEST_REQUIRED_FIELDS = {"name", "manifest_version", "entry_point"}

# Manifest 推荐字段
MANIFEST_RECOMMENDED_FIELDS = {
    "display_name", "description", "version", "author",
    "software", "category", "risk_level",
}


# ============================================================================
# B2: Manifest 解析与验证
# ============================================================================

class ManifestError(Exception):
    """manifest.json 解析/验证错误"""
    pass


class SkillManifest:
    """
    Skill 包的元数据，从 manifest.json 解析。

    宪法约束:
      - skill-management-system.md §4.2: manifest.json 规范
    """

    def __init__(self, data: dict, source_path: Path):
        self.raw = data
        self.source_path = source_path  # manifest.json 的所在目录

        # 必需字段
        self.name: str = data.get("name", "")
        self.manifest_version: str = data.get("manifest_version", "1.0")
        self.entry_point: str = data.get("entry_point", "__init__.py")

        # 推荐字段
        self.display_name: str = data.get("display_name", self.name)
        self.description: str = data.get("description", "")
        self.version: str = data.get("version", "0.0.0")
        self.author: str = data.get("author", "unknown")
        self.license: str = data.get("license", "")

        # 软件与版本
        self.software: str = data.get("software", "universal")
        self.software_version: dict = data.get("software_version", {})
        self.min_version: str = self.software_version.get("min", "")
        self.max_version: str = self.software_version.get("max", "")

        # 分类与风险
        self.category: str = data.get("category", "general")
        self.risk_level: str = data.get("risk_level", "low")

        # 依赖
        self.dependencies: List[str] = data.get("dependencies", [])

        # 元数据
        self.tags: List[str] = data.get("tags", [])
        self.tools: List[dict] = data.get("tools", [])

        # 运行时状态
        self.enabled: bool = True
        self.layer: str = ""  # 所属层级 (00_official, 01_team, etc.)
        self.priority: int = 99

    def to_dict(self) -> dict:
        """转为可序列化的字典"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "software": self.software,
            "software_version": self.software_version,
            "category": self.category,
            "risk_level": self.risk_level,
            "tags": self.tags,
            "tools": self.tools,
            "layer": self.layer,
            "priority": self.priority,
            "enabled": self.enabled,
            "source_path": str(self.source_path),
        }

    @staticmethod
    def parse(manifest_path: Path) -> "SkillManifest":
        """
        解析并验证 manifest.json。

        Args:
            manifest_path: manifest.json 文件路径

        Returns:
            SkillManifest 实例

        Raises:
            ManifestError: 验证失败
        """
        if not manifest_path.exists():
            raise ManifestError(f"manifest.json not found: {manifest_path}")

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ManifestError(f"Invalid JSON in {manifest_path}: {e}")

        if not isinstance(data, dict):
            raise ManifestError(f"manifest.json must be a JSON object: {manifest_path}")

        # 验证必需字段
        missing = MANIFEST_REQUIRED_FIELDS - set(data.keys())
        if missing:
            raise ManifestError(
                f"Missing required fields in {manifest_path}: {', '.join(missing)}"
            )

        manifest = SkillManifest(data, manifest_path.parent)

        # 验证字段值
        errors = []

        # name 格式验证
        if not re.match(r'^[a-z][a-z0-9_]*$', manifest.name):
            errors.append(
                f"Invalid name '{manifest.name}': must be lowercase snake_case"
            )

        # software 验证
        if manifest.software and manifest.software not in VALID_SOFTWARE:
            errors.append(
                f"Unknown software '{manifest.software}', "
                f"valid: {', '.join(sorted(VALID_SOFTWARE))}"
            )

        # category 验证
        if manifest.category and manifest.category not in VALID_CATEGORIES:
            errors.append(
                f"Unknown category '{manifest.category}', "
                f"valid: {', '.join(sorted(VALID_CATEGORIES))}"
            )

        # risk_level 验证
        if manifest.risk_level and manifest.risk_level not in VALID_RISK_LEVELS:
            errors.append(
                f"Unknown risk_level '{manifest.risk_level}', "
                f"valid: {', '.join(sorted(VALID_RISK_LEVELS))}"
            )

        # entry_point 文件存在性
        entry_path = manifest.source_path / manifest.entry_point
        if not entry_path.exists():
            errors.append(
                f"Entry point not found: {manifest.entry_point} in {manifest.source_path}"
            )

        if errors:
            raise ManifestError(
                f"Validation errors in {manifest_path}:\n" +
                "\n".join(f"  - {e}" for e in errors)
            )

        return manifest


# ============================================================================
# B3: 软件版本匹配
# ============================================================================

def _parse_version_tuple(version_str: str) -> Tuple[int, ...]:
    """解析版本号为元组，如 '5.4.1' → (5, 4, 1)"""
    if not version_str:
        return ()
    parts = []
    for part in version_str.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_version_match(
    manifest: SkillManifest,
    current_software: str,
    current_version: str,
) -> bool:
    """
    检查 Skill 是否与当前软件/版本兼容。

    宪法约束:
      - skill-management-system.md §5.2: 版本匹配策略

    Args:
        manifest: Skill 的 manifest
        current_software: 当前 DCC 软件标识 (如 "unreal_engine")
        current_version: 当前版本号 (如 "5.4")

    Returns:
        True 如果兼容
    """
    # universal 匹配所有软件
    if manifest.software == "universal":
        return True

    # 软件类型必须匹配
    if manifest.software != current_software:
        return False

    # 如果没有指定版本范围，视为兼容
    if not manifest.min_version and not manifest.max_version:
        return True

    current = _parse_version_tuple(current_version)
    if not current:
        return True  # 无法判断当前版本，默认兼容

    # 检查最低版本
    if manifest.min_version:
        min_ver = _parse_version_tuple(manifest.min_version)
        if current < min_ver:
            return False

    # 检查最高版本
    if manifest.max_version:
        max_ver = _parse_version_tuple(manifest.max_version)
        if current > max_ver:
            return False

    return True


# ============================================================================
# B1 + B4: 分层加载器与冲突检测
# ============================================================================

class LayeredSkillLoader:
    """
    分层 Skill 加载器。

    负责:
      - B1: 按优先级从 official → marketplace → user → custom 扫描
      - B2: 解析每个 Skill 的 manifest.json
      - B3: 过滤不兼容的版本
      - B4: 检测同名冲突，高优先级覆盖低优先级

    宪法约束:
      - skill-management-system.md §2.1: 分层加载机制
      - skill-management-system.md §5: 加载优先级
      - Skill与MCP管理面板设计 §6: DCC 区分
    """

    def __init__(
        self,
        skills_dir: Path,
        current_software: str = "unreal_engine",
        current_version: str = "",
    ):
        """
        Args:
            skills_dir: Skills/ 根目录 (含 official/ 等子目录)
            current_software: 当前 DCC 软件标识
            current_version: 当前 DCC 版本号
        """
        self._skills_dir = skills_dir
        self._current_software = current_software
        self._current_version = current_version

        # 已解析的 manifest: skill_name → SkillManifest
        self._manifests: Dict[str, SkillManifest] = {}

        # 被覆盖的 Skill 记录 (冲突检测): skill_name → list of (layer, path)
        self._overridden: Dict[str, List[Tuple[str, Path]]] = {}

        # 禁用的 Skill: skill_name set
        self._disabled: set = set()

        # 禁用记录文件
        self._disabled_file = skills_dir / ".disabled_skills.json"
        self._load_disabled_list()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def discover_all(self) -> Dict[str, SkillManifest]:
        """
        扫描所有层级目录，发现并解析 Skill。

        返回最终可用的 Skill 字典 (已去重、已过滤不兼容版本)。
        """
        self._manifests.clear()
        self._overridden.clear()

        # 按优先级顺序扫描（数字越小优先级越高）
        for layer_name, priority in sorted(LAYER_DIRS.items(), key=lambda x: x[1]):
            layer_dir = self._skills_dir / layer_name
            if not layer_dir.exists():
                continue

            self._scan_layer(layer_name, layer_dir, priority)

        UELogger.info(
            f"LayeredSkillLoader: discovered {len(self._manifests)} skills "
            f"({len(self._overridden)} name conflicts resolved by priority)"
        )

        return self._manifests

    def get_manifest(self, skill_name: str) -> Optional[SkillManifest]:
        """获取指定 Skill 的 manifest"""
        return self._manifests.get(skill_name)

    def get_all_manifests(self) -> Dict[str, SkillManifest]:
        """获取所有已发现的 manifest"""
        return dict(self._manifests)

    def get_overridden_skills(self) -> Dict[str, List[Tuple[str, Path]]]:
        """获取被覆盖的 Skill 信息（冲突记录）"""
        return dict(self._overridden)

    def get_skills_by_layer(self, layer: str) -> List[SkillManifest]:
        """获取指定层级的所有 Skill"""
        return [
            m for m in self._manifests.values()
            if m.layer == layer
        ]

    def get_skills_by_category(self, category: str) -> List[SkillManifest]:
        """按分类过滤 Skill"""
        return [
            m for m in self._manifests.values()
            if m.category == category
        ]

    def get_skills_by_software(self, software: str) -> List[SkillManifest]:
        """按软件过滤 Skill"""
        return [
            m for m in self._manifests.values()
            if m.software == software or m.software == "universal"
        ]

    def disable_skill(self, skill_name: str) -> bool:
        """禁用一个 Skill"""
        if skill_name not in self._manifests:
            return False
        self._disabled.add(skill_name)
        self._manifests[skill_name].enabled = False
        self._save_disabled_list()
        UELogger.info(f"Skill disabled: {skill_name}")
        return True

    def enable_skill(self, skill_name: str) -> bool:
        """启用一个 Skill"""
        self._disabled.discard(skill_name)
        if skill_name in self._manifests:
            self._manifests[skill_name].enabled = True
        self._save_disabled_list()
        UELogger.info(f"Skill enabled: {skill_name}")
        return True

    def is_disabled(self, skill_name: str) -> bool:
        """检查 Skill 是否被禁用"""
        return skill_name in self._disabled

    def ensure_layer_dirs(self):
        """确保所有层级目录存在，并迁移旧目录名"""
        # 迁移旧目录名到新目录名
        for old_name, new_name in _LEGACY_LAYER_MAP.items():
            old_path = self._skills_dir / old_name
            new_path = self._skills_dir / new_name
            if old_path.exists() and not new_path.exists():
                old_path.rename(new_path)
                UELogger.info(f"LayeredSkillLoader: migrated {old_name} → {new_name}")
            elif old_path.exists() and new_path.exists():
                # 两个都存在：把旧目录内容合并到新目录
                for item in old_path.iterdir():
                    dest = new_path / item.name
                    if not dest.exists():
                        if item.is_dir():
                            shutil.copytree(str(item), str(dest))
                        else:
                            shutil.copy2(str(item), str(dest))
                shutil.rmtree(str(old_path))
                UELogger.info(f"LayeredSkillLoader: merged {old_name} into {new_name}")

        for layer_name in LAYER_DIRS:
            layer_dir = self._skills_dir / layer_name
            layer_dir.mkdir(parents=True, exist_ok=True)

    def install_skill(
        self,
        source_path: Path,
        target_layer: str = "user",
    ) -> Optional[SkillManifest]:
        """
        安装一个 Skill 包到指定层级。

        Args:
            source_path: Skill 包目录
            target_layer: 目标层级

        Returns:
            安装后的 manifest，失败返回 None
        """
        if target_layer not in LAYER_DIRS:
            UELogger.mcp_error(f"Invalid layer: {target_layer}")
            return None

        # 验证源目录有 manifest.json
        manifest_path = source_path / "manifest.json"
        try:
            manifest = SkillManifest.parse(manifest_path)
        except ManifestError as e:
            UELogger.mcp_error(f"Install failed: {e}")
            return None

        # 目标目录
        target_dir = self._skills_dir / target_layer / manifest.name
        if target_dir.exists():
            UELogger.info(f"Overwriting existing skill: {manifest.name} in {target_layer}")
            shutil.rmtree(target_dir)

        # 复制
        shutil.copytree(str(source_path), str(target_dir))
        manifest.layer = target_layer
        manifest.priority = LAYER_DIRS[target_layer]
        manifest.source_path = target_dir

        # 更新注册表
        self._manifests[manifest.name] = manifest

        UELogger.info(
            f"Installed skill: {manifest.name} → {target_layer}/"
        )
        return manifest

    def uninstall_skill(self, skill_name: str) -> bool:
        """卸载一个 Skill"""
        manifest = self._manifests.get(skill_name)
        if manifest is None:
            UELogger.mcp_error(f"Skill not found: {skill_name}")
            return False

        # 删除目录
        skill_dir = manifest.source_path
        if skill_dir.exists():
            shutil.rmtree(str(skill_dir))

        del self._manifests[skill_name]
        self._disabled.discard(skill_name)
        self._save_disabled_list()

        UELogger.info(f"Uninstalled skill: {skill_name} from {skill_dir}")
        return True

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _scan_layer(self, layer_name: str, layer_dir: Path, priority: int):
        """扫描一个层级目录，支持 DCC 子目录 (universal/unreal/maya/max)"""
        UELogger.info(f"  Scanning layer: {layer_name}/ (priority={priority})")

        DCC_SUBDIRS = {"universal", "unreal", "maya", "max"}

        # 扫描子目录
        for item in sorted(layer_dir.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith((".", "_", "__")):
                continue

            manifest_path = item / "manifest.json"
            if manifest_path.exists():
                # 直接是 Skill 包
                self._try_register(item, manifest_path, layer_name, priority)
            elif item.name in DCC_SUBDIRS:
                # DCC 子目录：扫描其下的 Skill 包
                for sub_item in sorted(item.iterdir()):
                    if not sub_item.is_dir():
                        continue
                    if sub_item.name.startswith((".", "_", "__")):
                        continue
                    sub_manifest = sub_item / "manifest.json"
                    if sub_manifest.exists():
                        self._try_register(sub_item, sub_manifest, layer_name, priority)
            # else: 不是 DCC 子目录也不是 Skill 包，跳过

    def _try_register(self, item: Path, manifest_path: Path, layer_name: str, priority: int):
        """尝试解析 manifest 并注册一个 Skill"""
        try:
            manifest = SkillManifest.parse(manifest_path)
        except ManifestError as e:
            UELogger.mcp_error(f"    Skipping {item.name}: {e}")
            return

        manifest.layer = layer_name
        manifest.priority = priority

        # B3: 版本匹配检查
        if not check_version_match(
            manifest, self._current_software, self._current_version
        ):
            UELogger.info(
                f"    Skipping {manifest.name}: incompatible "
                f"(requires {manifest.software} {manifest.min_version}~{manifest.max_version}, "
                f"current: {self._current_software} {self._current_version})"
            )
            return

        # B4: 冲突检测
        if manifest.name in self._manifests:
            existing = self._manifests[manifest.name]
            if priority < existing.priority:
                # 当前层级优先级更高 → 覆盖
                UELogger.info(
                    f"    Conflict: {manifest.name} in {layer_name} "
                    f"overrides {existing.layer} (priority {priority} < {existing.priority})"
                )
                if manifest.name not in self._overridden:
                    self._overridden[manifest.name] = []
                self._overridden[manifest.name].append(
                    (existing.layer, existing.source_path)
                )
            else:
                # 当前层级优先级更低 → 被覆盖
                UELogger.info(
                    f"    Conflict: {manifest.name} in {layer_name} "
                    f"shadowed by {existing.layer} (priority {priority} >= {existing.priority})"
                )
                if manifest.name not in self._overridden:
                    self._overridden[manifest.name] = []
                self._overridden[manifest.name].append(
                    (layer_name, manifest.source_path)
                )
                return

        # 检查禁用状态
        if manifest.name in self._disabled:
            manifest.enabled = False

        self._manifests[manifest.name] = manifest
        UELogger.info(
            f"    Registered: {manifest.name} v{manifest.version} "
            f"[{manifest.category}] ({layer_name})"
            + (" [DISABLED]" if not manifest.enabled else "")
        )

    def _load_disabled_list(self):
        """加载禁用列表"""
        if self._disabled_file.exists():
            try:
                data = json.loads(self._disabled_file.read_text(encoding="utf-8"))
                self._disabled = set(data.get("disabled", []))
            except Exception:
                self._disabled = set()

    def _save_disabled_list(self):
        """保存禁用列表"""
        try:
            self._disabled_file.write_text(
                json.dumps({"disabled": sorted(self._disabled)}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            UELogger.mcp_error(f"Failed to save disabled list: {e}")
