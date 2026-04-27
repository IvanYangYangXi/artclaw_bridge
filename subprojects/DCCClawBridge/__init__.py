# ArtClaw Bridge - Blender Addon

bl_info = {
    "name": "ArtClaw Bridge",
    "author": "ArtClaw Team",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > ArtClaw",
    "description": "AI Agent bridge for Blender via ArtClaw",
    "category": "Interface",
}


def _ensure_path():
    import os, sys
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    core_dir = os.path.join(addon_dir, "core")
    for d in [addon_dir, core_dir]:
        if d not in sys.path:
            sys.path.insert(0, d)


def register():
    import sys, traceback
    _ensure_path()  # 确保 addon_dir + core_dir 已在 sys.path

    # 先注册触发器 handlers（在 blender_addon import 之前，路径最干净）
    try:
        for mod_name in list(sys.modules.keys()):
            if mod_name in ('blender_event_intercept', 'dcc_event_intercept_shared'):
                del sys.modules[mod_name]
        import blender_event_intercept as _bei
        _bei.register_handlers()
        print(f"[ArtClaw] Trigger handlers registered from: {_bei.__file__}")
    except Exception as e:
        print(f"[ArtClaw] register_handlers FAILED: {e}")
        traceback.print_exc()

    # 再注册 Blender 类
    from .blender_addon import register as _register
    _register()


def unregister():
    import traceback
    # 先反注册 handlers
    try:
        import blender_event_intercept as _bei
        _bei.unregister_handlers()
    except Exception as e:
        print(f"[ArtClaw] unregister_handlers error: {e}")
    # 再反注册 Blender 类
    from .blender_addon import unregister as _unregister
    _unregister()
