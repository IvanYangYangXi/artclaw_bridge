# Ref: docs/features/phase5-dcc-integration.md
"""
ScheduleManager — lightweight async scheduler using asyncio tasks.

No APScheduler or heavy external dependencies.  Each scheduled rule gets
its own ``asyncio.Task`` that sleeps between invocations.

Supported schedule types (from ``TriggerRule.schedule_config`` JSON):

    {"type": "interval", "seconds": 300}
    {"type": "once",     "run_at": 1712700000}   # unix timestamp
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)


# ======================================================================
# ScheduledJob
# ======================================================================

class ScheduledJob:
    """A single scheduled job backed by an ``asyncio.Task``."""

    def __init__(
        self,
        rule_id: str,
        schedule_type: str,
        callback: Callable[[str], Coroutine[Any, Any, None]],
        *,
        seconds: float = 60.0,
        run_at: Optional[float] = None,
    ) -> None:
        self.rule_id = rule_id
        self.schedule_type = schedule_type  # "interval" | "once"
        self.callback = callback
        self.interval_seconds = seconds
        self.run_at = run_at  # Unix timestamp (for "once")
        self._task: Optional[asyncio.Task[None]] = None
        self._running = False

    # --- lifecycle ---

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self.schedule_type == "interval":
            self._task = asyncio.create_task(
                self._interval_loop(), name=f"sched-{self.rule_id}"
            )
        elif self.schedule_type == "once":
            self._task = asyncio.create_task(
                self._once_timer(), name=f"sched-once-{self.rule_id}"
            )

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # --- internal loops ---

    async def _interval_loop(self) -> None:
        """Sleep → execute → repeat."""
        try:
            while self._running:
                await asyncio.sleep(self.interval_seconds)
                if self._running:
                    await self._safe_execute()
        except asyncio.CancelledError:
            pass

    async def _once_timer(self) -> None:
        """Wait until *run_at*, execute once."""
        try:
            if self.run_at is not None:
                delay = max(0.0, self.run_at - time.time())
                await asyncio.sleep(delay)
            if self._running:
                await self._safe_execute()
        except asyncio.CancelledError:
            pass

    async def _safe_execute(self) -> None:
        try:
            await self.callback(self.rule_id)
        except Exception:
            logger.exception("Scheduled job %s failed", self.rule_id)


# ======================================================================
# ScheduleManager
# ======================================================================

class ScheduleManager:
    """Manage a set of :class:`ScheduledJob` instances."""

    def __init__(self) -> None:
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False

    # --- lifecycle ---

    async def start(self) -> None:
        """Start all registered jobs."""
        self._running = True
        for job in self._jobs.values():
            await job.start()
        logger.info("ScheduleManager started with %d jobs", len(self._jobs))

    async def stop(self) -> None:
        """Stop and clear all jobs."""
        self._running = False
        for job in self._jobs.values():
            await job.stop()
        self._jobs.clear()
        logger.info("ScheduleManager stopped")

    # --- job management ---

    def add_job(
        self,
        rule_id: str,
        schedule_config: Dict[str, Any],
        callback: Callable[[str], Coroutine[Any, Any, None]],
    ) -> bool:
        """Register a new job.  Returns False if *rule_id* already exists."""
        if rule_id in self._jobs:
            return False

        stype = schedule_config.get("type", "interval")
        job = ScheduledJob(
            rule_id=rule_id,
            schedule_type=stype,
            callback=callback,
            seconds=float(schedule_config.get("seconds", 60)),
            run_at=schedule_config.get("run_at"),
        )
        self._jobs[rule_id] = job

        if self._running:
            asyncio.create_task(job.start())
        return True

    def remove_job(self, rule_id: str) -> bool:
        """Remove and stop a job.  Returns False if not found."""
        job = self._jobs.pop(rule_id, None)
        if job is None:
            return False
        asyncio.create_task(job.stop())
        return True

    @property
    def job_count(self) -> int:
        return len(self._jobs)
