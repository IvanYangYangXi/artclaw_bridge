"""
ArtClaw Bridge — 通用 DCC 插件入口
====================================

此文件同时作为 Blender addon / Substance Painter plugin / Substance Designer plugin 的入口。
根据运行环境自动分发到对应的启动逻辑。

Blender: 需要 bl_info 字面量（AST 扫描）+ register()/unregister()
SP:      需要 start_plugin()/close_plugin()
SD:      需要 initializeSDPlugin()/uninitializeSDPlugin()
"""

# ---------------------------------------------------------------------------
# Blender addon 元数据（bl_info 必须作为字面量定义，Blender AST 扫描不执行 import）
# ---------------------------------------------------------------------------
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
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

def register():
    _ensure_path()
    from .blender_addon import register as _register
    _register()


def unregister():
    from .blender_addon import unregister as _unregister
    _unregister()


# ---------------------------------------------------------------------------
# Substance Painter
# ---------------------------------------------------------------------------

def start_plugin():
    _ensure_path()
    from sp_plugin import start_plugin as _start
    _start()


def close_plugin():
    try:
        from sp_plugin import close_plugin as _close
        _close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Substance Designer
# ---------------------------------------------------------------------------

def initializeSDPlugin():
    _ensure_path()
    from sd_plugin import initializeSDPlugin as _init
    _init()


def uninitializeSDPlugin():
    try:
        from sd_plugin import uninitializeSDPlugin as _uninit
        _uninit()
    except Exception:
        pass
