"""
chat_messages.py - ArtClaw 聊天消息模型与渲染组件
===================================================

包含：
- ChatMessage  : 消息数据类
- MessageWidget : 单条普通消息的 QWidget
- ToolCallWidget: 工具调用可折叠卡片
- MessageListWidget: 消息列表容器（QScrollArea）

颜色引用 theme.py 常量，不含硬编码。
最多保留 MAX_MESSAGES=500 条消息；自动滚动到底部。

对齐 UE 实现:
- 消息内容使用只读 QTextEdit，支持文本选择和复制（Ctrl+C / 右键菜单）
- 工具卡片压缩高度，暗色底色
- 流式消息正确更新
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("artclaw.ui")

try:
    from PySide2.QtCore import Qt, QTimer
    from PySide2.QtWidgets import (
        QFrame, QHBoxLayout, QLabel, QPushButton,
        QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False
    logger.warning("PySide2 不可用，chat_messages 无法渲染 UI")

from .theme import (
    SENDER_ASSISTANT, SENDER_STREAMING, SENDER_SYSTEM, SENDER_THINKING,
    SENDER_TOOL_CALL, SENDER_TOOL_ERROR, SENDER_TOOL_RESULT,
    SENDER_TOOL_STATUS, SENDER_USER, get_theme,
)
from .utils import render_markdown

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_MESSAGES = 500


def _get_sender_labels() -> dict[str, str]:
    """动态生成 sender labels（根据当前语言）"""
    try:
        from .i18n import T
        return {
            "user": T("sender_user"), "assistant": T("sender_assistant"),
            "system": T("sender_system"), "thinking": T("sender_thinking"),
            "streaming": T("sender_streaming"), "tool_call": T("sender_tool_call"),
            "tool_result": T("sender_tool_result"), "tool_error": T("sender_tool_error"),
            "tool_status": T("sender_tool_status"), "plan": T("sender_plan"),
        }
    except Exception:
        return {
            "user": "用户", "assistant": "助手", "system": "系统",
            "thinking": "思考中", "streaming": "助手",
            "tool_call": "工具调用", "tool_result": "工具结果",
            "tool_error": "工具错误", "tool_status": "工具状态", "plan": "执行计划",
        }

SENDER_COLORS: dict[str, str] = {
    "user": SENDER_USER, "assistant": SENDER_ASSISTANT,
    "system": SENDER_SYSTEM, "thinking": SENDER_THINKING,
    "streaming": SENDER_STREAMING, "tool_call": SENDER_TOOL_CALL,
    "tool_result": SENDER_TOOL_RESULT, "tool_error": SENDER_TOOL_ERROR,
    "tool_status": SENDER_TOOL_STATUS, "plan": SENDER_THINKING,
}

# 暗色背景 — 对齐 UE 的低对比度风格
SENDER_BG: dict[str, str] = {
    "user": "#2A3530", "assistant": "#282C38", "system": "#2A2A2A",
    "thinking": "#2A283A", "streaming": "#282C38", "tool_call": "#262218",
    "tool_result": "#1E2E24", "tool_error": "#2E1E1E",
    "tool_status": "#2A2418", "plan": "#2A283A",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ChatMessage:
    """聊天消息数据类"""
    sender: str
    content: str
    timestamp: float = field(default_factory=time.time)
    is_code: bool = False
    tool_name: str = ""
    tool_id: str = ""
    tool_arguments: str = ""
    tool_result: str = ""
    tool_error: str = ""
    tool_collapsed: bool = True


# ---------------------------------------------------------------------------
# Qt widgets (only defined when PySide2 is available)
# ---------------------------------------------------------------------------

if HAS_QT:

    class _ReadOnlyTextEdit(QTextEdit):
        """只读 QTextEdit — 支持文本选择、复制、右键菜单。
        对齐 UE 的 SMultiLineEditableText(IsReadOnly=true, AllowContextMenu=true)。
        """

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setReadOnly(True)
            self.setFrameShape(QFrame.NoFrame)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            # 允许右键菜单（复制等）
            self.setContextMenuPolicy(Qt.DefaultContextMenu)

        def set_content_plain(self, text: str, style: str = ""):
            """设置纯文本内容"""
            self.setPlainText(text)
            if style:
                self.setStyleSheet(style)
            self._adjust_height()

        def set_content_html(self, html_text: str, style: str = ""):
            """设置富文本内容"""
            self.setHtml(html_text)
            if style:
                self.setStyleSheet(style)
            self._adjust_height()

        def _adjust_height(self):
            """根据内容自动调整高度"""
            doc = self.document()
            vw = self.viewport().width() if self.viewport() and self.viewport().width() > 10 else 0
            if vw <= 0 and self.parent():
                vw = self.parent().width() - 20
            if vw <= 0:
                vw = 380
            doc.setTextWidth(vw)
            height = int(doc.size().height()) + 4
            # 限制最大高度 800px，避免超长消息撑爆
            height = min(height, 800)
            self.setFixedHeight(max(height, 20))

        def resizeEvent(self, event):
            """窗口大小变化时重新计算高度"""
            super().resizeEvent(event)
            self._adjust_height()

    # -----------------------------------------------------------------------

    class MessageWidget(QFrame):
        """单条消息渲染组件（非工具调用类型）"""

        def __init__(self, message: ChatMessage, dcc_name: str = "maya",
                     parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self._msg = message
            self._t = get_theme(dcc_name)
            self._content_widget: Optional[_ReadOnlyTextEdit] = None
            self._build()

        def _build(self) -> None:
            m, t = self._msg, self._t
            color = SENDER_COLORS.get(m.sender, SENDER_SYSTEM)
            bg = SENDER_BG.get(m.sender, "#252525")
            self.setFrameShape(QFrame.NoFrame)
            self.setStyleSheet(
                f"QFrame{{background:{bg};border-radius:6px;margin:1px 4px;}}")
            lay = QVBoxLayout(self)
            lay.setContentsMargins(8, 4, 8, 4)
            lay.setSpacing(2)

            # Header row — 紧凑
            hdr = QHBoxLayout()
            hdr.setSpacing(6)
            slbl = QLabel(_get_sender_labels().get(m.sender, m.sender))
            slbl.setStyleSheet(
                f"color:{color};font-weight:bold;font-size:11px;background:transparent;")
            hdr.addWidget(slbl)
            tlbl = QLabel(time.strftime("%H:%M", time.localtime(m.timestamp)))
            tlbl.setStyleSheet(
                f"color:{t['text_muted']};font-size:10px;background:transparent;")
            hdr.addWidget(tlbl)
            hdr.addStretch()
            lay.addLayout(hdr)

            # Content
            self._content_widget = self._build_content()
            lay.addWidget(self._content_widget)

        def _build_content(self) -> _ReadOnlyTextEdit:
            m, t = self._msg, self._t
            w = _ReadOnlyTextEdit()

            base_style = (
                f"QTextEdit{{background:transparent;border:none;padding:0px;"
                f"selection-background-color:{t['accent']};}}"
            )

            if m.is_code or m.sender in ("tool_result", "tool_error"):
                w.set_content_plain(m.content,
                    f"QTextEdit{{font-family:Consolas,'Courier New',monospace;font-size:12px;"
                    f"color:{t['text']};background:{t['bg_code']};"
                    f"border:1px solid {t['border']};border-radius:4px;padding:4px 6px;"
                    f"selection-background-color:{t['accent']};}}")
            elif m.sender in ("thinking", "streaming"):
                w.set_content_plain(m.content,
                    f"QTextEdit{{color:{t['text_dim']};font-style:italic;font-size:12px;"
                    f"background:transparent;border:none;padding:0px;"
                    f"selection-background-color:{t['accent']};}}")
            else:
                w.set_content_html(render_markdown(m.content),
                    f"QTextEdit{{color:{t['text']};font-size:13px;background:transparent;"
                    f"border:none;padding:0px;line-height:1.4;"
                    f"selection-background-color:{t['accent']};}}")

            return w

        def update_content(self, new_content: str) -> None:
            """流式更新消息内容"""
            self._msg.content = new_content
            if self._content_widget:
                m, t = self._msg, self._t
                if m.sender in ("thinking", "streaming"):
                    self._content_widget.set_content_plain(new_content)
                else:
                    self._content_widget.set_content_html(render_markdown(new_content))

    # -------------------------------------------------------------------------

    class ToolCallWidget(QFrame):
        """工具调用可折叠卡片 — 压缩版，对齐 UE 的 tool_call 渲染。

        默认折叠，标题行：[🔧 工具名 [状态] ▶]
        展开显示参数 + 结果（如果有）。
        """

        _ICONS = {"pending": "⏳", "running": "⚙", "done": "✓", "error": "✗"}

        def __init__(self, message: ChatMessage, dcc_name: str = "maya",
                     parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self._msg = message
            self._t = get_theme(dcc_name)
            self._collapsed = message.tool_collapsed
            self._body: Optional[QWidget] = None
            self._toggle_btn: Optional[QPushButton] = None
            self._status_lbl: Optional[QLabel] = None
            self._build()

        def _build(self) -> None:
            m, t = self._msg, self._t
            # 暗色边框 — 不用亮色
            self.setFrameShape(QFrame.NoFrame)
            self.setStyleSheet(
                f"QFrame{{background:#1E1C16;border:1px solid #3A3520;"
                f"border-radius:4px;margin:1px 4px;}}")
            main = QVBoxLayout(self)
            main.setContentsMargins(0, 0, 0, 0)
            main.setSpacing(0)

            # --- Header (单行紧凑) ---
            hf = QWidget()
            hf.setStyleSheet("background:transparent;")
            hl = QHBoxLayout(hf)
            hl.setContentsMargins(8, 3, 6, 3)
            hl.setSpacing(4)

            hl.addWidget(self._lbl("🔧", "background:transparent;font-size:12px;"))
            hl.addWidget(self._lbl(
                m.tool_name or "未知工具",
                f"color:{SENDER_TOOL_CALL};font-weight:bold;font-size:12px;background:transparent;"))

            self._status_lbl = self._lbl(
                "[running]",
                f"color:{t['text_dim']};background:transparent;font-size:11px;")
            hl.addWidget(self._status_lbl)
            hl.addStretch()

            self._toggle_btn = QPushButton("▶" if self._collapsed else "▼")
            self._toggle_btn.setFixedSize(18, 18)
            self._toggle_btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{t['text_dim']};border:none;font-size:10px;}}"
                f"QPushButton:hover{{color:{t['text']};}}")
            self._toggle_btn.clicked.connect(self._toggle)
            hl.addWidget(self._toggle_btn)
            main.addWidget(hf)

            # --- Body (折叠区) ---
            self._body = QWidget()
            self._body.setStyleSheet("background:transparent;")
            bl = QVBoxLayout(self._body)
            bl.setContentsMargins(8, 2, 8, 4)
            bl.setSpacing(2)

            if m.tool_arguments:
                try:
                    from .i18n import T as _T
                    params_label = _T("tool_params")
                except Exception:
                    params_label = "参数："
                bl.addWidget(self._lbl(
                    params_label,
                    f"color:{t['text_dim']};font-size:10px;font-weight:bold;background:transparent;"))
                try:
                    pretty = json.dumps(json.loads(m.tool_arguments), ensure_ascii=False, indent=2)
                except (json.JSONDecodeError, TypeError):
                    pretty = m.tool_arguments
                # 截断显示，避免超长参数
                if len(pretty) > 1000:
                    pretty = pretty[:1000] + "\n... (截断)"
                al = _ReadOnlyTextEdit()
                al.set_content_plain(pretty,
                    f"QTextEdit{{font-family:Consolas,'Courier New',monospace;font-size:11px;"
                    f"color:{t['text_dim']};background:#1A1A14;"
                    f"border:1px solid #33301E;border-radius:3px;padding:3px 4px;"
                    f"selection-background-color:{t['accent']};}}")
                bl.addWidget(al)

            main.addWidget(self._body)
            self._body.setVisible(not self._collapsed)

        @staticmethod
        def _lbl(text: str, style: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(style)
            return lbl

        def _toggle(self) -> None:
            self._collapsed = not self._collapsed
            self._msg.tool_collapsed = self._collapsed
            if self._body:
                self._body.setVisible(not self._collapsed)
            if self._toggle_btn:
                self._toggle_btn.setText("▶" if self._collapsed else "▼")

        def set_result(self, result: str, is_error: bool = False) -> None:
            """附加工具结果/错误并更新状态"""
            t = self._t
            if self._status_lbl:
                label = "[error]" if is_error else "[done]"
                color = SENDER_TOOL_ERROR if is_error else SENDER_TOOL_RESULT
                self._status_lbl.setText(label)
                self._status_lbl.setStyleSheet(
                    f"color:{color};background:transparent;font-size:11px;")

            # 更新边框颜色
            if is_error:
                self.setStyleSheet(
                    "QFrame{background:#1E1616;border:1px solid #3A2020;"
                    "border-radius:4px;margin:1px 4px;}")
            else:
                self.setStyleSheet(
                    "QFrame{background:#161E18;border:1px solid #203A24;"
                    "border-radius:4px;margin:1px 4px;}")

            if self._body and self._body.layout():
                bl = self._body.layout()
                rc = SENDER_TOOL_ERROR if is_error else SENDER_TOOL_RESULT
                try:
                    from .i18n import T as _T
                    result_label = _T("tool_error_lbl") if is_error else _T("tool_result_lbl")
                except Exception:
                    result_label = "错误：" if is_error else "结果："
                bl.addWidget(self._lbl(
                    result_label,
                    f"color:{rc};font-size:10px;font-weight:bold;background:transparent;"))
                # 截断结果
                display = result[:1500] + "\n... (截断)" if len(result) > 1500 else result
                rl = _ReadOnlyTextEdit()
                rl.set_content_plain(display,
                    f"QTextEdit{{font-family:Consolas,'Courier New',monospace;font-size:11px;"
                    f"color:{t['text_dim']};background:#1A1A14;"
                    f"border:1px solid #33301E;border-radius:3px;padding:3px 4px;"
                    f"selection-background-color:{t['accent']};}}")
                bl.addWidget(rl)

            # 结果到达时不自动展开 — 减少 UI 干扰（对齐 UE 行为）

    # -------------------------------------------------------------------------

    class MessageListWidget(QScrollArea):
        """
        消息列表容器（QScrollArea）。

        API::

            w = MessageListWidget("maya")
            w.add_message("user", "你好")
            w.add_tool_call("read_file", "tc1", '{"path":"/tmp/x"}')
            w.add_tool_result("read_file", "tc1", "内容...", is_error=False)
            w.update_streaming_message("streaming", "正在生成…")
            w.finalize_streaming()
            w.clear()
        """

        def __init__(self, dcc_name: str = "maya",
                     parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self._dcc = dcc_name
            self._t = get_theme(dcc_name)
            self._messages: list[ChatMessage] = []
            self._widgets: list[QWidget] = []
            self._tool_map: dict[str, ToolCallWidget] = {}
            self._streaming_widget: Optional[MessageWidget] = None
            self._init_ui()

        def _init_ui(self) -> None:
            self.setWidgetResizable(True)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setStyleSheet("QScrollArea{border:none;background:transparent;}")
            self._cont = QWidget()
            self._cont.setStyleSheet(f"background:{self._t['bg_message']};")
            self._lay = QVBoxLayout(self._cont)
            self._lay.setContentsMargins(2, 2, 2, 2)
            self._lay.setSpacing(2)
            self._lay.addStretch()
            self.setWidget(self._cont)

        # ---- public API ----

        def add_message(self, sender: str, content: str, **kw) -> ChatMessage:
            """添加一条普通消息，返回 ChatMessage 对象"""
            # 如果添加非流式消息，先清除流式追踪
            if sender not in ("streaming", "thinking"):
                self._streaming_widget = None

            msg = ChatMessage(
                sender=sender, content=content,
                timestamp=kw.get("timestamp", time.time()),
                is_code=kw.get("is_code", False),
                tool_name=kw.get("tool_name", ""),
                tool_id=kw.get("tool_id", ""),
                tool_arguments=kw.get("tool_arguments", ""),
            )
            self._messages.append(msg)
            w = MessageWidget(msg, dcc_name=self._dcc)
            self._insert(w)
            self._widgets.append(w)
            self._trim()
            self._scroll()
            return msg

        def add_tool_call(self, tool_name: str, tool_id: str, arguments: str) -> ChatMessage:
            """添加工具调用消息（可折叠卡片）"""
            # 去重：如果已有相同 tool_id 的卡片，跳过
            if tool_id in self._tool_map:
                return self._messages[-1] if self._messages else ChatMessage(sender="tool_call", content="")

            msg = ChatMessage(
                sender="tool_call", content="",
                tool_name=tool_name, tool_id=tool_id,
                tool_arguments=arguments, tool_collapsed=True,
            )
            self._messages.append(msg)
            w = ToolCallWidget(msg, dcc_name=self._dcc)
            self._tool_map[tool_id] = w
            self._insert(w)
            self._widgets.append(w)
            self._trim()
            self._scroll()
            return msg

        def add_tool_result(self, tool_name: str, tool_id: str,
                            result: str, is_error: bool = False) -> None:
            """更新对应工具调用卡片的结果；找不到则新建结果消息"""
            w = self._tool_map.get(tool_id)
            if w:
                w.set_result(result, is_error=is_error)
                self._scroll()
            else:
                self.add_message("tool_error" if is_error else "tool_result",
                                 f"[{tool_name}] {result}")

        def update_streaming_message(self, sender: str, content: str) -> None:
            """更新/创建流式消息。

            如果上一条消息是 streaming/thinking，直接更新内容（不新建 widget）。
            否则创建新的流式消息 widget。
            """
            if (self._streaming_widget
                    and self._messages
                    and self._messages[-1].sender in ("streaming", "thinking")):
                # 更新已有流式消息
                self._streaming_widget.update_content(content)
                self._messages[-1].content = content
                self._messages[-1].sender = sender  # 允许 thinking → streaming 切换
                self._scroll()
            else:
                # 创建新的流式消息
                msg = self.add_message(sender, content)
                if self._widgets and isinstance(self._widgets[-1], MessageWidget):
                    self._streaming_widget = self._widgets[-1]

        def update_streaming_content_if_longer(self, full_text: str) -> None:
            """如果 full_text 比当前 streaming widget 的内容长，则更新。

            解决跨线程延迟导致最后几个 delta 没被 streaming widget 消费的问题。
            在 finalize_streaming() 之前调用。
            """
            if not self._streaming_widget or not self._messages:
                return
            last = self._messages[-1]
            if last.sender not in ("streaming", "thinking"):
                return
            if len(full_text) > len(last.content):
                last.content = full_text
                self._streaming_widget.update_content(full_text)

        def finalize_streaming(self) -> bool:
            """将所有 streaming 消息标记为 assistant 并刷新 widget 显示。"""
            had = False
            for i, m in enumerate(self._messages):
                if m.sender in ("streaming", "thinking"):
                    m.sender = "assistant"
                    had = True
                    # 重建 widget 以反映新 sender 样式
                    if i < len(self._widgets):
                        old_w = self._widgets[i]
                        new_w = MessageWidget(m, dcc_name=self._dcc)
                        self._lay.replaceWidget(old_w, new_w)
                        old_w.deleteLater()
                        self._widgets[i] = new_w
            self._streaming_widget = None
            # 延迟重新计算所有 widget 高度，避免 replaceWidget 后宽度为 0 导致高度偏大
            if had:
                QTimer.singleShot(100, self._readjust_heights)
            self._scroll()
            return had

        def _readjust_heights(self):
            """重新计算所有消息 widget 的高度"""
            for w in self._widgets:
                if hasattr(w, '_content_widget') and w._content_widget:
                    cw = w._content_widget
                    if hasattr(cw, '_adjust_height'):
                        cw._adjust_height()

        def remove_system_message(self, content: str) -> None:
            """移除特定内容的系统消息（如"思考中..."）"""
            for i in range(len(self._messages) - 1, -1, -1):
                if self._messages[i].sender == "system" and self._messages[i].content == content:
                    self._messages.pop(i)
                    if i < len(self._widgets):
                        w = self._widgets.pop(i)
                        w.deleteLater()
                    break

        def clear(self) -> None:
            """清空所有消息"""
            self._messages.clear()
            self._widgets.clear()
            self._tool_map.clear()
            self._streaming_widget = None
            while self._lay.count() > 1:
                item = self._lay.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()

        def get_messages(self) -> list[ChatMessage]:
            """返回消息列表的浅拷贝"""
            return list(self._messages)

        # ---- private ----

        def _insert(self, w: QWidget) -> None:
            self._lay.insertWidget(self._lay.count() - 1, w)

        def _trim(self) -> None:
            while len(self._messages) > MAX_MESSAGES:
                self._messages.pop(0)
                if self._widgets:
                    self._widgets.pop(0).deleteLater()

        def _scroll(self) -> None:
            QTimer.singleShot(50, lambda: (
                self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
                if self.verticalScrollBar() else None
            ))

else:
    # Minimal stubs so imports never fail in headless environments

    class MessageWidget:  # type: ignore[no-redef]
        pass

    class ToolCallWidget:  # type: ignore[no-redef]
        pass

    class MessageListWidget:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def add_message(self, *a, **kw): return None
        def add_tool_call(self, *a, **kw): return None
        def add_tool_result(self, *a, **kw): pass
        def update_streaming_message(self, *a, **kw): pass
        def finalize_streaming(self): return False
        def remove_system_message(self, *a, **kw): pass
        def clear(self): pass
        def get_messages(self): return []
