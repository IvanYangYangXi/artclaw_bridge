"""
ue_version_adapter.py - UE 版本兼容适配器
============================================

阶段 3.5: 跨 UE 版本兼容层

宪法约束:
  - 系统架构设计 §2.5: 跨版本兼容 (UE 5.3 ~ 5.5+)
  - 开发路线图 §3.5: 记录不同版本 API 差异并自动适配

设计说明:
  - 在插件启动时检测 UE 引擎版本
  - 为 API 差异提供统一的适配接口
  - 使用函数查找表 (lookup table) 模式避免运行时条件分支
  - 若 UE API 不存在则 graceful fallback
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, Optional, Tuple

try:
    import unreal
except ImportError:
    unreal = None  # type: ignore

from claw_bridge_logger import UELogger


# ============================================================================
# 1. 版本检测
# ============================================================================

class UEVersion:
    """UE 引擎版本信息"""

    major: int = 5
    minor: int = 0
    patch: int = 0
    version_str: str = "unknown"

    @classmethod
    def detect(cls) -> "UEVersion":
        """从引擎获取版本号"""
        instance = cls()

        if unreal is None:
            instance.version_str = "mock-5.4.0"
            instance.major, instance.minor, instance.patch = 5, 4, 0
            return instance

        try:
            # UE 5.x 方式
            version_str = unreal.SystemLibrary.get_engine_version()
            instance.version_str = version_str

            # 解析 "5.4.1-12345678+++UE5+Release-5.4"
            parts = version_str.split("-")[0].split(".")
            instance.major = int(parts[0]) if len(parts) > 0 else 5
            instance.minor = int(parts[1]) if len(parts) > 1 else 0
            instance.patch = int(parts[2]) if len(parts) > 2 else 0
        except Exception as e:
            UELogger.mcp_error(f"Version detection failed: {e}")
            instance.major, instance.minor, instance.patch = 5, 4, 0

        return instance

    def __ge__(self, other: Tuple[int, int]) -> bool:
        return (self.major, self.minor) >= other

    def __lt__(self, other: Tuple[int, int]) -> bool:
        return (self.major, self.minor) < other

    def __repr__(self) -> str:
        return f"UE {self.major}.{self.minor}.{self.patch}"


# ============================================================================
# 2. API 适配表
# ============================================================================

def _get_world_54() -> Any:
    """UE 5.4+ : unreal.EditorLevelLibrary.get_editor_world()"""
    return unreal.EditorLevelLibrary.get_editor_world()


def _get_world_53() -> Any:
    """UE 5.3: unreal.EditorLevelLibrary.get_editor_world() (same, but fallback)"""
    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except AttributeError:
        # 极早期版本
        return unreal.EditorLevelLibrary.get_game_world()


def _get_selected_actors_54() -> list:
    """UE 5.4+"""
    return list(unreal.EditorUtilityLibrary.get_selected_assets())


def _get_selected_actors_53() -> list:
    """UE 5.3 fallback"""
    try:
        return list(unreal.EditorUtilityLibrary.get_selected_assets())
    except Exception:
        return []


def _spawn_actor_54(actor_class, location, rotation=None) -> Any:
    """UE 5.4+: 使用 EditorLevelLibrary"""
    loc = location if isinstance(location, unreal.Vector) else unreal.Vector(*location)
    rot = rotation if isinstance(rotation, unreal.Rotator) else unreal.Rotator(0, 0, 0)
    return unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, loc, rot)


def _spawn_actor_53(actor_class, location, rotation=None) -> Any:
    """UE 5.3 fallback"""
    return _spawn_actor_54(actor_class, location, rotation)


def _set_actor_label_54(actor, label: str) -> None:
    """UE 5.4+"""
    actor.set_actor_label(label)


def _set_actor_label_53(actor, label: str) -> None:
    """UE 5.3: set_actor_label 可能不存在"""
    try:
        actor.set_actor_label(label)
    except AttributeError:
        actor.set_folder_path(label)  # 退而求其次


def _focus_viewport_54(actor) -> None:
    """UE 5.4+: 聚焦视口到 Actor"""
    try:
        unreal.EditorLevelLibrary.set_selected_level_actors([actor])
        unreal.EditorLevelLibrary.pilot_level_actor(actor)
    except Exception:
        pass


def _focus_viewport_53(actor) -> None:
    """UE 5.3 fallback"""
    try:
        unreal.EditorLevelLibrary.set_selected_level_actors([actor])
    except Exception:
        pass


def _get_content_browser_selection_54() -> list:
    """UE 5.4+"""
    try:
        return list(unreal.EditorUtilityLibrary.get_selected_assets())
    except Exception:
        return []


def _get_content_browser_selection_53() -> list:
    """UE 5.3 fallback"""
    try:
        return list(unreal.EditorUtilityLibrary.get_selected_assets())
    except Exception:
        return []


# PCG (Procedural Content Generation) - 5.4+ only
def _has_pcg_support_54() -> bool:
    return hasattr(unreal, "PCGComponent")


def _has_pcg_support_53() -> bool:
    return False


# ============================================================================
# 3. Version Adapter 主类
# ============================================================================

class UEVersionAdapter:
    """
    UE 版本兼容适配器。

    根据检测到的引擎版本选择对应的 API 实现。
    所有 Skill / Tool 都应通过此适配器调用 UE API，而不是直接调用。

    宪法约束:
      - 系统架构设计 §2.5: 跨版本兼容层
    """

    _ADAPTERS_54 = {
        "get_world": _get_world_54,
        "get_selected_actors": _get_selected_actors_54,
        "spawn_actor": _spawn_actor_54,
        "set_actor_label": _set_actor_label_54,
        "focus_viewport": _focus_viewport_54,
        "get_content_browser_selection": _get_content_browser_selection_54,
        "has_pcg_support": _has_pcg_support_54,
    }

    _ADAPTERS_53 = {
        "get_world": _get_world_53,
        "get_selected_actors": _get_selected_actors_53,
        "spawn_actor": _spawn_actor_53,
        "set_actor_label": _set_actor_label_53,
        "focus_viewport": _focus_viewport_53,
        "get_content_browser_selection": _get_content_browser_selection_53,
        "has_pcg_support": _has_pcg_support_53,
    }

    def __init__(self):
        self.version = UEVersion.detect()
        self._adapters: Dict[str, Callable] = {}
        self._select_adapters()
        UELogger.info(f"UEVersionAdapter: detected {self.version}")

    def _select_adapters(self) -> None:
        """根据版本选择适配函数表"""
        if self.version >= (5, 4):
            self._adapters = dict(self._ADAPTERS_54)
        else:
            self._adapters = dict(self._ADAPTERS_53)

    def call(self, api_name: str, *args, **kwargs) -> Any:
        """
        通过适配器调用 UE API。

        用法:
            adapter.call("get_world")
            adapter.call("spawn_actor", actor_class, location)
        """
        fn = self._adapters.get(api_name)
        if fn is None:
            raise KeyError(f"Unknown adapter API: {api_name}. "
                          f"Available: {list(self._adapters.keys())}")
        return fn(*args, **kwargs)

    def get_world(self) -> Any:
        return self.call("get_world")

    def get_selected_actors(self) -> list:
        return self.call("get_selected_actors")

    def spawn_actor(self, actor_class, location, rotation=None) -> Any:
        return self.call("spawn_actor", actor_class, location, rotation)

    def set_actor_label(self, actor, label: str) -> None:
        self.call("set_actor_label", actor, label)

    def focus_viewport(self, actor) -> None:
        self.call("focus_viewport", actor)

    def has_pcg_support(self) -> bool:
        return self.call("has_pcg_support")

    def get_version_info(self) -> dict:
        """返回版本信息（用于 MCP Resource 暴露）"""
        return {
            "engine_version": self.version.version_str,
            "major": self.version.major,
            "minor": self.version.minor,
            "patch": self.version.patch,
            "supported_apis": list(self._adapters.keys()),
            "pcg_support": self.has_pcg_support(),
        }

    def register_adapter(self, api_name: str, fn: Callable,
                         min_version: Tuple[int, int] = (5, 3)) -> None:
        """
        注册自定义适配器。供 Skill 扩展。

        宪法约束:
          - 核心机制文档: Skill 可通过 adapter 注册版本适配
        """
        if self.version >= min_version:
            self._adapters[api_name] = fn
            UELogger.info(f"UEVersionAdapter: registered custom adapter '{api_name}' (>= {min_version})")


# ============================================================================
# 4. 全局单例 + MCP 注册
# ============================================================================

_adapter_instance: Optional[UEVersionAdapter] = None


def init_version_adapter(mcp_server=None) -> UEVersionAdapter:
    """初始化版本适配器"""
    global _adapter_instance
    _adapter_instance = UEVersionAdapter()

    # 注册 MCP Resource (如果提供了 server)
    if mcp_server is not None:
        mcp_server.register_resource(
            uri="unreal://engine/version",
            name="Engine Version",
            description="Current UE engine version and supported APIs",
            handler=lambda: json.dumps(_adapter_instance.get_version_info(), indent=2),
        )
        UELogger.info("UEVersionAdapter: registered MCP resource 'unreal://engine/version'")

    return _adapter_instance


def get_adapter() -> Optional[UEVersionAdapter]:
    return _adapter_instance
