"""
skill_conflict.py - Skill 冲突检测
=====================================

阶段 B4: Skill 冲突检测

宪法约束:
  - skill-management-system.md §5.1: 加载优先级
  - skill-management-system.md §2.1: 同名 Skill 高优先级覆盖低优先级

设计说明:
  - 检测同名 Skill 在不同层级中的冲突
  - 检测同名 Tool 在不同 Skill 中的冲突
  - 生成冲突报告，记录覆盖关系
  - 支持显式禁用特定 Skill 以解决冲突
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from skill_manifest import SkillManifest


# ============================================================================
# 1. 层级优先级
# ============================================================================

# 数字越小优先级越高
# v2.6: 层级名更新 (team → marketplace)
LAYER_PRIORITY = {
    "official": 0,       # skills/official/
    "marketplace": 1,    # skills/marketplace/ (原 team)
    "user": 2,           # Skills/user/ (运行时)
    "custom": 99,        # Skills/custom/ (运行时)
}

LAYER_DISPLAY = {
    "official": "官方库",
    "marketplace": "市集",
    "user": "用户库",
    "custom": "临时/实验",
}

# 旧层级名兼容（旧名 → 新名）
_LAYER_ALIAS = {
    "team": "marketplace",
}


# ============================================================================
# 2. 冲突类型
# ============================================================================

@dataclass
class SkillConflict:
    """Skill 级别冲突：同名 Skill 在不同层级"""
    skill_name: str
    winner: SkillManifest  # 最终生效的 Skill
    losers: List[SkillManifest] = field(default_factory=list)  # 被覆盖的 Skill
    conflict_type: str = "skill_override"  # skill_override | tool_clash

    def __str__(self):
        loser_layers = [m.source_layer or "unknown" for m in self.losers]
        return (
            f"Skill '{self.skill_name}': "
            f"{self.winner.source_layer} (v{self.winner.version}) wins over "
            f"{', '.join(loser_layers)}"
        )

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "conflict_type": self.conflict_type,
            "winner": {
                "name": self.winner.name,
                "version": self.winner.version,
                "layer": self.winner.source_layer,
                "source_dir": self.winner.source_dir,
            },
            "losers": [
                {
                    "name": m.name,
                    "version": m.version,
                    "layer": m.source_layer,
                    "source_dir": m.source_dir,
                }
                for m in self.losers
            ],
        }


@dataclass
class ToolConflict:
    """Tool 级别冲突：不同 Skill 暴露同名 Tool"""
    tool_name: str
    skills: List[SkillManifest] = field(default_factory=list)
    winner_skill: Optional[str] = None  # 最终注册的 Skill

    def __str__(self):
        skill_names = [m.name for m in self.skills]
        return (
            f"Tool '{self.tool_name}' defined in multiple skills: "
            f"{', '.join(skill_names)} → winner: {self.winner_skill}"
        )

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "conflict_type": "tool_clash",
            "skills": [
                {
                    "name": m.name,
                    "version": m.version,
                    "layer": m.source_layer,
                }
                for m in self.skills
            ],
            "winner_skill": self.winner_skill,
        }


@dataclass
class ConflictReport:
    """冲突检测报告"""
    skill_conflicts: List[SkillConflict] = field(default_factory=list)
    tool_conflicts: List[ToolConflict] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return len(self.skill_conflicts) > 0 or len(self.tool_conflicts) > 0

    @property
    def total_conflicts(self) -> int:
        return len(self.skill_conflicts) + len(self.tool_conflicts)

    def to_dict(self) -> dict:
        return {
            "has_conflicts": self.has_conflicts,
            "total_conflicts": self.total_conflicts,
            "skill_conflicts": [c.to_dict() for c in self.skill_conflicts],
            "tool_conflicts": [c.to_dict() for c in self.tool_conflicts],
        }

    def summary(self) -> str:
        """生成人类可读的冲突摘要"""
        if not self.has_conflicts:
            return "No conflicts detected."

        lines = [f"Detected {self.total_conflicts} conflict(s):"]
        for c in self.skill_conflicts:
            lines.append(f"  [SKILL] {c}")
        for c in self.tool_conflicts:
            lines.append(f"  [TOOL]  {c}")
        return "\n".join(lines)


# ============================================================================
# 3. 冲突检测引擎
# ============================================================================

class ConflictDetector:
    """
    Skill 冲突检测器。

    使用方式:
        detector = ConflictDetector()
        report = detector.detect(all_manifests)
        resolved = detector.resolve(all_manifests)  # 返回去重后的列表
    """

    def __init__(self, disabled_skills: Optional[Set[str]] = None):
        """
        Args:
            disabled_skills: 被显式禁用的 Skill 名称集合
        """
        self._disabled = disabled_skills or set()

    def detect(self, manifests: List[SkillManifest]) -> ConflictReport:
        """
        检测所有冲突。

        Args:
            manifests: 所有发现的 SkillManifest 列表（可能包含同名）

        Returns:
            ConflictReport 冲突报告
        """
        report = ConflictReport()

        # 1. 检测同名 Skill 冲突
        by_name: Dict[str, List[SkillManifest]] = {}
        for m in manifests:
            if m.name in self._disabled:
                continue
            by_name.setdefault(m.name, []).append(m)

        for name, candidates in by_name.items():
            if len(candidates) <= 1:
                continue

            # 按层级优先级排序
            sorted_candidates = sorted(
                candidates,
                key=lambda m: LAYER_PRIORITY.get(m.source_layer or "custom", 99)
            )
            winner = sorted_candidates[0]
            losers = sorted_candidates[1:]

            report.skill_conflicts.append(SkillConflict(
                skill_name=name,
                winner=winner,
                losers=losers,
            ))

        # 2. 检测跨 Skill 的 Tool 名称冲突
        # 先得到去重后的 Skill 列表（同名取 winner）
        resolved = self._resolve_skill_conflicts(manifests)

        tool_owners: Dict[str, List[SkillManifest]] = {}
        for m in resolved:
            for tool in m.tools:
                tool_owners.setdefault(tool.name, []).append(m)

        for tool_name, owners in tool_owners.items():
            if len(owners) <= 1:
                continue

            # Tool 冲突: 多个不同 Skill 暴露同名 Tool
            # 按 Skill 层级优先级取 winner
            sorted_owners = sorted(
                owners,
                key=lambda m: LAYER_PRIORITY.get(m.source_layer or "custom", 99)
            )
            report.tool_conflicts.append(ToolConflict(
                tool_name=tool_name,
                skills=owners,
                winner_skill=sorted_owners[0].name,
            ))

        return report

    def resolve(self, manifests: List[SkillManifest]) -> List[SkillManifest]:
        """
        解析冲突，返回最终生效的 Skill 列表（去重）。

        同名 Skill 按层级优先级保留 winner。
        被禁用的 Skill 被排除。

        Args:
            manifests: 所有发现的 SkillManifest

        Returns:
            去重后的生效 Skill 列表
        """
        return self._resolve_skill_conflicts(manifests)

    def _resolve_skill_conflicts(self, manifests: List[SkillManifest]) -> List[SkillManifest]:
        """内部方法：解析同名 Skill 冲突"""
        by_name: Dict[str, List[SkillManifest]] = {}
        for m in manifests:
            if m.name in self._disabled:
                continue
            by_name.setdefault(m.name, []).append(m)

        resolved = []
        for name, candidates in by_name.items():
            if len(candidates) == 1:
                resolved.append(candidates[0])
            else:
                # 按层级优先级排序，取第一个
                sorted_candidates = sorted(
                    candidates,
                    key=lambda m: LAYER_PRIORITY.get(m.source_layer or "custom", 99)
                )
                resolved.append(sorted_candidates[0])

        return resolved
