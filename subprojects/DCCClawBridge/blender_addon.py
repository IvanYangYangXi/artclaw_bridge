"""
blender_addon.py - Blender Addon 入口文件
==========================================

通过 Blender 的 addon 系统加载，在 3D 视口侧栏提供 ArtClaw 面板。

安装方式：
    1. 在 Blender 中 Edit → Preferences → Add-ons → Install
    2. 选择此文件或包含此文件的 zip
    3. 勾选启用 "Interface: ArtClaw Bridge"

面板位置：View3D → Sidebar (N 键) → ArtClaw
"""

from __future__ import annotations

import logging

logger = logging.getLogger("artclaw.blender")


# ── Blender Addon 元信息 ──

bl_info = {
    "name": "ArtClaw Bridge",
    "author": "ArtClaw Team",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > ArtClaw",
    "description": "AI Agent bridge for Blender via ArtClaw",
    "category": "Interface",
}


# ── 全局状态 ──

_global_state = {
    "adapter": None,
    "bridge": None,
    "running": False,
}


# ── Blender 延迟 import ──

def _require_blender():
    """延迟 import bpy"""
    import bpy
    return bpy


# ── Operators ──

class ARTCLAW_OT_StartBridge:
    """启动 ArtClaw Bridge 的 Operator"""

    bl_idname = "artclaw.start_bridge"
    bl_label = "Start ArtClaw"
    bl_description = "Start ArtClaw AI Bridge and Chat Panel"

    def execute(self, context):
        """启动 adapter + Qt bridge，或重新打开已关闭的面板"""
        if _global_state["running"]:
            # Bridge 已运行 — 尝试重新显示面板
            bridge = _global_state["bridge"]
            if bridge is not None:
                bridge.show_panel()
                self.report({"INFO"}, "ArtClaw Chat Panel reopened")
            else:
                self.report({"WARNING"}, "ArtClaw Bridge is running but bridge reference lost")
            return {"FINISHED"}

        try:
            # 创建并启动 adapter
            from adapters.blender_adapter import BlenderAdapter
            adapter = BlenderAdapter()
            adapter.on_startup()

            # 创建并启动 Qt bridge
            from blender_qt_bridge import BlenderQtBridge
            bridge = BlenderQtBridge(adapter)
            bridge.start()

            # 保存到全局状态
            _global_state["adapter"] = adapter
            _global_state["bridge"] = bridge
            _global_state["running"] = True

            self.report({"INFO"}, "ArtClaw Bridge started")
            logger.info("ArtClaw Bridge started successfully")

        except Exception as e:
            self.report({"ERROR"}, f"Failed to start ArtClaw Bridge: {e}")
            logger.error("ArtClaw Bridge startup failed: %s", e, exc_info=True)
            return {"CANCELLED"}

        return {"FINISHED"}


class ARTCLAW_OT_StopBridge:
    """停止 ArtClaw Bridge 的 Operator"""

    bl_idname = "artclaw.stop_bridge"
    bl_label = "Stop ArtClaw"
    bl_description = "Stop ArtClaw AI Bridge and Chat Panel"

    def execute(self, context):
        """停止 bridge + adapter"""
        if not _global_state["running"]:
            self.report({"WARNING"}, "ArtClaw Bridge is not running")
            return {"CANCELLED"}

        try:
            # 停止 Qt bridge
            bridge = _global_state["bridge"]
            if bridge is not None:
                bridge.stop()

            # 停止 adapter
            adapter = _global_state["adapter"]
            if adapter is not None:
                adapter.on_shutdown()

            # 清理全局状态
            _global_state["adapter"] = None
            _global_state["bridge"] = None
            _global_state["running"] = False

            self.report({"INFO"}, "ArtClaw Bridge stopped")
            logger.info("ArtClaw Bridge stopped")

        except Exception as e:
            self.report({"ERROR"}, f"Failed to stop ArtClaw Bridge: {e}")
            logger.error("ArtClaw Bridge stop failed: %s", e, exc_info=True)
            return {"CANCELLED"}

        return {"FINISHED"}


# ── Panel ──

class ARTCLAW_PT_MainPanel:
    """ArtClaw 侧栏面板"""

    bl_label = "ArtClaw"
    bl_idname = "ARTCLAW_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ArtClaw"

    def draw(self, context):
        """绘制面板 UI"""
        layout = self.layout

        if _global_state["running"]:
            # 运行中：显示状态 + 打开面板 / 停止按钮
            box = layout.box()
            box.label(text="Status: Running", icon="CHECKMARK")

            # 显示/重新打开面板按钮
            row = layout.row(align=True)
            row.operator(
                ARTCLAW_OT_StartBridge.bl_idname,
                text="Show Chat Panel",
                icon="WINDOW",
            )
            row.operator(
                ARTCLAW_OT_StopBridge.bl_idname,
                icon="CANCEL",
            )
        else:
            # 未运行：显示启动按钮
            box = layout.box()
            box.label(text="Status: Disconnected", icon="ERROR")
            layout.operator(
                ARTCLAW_OT_StartBridge.bl_idname,
                icon="PLAY",
            )


# ── 需要 bpy 的类注册（延迟定义基类） ──

def _build_classes():
    """
    在 register() 时构建最终的 Blender 类。

    Blender 要求 Operator 继承 bpy.types.Operator、
    Panel 继承 bpy.types.Panel，
    这些基类只在 Blender 环境中可用。
    """
    bpy = _require_blender()

    # 动态创建继承 bpy 基类的最终类
    classes = []

    # StartBridge Operator
    start_op = type(
        "ARTCLAW_OT_StartBridge",
        (bpy.types.Operator, ARTCLAW_OT_StartBridge),
        {},
    )
    classes.append(start_op)

    # StopBridge Operator
    stop_op = type(
        "ARTCLAW_OT_StopBridge",
        (bpy.types.Operator, ARTCLAW_OT_StopBridge),
        {},
    )
    classes.append(stop_op)

    # Main Panel
    main_panel = type(
        "ARTCLAW_PT_MainPanel",
        (bpy.types.Panel, ARTCLAW_PT_MainPanel),
        {},
    )
    classes.append(main_panel)

    return classes


# 缓存已构建的类列表
_registered_classes: list = []


def register():
    """Blender addon 注册入口"""
    global _registered_classes
    bpy = _require_blender()

    _registered_classes = _build_classes()
    for cls in _registered_classes:
        bpy.utils.register_class(cls)

    logger.info("ArtClaw Bridge addon registered")


def unregister():
    """Blender addon 反注册入口"""
    global _registered_classes
    bpy = _require_blender()

    # 如果正在运行，先停止
    if _global_state["running"]:
        try:
            bridge = _global_state["bridge"]
            if bridge is not None:
                bridge.stop()
            adapter = _global_state["adapter"]
            if adapter is not None:
                adapter.on_shutdown()
        except Exception as e:
            logger.error("ArtClaw: Error during addon unregister cleanup: %s", e)
        finally:
            _global_state["adapter"] = None
            _global_state["bridge"] = None
            _global_state["running"] = False

    # 反注册触发器事件 handlers
    try:
        from blender_event_intercept import unregister_handlers
        unregister_handlers()
    except Exception as e:
        logger.warning("ArtClaw: Failed to unregister event handlers: %s", e)

    # 反注册 Blender 类
    for cls in reversed(_registered_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    _registered_classes.clear()

    logger.info("ArtClaw Bridge addon unregistered")
