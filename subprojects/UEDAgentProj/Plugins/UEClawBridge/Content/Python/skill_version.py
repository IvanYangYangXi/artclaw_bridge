"""
skill_version.py - 软件版本匹配
=================================

阶段 B3: 软件版本匹配

宪法约束:
  - skill-management-system.md §5.2: 版本匹配策略
  - MANIFEST_SPEC.md: software_version 对象定义

设计说明:
  - 解析 DCC 软件版本字符串（如 "5.4.1", "2024.3"）
  - 匹配 Skill 的 software_version.min / .max 范围
  - 支持 universal Skill 跳过版本检查
  - 当有多个候选 Skill 时，选择版本最接近的
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from skill_manifest import SkillManifest, SoftwareVersion


# ============================================================================
# 1. 版本解析
# ============================================================================

def parse_version(version_str: str) -> Tuple[int, ...]:
    """
    将版本字符串解析为整数元组，用于比较。

    支持格式:
      - "5.4" → (5, 4)
      - "5.4.1" → (5, 4, 1)
      - "2024.3" → (2024, 3)
      - "5.4.1-preview" → (5, 4, 1)  (忽略后缀)

    Args:
        version_str: 版本字符串

    Returns:
        整数元组，可直接用于比较操作
    """
    if not version_str:
        return (0,)

    # 去除非数字后缀（如 -preview, -beta, +build）
    cleaned = re.split(r"[-+]", version_str)[0].strip()

    # 提取所有数字段
    parts = re.findall(r"\d+", cleaned)
    if not parts:
        return (0,)

    return tuple(int(p) for p in parts)


def version_gte(v1: str, v2: str) -> bool:
    """v1 >= v2"""
    return parse_version(v1) >= parse_version(v2)


def version_lte(v1: str, v2: str) -> bool:
    """v1 <= v2"""
    return parse_version(v1) <= parse_version(v2)


def version_eq(v1: str, v2: str) -> bool:
    """v1 == v2（主版本号+次版本号匹配即可）"""
    p1 = parse_version(v1)
    p2 = parse_version(v2)
    # 比较到较短的那个长度
    min_len = min(len(p1), len(p2))
    return p1[:min_len] == p2[:min_len]


# ============================================================================
# 2. 版本匹配
# ============================================================================

def matches_software_version(
    skill_sw_version: Optional[SoftwareVersion],
    current_version: str,
) -> bool:
    """
    检查 Skill 是否兼容指定的软件版本。

    匹配规则:
      - 如果 skill_sw_version 为 None，表示无版本限制 → 匹配
      - 如果 min 存在且 current < min → 不匹配
      - 如果 max 存在且 current > max → 不匹配
      - 其他情况 → 匹配

    Args:
        skill_sw_version: Skill manifest 中的 software_version 对象
        current_version: 当前 DCC 软件版本

    Returns:
        True 表示兼容
    """
    if skill_sw_version is None:
        return True

    if not current_version:
        return True  # 无法确定当前版本时，默认兼容

    current = parse_version(current_version)

    if skill_sw_version.min_version:
        min_v = parse_version(skill_sw_version.min_version)
        if current < min_v:
            return False

    if skill_sw_version.max_version:
        max_v = parse_version(skill_sw_version.max_version)
        if current > max_v:
            return False

    return True


def version_distance(
    skill_sw_version: Optional[SoftwareVersion],
    current_version: str,
) -> float:
    """
    计算 Skill 版本范围与当前版本的"距离"。

    距离越小表示越匹配。用于在多个候选 Skill 中选择最佳。

    规则:
      - 无版本限制 → 距离为 100 (低优先级)
      - 版本范围包含当前版本 → 距离为范围大小
      - 不包含当前版本 → 距离为 float('inf')

    Args:
        skill_sw_version: Skill 的版本范围
        current_version: 当前版本

    Returns:
        距离值，越小越好
    """
    if not matches_software_version(skill_sw_version, current_version):
        return float("inf")

    if skill_sw_version is None:
        return 100.0  # 无限制的 Skill 优先级较低

    current = parse_version(current_version)

    # 计算范围大小作为距离（范围越窄越精确）
    min_v = parse_version(skill_sw_version.min_version) if skill_sw_version.min_version else (0,)
    max_v = parse_version(skill_sw_version.max_version) if skill_sw_version.max_version else (9999,)

    # 简化距离计算：主版本差 * 1000 + 次版本差 * 10 + 补丁差
    def _to_score(v: Tuple[int, ...]) -> int:
        padded = list(v) + [0, 0, 0]
        return padded[0] * 10000 + padded[1] * 100 + padded[2]

    range_size = abs(_to_score(max_v) - _to_score(min_v))
    return float(range_size)


# ============================================================================
# 3. 最佳版本选择
# ============================================================================

def select_best_match(
    candidates: List[SkillManifest],
    current_software: str,
    current_version: str,
) -> Optional[SkillManifest]:
    """
    从多个同名 Skill 候选中，选择最佳匹配。

    优先级规则:
      1. software 完全匹配 > universal
      2. 版本范围包含当前版本
      3. 版本范围越窄越精确

    Args:
        candidates: 同名 Skill 的多个候选
        current_software: 当前 DCC 软件标识 (如 "unreal_engine")
        current_version: 当前 DCC 软件版本 (如 "5.4")

    Returns:
        最佳匹配的 SkillManifest，无匹配返回 None
    """
    if not candidates:
        return None

    # 过滤兼容的候选
    compatible = []
    for c in candidates:
        # software 匹配: 精确匹配或 universal
        if c.software != current_software and c.software != "universal":
            continue
        # 版本匹配
        if not matches_software_version(c.software_version, current_version):
            continue
        compatible.append(c)

    if not compatible:
        return None

    if len(compatible) == 1:
        return compatible[0]

    # 排序: software 精确匹配优先，然后版本距离
    def _sort_key(m: SkillManifest) -> tuple:
        sw_priority = 0 if m.software == current_software else 1
        dist = version_distance(m.software_version, current_version)
        return (sw_priority, dist)

    compatible.sort(key=_sort_key)
    return compatible[0]
