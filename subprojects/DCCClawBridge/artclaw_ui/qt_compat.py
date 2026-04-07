"""
qt_compat.py - PySide2/PySide6 兼容层
========================================

所有 artclaw_ui 模块统一从此文件导入 Qt 模块。
优先 PySide2（Maya/Max 内置），fallback PySide6（Blender pip 安装）。
"""

from __future__ import annotations

try:
    from PySide2 import QtWidgets, QtCore, QtGui  # noqa: F401
    from PySide2.QtWidgets import *  # noqa: F401, F403
    from PySide2.QtCore import *  # noqa: F401, F403
    from PySide2.QtCore import Qt, Slot, Signal, QTimer, QSize, QPoint, QUrl  # noqa: F401
    from PySide2.QtGui import *  # noqa: F401, F403
    QT_BINDING = "PySide2"
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui  # noqa: F401
    from PySide6.QtWidgets import *  # noqa: F401, F403
    from PySide6.QtCore import *  # noqa: F401, F403
    from PySide6.QtCore import Qt, Slot, Signal, QTimer, QSize, QPoint, QUrl  # noqa: F401
    from PySide6.QtGui import *  # noqa: F401, F403
    QT_BINDING = "PySide6"

HAS_QT = True
