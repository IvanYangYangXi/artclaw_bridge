"""
theme.py - ArtClaw UI 主题管理
================================

DCC 配色适配（Maya / Max / 通用暗色）。
包含颜色常量、DCC_THEMES 字典、按钮样式辅助函数以及全局 QSS 生成器。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Sender / message-type colors
# ---------------------------------------------------------------------------

SENDER_USER = "#3ADA8C"
SENDER_ASSISTANT = "#66BFFF"
SENDER_SYSTEM = "#8C8C8C"
SENDER_THINKING = "#A699D9"
SENDER_STREAMING = "#80B3E6"
SENDER_TOOL_CALL = "#D9A64D"
SENDER_TOOL_RESULT = "#66BF80"
SENDER_TOOL_ERROR = "#E65959"
SENDER_TOOL_STATUS = "#A68C59"

# ---------------------------------------------------------------------------
# Connection status
# ---------------------------------------------------------------------------

STATUS_CONNECTED = "#33CC33"
STATUS_DISCONNECTED = "#999999"

# ---------------------------------------------------------------------------
# Plan step colors
# ---------------------------------------------------------------------------

PLAN_PENDING = "#999999"
PLAN_RUNNING = "#FFBA33"
PLAN_DONE = "#33CC33"
PLAN_FAILED = "#E64D4D"
PLAN_SKIPPED = "#666666"

# ---------------------------------------------------------------------------
# Risk colors
# ---------------------------------------------------------------------------

RISK_HIGH = "#E63333"
RISK_MEDIUM = "#E6B333"

# ---------------------------------------------------------------------------
# Layer / source badge colors
# ---------------------------------------------------------------------------

BADGE_OFFICIAL = "#33B34D"
BADGE_MARKETPLACE = "#4D80E6"
BADGE_USER = "#CC9933"
BADGE_CUSTOM = "#994D99"
BADGE_PLATFORM = "#806699"

# ---------------------------------------------------------------------------
# Install status colors
# ---------------------------------------------------------------------------

INSTALL_INSTALLED = "#33A680"
INSTALL_NOT_INSTALLED = "#994D66"

# ---------------------------------------------------------------------------
# DCC full theme dicts
# ---------------------------------------------------------------------------

DCC_THEMES: dict[str, dict[str, str]] = {
    "maya": {
        # Blender-inspired dark theme — 低对比度、柔和暗色
        "bg_primary": "#303030",
        "bg_secondary": "#3D3D3D",
        "bg_tertiary": "#282828",
        "bg_input": "#353535",
        "bg_message": "#252525",
        "bg_message_user": "#2A3530",
        "bg_message_assistant": "#282C38",
        "bg_message_tool": "#38321E",
        "bg_code": "#1D1D1D",
        "bg_card": "#353535",
        "bg_card_header": "#3A3A3A",
        "bg_hover": "#4A4A4A",
        "accent": "#4B7BAC",
        "accent_hover": "#5B8BBC",
        "accent_pressed": "#3B6B9C",
        "text": "#E0E0E0",
        "text_dim": "#9A9A9A",
        "text_muted": "#686868",
        "text_user": "#8CC5FF",
        "text_assistant": "#B8B8B8",
        "text_system": "#808080",
        "border": "#484848",
        "border_focus": "#5B8BBC",
        "scrollbar": "#484848",
        "scrollbar_hover": "#5A5A5A",
        "status_ok": "#71B345",
        "status_error": "#E05555",
        "status_warn": "#DBA040",
        "btn_primary_bg": "#4B7BAC",
        "btn_primary_hover": "#5B8BBC",
        "btn_danger_bg": "#A04040",
        "btn_danger_hover": "#B85050",
        "btn_secondary_bg": "#454545",
        "btn_secondary_hover": "#525252",
    },
    "max": {
        "bg_primary": "#3F3F3F",
        "bg_secondary": "#505050",
        "bg_tertiary": "#353535",
        "bg_input": "#3F3F3F",
        "bg_message": "#2D2D2D",
        "bg_message_user": "#2E3D35",
        "bg_message_assistant": "#2B3040",
        "bg_message_tool": "#3D3520",
        "bg_code": "#1E1E1E",
        "bg_card": "#3A3A3A",
        "bg_card_header": "#444444",
        "bg_hover": "#555555",
        "accent": "#4A90D9",
        "accent_hover": "#5AA0E9",
        "accent_pressed": "#3A80C9",
        "text": "#E0E0E0",
        "text_dim": "#999999",
        "text_muted": "#666666",
        "text_user": "#7CB3F2",
        "text_assistant": "#C0C0C0",
        "text_system": "#999999",
        "border": "#606060",
        "border_focus": "#5AA0E9",
        "scrollbar": "#606060",
        "scrollbar_hover": "#707070",
        "status_ok": "#4CAF50",
        "status_error": "#F44336",
        "status_warn": "#FF9800",
        "btn_primary_bg": "#4A90D9",
        "btn_primary_hover": "#5AA0E9",
        "btn_danger_bg": "#A64242",
        "btn_danger_hover": "#C05050",
        "btn_secondary_bg": "#555555",
        "btn_secondary_hover": "#656565",
    },
    "generic": {
        "bg_primary": "#383838",
        "bg_secondary": "#464646",
        "bg_tertiary": "#2E2E2E",
        "bg_input": "#383838",
        "bg_message": "#282828",
        "bg_message_user": "#2E3D35",
        "bg_message_assistant": "#2B3040",
        "bg_message_tool": "#3D3520",
        "bg_code": "#1E1E1E",
        "bg_card": "#363636",
        "bg_card_header": "#404040",
        "bg_hover": "#4C4C4C",
        "accent": "#5080B0",
        "accent_hover": "#6090C0",
        "accent_pressed": "#4070A0",
        "text": "#DDDDDD",
        "text_dim": "#888888",
        "text_muted": "#666666",
        "text_user": "#7CB3F2",
        "text_assistant": "#BBBBBB",
        "text_system": "#888888",
        "border": "#555555",
        "border_focus": "#6090C0",
        "scrollbar": "#555555",
        "scrollbar_hover": "#666666",
        "status_ok": "#4CAF50",
        "status_error": "#F44336",
        "status_warn": "#FF9800",
        "btn_primary_bg": "#5080B0",
        "btn_primary_hover": "#6090C0",
        "btn_danger_bg": "#A64242",
        "btn_danger_hover": "#C05050",
        "btn_secondary_bg": "#505050",
        "btn_secondary_hover": "#606060",
    },
}


def get_theme(dcc_name: str = "maya") -> dict[str, str]:
    """获取指定 DCC 的主题配色字典"""
    return DCC_THEMES.get(dcc_name.lower(), DCC_THEMES["maya"])


# ---------------------------------------------------------------------------
# 模块级默认主题（供 from artclaw_ui.theme import COLORS 使用）
# ---------------------------------------------------------------------------
# 初始值为 maya 主题；init_theme() 可按实际 DCC 重新设置。

# 将独立颜色常量合并到 COLORS 中，使模块统一通过 COLORS["key"] 访问
_EXTRA_COLORS: dict[str, str] = {
    # Skill 层级
    "layer_official": BADGE_OFFICIAL,
    "layer_marketplace": BADGE_MARKETPLACE,
    "layer_user": BADGE_USER,
    "layer_custom": BADGE_CUSTOM,
    "layer_platform": BADGE_PLATFORM,
    # 安装状态
    "install_installed": INSTALL_INSTALLED,
    "install_not_installed": INSTALL_NOT_INSTALLED,
    # Sender / 消息类型
    "sender_user": SENDER_USER,
    "sender_assistant": SENDER_ASSISTANT,
    "sender_system": SENDER_SYSTEM,
    "sender_thinking": SENDER_THINKING,
    "sender_streaming": SENDER_STREAMING,
    "sender_tool_call": SENDER_TOOL_CALL,
    "sender_tool_result": SENDER_TOOL_RESULT,
    "sender_tool_error": SENDER_TOOL_ERROR,
    "sender_tool_status": SENDER_TOOL_STATUS,
    # 连接状态
    "status_connected": STATUS_CONNECTED,
    "status_disconnected": STATUS_DISCONNECTED,
    # Plan
    "plan_pending": PLAN_PENDING,
    "plan_running": PLAN_RUNNING,
    "plan_done": PLAN_DONE,
    "plan_failed": PLAN_FAILED,
    "plan_skipped": PLAN_SKIPPED,
    # 风险
    "risk_high": RISK_HIGH,
    "risk_medium": RISK_MEDIUM,
}

COLORS: dict[str, str] = {**DCC_THEMES["maya"], **_EXTRA_COLORS}


def init_theme(dcc_name: str = "maya") -> dict[str, str]:
    """根据当前 DCC 初始化模块级 COLORS 并返回。应在插件启动时调用一次。"""
    global COLORS
    COLORS = {**get_theme(dcc_name), **_EXTRA_COLORS}
    return COLORS


# ---------------------------------------------------------------------------
# Button style helpers (inline QSS snippets)
# ---------------------------------------------------------------------------

def btn_style_primary(t: dict[str, str]) -> str:
    """主要按钮 QSS"""
    return (
        f"QPushButton{{background:{t['btn_primary_bg']};color:#FFF;border:none;"
        f"border-radius:4px;padding:4px 12px;font-weight:bold;}}"
        f"QPushButton:hover{{background:{t['btn_primary_hover']};}}"
        f"QPushButton:pressed{{background:{t['accent_pressed']};}}"
        f"QPushButton:disabled{{background:{t['text_muted']};color:{t['text_dim']};}}"
    )


def btn_style_danger(t: dict[str, str]) -> str:
    """危险按钮 QSS（删除/清除等）"""
    return (
        f"QPushButton{{background:{t['btn_danger_bg']};color:#FFF;border:none;"
        f"border-radius:4px;padding:4px 12px;}}"
        f"QPushButton:hover{{background:{t['btn_danger_hover']};}}"
        f"QPushButton:disabled{{background:{t['text_muted']};color:{t['text_dim']};}}"
    )


def btn_style_secondary(t: dict[str, str]) -> str:
    """次要按钮 QSS"""
    return (
        f"QPushButton{{background:{t['btn_secondary_bg']};color:{t['text']};"
        f"border:1px solid {t['border']};border-radius:4px;padding:4px 12px;}}"
        f"QPushButton:hover{{background:{t['btn_secondary_hover']};}}"
        f"QPushButton:disabled{{color:{t['text_dim']};}}"
    )


def btn_style_toggle(t: dict[str, str], active: bool = False) -> str:
    """切换按钮 QSS，active=True 时显示强调色"""
    bg = t["accent"] if active else t["btn_secondary_bg"]
    bg_h = t["accent_hover"] if active else t["btn_secondary_hover"]
    return (
        f"QPushButton{{background:{bg};color:#FFF;"
        f"border:1px solid {t['border']};border-radius:4px;padding:4px 10px;}}"
        f"QPushButton:hover{{background:{bg_h};}}"
    )


# ---------------------------------------------------------------------------
# Full-app QSS stylesheet
# ---------------------------------------------------------------------------

def get_stylesheet(dcc_name: str = "maya") -> str:
    """返回整个 App 的 QSS 字符串。dcc_name: 'maya'|'max'|'generic'"""
    t = get_theme(dcc_name)
    # fmt: off
    return f"""
QWidget{{background:{t['bg_primary']};color:{t['text']};
    font-family:"Microsoft YaHei","PingFang SC","Segoe UI",Arial,sans-serif;font-size:13px;}}
QMainWindow,QDialog{{background:{t['bg_primary']};}}
QGroupBox{{border:1px solid {t['border']};border-radius:4px;margin-top:8px;
    padding-top:6px;color:{t['text_dim']};font-size:12px;}}
QGroupBox::title{{subcontrol-origin:margin;left:8px;padding:0 4px;}}
QLabel{{background:transparent;color:{t['text']};}}
QPushButton{{background:{t['btn_secondary_bg']};color:{t['text']};
    border:1px solid {t['border']};border-radius:4px;padding:4px 10px;min-height:22px;}}
QPushButton:hover{{background:{t['btn_secondary_hover']};border-color:{t['border_focus']};}}
QPushButton:pressed{{background:{t['accent_pressed']};}}
QPushButton:disabled{{color:{t['text_muted']};background:{t['bg_secondary']};}}
QPushButton[class="primary"]{{background:{t['btn_primary_bg']};color:#FFF;border:none;font-weight:bold;}}
QPushButton[class="primary"]:hover{{background:{t['btn_primary_hover']};}}
QPushButton[class="danger"]{{background:{t['btn_danger_bg']};color:#FFF;border:none;}}
QPushButton[class="danger"]:hover{{background:{t['btn_danger_hover']};}}
QPushButton[class="icon"]{{background:transparent;border:none;padding:2px;min-width:24px;min-height:24px;}}
QPushButton[class="icon"]:hover{{background:{t['bg_hover']};border-radius:3px;}}
QLineEdit{{background:{t['bg_input']};color:{t['text']};border:1px solid {t['border']};
    border-radius:4px;padding:4px 8px;selection-background-color:{t['accent']};}}
QLineEdit:focus{{border-color:{t['border_focus']};}}
QLineEdit:disabled{{color:{t['text_dim']};background:{t['bg_secondary']};}}
QTextEdit,QPlainTextEdit{{background:{t['bg_input']};color:{t['text']};
    border:1px solid {t['border']};border-radius:4px;padding:4px;
    selection-background-color:{t['accent']};}}
QTextEdit:focus,QPlainTextEdit:focus{{border-color:{t['border_focus']};}}
QComboBox{{background:{t['bg_input']};color:{t['text']};border:1px solid {t['border']};
    border-radius:4px;padding:3px 8px;min-height:22px;}}
QComboBox:hover{{border-color:{t['border_focus']};}}
QComboBox::drop-down{{border:none;width:20px;}}
QComboBox QAbstractItemView{{background:{t['bg_secondary']};color:{t['text']};
    border:1px solid {t['border']};selection-background-color:{t['accent']};outline:none;}}
QListWidget,QTreeWidget,QTableWidget{{background:{t['bg_message']};color:{t['text']};
    border:1px solid {t['border']};border-radius:4px;outline:none;}}
QListWidget::item,QTreeWidget::item{{padding:3px 6px;}}
QListWidget::item:hover,QTreeWidget::item:hover{{background:{t['bg_hover']};}}
QListWidget::item:selected,QTreeWidget::item:selected{{background:{t['accent']};color:#FFF;}}
QHeaderView::section{{background:{t['bg_secondary']};color:{t['text_dim']};
    border:none;border-right:1px solid {t['border']};padding:4px 8px;font-size:12px;}}
QScrollArea{{border:none;background:transparent;}}
QScrollBar:vertical{{background:{t['bg_message']};width:8px;border-radius:4px;}}
QScrollBar::handle:vertical{{background:{t['scrollbar']};border-radius:4px;min-height:24px;}}
QScrollBar::handle:vertical:hover{{background:{t['scrollbar_hover']};}}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
QScrollBar:horizontal{{background:{t['bg_message']};height:8px;border-radius:4px;}}
QScrollBar::handle:horizontal{{background:{t['scrollbar']};border-radius:4px;min-width:24px;}}
QScrollBar::handle:horizontal:hover{{background:{t['scrollbar_hover']};}}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0;}}
QTabWidget::pane{{border:1px solid {t['border']};background:{t['bg_primary']};}}
QTabBar::tab{{background:{t['bg_secondary']};color:{t['text_dim']};border:1px solid {t['border']};
    border-bottom:none;padding:5px 14px;margin-right:2px;
    border-top-left-radius:4px;border-top-right-radius:4px;}}
QTabBar::tab:selected{{background:{t['bg_primary']};color:{t['text']};}}
QTabBar::tab:hover:!selected{{background:{t['bg_hover']};color:{t['text']};}}
QSplitter::handle{{background:{t['border']};}}
QSplitter::handle:horizontal{{width:2px;}}
QSplitter::handle:vertical{{height:2px;}}
QToolTip{{background:{t['bg_secondary']};color:{t['text']};border:1px solid {t['border']};
    padding:4px 8px;border-radius:3px;font-size:12px;}}
QProgressBar{{background:{t['bg_secondary']};border:1px solid {t['border']};
    border-radius:4px;text-align:center;color:{t['text']};height:16px;}}
QProgressBar::chunk{{background:{t['accent']};border-radius:3px;}}
QCheckBox{{color:{t['text']};spacing:6px;}}
QCheckBox::indicator{{width:14px;height:14px;border:1px solid {t['border']};
    border-radius:3px;background:{t['bg_input']};}}
QCheckBox::indicator:checked{{background:{t['accent']};border-color:{t['accent']};}}
QCheckBox::indicator:hover{{border-color:{t['border_focus']};}}
QRadioButton{{color:{t['text']};spacing:6px;}}
QRadioButton::indicator{{width:14px;height:14px;border:1px solid {t['border']};
    border-radius:7px;background:{t['bg_input']};}}
QRadioButton::indicator:checked{{background:{t['accent']};border-color:{t['accent']};}}
QSlider::groove:horizontal{{background:{t['bg_secondary']};height:4px;border-radius:2px;}}
QSlider::handle:horizontal{{background:{t['accent']};width:14px;height:14px;
    border-radius:7px;margin:-5px 0;}}
QSlider::sub-page:horizontal{{background:{t['accent']};border-radius:2px;}}
QMenu{{background:{t['bg_secondary']};color:{t['text']};border:1px solid {t['border']};padding:4px;}}
QMenu::item{{padding:5px 24px 5px 12px;border-radius:3px;}}
QMenu::item:selected{{background:{t['accent']};color:#FFF;}}
QMenu::separator{{height:1px;background:{t['border']};margin:4px 8px;}}
QStatusBar{{background:{t['bg_tertiary']};color:{t['text_dim']};
    border-top:1px solid {t['border']};font-size:12px;}}
QFrame[class="message-card"]{{background:{t['bg_card']};border:1px solid {t['border']};border-radius:6px;}}
QFrame[class="code-block"]{{background:{t['bg_code']};border:1px solid {t['border']};border-radius:4px;
    font-family:Consolas,"Courier New",monospace;}}
"""
    # fmt: on
