"""
tool_event_bridge.py - UE ↔ Tool Manager 事件桥接 (Python 补充层)
===================================================================

C++ UEAgentSubsystem::HandleObjectPreSave 已经通过同步 HTTP POST
将 pre-save 事件发送到 Tool Manager 并处理拦截。

本模块作为补充层，为 Python 端提供:
  - post-save / import / delete / level 事件的异步转发
  - Python 侧的事件监听回调

注意: pre-save 事件由 C++ 同步处理（可以阻断），Python 侧不再
发送 pre-save 事件避免重复。

生命周期:
  - init_tool_event_bridge() 在 MCP Server 启动后调用
  - shutdown_tool_event_bridge() 在编辑器关闭时调用
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, Optional
from urllib import request as urllib_request
from urllib.error import URLError

import unreal

logger = logging.getLogger("artclaw.tool_event_bridge")

# Tool Manager 默认地址
_TOOL_MANAGER_URL = "http://localhost:9876"

# 全局实例
_bridge: Optional[ToolEventBridge] = None


class ToolEventBridge:
    """将 UE C++ delegate 事件转发到 Tool Manager TriggerEngine。"""

    def __init__(self, tool_manager_url: str = _TOOL_MANAGER_URL):
        self._url = tool_manager_url.rstrip("/")
        self._registered = False
        self._subsystem = None
        # 回调引用，防止被 GC
        self._callbacks: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """绑定 UEAgentSubsystem delegate，开始监听事件。"""
        if self._registered:
            return True

        try:
            self._subsystem = unreal.get_editor_subsystem(unreal.UEAgentSubsystem)
        except Exception:
            self._subsystem = None

        if not self._subsystem:
            logger.warning("UEAgentSubsystem not available, tool event bridge disabled")
            return False

        try:
            # --- asset.save (post only — pre 由 C++ 同步处理) ---
            def on_asset_post_save(asset_path, success):
                self._forward("asset.save", "post", {
                    "asset_path": str(asset_path),
                    "success": bool(success),
                })

            self._subsystem.on_asset_post_save.add_callable(on_asset_post_save)
            self._callbacks["asset_post_save"] = on_asset_post_save

            # --- asset.import ---
            def on_asset_imported(asset_path, asset_class):
                self._forward("asset.import", "post", {
                    "asset_path": str(asset_path),
                    "asset_class": str(asset_class),
                })

            self._subsystem.on_asset_imported.add_callable(on_asset_imported)
            self._callbacks["asset_imported"] = on_asset_imported

            # --- asset.delete ---
            def on_asset_pre_delete(asset_path):
                self._forward("asset.delete", "pre", {
                    "asset_path": str(asset_path),
                })

            self._subsystem.on_asset_pre_delete.add_callable(on_asset_pre_delete)
            self._callbacks["asset_pre_delete"] = on_asset_pre_delete

            # --- level.save ---
            def on_level_pre_save(level_path):
                self._forward("level.save", "pre", {
                    "level_path": str(level_path),
                })

            def on_level_post_save(level_path, success):
                self._forward("level.save", "post", {
                    "level_path": str(level_path),
                    "success": bool(success),
                })

            self._subsystem.on_level_pre_save.add_callable(on_level_pre_save)
            self._subsystem.on_level_post_save.add_callable(on_level_post_save)
            self._callbacks["level_pre_save"] = on_level_pre_save
            self._callbacks["level_post_save"] = on_level_post_save

            # --- level.load ---
            def on_level_loaded(level_path):
                self._forward("level.load", "post", {
                    "level_path": str(level_path),
                })

            self._subsystem.on_level_loaded.add_callable(on_level_loaded)
            self._callbacks["level_loaded"] = on_level_loaded

            self._registered = True
            logger.info("Tool event bridge started — 5 delegate callbacks registered (pre-save handled by C++)")
            return True

        except Exception as e:
            logger.error(f"Failed to register delegate callbacks: {e}")
            return False

    def stop(self) -> None:
        """解绑所有 delegate 回调。"""
        if not self._registered or not self._subsystem:
            return

        try:
            if "asset_post_save" in self._callbacks:
                self._subsystem.on_asset_post_save.remove_callable(self._callbacks["asset_post_save"])
            if "asset_imported" in self._callbacks:
                self._subsystem.on_asset_imported.remove_callable(self._callbacks["asset_imported"])
            if "asset_pre_delete" in self._callbacks:
                self._subsystem.on_asset_pre_delete.remove_callable(self._callbacks["asset_pre_delete"])
            if "level_pre_save" in self._callbacks:
                self._subsystem.on_level_pre_save.remove_callable(self._callbacks["level_pre_save"])
            if "level_post_save" in self._callbacks:
                self._subsystem.on_level_post_save.remove_callable(self._callbacks["level_post_save"])
            if "level_loaded" in self._callbacks:
                self._subsystem.on_level_loaded.remove_callable(self._callbacks["level_loaded"])
        except Exception as e:
            logger.warning(f"Error unregistering callbacks: {e}")

        self._callbacks.clear()
        self._registered = False
        logger.info("Tool event bridge stopped")

    # ------------------------------------------------------------------
    # 事件转发
    # ------------------------------------------------------------------

    def _forward(self, event_type: str, timing: str, data: Dict[str, Any]) -> None:
        """将事件转发到 Tool Manager（后台线程，非阻塞）。"""
        payload = {
            "dcc_type": "ue5",
            "event_type": event_type,
            "timing": timing,
            "data": data,
        }
        # 后台线程发 HTTP，不阻塞 UE 主线程
        t = threading.Thread(
            target=self._post_event,
            args=(payload,),
            daemon=True,
            name=f"ToolEvent-{event_type}-{timing}",
        )
        t.start()

    def _post_event(self, payload: Dict[str, Any]) -> None:
        """HTTP POST 到 Tool Manager /api/v1/dcc-events。"""
        url = f"{self._url}/api/v1/dcc-events"
        body = json.dumps(payload).encode("utf-8")

        req = urllib_request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib_request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                trigger_data = result.get("data", {})

                if trigger_data.get("triggered"):
                    logger.info(
                        "Event %s(%s) triggered %d rules",
                        payload["event_type"],
                        payload["timing"],
                        trigger_data.get("rules_executed", 0),
                    )

        except URLError:
            # Tool Manager 未运行，静默跳过
            pass
        except Exception as e:
            logger.debug("Event forward failed: %s", e)


# ==================================================================
# 公开 API
# ==================================================================

def init_tool_event_bridge(tool_manager_url: str = _TOOL_MANAGER_URL) -> Optional[ToolEventBridge]:
    """初始化 Tool Event Bridge（由 mcp_server.py 启动后调用）。"""
    global _bridge

    if _bridge is not None:
        return _bridge

    _bridge = ToolEventBridge(tool_manager_url)
    if _bridge.start():
        return _bridge
    else:
        _bridge = None
        return None


def shutdown_tool_event_bridge() -> None:
    """关闭 Tool Event Bridge。"""
    global _bridge
    if _bridge:
        _bridge.stop()
        _bridge = None
