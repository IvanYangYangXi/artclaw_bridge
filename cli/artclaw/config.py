"""
artclaw.config - 路径发现与配置
=================================

自动检测项目结构，定位:
  - artclaw/skills/ (官方库)
  - team_skills/ (团队库)
  - ~/.artclaw/skills/ (用户库)
  - UEEditorAgent/Content/Python/Skills/ (运行时目录)
  - artclaw/skills/templates/ (模板目录)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def find_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """
    向上搜索项目根目录（包含 artclaw/ 目录或 .artclaw_root 标记文件的目录）。
    """
    current = start or Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "skills").is_dir() and (parent / "docs").is_dir():
            return parent
        if (parent / ".artclaw_root").exists():
            return parent
        if (parent / "artclaw").is_dir() and (parent / "artclaw" / "skills").is_dir():
            return parent / "artclaw" if (parent / "artclaw" / "skills").is_dir() else parent
    return None


def get_skills_dir(project_root: Optional[Path] = None) -> Optional[Path]:
    """获取官方 Skill 库目录"""
    root = project_root or find_project_root()
    if root is None:
        return None
    candidates = [
        root / "skills",
        root / "artclaw" / "skills",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def get_templates_dir(project_root: Optional[Path] = None) -> Optional[Path]:
    """获取模板目录"""
    skills = get_skills_dir(project_root)
    if skills and (skills / "templates").is_dir():
        return skills / "templates"
    return None


def get_runtime_skills_dir(project_root: Optional[Path] = None) -> Optional[Path]:
    """获取 UE 插件运行时 Skills 目录"""
    root = project_root or find_project_root()
    if root is None:
        return None

    # 常见路径
    candidates = [
        root / "subprojects" / "UEDAgentProj" / "Plugins" / "UEEditorAgent" / "Content" / "Python" / "Skills",
        root / "Plugins" / "UEEditorAgent" / "Content" / "Python" / "Skills",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def get_user_skills_dir() -> Path:
    """获取用户个人 Skill 目录 (~/.artclaw/skills/)"""
    user_dir = Path.home() / ".artclaw" / "skills"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_team_skills_dir(project_root: Optional[Path] = None) -> Optional[Path]:
    """获取团队 Skill 目录"""
    root = project_root or find_project_root()
    if root is None:
        return None
    team_dir = root / "team_skills"
    if team_dir.is_dir():
        return team_dir
    return None


class ArtClawConfig:
    """CLI 配置聚合"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or find_project_root()
        self.skills_dir = get_skills_dir(self.project_root)
        self.templates_dir = get_templates_dir(self.project_root)
        self.runtime_skills_dir = get_runtime_skills_dir(self.project_root)
        self.user_skills_dir = get_user_skills_dir()
        self.team_skills_dir = get_team_skills_dir(self.project_root)

    def get_target_dir(self, layer: str) -> Optional[Path]:
        """根据层级获取目标目录"""
        if self.runtime_skills_dir:
            target = self.runtime_skills_dir / layer
            target.mkdir(parents=True, exist_ok=True)
            return target
        return None

    def summary(self) -> dict:
        return {
            "project_root": str(self.project_root) if self.project_root else None,
            "skills_dir": str(self.skills_dir) if self.skills_dir else None,
            "templates_dir": str(self.templates_dir) if self.templates_dir else None,
            "runtime_skills_dir": str(self.runtime_skills_dir) if self.runtime_skills_dir else None,
            "user_skills_dir": str(self.user_skills_dir),
            "team_skills_dir": str(self.team_skills_dir) if self.team_skills_dir else None,
        }
