"""SQLite event log. Source of truth for treat counting and the app's training stats.

Every event can be attributed to a dog (``dog_id``) and to the schedule that produced it
(``schedule_id``), so limits and stats work per dog / per schedule. Older databases are
migrated in place (the two columns are added if missing).
"""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,          -- passive_capture | command_success | command_fail | command_rejected | manual_treat
    target TEXT,
    detected TEXT,
    reaction_s REAL,
    treat INTEGER NOT NULL DEFAULT 0,
    confidence REAL,
    command_id TEXT,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""

# Columns added after the first version (kept separate so old databases can be migrated).
EXTRA_COLUMNS = {"dog_id": "INTEGER", "schedule_id": "INTEGER"}


@dataclass
class Event:
    kind: str
    ts: float = field(default_factory=time.time)
    target: Optional[str] = None
    detected: Optional[str] = None
    reaction_s: Optional[float] = None
    treat: bool = False
    confidence: Optional[float] = None
    command_id: Optional[str] = None
    detail: Optional[str] = None
    dog_id: Optional[int] = None
    schedule_id: Optional[int] = None


def start_of_day(ts: float) -> float:
    d = datetime.fromtimestamp(ts)
    return datetime(d.year, d.month, d.day).timestamp()


def _where(since_ts: Optional[float] = None, dog_id: Optional[int] = None,
           schedule_id: Optional[int] = None):
    clauses, params = [], []
    if since_ts is not None:
        clauses.append("ts >= ?")
        params.append(since_ts)
    if dog_id is not None:
        clauses.append("dog_id = ?")
        params.append(dog_id)
    if schedule_id is not None:
        clauses.append("schedule_id = ?")
        params.append(schedule_id)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


class EventLog:
    def __init__(self, path: Path = DATA_DIR / "events.db"):
        path = Path(path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.executescript(SCHEMA)
        existing = {row[1] for row in self._conn.execute("PRAGMA table_info(events)")}
        for name, sql_type in EXTRA_COLUMNS.items():
            if name not in existing:
                self._conn.execute(f"ALTER TABLE events ADD COLUMN {name} {sql_type}")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_dog_ts ON events(dog_id, ts)")
        self._conn.commit()
        self._lock = threading.Lock()

    def add(self, event: Event) -> None:
        row = asdict(event)
        row["treat"] = int(row["treat"])
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, kind, target, detected, reaction_s, treat, confidence, command_id,"
                " detail, dog_id, schedule_id) VALUES (:ts, :kind, :target, :detected, :reaction_s, :treat,"
                " :confidence, :command_id, :detail, :dog_id, :schedule_id)",
                row)
            self._conn.commit()

    def treats_since(self, since_ts: float, dog_id: Optional[int] = None,
                     schedule_id: Optional[int] = None) -> int:
        where, params = _where(since_ts, dog_id, schedule_id)
        with self._lock:
            (n,) = self._conn.execute(f"SELECT COALESCE(SUM(treat), 0) FROM events{where}", params).fetchone()
        return int(n)

    def last_treat_ts(self, dog_id: Optional[int] = None, schedule_id: Optional[int] = None) -> Optional[float]:
        where, params = _where(None, dog_id, schedule_id)
        where = (where + " AND" if where else " WHERE") + " treat = 1"
        with self._lock:
            (ts,) = self._conn.execute(f"SELECT MAX(ts) FROM events{where}", params).fetchone()
        return ts

    def recent(self, limit: int = 50, dog_id: Optional[int] = None) -> List[Dict]:
        where, params = _where(None, dog_id)
        with self._lock:
            cur = self._conn.execute(f"SELECT * FROM events{where} ORDER BY ts DESC LIMIT ?", params + [limit])
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def count(self, kind: str, target: Optional[str] = None, dog_id: Optional[int] = None) -> int:
        where, params = _where(None, dog_id)
        where = (where + " AND" if where else " WHERE") + " kind = ?"
        params.append(kind)
        if target is not None:
            where += " AND target = ?"
            params.append(target)
        with self._lock:
            (n,) = self._conn.execute(f"SELECT COUNT(*) FROM events{where}", params).fetchone()
        return int(n)

    def best_reaction(self, target: str, dog_id: Optional[int] = None,
                      before_ts: Optional[float] = None) -> Optional[float]:
        where, params = _where(None, dog_id)
        where = (where + " AND" if where else " WHERE") + " kind = 'command_success' AND target = ?"
        params.append(target)
        if before_ts is not None:
            where += " AND ts < ?"
            params.append(before_ts)
        with self._lock:
            (best,) = self._conn.execute(f"SELECT MIN(reaction_s) FROM events{where}", params).fetchone()
        return best

    def stats(self, since_ts: Optional[float] = None, dog_id: Optional[int] = None) -> Dict:
        since_ts = start_of_day(time.time()) if since_ts is None else since_ts
        where, params = _where(since_ts, dog_id)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT kind, target, reaction_s, treat FROM events{where}", params).fetchall()
        per_pose: Dict[str, Dict] = {}
        for kind, target, reaction, treat in rows:
            p = per_pose.setdefault(target or "-", {"commands": 0, "successes": 0, "captures": 0,
                                                     "reaction_times": []})
            if kind in ("command_success", "command_fail"):
                p["commands"] += 1
            if kind == "command_success":
                p["successes"] += 1
                if reaction is not None:
                    p["reaction_times"].append(reaction)
            if kind == "passive_capture":
                p["captures"] += 1
        for p in per_pose.values():
            rts = p.pop("reaction_times")
            p["success_rate"] = p["successes"] / p["commands"] if p["commands"] else None
            p["avg_reaction_s"] = sum(rts) / len(rts) if rts else None
        return {"since": since_ts, "treats": sum(r[3] for r in rows), "per_pose": per_pose}

    def daily(self, days: int = 7, dog_id: Optional[int] = None, today: Optional[date] = None) -> List[Dict]:
        """One row per day (oldest first): commands, successes, success_rate, captures, treats,
        avg_reaction_s. Days without events are included with zeros (for charts)."""
        today = today or date.today()
        first = today - timedelta(days=days - 1)
        since = datetime(first.year, first.month, first.day).timestamp()
        where, params = _where(since, dog_id)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT ts, kind, reaction_s, treat FROM events{where}", params).fetchall()
        buckets = {(first + timedelta(days=i)).isoformat(): {"commands": 0, "successes": 0, "captures": 0,
                                                               "treats": 0, "_rt": []} for i in range(days)}
        for ts, kind, reaction, treat in rows:
            b = buckets.get(date.fromtimestamp(ts).isoformat())
            if b is None:
                continue
            if kind in ("command_success", "command_fail"):
                b["commands"] += 1
            if kind == "command_success":
                b["successes"] += 1
                if reaction is not None:
                    b["_rt"].append(reaction)
            if kind == "passive_capture":
                b["captures"] += 1
            b["treats"] += int(treat or 0)
        out = []
        for day, b in buckets.items():
            rts = b.pop("_rt")
            out.append({"date": day, **b,
                        "success_rate": b["successes"] / b["commands"] if b["commands"] else None,
                        "avg_reaction_s": sum(rts) / len(rts) if rts else None})
        return out

    def streak_days(self, dog_id: Optional[int] = None, today: Optional[date] = None) -> int:
        """Consecutive days (ending today, or yesterday if nothing yet today) with any training."""
        where, params = _where(None, dog_id)
        where = (where + " AND" if where else " WHERE") + \
            " kind IN ('passive_capture', 'command_success', 'command_fail')"
        with self._lock:
            rows = self._conn.execute(f"SELECT DISTINCT date(ts, 'unixepoch', 'localtime') FROM events{where}",
                                      params).fetchall()
        active = {r[0] for r in rows}
        day = today or date.today()
        if day.isoformat() not in active:
            day -= timedelta(days=1)
        streak = 0
        while day.isoformat() in active:
            streak += 1
            day -= timedelta(days=1)
        return streak
