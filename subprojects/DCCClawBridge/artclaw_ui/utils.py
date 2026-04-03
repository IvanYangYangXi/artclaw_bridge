"""
utils.py - ArtClaw UI 公共工具函数
=====================================

提供整个 UI 系统共用的辅助函数：
- 文件大小/类型检测
- HTML 转义和 Markdown 渲染
- ArtClaw 配置文件读写
- 数据目录路径计算
- OpenClaw 配置路径

所有函数均无副作用（配置写入函数除外），可在任意 DCC 环境中安全调用。
"""

from __future__ import annotations

import html
import json
import logging
import mimetypes
import os
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("artclaw.ui")

# ---------------------------------------------------------------------------
# Image / MIME helpers
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp",
    ".webp", ".tiff", ".tif", ".svg", ".ico",
    ".exr", ".hdr", ".tga",
}


def format_file_size(size_bytes: int) -> str:
    """将字节数转换为可读字符串（如 '1.2 MB'）"""
    if size_bytes < 0:
        return "未知大小"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024.0:
            if unit == "B":
                return f"{int(size_bytes)} {unit}"
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def is_image_file(path: str) -> bool:
    """判断路径是否为图片文件（按扩展名）"""
    ext = Path(path).suffix.lower()
    return ext in _IMAGE_EXTS


def get_mime_type(path: str) -> str:
    """获取文件的 MIME 类型，未知时返回 'application/octet-stream'"""
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


# ---------------------------------------------------------------------------
# HTML / Markdown helpers
# ---------------------------------------------------------------------------

def escape_html(text: str) -> str:
    """HTML 转义（& < > \" '）"""
    return html.escape(text, quote=True)


def render_markdown(text: str) -> str:
    """
    将 Markdown 文本渲染为 HTML 字符串（适用于 QLabel 富文本）。

    支持：
    - ``` 代码块（多行，含语言标记）
    - ` 行内代码
    - **粗体** / *斜体*
    - # ## ### 标题
    - --- 水平线
    - 换行（\\n → <br>）

    不依赖第三方库，纯正则实现，适合 DCC 环境。
    """
    if not text:
        return ""

    # 将整段文字按代码块分割，代码块内容不做 Markdown 解析
    parts: list[str] = []
    code_block_pattern = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)

    last_end = 0
    for m in code_block_pattern.finditer(text):
        # 处理代码块前的普通文本
        before = text[last_end:m.start()]
        if before:
            parts.append(_render_inline(before))
        # 处理代码块
        lang = m.group(1) or ""
        code = escape_html(m.group(2))
        lang_label = f'<span style="color:#888;font-size:11px;">{escape_html(lang)}</span><br>' if lang else ""
        parts.append(
            f'<div style="background:#1E1E1E;border:1px solid #444;border-radius:4px;'
            f'padding:6px 10px;margin:4px 0;font-family:Consolas,\'Courier New\',monospace;'
            f'font-size:12px;color:#D4D4D4;">'
            f'{lang_label}<pre style="margin:0;white-space:pre-wrap;">{code}</pre></div>'
        )
        last_end = m.end()

    # 剩余文本
    tail = text[last_end:]
    if tail:
        parts.append(_render_inline(tail))

    return "".join(parts)


def _render_inline(text: str) -> str:
    """渲染行内 Markdown 元素（不含代码块）"""
    lines = text.split("\n")
    result_lines: list[str] = []

    for line in lines:
        # H3
        m = re.match(r"^###\s+(.+)$", line)
        if m:
            result_lines.append(
                f'<h4 style="color:#AAAAAA;margin:4px 0;">{escape_html(m.group(1))}</h4>'
            )
            continue
        # H2
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            result_lines.append(
                f'<h3 style="color:#BBBBBB;margin:4px 0;">{escape_html(m.group(1))}</h3>'
            )
            continue
        # H1
        m = re.match(r"^#\s+(.+)$", line)
        if m:
            result_lines.append(
                f'<h2 style="color:#CCCCCC;margin:4px 0;">{escape_html(m.group(1))}</h2>'
            )
            continue
        # 水平线
        if re.match(r"^-{3,}$", line.strip()):
            result_lines.append('<hr style="border:none;border-top:1px solid #555;margin:6px 0;">')
            continue
        # 行内处理
        line = escape_html(line)
        # 行内代码
        line = re.sub(
            r"`([^`]+)`",
            r'<code style="background:#1E1E1E;color:#CE9178;padding:1px 4px;'
            r'border-radius:3px;font-family:Consolas,monospace;font-size:12px;">\1</code>',
            line,
        )
        # 粗体
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(r"__(.+?)__", r"<strong>\1</strong>", line)
        # 斜体
        line = re.sub(r"\*(.+?)\*", r"<em>\1</em>", line)
        line = re.sub(r"_(.+?)_", r"<em>\1</em>", line)
        result_lines.append(line)

    return "<br>".join(result_lines)


# ---------------------------------------------------------------------------
# ArtClaw config file I/O
# ---------------------------------------------------------------------------

def _get_artclaw_config_dir() -> Path:
    """返回 ~/.artclaw 目录路径（自动创建）"""
    config_dir = Path.home() / ".artclaw"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_artclaw_config_path() -> Path:
    """返回 ~/.artclaw/config.json 的 Path"""
    return _get_artclaw_config_dir() / "config.json"


def get_artclaw_config() -> dict[str, Any]:
    """
    读取 ~/.artclaw/config.json，返回配置字典。
    文件不存在或解析失败时返回空字典。
    """
    path = _get_artclaw_config_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("读取 ArtClaw 配置失败：%s", e)
        return {}


def save_artclaw_config(config: dict[str, Any]) -> bool:
    """
    合并并保存配置到 ~/.artclaw/config.json（浅合并，不覆盖全文件）。
    返回 True 表示保存成功。
    """
    existing = get_artclaw_config()
    existing.update(config)
    path = _get_artclaw_config_path()
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        logger.error("保存 ArtClaw 配置失败：%s", e)
        return False


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_data_dir(dcc_name: str, dcc_version: str = "") -> str:
    """
    返回 DCC 数据目录路径（~/.artclaw/data/<dcc_name>/<version>/）。
    目录不存在时自动创建。
    """
    base = _get_artclaw_config_dir() / "data" / dcc_name.lower()
    if dcc_version:
        base = base / dcc_version
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


def get_quick_input_path(adapter: str) -> str:
    """
    返回快速输入文件路径（~/.artclaw/quick_input/<adapter>.txt）。
    用于 DCC 端与 OpenClaw 之间的快速文本传递。
    """
    dir_path = _get_artclaw_config_dir() / "quick_input"
    dir_path.mkdir(parents=True, exist_ok=True)
    return str(dir_path / f"{adapter}.txt")


def get_openclaw_config_path() -> str:
    """
    返回 OpenClaw 主配置文件路径。
    优先读取 ~/.artclaw/config.json 中的 openclaw_config_path 字段，
    否则根据平台使用默认路径。
    """
    artclaw_cfg = get_artclaw_config()
    custom = artclaw_cfg.get("openclaw_config_path", "")
    if custom and os.path.exists(custom):
        return custom

    # 默认路径：跟随 OpenClaw 的约定
    # OpenClaw 实际使用 ~/.openclaw/openclaw.json
    home_openclaw = str(Path.home() / ".openclaw" / "openclaw.json")
    if os.path.exists(home_openclaw):
        return home_openclaw

    # 备选：%APPDATA%/openclaw/config.json (旧约定)
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return os.path.join(app_data, "openclaw", "config.json")
    elif sys.platform == "darwin":
        return str(Path.home() / "Library" / "Application Support" / "openclaw" / "config.json")
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return os.path.join(xdg, "openclaw", "config.json")
