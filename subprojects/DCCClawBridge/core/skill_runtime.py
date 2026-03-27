"""
skill_runtime.py - DCCClawBridge Skill 加载与管理
===================================================

从 UEClawBridge 的 skill_hub.py 移植简化版。
核心功能: 扫描目录 → 解析 manifest → 注册 MCP 工具

分层优先级: 官方(00) > 团队(01) > 用户(02) > 临时(99)
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("artclaw.skill")

# 分层目录名 → 优先级
LAYER_PRIORITY = {
    "00_official": 0,
    "01_team": 1,
    "02_user": 2,
    "99_temp": 99,
}


class SkillManifest:
    """Skill 清单定义"""

    def __init__(self, data: dict, skill_dir: str, layer: str = "02_user"):
        self.name: str = data.get("name", "")
        self.version: str = data.get("version", "0.1.0")
        self.description: str = data.get("description", "")
        self.author: str = data.get("author", "")
        self.category: str = data.get("category", "general")
        self.tags: List[str] = data.get("tags", [])
        self.entry: str = data.get("entry", "__init__.py")
        self.tools: List[dict] = data.get("tools", [])
        self.enabled: bool = data.get("enabled", True)
        self.skill_dir: str = skill_dir
        self.layer: str = layer
        self.priority: int = LAYER_PRIORITY.get(layer, 50)


class SkillRuntime:
    """
    Skill 运行时管理器。

    扫描 skills 目录，加载 manifest.json，注册工具到 MCP Server。
    """

    def __init__(self, mcp_server, skills_base_dir: str = "", adapter=None):
        self._server = mcp_server
        self._adapter = adapter
        self._skills: Dict[str, SkillManifest] = {}
        self._disabled: set = set()

        # skills 目录
        if skills_base_dir:
            self._skills_dir = Path(skills_base_dir)
        else:
            self._skills_dir = Path(__file__).parent.parent / "skills"

    def scan_and_register(self) -> int:
        """扫描并注册所有 Skill，返回注册数量"""
        if not self._skills_dir.exists():
            logger.info(f"Skills dir not found: {self._skills_dir}")
            return 0

        count = 0
        dcc_name = self._adapter.get_software_name() if self._adapter else "dcc"

        # 扫描 DCC 特有目录 (skills/maya/ 或 skills/max/)
        dcc_skills_dir = self._skills_dir / dcc_name
        if dcc_skills_dir.exists():
            count += self._scan_directory(dcc_skills_dir)

        # 扫描通用目录 (skills/common/)
        common_dir = self._skills_dir / "common"
        if common_dir.exists():
            count += self._scan_directory(common_dir)

        # 扫描分层目录 (skills/maya/00_official/, 01_team/, 02_user/)
        for layer_name in sorted(LAYER_PRIORITY.keys()):
            layer_dir = dcc_skills_dir / layer_name
            if layer_dir.exists():
                count += self._scan_directory(layer_dir, layer=layer_name)

        logger.info(f"Skill scan complete: {count} skills registered")
        return count

    def _scan_directory(self, directory: Path, layer: str = "02_user") -> int:
        """扫描单个目录下的所有 Skill"""
        count = 0
        for item in directory.iterdir():
            if not item.is_dir():
                continue
            # 跳过 templates/ 目录（UE 教训 #16）
            if item.name in ("templates", "__pycache__", ".git"):
                continue

            manifest_path = item / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest = self._load_manifest(manifest_path, layer)
                    if manifest and manifest.enabled:
                        self._register_skill(manifest)
                        count += 1
                except Exception as e:
                    logger.error(f"Failed to load skill {item.name}: {e}")

        return count

    def _load_manifest(self, path: Path, layer: str) -> Optional[SkillManifest]:
        """加载 manifest.json"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SkillManifest(data, str(path.parent), layer)
        except Exception as e:
            logger.error(f"Invalid manifest {path}: {e}")
            return None

    def _register_skill(self, manifest: SkillManifest):
        """注册 Skill 的工具到 MCP Server"""
        # 检查同名冲突（高优先级覆盖）
        if manifest.name in self._skills:
            existing = self._skills[manifest.name]
            if existing.priority <= manifest.priority:
                logger.info(
                    f"Skill '{manifest.name}' already registered by higher priority "
                    f"layer ({existing.layer}), skipping {manifest.layer}"
                )
                return

        self._skills[manifest.name] = manifest

        # 加载 Python 模块
        entry_path = Path(manifest.skill_dir) / manifest.entry
        if entry_path.exists():
            try:
                self._load_skill_module(manifest, entry_path)
            except Exception as e:
                logger.error(f"Failed to load skill module {manifest.name}: {e}")

        logger.info(f"Skill registered: {manifest.name} v{manifest.version} [{manifest.layer}]")

    def _load_skill_module(self, manifest: SkillManifest, entry_path: Path):
        """加载 Skill 的 Python 模块并注册 MCP 工具"""
        module_name = f"artclaw_skill_{manifest.name}"

        # 确保 Skill 目录在 sys.path 中
        skill_dir = str(entry_path.parent)
        if skill_dir not in sys.path:
            sys.path.insert(0, skill_dir)

        spec = importlib.util.spec_from_file_location(module_name, str(entry_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {entry_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # 查找并注册标记了 @tool 的函数，或从 manifest.tools 注册
        if manifest.tools:
            for tool_def in manifest.tools:
                tool_name = tool_def.get("name", "")
                handler_name = tool_def.get("handler", tool_name)
                handler = getattr(module, handler_name, None)
                if handler and callable(handler):
                    # v2.6: 默认不注册 Skill MCP 工具，通过 run_python 调用
                    if os.environ.get("ARTCLAW_LEGACY_MCP", "").lower() == "true":
                        self._server.register_tool(
                            name=tool_name,
                            description=tool_def.get("description", ""),
                            input_schema=tool_def.get("inputSchema", {"type": "object", "properties": {}}),
                            handler=handler,
                            main_thread=tool_def.get("mainThread", True),
                        )

        # 检查 register_tools 函数（约定式注册）
        register_fn = getattr(module, "register_tools", None)
        if register_fn and callable(register_fn):
            # v2.6: 默认不调用约定式 MCP 注册，通过 run_python 调用
            if os.environ.get("ARTCLAW_LEGACY_MCP", "").lower() == "true":
                register_fn(self._server)

    # --- 查询接口 ---

    def get_skill_list(self) -> List[dict]:
        result = []
        for name, m in sorted(self._skills.items()):
            result.append({
                "name": m.name,
                "version": m.version,
                "description": m.description,
                "category": m.category,
                "layer": m.layer,
                "enabled": m.name not in self._disabled,
                "tools": [t.get("name", "") for t in m.tools],
            })
        return result

    def get_skill_info(self, name: str) -> Optional[dict]:
        m = self._skills.get(name)
        if not m:
            return None
        return {
            "name": m.name,
            "version": m.version,
            "description": m.description,
            "author": m.author,
            "category": m.category,
            "tags": m.tags,
            "layer": m.layer,
            "skill_dir": m.skill_dir,
            "enabled": m.name not in self._disabled,
            "tools": m.tools,
        }

    def enable_skill(self, name: str) -> bool:
        if name in self._disabled:
            self._disabled.discard(name)
            return True
        return False

    def disable_skill(self, name: str) -> bool:
        if name in self._skills:
            self._disabled.add(name)
            # 注销工具
            manifest = self._skills[name]
            for tool_def in manifest.tools:
                self._server.unregister_tool(tool_def.get("name", ""))
            return True
        return False

    # --- Skill 执行接口（供 run_python 内部调用） ---

    def execute_skill(self, skill_name: str, params: dict = None) -> dict:
        """
        统一 Skill 执行入口，供 run_python 调用。

        用法 (AI 通过 run_python 执行):
            from core.skill_runtime import get_skill_runtime
            rt = get_skill_runtime()
            result = rt.execute_skill("batch_rename_nodes", {"prefix": "SM_"})

        Returns:
            {"success": True, "result": ...} 或 {"success": False, "error": "..."}
        """
        if params is None:
            params = {}

        if skill_name not in self._skills:
            return {"success": False, "error": f"Skill 未找到: {skill_name}"}

        manifest = self._skills[skill_name]

        # 检查是否被禁用
        if skill_name in self._disabled:
            return {"success": False, "error": f"Skill '{skill_name}' 已被禁用"}

        # 从 manifest.tools 中找到对应的 handler
        # 尝试加载模块并调用 handler
        entry_path = Path(manifest.skill_dir) / manifest.entry
        module_name = f"artclaw_skill_{manifest.name}"
        module = sys.modules.get(module_name)

        if not module:
            return {"success": False, "error": f"Skill '{skill_name}' 模块未加载"}

        # 查找 execute 或与 skill 同名的函数
        handler = getattr(module, "execute", None)
        if not handler:
            handler = getattr(module, skill_name, None)
        if not handler:
            # 尝试 manifest 中第一个 tool 的 handler
            if manifest.tools:
                handler_name = manifest.tools[0].get("handler", manifest.tools[0].get("name", ""))
                handler = getattr(module, handler_name, None)

        if not handler or not callable(handler):
            return {"success": False, "error": f"Skill '{skill_name}' 没有可调用的 handler"}

        try:
            result = handler(params)
            return {"success": True, "result": result}
        except Exception as e:
            logger.exception(f"Skill execution error ({skill_name}): {e}")
            return {"success": False, "error": str(e)}

    def list_skills(self, category: str = None, layer: str = None) -> list:
        """
        列出已注册的 Skill，供 run_python 调用。

        用法:
            from core.skill_runtime import get_skill_runtime
            rt = get_skill_runtime()
            skills = rt.list_skills(category="material")

        Returns:
            [{"name": "...", "description": "...", "category": "...", ...}, ...]
        """
        results = []
        for name, manifest in self._skills.items():
            entry = {
                "name": manifest.name,
                "description": manifest.description,
                "category": manifest.category,
                "version": manifest.version,
                "layer": manifest.layer,
                "author": manifest.author,
                "enabled": name not in self._disabled,
                "tools": [t.get("name", "") for t in manifest.tools],
            }

            # 过滤
            if category and entry.get("category") != category:
                continue
            if layer and entry.get("layer") != layer:
                continue

            results.append(entry)
        return results


# --- 全局单例 ---

_skill_runtime_instance: Optional[SkillRuntime] = None


def get_skill_runtime() -> Optional[SkillRuntime]:
    """获取 SkillRuntime 单例，供 run_python 内部调用"""
    return _skill_runtime_instance


def init_skill_runtime(mcp_server, skills_base_dir: str = "", adapter=None) -> SkillRuntime:
    """初始化 SkillRuntime 单例并返回"""
    global _skill_runtime_instance
    _skill_runtime_instance = SkillRuntime(mcp_server, skills_base_dir, adapter)
    return _skill_runtime_instance
