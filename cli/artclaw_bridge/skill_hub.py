"""
artclaw_bridge.skill_hub - CLI 侧 Skill 管理中心
=============================================

实现 Skill 的分层加载、版本匹配和冲突检测。

加载优先级（数字越小优先级越高）:
  - 00_official/  ← artclaw_bridge/skills/     官方库
  - 01_team/      ← artclaw_bridge/team_skills/ 团队库
  - 02_user/      ← ~/.artclaw_bridge/skills/  用户库
  - 99_custom/    ← 运行时动态/临时实验

同名 Skill 高优先级覆盖低优先级。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from artclaw_bridge.config import artclaw_bridgeConfig
from artclaw_bridge.manifest import ManifestValidator, load_manifest

logger = logging.getLogger("artclaw_bridge.skill_hub")

# ── 层级定义 ──────────────────────────────────────────────

LAYER_OFFICIAL = "00_official"
LAYER_TEAM = "01_team"
LAYER_USER = "02_user"
LAYER_CUSTOM = "99_custom"

LAYER_PRIORITY: dict[str, int] = {
    LAYER_OFFICIAL: 0,
    LAYER_TEAM: 1,
    LAYER_USER: 2,
    LAYER_CUSTOM: 99,
}
"""层级名 → 优先级数值，数值越小优先级越高。"""


# ── 数据类 ────────────────────────────────────────────────

@dataclass
class SkillEntry:
    """已发现的 Skill 条目。

    Attributes:
        name: Skill 唯一标识符。
        layer: 所属层级（如 '00_official'）。
        path: Skill 目录路径。
        manifest: 解析后的 manifest 字典。
    """

    name: str
    layer: str
    path: Path
    manifest: dict[str, Any]

    @property
    def priority(self) -> int:
        """层级优先级数值，数值越小优先级越高。"""
        return LAYER_PRIORITY.get(self.layer, 999)

    @property
    def software(self) -> str:
        """适用软件。"""
        return self.manifest.get("software", "universal")

    @property
    def category(self) -> str:
        """标准分类。"""
        return self.manifest.get("category", "")

    @property
    def version(self) -> str:
        """Skill 版本号。"""
        return self.manifest.get("version", "0.0.0")

    @property
    def display_name(self) -> str:
        """显示名称。"""
        return self.manifest.get("display_name", self.name)


@dataclass
class ConflictInfo:
    """Skill 冲突信息。

    Attributes:
        name: 冲突的 Skill 名称。
        winner: 生效的 SkillEntry（高优先级）。
        overridden: 被覆盖的 SkillEntry 列表（低优先级）。
    """

    name: str
    winner: SkillEntry
    overridden: list[SkillEntry] = field(default_factory=list)


# ── 版本比较工具 ──────────────────────────────────────────

def _parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """将版本字符串解析为整数元组，便于比较。

    仅取主版本号部分（MAJOR.MINOR.PATCH），忽略预发布标签。

    Args:
        version_str: 版本字符串，如 "5.3" 或 "5.3.1"。

    Returns:
        整数元组，如 (5, 3) 或 (5, 3, 1)。
    """
    # 去掉预发布后缀
    base = version_str.split("-")[0].split("+")[0]
    parts: list[int] = []
    for segment in base.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def version_match(
    skill_manifest: dict[str, Any],
    current_software: str,
    current_version: str,
) -> bool:
    """判断 Skill 是否与当前软件及版本匹配。

    匹配规则:
      1. manifest.software 必须等于 current_software 或为 'universal'。
      2. 若 manifest 包含 software_version，则 current_version 须在
         [min, max] 范围内（包含边界）。省略 min 表示无下限，
         省略 max 表示无上限。

    Args:
        skill_manifest: Skill 的 manifest 字典。
        current_software: 当前 DCC 软件标识。
        current_version: 当前软件版本字符串。

    Returns:
        True 表示匹配，False 表示不匹配。
    """
    skill_sw = skill_manifest.get("software", "universal")
    if skill_sw != "universal" and skill_sw != current_software:
        return False

    sv = skill_manifest.get("software_version")
    if sv is None:
        return True

    current_tuple = _parse_version_tuple(current_version)

    min_ver = sv.get("min")
    if min_ver is not None:
        if current_tuple < _parse_version_tuple(min_ver):
            return False

    max_ver = sv.get("max")
    if max_ver is not None:
        if current_tuple > _parse_version_tuple(max_ver):
            return False

    return True


def _version_distance(
    skill_manifest: dict[str, Any], current_version: str
) -> float:
    """计算 Skill 软件版本范围与当前版本的"距离"。

    距离越小表示匹配度越高。当 Skill 未指定 software_version 时
    返回一个较大值（仍可用，但优先级低于精确匹配的 Skill）。

    Args:
        skill_manifest: Skill 的 manifest 字典。
        current_version: 当前软件版本字符串。

    Returns:
        非负浮点数，0.0 表示完全匹配。
    """
    sv = skill_manifest.get("software_version")
    if sv is None:
        return 1000.0  # 未指定版本范围，给一个较大的距离

    current_tuple = _parse_version_tuple(current_version)

    min_ver = sv.get("min")
    max_ver = sv.get("max")

    # 计算与范围中点的距离
    min_tuple = _parse_version_tuple(min_ver) if min_ver else current_tuple
    max_tuple = _parse_version_tuple(max_ver) if max_ver else current_tuple

    # 补齐长度
    max_len = max(len(current_tuple), len(min_tuple), len(max_tuple))
    cur = current_tuple + (0,) * (max_len - len(current_tuple))
    lo = min_tuple + (0,) * (max_len - len(min_tuple))
    hi = max_tuple + (0,) * (max_len - len(max_tuple))

    # 如果在范围内，距离为 0
    if lo <= cur <= hi:
        return 0.0

    # 超出范围时计算到最近边界的距离
    if cur < lo:
        return float(sum(abs(a - b) for a, b in zip(cur, lo)))
    return float(sum(abs(a - b) for a, b in zip(cur, hi)))


# ── SkillHub ──────────────────────────────────────────────

class SkillHub:
    """CLI 侧 Skill 管理中心。

    负责扫描所有层级目录，发现、加载、过滤 Skill，
    并提供版本匹配和冲突检测功能。
    """

    def __init__(self, config: Optional[artclaw_bridgeConfig] = None) -> None:
        """初始化 SkillHub。

        Args:
            config: artclaw_bridgeConfig 实例。为 None 时自动创建。
        """
        self._config = config or artclaw_bridgeConfig()
        self._validator = ManifestValidator()

        # name → 按优先级排序的 SkillEntry 列表（索引 0 优先级最高）
        self._skills: dict[str, list[SkillEntry]] = {}

        # 层级 → 源目录映射
        self._layer_sources: dict[str, Optional[Path]] = {
            LAYER_OFFICIAL: self._config.skills_dir,
            LAYER_TEAM: self._config.team_skills_dir,
            LAYER_USER: self._config.user_skills_dir,
            LAYER_CUSTOM: None,  # 运行时目录下的 99_custom/
        }
        # 如果存在 runtime 目录，99_custom 指向其下的子目录
        if self._config.runtime_skills_dir:
            custom_dir = self._config.runtime_skills_dir / LAYER_CUSTOM
            if custom_dir.is_dir():
                self._layer_sources[LAYER_CUSTOM] = custom_dir

    def scan_all_skills(self) -> int:
        """扫描所有层级目录，发现 Skill（通过查找 manifest.json）。

        每次调用会清空已有记录并重新扫描。

        Returns:
            发现的 Skill 总数（去重前，含所有层级的条目）。
        """
        self._skills.clear()
        total = 0

        for layer, source_dir in self._layer_sources.items():
            if source_dir is None or not source_dir.is_dir():
                logger.debug("跳过层级 %s: 目录不存在或未配置", layer)
                continue

            count = self._scan_layer(layer, source_dir)
            total += count
            logger.info("层级 %s: 发现 %d 个 Skill (%s)", layer, count, source_dir)

        # 对每个 name 按优先级排序
        for name in self._skills:
            self._skills[name].sort(key=lambda e: e.priority)

        logger.info("扫描完成: 共发现 %d 个 Skill 条目", total)
        return total

    def get_skill(self, name: str) -> Optional[SkillEntry]:
        """按名称查找 Skill（高优先级覆盖低优先级）。

        Args:
            name: Skill 名称。

        Returns:
            优先级最高的 SkillEntry，未找到时返回 None。
        """
        entries = self._skills.get(name)
        if not entries:
            return None
        return entries[0]

    def get_skill_for_software(
        self,
        name: str,
        current_software: str,
        current_version: str,
    ) -> Optional[SkillEntry]:
        """按名称查找最匹配当前软件版本的 Skill。

        在所有同名候选中，先筛选版本匹配的，再按优先级和版本距离排序。

        Args:
            name: Skill 名称。
            current_software: 当前 DCC 软件标识。
            current_version: 当前软件版本字符串。

        Returns:
            最佳匹配的 SkillEntry，未找到时返回 None。
        """
        entries = self._skills.get(name)
        if not entries:
            return None

        matched = [
            e for e in entries
            if version_match(e.manifest, current_software, current_version)
        ]
        if not matched:
            return None

        # 优先选择：① 层级优先级高 ② 版本距离近
        matched.sort(
            key=lambda e: (
                e.priority,
                _version_distance(e.manifest, current_version),
            )
        )
        return matched[0]

    def list_skills(
        self,
        category: Optional[str] = None,
        software: Optional[str] = None,
        source: Optional[str] = None,
    ) -> list[SkillEntry]:
        """按条件过滤 Skill 列表。

        返回每个名称下优先级最高的 SkillEntry。

        Args:
            category: 按分类筛选（如 'material'）。
            software: 按适用软件筛选（如 'unreal_engine'）。
            source: 按来源层级筛选（如 '00_official'）。

        Returns:
            符合条件的 SkillEntry 列表。
        """
        result: list[SkillEntry] = []

        for entries in self._skills.values():
            if not entries:
                continue

            # 如果指定了 source，从该层级中取
            if source is not None:
                candidates = [e for e in entries if e.layer == source]
            else:
                # 默认取优先级最高的
                candidates = [entries[0]]

            for entry in candidates:
                if category is not None and entry.category != category:
                    continue
                if software is not None and entry.software != software:
                    continue
                result.append(entry)

        result.sort(key=lambda e: e.name)
        return result

    def get_skill_info(self, name: str) -> Optional[dict[str, Any]]:
        """返回完整的 Skill 元数据。

        包含 manifest 原始数据以及额外的管理信息（层级、路径、
        是否有冲突等）。

        Args:
            name: Skill 名称。

        Returns:
            元数据字典，未找到时返回 None。
        """
        entries = self._skills.get(name)
        if not entries:
            return None

        winner = entries[0]
        info: dict[str, Any] = {
            **winner.manifest,
            "_layer": winner.layer,
            "_path": str(winner.path),
            "_priority": winner.priority,
        }

        if len(entries) > 1:
            info["_overridden_by"] = [
                {"layer": e.layer, "path": str(e.path), "version": e.version}
                for e in entries[1:]
            ]

        return info

    def detect_conflicts(self) -> list[ConflictInfo]:
        """检测 Skill 冲突（多个层级存在同名 Skill）。

        高优先级覆盖低优先级时输出警告日志。

        Returns:
            冲突信息列表。
        """
        conflicts: list[ConflictInfo] = []

        for name, entries in self._skills.items():
            if len(entries) <= 1:
                continue

            winner = entries[0]
            overridden = entries[1:]

            conflict = ConflictInfo(
                name=name,
                winner=winner,
                overridden=overridden,
            )
            conflicts.append(conflict)

            overridden_layers = ", ".join(
                f"{e.layer}({e.path})" for e in overridden
            )
            logger.warning(
                "Skill 冲突: '%s' — 层级 %s(%s) 覆盖 %s",
                name,
                winner.layer,
                winner.path,
                overridden_layers,
            )

        return conflicts

    # ── 私有方法 ──────────────────────────────────────────

    def _scan_layer(self, layer: str, source_dir: Path) -> int:
        """扫描单个层级目录，递归查找含 manifest.json 的 Skill 包。

        Args:
            layer: 层级名称。
            source_dir: 层级源目录。

        Returns:
            在该层级中发现的 Skill 数量。
        """
        count = 0

        try:
            for manifest_path in source_dir.rglob("manifest.json"):
                # 跳过模板目录（模板包含 TODO 占位符，不是有效 Skill）
                if "templates" in manifest_path.parts:
                    continue
                entry = self._load_skill_entry(layer, manifest_path)
                if entry is not None:
                    self._register_entry(entry)
                    count += 1
        except OSError as exc:
            logger.error("扫描目录失败 (%s): %s", source_dir, exc)

        return count

    def _load_skill_entry(
        self, layer: str, manifest_path: Path
    ) -> Optional[SkillEntry]:
        """从 manifest.json 加载单个 SkillEntry。

        Args:
            layer: 所属层级。
            manifest_path: manifest.json 文件路径。

        Returns:
            SkillEntry 或 None（验证失败时）。
        """
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("加载 manifest 失败 (%s): %s", manifest_path, exc)
            return None

        if not isinstance(data, dict):
            logger.warning("manifest 格式错误，非 JSON 对象: %s", manifest_path)
            return None

        result = self._validator.validate(data)
        if not result.success:
            for err in result.errors:
                logger.warning("manifest 验证失败 (%s): %s", manifest_path, err)
            return None

        name = data["name"]
        skill_dir = manifest_path.parent

        return SkillEntry(
            name=name,
            layer=layer,
            path=skill_dir,
            manifest=data,
        )

    def _register_entry(self, entry: SkillEntry) -> None:
        """将 SkillEntry 注册到内部索引。

        Args:
            entry: 要注册的 SkillEntry。
        """
        if entry.name not in self._skills:
            self._skills[entry.name] = []
        self._skills[entry.name].append(entry)
