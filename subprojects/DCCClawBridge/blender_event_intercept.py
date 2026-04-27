"""
blender_event_intercept.py — Blender 触发器执行层
=================================================

设计要点：
  - register_handlers() 注册的是模块级 _save_post_wrapper / _load_post_wrapper
  - wrapper 内部通过 sys.modules 动态查找最新实现，彻底规避 Blender
    "module changed on disk: reloading..." 导致函数 id 变化、旧引用失效的问题
  - 实现函数 _save_post_impl / _load_post_impl 可随 reload 更新，无需重新注册

公共逻辑来自 dcc_event_intercept_shared，本模块只实现：
  - Blender bpy.app.handlers 回调入口
  - Blender 特有通知函数 _notify_blender

支持的事件：
  - file.save.post : Blender 文件保存后（推荐：不阻断工作流，检查并通知）
  - file.open.post : 文件打开后自动检查

⚠️ 注意：
  - file.save.pre (save_pre) 不支持真正拦截（Blender 无法阻止保存），已移除
  - 通知弹窗必须用 bpy.app.timers 延迟到主线程执行

注册方式（在 blender_addon.py 的 register() 中调用）：
    from blender_event_intercept import register_handlers, unregister_handlers
    register_handlers()
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("artclaw.blender_intercept")


# ── 共享层懒加载 ──────────────────────────────────────────────────────────────

def _import_shared():
    try:
        import dcc_event_intercept_shared as _s
        return _s
    except ImportError:
        pass
    import json
    cfg_path = Path.home() / ".artclaw" / "config.json"
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            root = cfg.get("project_root", "")
            if root:
                core_dir = os.path.join(root, "subprojects", "DCCClawBridge", "core")
                addon_dir = os.path.dirname(os.path.abspath(__file__))
                for d in (core_dir, addon_dir):
                    if d not in sys.path:
                        sys.path.insert(0, d)
                import dcc_event_intercept_shared as _s
                return _s
        except Exception as e:
            print(f"[ArtClaw] _import_shared error: {e}")
    return None


# ── 通知 ──────────────────────────────────────────────────────────────────────

def _notify_blender(reason: str, mode: str) -> None:
    print(f"[ArtClaw] {reason}")
    if mode not in ("notify", "interactive"):
        return
    try:
        import bpy
        _snap = reason

        def _show_popup():
            try:
                def draw(self, context):
                    for line in _snap.split("\n"):
                        self.layout.label(text=line)
                bpy.context.window_manager.popup_menu(
                    draw, title="ArtClaw — 规范检查", icon="ERROR"
                )
            except Exception as e:
                print(f"[ArtClaw] popup_menu failed: {e}")

        bpy.app.timers.register(_show_popup, first_interval=0.1)
    except Exception as e:
        print(f"[ArtClaw] _notify_blender failed: {e}")


def _notify_blender_issues(issues: list) -> None:
    if not issues:
        return
    lines = ["以下对象/文件未通过规范检查："]
    for issue in issues:
        lines.append(f"• [{issue.get('tool', '?')}] {issue.get('reason', '')}")
    _notify_blender("\n".join(lines), "notify")


# ── 实现函数（随模块 reload 更新）────────────────────────────────────────────

def _save_post_impl(scene=None, depsgraph=None):
    try:
        import bpy
        blend_path = bpy.data.filepath or ""
        scene_name = scene.name if hasattr(scene, "name") else (
            bpy.context.scene.name if bpy.context.scene else ""
        )
        shared = _import_shared()
        if shared is None:
            print("[ArtClaw] _save_post_impl: shared module not found")
            return
        event_data = {
            "dcc_type": "blender",
            "event_type": "file.save",
            "timing": "post",
            "data": {
                "asset_path": blend_path,
                "asset_name": scene_name,
                "asset_class": "BlendFile",
                "scene_name": scene_name,
            },
        }
        result = shared._handle_post_event("file.save", event_data)
        if result.get("issues"):
            _notify_blender_issues(result["issues"])
    except Exception as e:
        import traceback
        print(f"[ArtClaw] _save_post_impl ERROR: {e}")
        traceback.print_exc()


def _load_post_impl(scene=None, depsgraph=None):
    try:
        import bpy
        blend_path = bpy.data.filepath or ""
        scene_name = scene.name if hasattr(scene, "name") else (
            bpy.context.scene.name if bpy.context.scene else ""
        )
        shared = _import_shared()
        if shared is None:
            return
        event_data = {
            "dcc_type": "blender",
            "event_type": "file.open",
            "timing": "post",
            "data": {
                "asset_path": blend_path,
                "asset_name": scene_name,
                "asset_class": "BlendFile",
                "scene_name": scene_name,
            },
        }
        result = shared._handle_post_event("file.open", event_data)
        if result.get("issues"):
            _notify_blender_issues(result["issues"])
    except Exception as e:
        import traceback
        print(f"[ArtClaw] _load_post_impl ERROR: {e}")
        traceback.print_exc()


# ── 稳定 Wrapper（注册进 handler 列表，函数对象不随 reload 变化）──────────────
# _WRAPPER_REGISTRY 存储在 sys.modules 的特殊 key 下，不在本模块命名空间内，
# 因此 Blender reload 本模块时不会被重置，wrapper 函数 id 始终稳定。

_REGISTRY_KEY = "__artclaw_blender_wrappers__"


def _get_or_create_wrappers():
    """返回持久化的 wrapper 函数对（跨 reload 保持同一 id）。"""
    registry = sys.modules.get(_REGISTRY_KEY)
    if registry is not None:
        return registry["save_post"], registry["load_post"]

    import bpy

    @bpy.app.handlers.persistent
    def save_post_wrapper(scene=None, depsgraph=None):
        mod = sys.modules.get("blender_event_intercept")
        if mod:
            mod._save_post_impl(scene, depsgraph)

    @bpy.app.handlers.persistent
    def load_post_wrapper(scene=None, depsgraph=None):
        mod = sys.modules.get("blender_event_intercept")
        if mod:
            mod._load_post_impl(scene, depsgraph)

    registry = {"save_post": save_post_wrapper, "load_post": load_post_wrapper}
    sys.modules[_REGISTRY_KEY] = registry  # 存到 sys.modules，跨 reload 存活
    return save_post_wrapper, load_post_wrapper


# ── 注册 / 反注册 ─────────────────────────────────────────────────────────────

def register_handlers() -> None:
    import traceback
    try:
        import bpy
        save_w, load_w = _get_or_create_wrappers()

        if save_w not in bpy.app.handlers.save_post:
            bpy.app.handlers.save_post.append(save_w)
            print("[ArtClaw] Registered: save_post wrapper")

        if load_w not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(load_w)
            print("[ArtClaw] Registered: load_post wrapper")

        print("[ArtClaw] Blender event handlers registered")
    except Exception as e:
        print(f"[ArtClaw] register_handlers FAILED: {e}")
        traceback.print_exc()


def unregister_handlers() -> None:
    try:
        import bpy
        save_w, load_w = _get_or_create_wrappers()
        for handler_list, fn in [
            (bpy.app.handlers.save_post, save_w),
            (bpy.app.handlers.load_post, load_w),
        ]:
            if fn in handler_list:
                handler_list.remove(fn)
        print("[ArtClaw] Blender event handlers unregistered")
    except Exception as e:
        print(f"[ArtClaw] unregister_handlers error: {e}")