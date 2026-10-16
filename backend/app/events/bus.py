"""In-memory SSE event bus for investigation runs."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Deque, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowEvent:
    run_id: str
    event_id: str
    timestamp: str
    event_type: str
    status: str
    node_id: Optional[str] = None
    duration_ms: Optional[float] = None
    input_summary: Optional[Any] = None
    output_summary: Optional[Any] = None
    error: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "run_id": self.run_id,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "status": self.status,
            "node_id": self.node_id,
            "duration_ms": self.duration_ms,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "error": self.error,
        }
        if self.extra:
            payload.update(self.extra)
        return payload


class EventBus:
    """Small in-memory pub/sub with reconnect history."""

    def __init__(self, history_limit: int = 500) -> None:
        self._history: Dict[str, Deque[WorkflowEvent]] = defaultdict(
            lambda: deque(maxlen=history_limit)
        )
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def create_run(self, claim_id: str, question: str) -> str:
        run_id = str(uuid.uuid4())
        self._runs[run_id] = {
            "run_id": run_id,
            "claim_id": claim_id,
            "question": question,
            "status": "created",
            "created_at": _utc_now(),
            "report": None,
            "error": None,
        }
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._runs.get(run_id)

    def update_run(self, run_id: str, **kwargs: Any) -> None:
        if run_id in self._runs:
            self._runs[run_id].update(kwargs)

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        runs = sorted(
            self._runs.values(),
            key=lambda r: r.get("created_at", ""),
            reverse=True,
        )
        return runs[:limit]

    def emit(
        self,
        run_id: str,
        event_type: str,
        status: str = "info",
        node_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        input_summary: Any = None,
        output_summary: Any = None,
        error: Optional[str] = None,
        **extra: Any,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            run_id=run_id,
            event_id=str(uuid.uuid4()),
            timestamp=_utc_now(),
            event_type=event_type,
            status=status,
            node_id=node_id,
            duration_ms=duration_ms,
            input_summary=_safe_summary(input_summary),
            output_summary=_safe_summary(output_summary),
            error=error,
            extra=extra,
        )
        self._history[run_id].append(event)
        for queue in list(self._subscribers.get(run_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
        return event

    def history(self, run_id: str, after_event_id: Optional[str] = None) -> List[WorkflowEvent]:
        events = list(self._history.get(run_id, []))
        if not after_event_id:
            return events
        found = False
        out: List[WorkflowEvent] = []
        for ev in events:
            if found:
                out.append(ev)
            elif ev.event_id == after_event_id:
                found = True
        return out

    async def subscribe(
        self, run_id: str, last_event_id: Optional[str] = None
    ) -> AsyncIterator[WorkflowEvent]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers[run_id].append(queue)
        try:
            for ev in self.history(run_id, after_event_id=last_event_id):
                yield ev
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield ev
                    if ev.event_type in {"workflow_completed", "workflow_failed"}:
                        break
                except asyncio.TimeoutError:
                    # heartbeat as empty ping event
                    yield WorkflowEvent(
                        run_id=run_id,
                        event_id=str(uuid.uuid4()),
                        timestamp=_utc_now(),
                        event_type="heartbeat",
                        status="ok",
                    )
        finally:
            if queue in self._subscribers[run_id]:
                self._subscribers[run_id].remove(queue)


def _safe_summary(value: Any, max_chars: int = 4000) -> Any:
    """Truncate nested structures for SSE safety (no secrets expected)."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and len(value) > max_chars:
            return value[:max_chars] + "…"
        return value
    if isinstance(value, dict):
        return {k: _safe_summary(v, max_chars // 2) for k, v in list(value.items())[:40]}
    if isinstance(value, (list, tuple)):
        return [_safe_summary(v, max_chars // 2) for v in list(value)[:40]]
    text = str(value)
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


event_bus = EventBus()
