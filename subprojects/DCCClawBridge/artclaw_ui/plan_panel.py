"""
plan_panel.py - ArtClaw DCC Plan Mode UI

Provides PlanManager for managing multi-step AI plans, and PlanCardWidget
for displaying and controlling plan execution in the DCC chat UI.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Callable, List, Optional

try:
    from PySide2.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QFrame, QScrollArea, QSizePolicy
    )
    from PySide2.QtCore import Signal, Qt
    from PySide2.QtGui import QFont
except ImportError:
    raise ImportError("PySide2 is required.")

from artclaw_ui.theme import COLORS, get_theme

logger = logging.getLogger(__name__)

STATUS_ICONS = {
    "pending":  ("[ ]", "#888888"),
    "running":  ("[>>]", "#f39c12"),
    "done":     ("[OK]", "#2ecc71"),
    "failed":   ("[!!]", "#e74c3c"),
    "skipped":  ("[-]", "#555555"),
}


@dataclass
class PlanStep:
    """A single step within a Plan."""
    index: int
    title: str
    description: str
    status: str = "pending"  # pending / running / done / failed / skipped
    result: str = ""


@dataclass
class Plan:
    """A multi-step AI execution plan."""
    plan_id: str
    user_request: str
    steps: List[PlanStep] = field(default_factory=list)
    is_executing: bool = False
    is_paused: bool = False
    current_step_index: int = 0


class PlanManager:
    """Manages the current plan and its execution state."""

    def __init__(self):
        self.current_plan: Optional[Plan] = None
        self.plan_mode: bool = False
        self._is_plan_step = False

    # ------------------------------------------------------------------ #
    # Parse                                                                 #
    # ------------------------------------------------------------------ #

    def try_parse_plan(self, response_text: str) -> bool:
        """Try to parse a JSON plan from AI response. Returns True on success."""
        start = response_text.find("```json")
        if start == -1:
            start = response_text.find("{")
        else:
            start = response_text.find("{", start)

        end = response_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return False

        try:
            raw = response_text[start:end + 1]
            data = json.loads(raw)
        except json.JSONDecodeError:
            return False

        if "steps" not in data:
            return False

        steps = []
        for i, s in enumerate(data["steps"]):
            steps.append(PlanStep(
                index=i,
                title=s.get("title", f"步骤 {i + 1}"),
                description=s.get("description", ""),
                status="pending",
            ))

        self.current_plan = Plan(
            plan_id=data.get("plan_id", str(uuid.uuid4())),
            user_request=data.get("user_request", ""),
            steps=steps,
        )
        logger.info("Parsed plan with %d steps: %s", len(steps), self.current_plan.plan_id)
        return True

    # ------------------------------------------------------------------ #
    # Execution Control                                                     #
    # ------------------------------------------------------------------ #

    def execute_next_step(self, send_callback: Callable[[str], None]):
        """Send the next pending step's description to the AI."""
        plan = self.current_plan
        if not plan or plan.is_paused:
            return

        plan.is_executing = True
        for step in plan.steps:
            if step.status == "pending":
                plan.current_step_index = step.index
                step.status = "running"
                self._is_plan_step = True
                msg = f"[Plan Step {step.index + 1}/{len(plan.steps)}] {step.description}"
                send_callback(msg)
                logger.info("Executing plan step %d: %s", step.index, step.title)
                return

        # All done
        plan.is_executing = False
        logger.info("All plan steps completed for plan: %s", plan.plan_id)

    def pause(self):
        if self.current_plan:
            self.current_plan.is_paused = True
            logger.info("Plan paused: %s", self.current_plan.plan_id)

    def resume(self, send_callback: Callable[[str], None]):
        if self.current_plan:
            self.current_plan.is_paused = False
            logger.info("Plan resumed: %s", self.current_plan.plan_id)
            self.execute_next_step(send_callback)

    def cancel(self, stop_callback: Optional[Callable[[], None]] = None):
        if self.current_plan:
            logger.info("Plan cancelled: %s", self.current_plan.plan_id)
            self.current_plan.is_executing = False
            self.current_plan.is_paused = False
            for step in self.current_plan.steps:
                if step.status in ("pending", "running"):
                    step.status = "skipped"
        if stop_callback:
            stop_callback()
        self.current_plan = None
        self._is_plan_step = False

    def delete_step(self, index: int):
        """Mark a step as skipped (logical delete)."""
        if not self.current_plan:
            return
        for step in self.current_plan.steps:
            if step.index == index:
                step.status = "skipped"
                logger.info("Plan step %d marked as skipped", index)
                return

    def is_plan_response(self) -> bool:
        return self._is_plan_step

    def handle_step_result(
        self,
        response: str,
        send_callback: Optional[Callable[[str], None]] = None,
    ):
        """Update the current running step's result and advance."""
        self._is_plan_step = False
        plan = self.current_plan
        if not plan:
            return
        for step in plan.steps:
            if step.status == "running":
                error_hints = ["error", "failed", "traceback", "exception"]
                has_error = any(h in response.lower() for h in error_hints)
                step.status = "failed" if has_error else "done"
                step.result = response[:500]
                logger.info("Step %d finished with status: %s", step.index, step.status)
                break

        if send_callback and not plan.is_paused:
            self.execute_next_step(send_callback)


# ------------------------------------------------------------------ #
# PlanCardWidget                                                        #
# ------------------------------------------------------------------ #

class PlanCardWidget(QWidget):
    """Widget displaying a plan card with step list and controls."""

    execute_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    cancel_requested = Signal()
    step_deleted = Signal(int)

    def __init__(self, manager: PlanManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._manager = manager
        self._step_widgets: List[QWidget] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        theme = get_theme()
        self.setStyleSheet(
            f"background: {COLORS.get('bg_secondary', '#2a2a2a')};"
            f"border-radius: 6px; border: 1px solid {COLORS.get('border', '#3a3a3a')};"
        )

        # Title row
        title_row = QHBoxLayout()
        self._title_lbl = QLabel("📋 计划")
        font = QFont()
        font.setBold(True)
        self._title_lbl.setFont(font)
        self._title_lbl.setStyleSheet(f"color: {COLORS.get('text_primary', '#e0e0e0')};")
        title_row.addWidget(self._title_lbl)
        title_row.addStretch()
        layout.addLayout(title_row)

        # User request label
        self._request_lbl = QLabel()
        self._request_lbl.setWordWrap(True)
        self._request_lbl.setStyleSheet(f"color: {COLORS.get('text_secondary', '#aaa')}; font-size: 11px;")
        layout.addWidget(self._request_lbl)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # Steps scroll area
        self._steps_scroll = QScrollArea()
        self._steps_scroll.setWidgetResizable(True)
        self._steps_scroll.setFrameShape(QFrame.NoFrame)
        self._steps_scroll.setMaximumHeight(200)
        self._steps_container = QWidget()
        self._steps_layout = QVBoxLayout(self._steps_container)
        self._steps_layout.setSpacing(2)
        self._steps_layout.setContentsMargins(0, 0, 0, 0)
        self._steps_scroll.setWidget(self._steps_container)
        layout.addWidget(self._steps_scroll)

        # Action buttons row
        btn_row = QHBoxLayout()
        self._btn_execute = QPushButton("执行全部")
        self._btn_execute.setFixedHeight(28)
        self._btn_execute.setStyleSheet(
            f"background-color: {COLORS.get('accent_blue', '#1e90ff')}; color: white; border-radius: 3px;"
        )
        self._btn_execute.clicked.connect(self.execute_requested)

        self._btn_pause = QPushButton("暂停")
        self._btn_pause.setFixedHeight(28)
        self._btn_pause.setStyleSheet(
            f"background-color: {COLORS.get('accent_orange', '#e67e22')}; color: white; border-radius: 3px;"
        )
        self._btn_pause.clicked.connect(self.pause_requested)
        self._btn_pause.hide()

        self._btn_resume = QPushButton("继续")
        self._btn_resume.setFixedHeight(28)
        self._btn_resume.setStyleSheet(
            f"background-color: {COLORS.get('accent_green', '#2ecc71')}; color: white; border-radius: 3px;"
        )
        self._btn_resume.clicked.connect(self.resume_requested)
        self._btn_resume.hide()

        self._btn_cancel = QPushButton("取消计划")
        self._btn_cancel.setFixedHeight(28)
        self._btn_cancel.setStyleSheet(
            f"background-color: {COLORS.get('accent_red', '#e74c3c')}; color: white; border-radius: 3px;"
        )
        self._btn_cancel.clicked.connect(self.cancel_requested)

        btn_row.addWidget(self._btn_execute)
        btn_row.addWidget(self._btn_pause)
        btn_row.addWidget(self._btn_resume)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_cancel)
        layout.addLayout(btn_row)

    def refresh(self):
        """Rebuild step list from current plan."""
        plan = self._manager.current_plan
        if not plan:
            self.hide()
            return

        self.show()
        self._title_lbl.setText(f"📋 {plan.plan_id[:20]}")
        self._request_lbl.setText(plan.user_request[:100])

        # Clear steps
        while self._steps_layout.count():
            item = self._steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._step_widgets.clear()

        for step in plan.steps:
            row = self._make_step_row(step)
            self._steps_layout.addWidget(row)
            self._step_widgets.append(row)

        # Update buttons
        is_exec = plan.is_executing
        is_paused = plan.is_paused
        self._btn_execute.setVisible(not is_exec)
        self._btn_pause.setVisible(is_exec and not is_paused)
        self._btn_resume.setVisible(is_paused)

    def _make_step_row(self, step: PlanStep) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        icon_text, icon_color = STATUS_ICONS.get(step.status, ("[ ]", "#888"))
        icon_lbl = QLabel(icon_text)
        icon_lbl.setFixedWidth(36)
        icon_lbl.setStyleSheet(f"color: {icon_color}; font-family: monospace;")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(f"{step.index + 1}. {step.title}")
        title_lbl.setStyleSheet(
            f"color: {COLORS.get('text_primary', '#e0e0e0')}; font-size: 11px;"
        )
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl, 1)

        if step.status in ("pending", "skipped"):
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(18, 18)
            del_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #666; border: none; }"
                "QPushButton:hover { color: #e74c3c; }"
            )
            del_btn.setProperty("step_index", step.index)
            del_btn.clicked.connect(self._on_delete_step)
            layout.addWidget(del_btn)

        return row

    def _on_delete_step(self):
        btn = self.sender()
        if not btn:
            return
        idx = btn.property("step_index")
        self._manager.delete_step(idx)
        self.step_deleted.emit(idx)
        self.refresh()
