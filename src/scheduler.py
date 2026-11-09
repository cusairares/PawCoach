"""Decides which schedules are active right now.

* learn schedules open a time window in which passive capture runs for that dog's
  exercises, with the schedule's treat cap and minimum interval between treats.
* train schedules start an automatic session (``reps`` commands) at each listed time,
  once per day per time slot.
"""
from __future__ import annotations

from datetime import datetime, time as dtime
from typing import List, Optional, Set, Tuple

from .app_store import Schedule

SESSION_GRACE_S = 120          # a training slot can start up to 2 minutes late


def _t(hhmm: str) -> dtime:
    h, m = hhmm.split(":")
    return dtime(int(h), int(m))


def learning_window(schedules: List[Schedule], dog_id: int, now: datetime) -> Optional[Schedule]:
    """The enabled learn schedule for this dog covering ``now`` (first match), if any."""
    for s in schedules:
        if (s.enabled and s.kind == "learn" and s.dog_id == dog_id and now.weekday() in s.days
                and _t(s.start) <= now.time() < _t(s.end)):
            return s
    return None


def window_start(s: Schedule, now: datetime) -> float:
    return datetime.combine(now.date(), _t(s.start)).timestamp()


def has_learning_schedules(schedules: List[Schedule], dog_id: int) -> bool:
    return any(s.enabled and s.kind == "learn" and s.dog_id == dog_id for s in schedules)


class SessionClock:
    """Remembers which training slots already ran today, so each one starts once."""

    def __init__(self) -> None:
        self._done: Set[Tuple[int, str, str]] = set()

    def due(self, schedules: List[Schedule], now: datetime) -> List[Tuple[Schedule, str]]:
        out = []
        for s in schedules:
            if not (s.enabled and s.kind == "train" and now.weekday() in s.days):
                continue
            for slot in s.times:
                start = datetime.combine(now.date(), _t(slot))
                key = (s.id, now.date().isoformat(), slot)
                if key not in self._done and 0 <= (now - start).total_seconds() <= SESSION_GRACE_S:
                    self._done.add(key)
                    out.append((s, slot))
        return out
