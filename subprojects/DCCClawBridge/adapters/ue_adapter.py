"""
ue_adapter.py - Unreal Engine 适配层实现
=========================================

Unreal Engine 5.x (Python 3.x, Game Thread)

所有 unreal.* 调用集中在此文件。
其余模块（UI / Bridge / Skill）通过 adapter 接口访问 UE 功能。
"""

from __future__ import annotations

import contextlib
import io
import logging
import sys
from typing import Any, Callable, Dict, List, Optional

from .base_adapter import BaseDCCAdapter

logger = logging.getLogger("artclaw.ue")


def _require_unreal():
    """延迟 import unreal 模块，仅在 Unreal Engine Python 运行时中可用"""
    try:
        import unreal
        return unreal
    except ImportError:
        raise RuntimeError("UEAdapter 只能在 Unreal Engine Python 运行时中使用")


class UEAdapter(BaseDCCAdapter):
    """Unreal Engine DCC 适配层"""

    def __init__(self):
        super().__init__()  # 初始化持久化命名空间

        # 初始化时尝试将 unreal 模块注入持久化命名空间
        try:
            import unreal
            self._exec_namespace["unreal"] = unreal
        except ImportError:
            pass

    # ── 基础信息 ──

    def get_software_name(self) -> str:
        return "unreal_engine"

    def get_software_version(self) -> str:
        unreal = _require_unreal()
        try:
            return unreal.SystemLibrary.get_engine_version()
        except Exception:
            pass
        try:
            return str(unreal.ENGINE_MINOR_VERSION)
        except Exception:
            pass
        try:
            return str(unreal.ENGINE_VERSION_MAJOR)
        except Exception:
            pass
        return "5.x"

    def get_python_version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # ── 生命周期 ──

    def on_startup(self) -> None:
        """UE 启动时调用 — 插件已有自己的启动逻辑，此处为扩展点"""
        logger.info("ArtClaw: UEAdapter started")
        print("UEAdapter started")

    def on_shutdown(self) -> None:
        """UE 关闭时调用"""
        logger.info("ArtClaw: UEAdapter shutdown")
        print("UEAdapter shutdown")

    # ── 主线程调度 ──

    def execute_on_main_thread(self, fn: Callable, *args) -> Any:
        """在 UE 游戏线程执行函数。
        UE Python 本身已运行在游戏线程，直接调用即可。
        """
        return fn(*args)

    def execute_deferred(self, fn: Callable, *args) -> None:
        """延迟到游戏线程空闲时执行。
        尝试使用 unreal.call_deferred；如果 API 不存在则直接执行。
        """
        unreal = _require_unreal()
        try:
            if args:
                unreal.call_deferred(lambda: fn(*args))
            else:
                unreal.call_deferred(fn)
        except AttributeError:
            # unreal.call_deferred 不可用，降级为直接调用
            fn(*args)

    # ── 上下文采集 ──

    def get_selected_objects(self) -> List[Dict]:
        unreal = _require_unreal()
        result = []

        # 尝试获取选中的 Asset（Content Browser）
        try:
            lib = unreal.EditorUtilityLibrary
            for asset in lib.get_selected_assets():
                result.append({
                    "name": asset.get_name(),
                    "type": "asset",
                    "class": asset.get_class().get_name(),
                    "path": str(asset.get_path_name()),
                })
        except Exception:
            pass

        # 尝试获取选中的 Actor（关卡视口）
        try:
            for actor in unreal.EditorLevelLibrary.get_selected_level_actors():
                result.append({
                    "name": actor.get_name(),
                    "type": "actor",
                    "class": actor.get_class().get_name(),
                    "path": str(actor.get_path_name()),
                })
        except Exception:
            pass

        return result

    def get_scene_info(self) -> Dict:
        unreal = _require_unreal()
        info: Dict[str, Any] = {"dcc": "unreal_engine"}

        # 当前关卡信息
        try:
            world = unreal.EditorLevelLibrary.get_editor_world()
            if world:
                info["current_level"] = world.get_name()
                info["level_path"] = str(world.get_path_name())
        except Exception:
            pass

        # 项目名称
        try:
            info["project_name"] = unreal.SystemLibrary.get_game_name()
        except Exception:
            pass

        # 关卡中 Actor 总数
        try:
            all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
            info["actor_count"] = len(all_actors)
        except Exception:
            pass

        return info

    def get_current_file(self) -> Optional[str]:
        unreal = _require_unreal()
        try:
            path = unreal.Paths.get_project_file_path()
            return path if path else None
        except Exception:
            return None

    # ── UI 集成 ──

    def get_main_window(self) -> Any:
        """UE 不暴露主窗口 Python API，返回 None"""
        return None

    def register_menu(self, menu_name: str, callback: Callable) -> None:
        """UE 菜单注册需借助 EditorUtilityWidget / ToolMenu，此处为扩展点，留空"""
        pass

    # ── 代码执行 ──

    def execute_code(self, code: str, context: Optional[Dict] = None) -> Dict:
        """
        在 UE 环境中执行 Python 代码。

        使用持久化命名空间：跨调用保持用户定义的变量。
        每次调用时 DCC 上下文变量会刷新为最新值。

        上下文变量:
            unreal  = unreal 模块
            S       = 当前选中对象列表
            W       = 当前项目文件路径
        """
        unreal = _require_unreal()

        # ── 持久化命名空间：刷新 DCC 上下文变量 ──
        ns = self._exec_namespace
        ns["__builtins__"] = __builtins__
        ns["unreal"] = unreal

        # 刷新选中对象和当前文件
        try:
            ns["S"] = self.get_selected_objects()
        except Exception:
            ns["S"] = []

        try:
            ns["W"] = self.get_current_file() or ""
        except Exception:
            ns["W"] = ""

        if context:
            ns.update(context)

        # 清除上次的 result
        ns.pop("result", None)

        # 捕获 stdout
        stdout_capture = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout_capture):
                exec(code, ns)  # noqa: S102

            output = stdout_capture.getvalue()
            result = ns.get("result")

            return {
                "success": True,
                "result": result,
                "error": None,
                "output": output,
            }

        except Exception as e:
            output = stdout_capture.getvalue()
            return {
                "success": False,
                "result": None,
                "error": f"{type(e).__name__}: {str(e)}",
                "output": output,
            }
