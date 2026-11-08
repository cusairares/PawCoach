"""SQLite event log. Source of truth for treat counting and the app's training stats."""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,          -- passive_capture | command_success | command_fail | command_rejected
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


def start_of_day(ts: float) -> float:
    d = datetime.fromtimestamp(ts)
    return datetime(d.year, d.month, d.day).timestamp()


class EventLog:
    def __init__(self, path: Path = DATA_DIR / "events.db"):
        path = Path(path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def add(self, event: Event) -> None:
        row = asdict(event)
        row["treat"] = int(row["treat"])
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, kind, target, detected, reaction_s, treat, confidence, command_id, detail)"
                " VALUES (:ts, :kind, :target, :detected, :reaction_s, :treat, :confidence, :command_id, :detail)",
                row)
            self._conn.commit()

    def treats_since(self, since_ts: float) -> int:
        with self._lock:
            (n,) = self._conn.execute("SELECT COALESCE(SUM(treat), 0) FROM events WHERE ts >= ?",
                                      (since_ts,)).fetchone()
        return int(n)

    def recent(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,))
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def stats(self, since_ts: Optional[float] = None) -> Dict:
        since_ts = start_of_day(time.time()) if since_ts is None else since_ts
        with self._lock:
            rows = self._conn.execute(
                "SELECT kind, target, reaction_s, treat FROM events WHERE ts >= ?", (since_ts,)).fetchall()
        per_pose: Dict[str, Dict] = {}
        for kind, target, reaction, treat in rows:
            p = per_pose.setdefault(target or "-", {"commands": 0, "successes": 0, "captures": 0,
                                                     "reaction_times": []})
            if kind.startswith("command_") and kind != "command_rejected":
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
