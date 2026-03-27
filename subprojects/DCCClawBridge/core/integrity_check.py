"""
integrity_check.py - 插件启动完整性检查与自动修复
==================================================

在 UE/DCC 插件启动时检查共享模块是否完整，
缺失时尝试从已知位置自动复制补全。

共享模块清单:
  - bridge_core.py       (OpenClaw 通信核心)
  - bridge_config.py     (通信配置)
  - bridge_diagnostics.py (连接诊断)
  - memory_core.py       (记忆管理系统 v2 核心)

搜索优先级:
  1. 当前目录（已部署）
  2. openclaw-mcp-bridge/ 目录（开发模式，通过相对路径）
  3. 环境变量 ARTCLAW_BRIDGE_DIR 指向的目录

使用方式:
  from integrity_check import check_and_repair
  result = check_and_repair()  # 返回 CheckResult
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("artclaw.integrity")

# 共享模块清单：(文件名, 是否必需, 用途说明)
SHARED_MODULES = [
    ("bridge_core.py", True, "OpenClaw Gateway 通信核心"),
    ("bridge_config.py", True, "通信配置与常量"),
    ("bridge_diagnostics.py", False, "连接诊断工具"),
    ("memory_core.py", True, "记忆管理系统 v2 核心"),
]


@dataclass
class IntegrityResult:
    """完整性检查结果"""
    ok: bool = True
    missing: List[str] = field(default_factory=list)
    repaired: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_dir: Optional[str] = None

    def summary(self) -> str:
        """返回人类可读的摘要"""
        if self.ok and not self.repaired:
            return "共享模块完整性检查通过"

        parts = []
        if self.repaired:
            parts.append(f"已自动修复 {len(self.repaired)} 个文件: {', '.join(self.repaired)}")
        if self.failed:
            parts.append(f"无法修复 {len(self.failed)} 个文件: {', '.join(self.failed)}")
        if self.warnings:
            for w in self.warnings:
                parts.append(f"警告: {w}")

        return "; ".join(parts) if parts else "检查完成"

    def ai_diagnostic(self) -> str:
        """返回 AI 可处理的诊断信息（供 AI 读取并指导用户）"""
        if self.ok:
            return ""

        lines = [
            "## 插件完整性问题",
            "",
            "以下共享模块缺失且无法自动修复:",
            "",
        ]
        for f in self.failed:
            desc = next((m[2] for m in SHARED_MODULES if m[0] == f), "未知模块")
            lines.append(f"- `{f}` — {desc}")

        lines.extend([
            "",
            "### 修复方法",
            "",
            "**方法 1 (推荐):** 使用安装脚本重新安装插件",
            "```",
            "cd <artclaw_bridge项目目录>/openclaw-mcp-bridge",
            "setup.bat <UE项目路径>",
            "```",
            "",
            "**方法 2:** 手动复制缺失文件",
            f"从 `openclaw-mcp-bridge/` 目录复制以下文件到插件的 `Content/Python/` 目录:",
        ])
        for f in self.failed:
            lines.append(f"- `{f}`")

        lines.extend([
            "",
            "**方法 3:** 设置环境变量指向 artclaw_bridge 源码目录",
            "```",
            "set ARTCLAW_BRIDGE_DIR=D:\\path\\to\\artclaw_bridge\\openclaw-mcp-bridge",
            "```",
        ])

        return "\n".join(lines)


def _find_source_dir(plugin_python_dir: str) -> Optional[str]:
    """搜索共享模块的源目录

    搜索优先级:
    1. 环境变量 ARTCLAW_BRIDGE_DIR
    2. 相对路径回溯到 openclaw-mcp-bridge/ (UE 开发模式)
    3. 相对路径回溯到 openclaw-mcp-bridge/ (DCC 开发模式)
    """
    # 1. 环境变量
    env_dir = os.environ.get("ARTCLAW_BRIDGE_DIR", "")
    if env_dir and os.path.isdir(env_dir):
        # 验证目录包含 bridge_core.py
        if os.path.exists(os.path.join(env_dir, "bridge_core.py")):
            logger.info(f"从环境变量找到源目录: {env_dir}")
            return env_dir

    # 2. UE 开发模式回溯: Content/Python/ → 6级上 → openclaw-mcp-bridge/
    ue_candidate = os.path.normpath(
        os.path.join(plugin_python_dir, "..", "..", "..", "..", "..", "..",
                     "openclaw-mcp-bridge")
    )
    if os.path.isdir(ue_candidate) and os.path.exists(os.path.join(ue_candidate, "bridge_core.py")):
        logger.info(f"从 UE 开发路径找到源目录: {ue_candidate}")
        return ue_candidate

    # 3. DCC 开发模式回溯: core/ → 3级上 → openclaw-mcp-bridge/
    dcc_candidate = os.path.normpath(
        os.path.join(plugin_python_dir, "..", "..", "..", "openclaw-mcp-bridge")
    )
    if os.path.isdir(dcc_candidate) and os.path.exists(os.path.join(dcc_candidate, "bridge_core.py")):
        logger.info(f"从 DCC 开发路径找到源目录: {dcc_candidate}")
        return dcc_candidate

    return None


def check_and_repair(plugin_python_dir: Optional[str] = None,
                     auto_repair: bool = True) -> IntegrityResult:
    """检查并修复共享模块完整性

    Args:
        plugin_python_dir: 插件 Python 目录路径。None 时自动检测（本文件所在目录）
        auto_repair: 是否自动修复缺失文件

    Returns:
        IntegrityResult 检查结果
    """
    if plugin_python_dir is None:
        plugin_python_dir = os.path.dirname(os.path.abspath(__file__))

    result = IntegrityResult()

    # 1. 检查哪些文件缺失
    for filename, required, description in SHARED_MODULES:
        filepath = os.path.join(plugin_python_dir, filename)
        if not os.path.exists(filepath):
            if required:
                result.missing.append(filename)
                logger.warning(f"共享模块缺失: {filename} ({description})")
            else:
                result.warnings.append(f"可选模块缺失: {filename} ({description})")
                logger.info(f"可选模块缺失（非致命）: {filename}")

    if not result.missing:
        logger.info("共享模块完整性检查通过")
        return result

    # 2. 如果不自动修复，标记失败
    if not auto_repair:
        result.failed = result.missing.copy()
        result.ok = False
        return result

    # 3. 寻找源目录
    source_dir = _find_source_dir(plugin_python_dir)
    result.source_dir = source_dir

    if not source_dir:
        logger.error(
            "无法找到共享模块源目录。"
            "请使用 setup.bat 重新安装插件，"
            "或设置环境变量 ARTCLAW_BRIDGE_DIR 指向 openclaw-mcp-bridge 目录。"
        )
        result.failed = result.missing.copy()
        result.ok = False
        return result

    # 4. 逐个复制缺失文件
    for filename in result.missing:
        src = os.path.join(source_dir, filename)
        dst = os.path.join(plugin_python_dir, filename)

        if not os.path.exists(src):
            logger.error(f"源文件不存在: {src}")
            result.failed.append(filename)
            continue

        try:
            shutil.copy2(src, dst)
            result.repaired.append(filename)
            logger.info(f"已自动修复: {filename} ← {src}")
        except Exception as e:
            logger.error(f"复制失败 {filename}: {e}")
            result.failed.append(filename)

    # 从 missing 中移除已修复的
    result.missing = [f for f in result.missing if f not in result.repaired]

    # 5. 判断最终结果
    result.ok = len(result.failed) == 0

    if result.ok:
        logger.info(f"完整性修复完成: 修复了 {len(result.repaired)} 个文件")
    else:
        logger.error(f"完整性修复未完全成功: {len(result.failed)} 个文件无法修复")

        # 写入诊断文件，供 AI 读取
        diag_path = os.path.join(plugin_python_dir, "_integrity_issues.md")
        try:
            with open(diag_path, "w", encoding="utf-8") as f:
                f.write(result.ai_diagnostic())
            logger.info(f"诊断信息已写入: {diag_path}")
        except Exception as e:
            logger.warning(f"无法写入诊断文件: {e}")

    return result


def check_only(plugin_python_dir: Optional[str] = None) -> List[str]:
    """仅检查缺失文件（不修复），返回缺失文件名列表"""
    if plugin_python_dir is None:
        plugin_python_dir = os.path.dirname(os.path.abspath(__file__))

    missing = []
    for filename, required, _ in SHARED_MODULES:
        if required and not os.path.exists(os.path.join(plugin_python_dir, filename)):
            missing.append(filename)
    return missing
