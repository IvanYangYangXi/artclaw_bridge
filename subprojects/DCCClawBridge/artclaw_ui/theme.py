"""
theme.py - ArtClaw UI 主题管理
================================

DCC 配色适配（Maya 蓝 / Max 蓝 / 通用暗色）
"""

DCC_THEMES = {
    "maya": {
        "bg_primary": "#3C3C3C",
        "bg_secondary": "#4A4A4A",
        "bg_input": "#3C3C3C",
        "bg_message": "#2B2B2B",
        "bg_code": "#1E1E1E",
        "accent": "#5285A6",
        "accent_hover": "#6295B6",
        "accent_pressed": "#4275A6",
        "text": "#E0E0E0",
        "text_dim": "#888888",
        "text_user": "#7CB3F2",
        "text_assistant": "#C0C0C0",
        "text_system": "#888888",
        "border": "#555555",
        "status_ok": "#4CAF50",
        "status_error": "#F44336",
        "status_warn": "#FF9800",
    },
    "max": {
        "bg_primary": "#3F3F3F",
        "bg_secondary": "#505050",
        "bg_input": "#3F3F3F",
        "bg_message": "#2D2D2D",
        "bg_code": "#1E1E1E",
        "accent": "#4A90D9",
        "accent_hover": "#5AA0E9",
        "accent_pressed": "#3A80C9",
        "text": "#E0E0E0",
        "text_dim": "#999999",
        "text_user": "#7CB3F2",
        "text_assistant": "#C0C0C0",
        "text_system": "#999999",
        "border": "#606060",
        "status_ok": "#4CAF50",
        "status_error": "#F44336",
        "status_warn": "#FF9800",
    },
}


def get_theme(dcc_name: str = "maya") -> dict:
    """获取指定 DCC 的主题配色"""
    return DCC_THEMES.get(dcc_name, DCC_THEMES["maya"])
