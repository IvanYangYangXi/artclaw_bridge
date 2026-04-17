"""
blender_qt_bridge.py - Blender 与 Qt 主线程桥接模块
===================================================

Qt6 (PySide6) 要求 QApplication 必须在主线程创建，否则初始化 platform
plugin 时访问 QPixmap 导致 EXCEPTION_ACCESS_VIOLATION 崩溃。

因此不使用独立 Qt 子线程，而是：
  1. 在 Blender 主线程（bpy.app.timers 回调）中创建 QApplication
  2. 用 bpy.app.timers 定期调用 QApplication.processEvents() 驱动事件循环
  3. bpy 操作本身就在主线程，无需跨线程调度

架构:
    Blender 主线程 (bpy)
    ┌───────────────────────────────────────┐
    │  bpy.app.timers (50ms interval)       │
    │  ├─ QApplication.processEvents()      │
    │  └─ Chat Panel / bridge_dcc.py 运行   │
    └───────────────────────────────────────┘
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.blender_adapter import BlenderAdapter

logger = logging.getLogger("artclaw.blender")


class BlenderQtBridge:
    """Blender ↔ Qt 主线程桥接器（无子线程）"""

    def __init__(self, adapter: "BlenderAdapter"):
        self._adapter = adapter
        self._qt_app = None
        self._chat_panel = None
        self._running: bool = False
        self._timer_registered: bool = False
        self._on_window_closed: Optional[Any] = None

    def start(self) -> None:
        """在主线程创建 QApplication + Chat Panel，并注册事件循环 timer"""
        if self._running:
            logger.warning("BlenderQtBridge 已在运行，跳过重复启动")
            return

        logger.info("BlenderQtBridge: 在主线程初始化 Qt")

        # 创建 QApplication（必须在主线程）
        self._init_qt_app()

        # 创建并显示 Chat Panel
        self._create_panel()

        # 注册 bpy.app.timers 驱动 Qt 事件循环
        self._register_timer()
        self._running = True

    def stop(self) -> None:
        """停止 Qt 事件泵 + 关闭面板"""
        if not self._running:
            return

        logger.info("BlenderQtBridge: 停止")
        self._running = False

        # 反注册 timer（停止事件泵）
        self._unregister_timer()

        # 关闭面板
        if self._chat_panel is not None:
            try:
                self._chat_panel.close()
            except Exception:
                pass
            self._chat_panel = None

        # 不要 quit QApplication — 可能有其他 addon 在用
        # self._qt_app 保留，下次 start() 复用

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Qt 初始化（主线程） ──

    def _init_qt_app(self) -> None:
        """获取或创建 QApplication（必须在主线程调用）"""
        try:
            from PySide6 import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets

        self._qt_app = QtWidgets.QApplication.instance()
        if self._qt_app is None:
            self._qt_app = QtWidgets.QApplication(sys.argv)

        # 应用完整 QSS 主题（独立 QApp 无默认样式）
        try:
            from artclaw_ui.theme import get_stylesheet, init_theme
            init_theme("blender")
            self._qt_app.setStyleSheet(get_stylesheet("blender"))
        except Exception as e:
            logger.warning("BlenderQtBridge: 应用 QSS 主题失败: %s", e)

    def _create_panel(self) -> None:
        """创建并显示 Chat Panel"""
        try:
            from artclaw_ui.chat_panel import show_chat_panel
            self._chat_panel = show_chat_panel(
                parent=None, adapter=self._adapter
            )
            self._chat_panel.destroyed.connect(self._on_panel_destroyed)
            logger.info("BlenderQtBridge: Chat Panel 已启动")
        except Exception as e:
            logger.error("BlenderQtBridge: 创建 Chat Panel 失败: %s", e)
            import traceback
            traceback.print_exc()

    # ── 面板管理 ──

    def show_panel(self) -> None:
        """显示或重新创建 Chat Panel（窗口关闭后可再次打开）"""
        if self._chat_panel is not None:
            try:
                self._chat_panel.show()
                self._chat_panel.raise_()
                self._chat_panel.activateWindow()
                return
            except RuntimeError:
                # C++ 对象已销毁
                self._chat_panel = None

        # 重新创建面板
        self._create_panel()

    def _on_panel_destroyed(self) -> None:
        """Chat Panel 被销毁时的清理回调"""
        logger.info("BlenderQtBridge: Chat Panel 已关闭")
        self._chat_panel = None
        # 清除 chat_panel 模块的单例引用
        try:
            import artclaw_ui.chat_panel as cp
            cp._panel_instance = None
        except Exception:
            pass
        # 通知外部
        if self._on_window_closed is not None:
            try:
                self._on_window_closed()
            except Exception:
                pass

    # ── Qt 事件泵（主线程 timer） ──

    def _pump_qt_events(self) -> Optional[float]:
        """
        bpy.app.timers 回调：在主线程驱动 Qt 事件循环。

        调用 processEvents() 处理所有待处理的 Qt 事件（UI 绘制、
        信号/槽、网络回调等），然后返回控制权给 Blender。

        返回 0.05（50ms 间隔 ≈ 20 fps UI 刷新）。
        """
        if not self._running:
            return None  # 返回 None 停止 timer

        if self._qt_app is not None:
            try:
                self._qt_app.processEvents()
            except Exception as e:
                logger.error("BlenderQtBridge: processEvents 异常: %s", e)

        return 0.05

    # ── Timer 管理 ──

    def _register_timer(self) -> None:
        """注册 bpy.app.timers 回调（幂等）"""
        if self._timer_registered:
            return
        try:
            import bpy
            if not bpy.app.timers.is_registered(self._pump_qt_events):
                bpy.app.timers.register(
                    self._pump_qt_events,
                    first_interval=0.05,
                    persistent=True,
                )
            self._timer_registered = True
        except Exception as e:
            logger.error("BlenderQtBridge: 注册 timer 失败: %s", e)

    def _unregister_timer(self) -> None:
        """反注册 bpy.app.timers 回调"""
        if not self._timer_registered:
            return
        try:
            import bpy
            if bpy.app.timers.is_registered(self._pump_qt_events):
                bpy.app.timers.unregister(self._pump_qt_events)
            self._timer_registered = False
        except Exception as e:
            logger.error("BlenderQtBridge: 反注册 timer 失败: %s", e)
