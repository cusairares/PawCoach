"""Persistent app data: dog profiles, exercise progress, schedules and highlights.

Stored in ``data/app/app.db`` (SQLite), separate from the event log so the vision /
behavior code stays independent of the app's data model.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_DIR
from .training_plan import EXERCISES, Progress, new_progress

APP_DIR = DATA_DIR / "app"

SCHEMA = """
CREATE TABLE IF NOT EXISTS dogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    breed TEXT,
    birth_date TEXT,                 -- YYYY-MM-DD
    weight_kg REAL,
    color TEXT,                      -- avatar color in the app
    pronoun TEXT NOT NULL DEFAULT 'he',  -- he | she, for the app's texts
    daily_treat_limit INTEGER NOT NULL DEFAULT 20,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS progress (
    dog_id INTEGER NOT NULL,
    exercise_id TEXT NOT NULL,
    data TEXT NOT NULL,              -- JSON of training_plan.Progress
    PRIMARY KEY (dog_id, exercise_id)
);
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL               -- JSON of Schedule
);
CREATE TABLE IF NOT EXISTS highlights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    dog_id INTEGER,
    kind TEXT NOT NULL,              -- personal_best | first_time | level_up | learned | mastered
    title TEXT NOT NULL,
    exercise_id TEXT,
    value REAL,
    clip_path TEXT,
    duration_s REAL
);
"""


@dataclass
class Dog:
    name: str
    breed: Optional[str] = None
    birth_date: Optional[str] = None
    weight_kg: Optional[float] = None
    color: Optional[str] = None
    daily_treat_limit: int = 20
    pronoun: str = "he"                        # he | she
    id: Optional[int] = None
    archived: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Schedule:
    """A learning window (``kind='learn'``) or training sessions at fixed times (``kind='train'``).

    max_treats      learn: per window and day · train: per session
    min_interval_s  learn: at most one treat per this many seconds (app: "one every 30 min")
    """
    dog_id: int
    kind: str                                  # learn | train
    exercise_ids: List[str]
    days: List[int] = field(default_factory=lambda: list(range(7)))   # 0 = Monday
    start: Optional[str] = None                # learn: "10:00"
    end: Optional[str] = None                  # learn: "17:00"
    times: List[str] = field(default_factory=list)                    # train: ["08:00", "18:30"]
    reps: int = 10
    max_treats: int = 10
    min_interval_s: float = 1800.0
    enabled: bool = True
    id: Optional[int] = None

    def __post_init__(self) -> None:
        if self.kind not in ("learn", "train"):
            raise ValueError("kind must be 'learn' or 'train'")
        unknown = [e for e in self.exercise_ids if e not in EXERCISES]
        if unknown:
            raise ValueError(f"Unknown exercises: {unknown}")
        if self.kind == "learn" and not (self.start and self.end):
            raise ValueError("A learning schedule needs start and end times")
        if self.kind == "train" and not self.times:
            raise ValueError("A training schedule needs at least one time")

    @property
    def sessions_per_day(self) -> int:
        return len(self.times) if self.kind == "train" else 1

    @property
    def treats_per_day(self) -> int:
        return self.max_treats * self.sessions_per_day

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["treats_per_day"] = self.treats_per_day
        return d


def _schedule_from(data: Dict, id_: int) -> Schedule:
    names = {f.name for f in fields(Schedule)}
    return Schedule(**{k: v for k, v in data.items() if k in names and k != "id"}, id=id_)


class AppStore:
    def __init__(self, path: Path = APP_DIR / "app.db"):
        path = Path(path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._lock = threading.RLock()

    def _migrate(self) -> None:
        """Adds columns that older app.db files don't have yet."""
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(dogs)")}
        if "pronoun" not in cols:
            self._conn.execute("ALTER TABLE dogs ADD COLUMN pronoun TEXT NOT NULL DEFAULT 'he'")
            self._conn.commit()

    # ------------------------------------------------------------------ dogs
    def add_dog(self, dog: Dog) -> Dog:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO dogs (name, breed, birth_date, weight_kg, color, daily_treat_limit, pronoun,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (dog.name, dog.breed, dog.birth_date, dog.weight_kg, dog.color, dog.daily_treat_limit,
                 dog.pronoun, dog.created_at))
        dog.id = cur.lastrowid
        for ex_id in EXERCISES:
            self.save_progress(new_progress(dog.id, ex_id))
        return dog

    def dogs(self, include_archived: bool = False) -> List[Dog]:
        sql = "SELECT * FROM dogs" + ("" if include_archived else " WHERE archived = 0") + " ORDER BY id"
        with self._lock:
            return [Dog(**{**dict(r), "archived": bool(r["archived"])}) for r in self._conn.execute(sql)]

    def dog(self, dog_id: int) -> Optional[Dog]:
        with self._lock:
            r = self._conn.execute("SELECT * FROM dogs WHERE id = ?", (dog_id,)).fetchone()
        return Dog(**{**dict(r), "archived": bool(r["archived"])}) if r else None

    def update_dog(self, dog_id: int, values: Dict) -> Dog:
        allowed = {"name", "breed", "birth_date", "weight_kg", "color", "daily_treat_limit", "pronoun",
                   "archived"}
        unknown = set(values) - allowed
        if unknown:
            raise KeyError(f"Unknown dog fields: {sorted(unknown)}")
        if values:
            cols = ", ".join(f"{k} = ?" for k in values)
            with self._lock, self._conn:
                self._conn.execute(f"UPDATE dogs SET {cols} WHERE id = ?", (*values.values(), dog_id))
        return self.dog(dog_id)

    # ------------------------------------------------------------------ progress
    def progress(self, dog_id: int, exercise_id: str) -> Progress:
        with self._lock:
            r = self._conn.execute("SELECT data FROM progress WHERE dog_id = ? AND exercise_id = ?",
                                   (dog_id, exercise_id)).fetchone()
        return Progress(**json.loads(r["data"])) if r else new_progress(dog_id, exercise_id)

    def all_progress(self, dog_id: int) -> List[Progress]:
        return [self.progress(dog_id, ex_id) for ex_id in EXERCISES]

    def save_progress(self, p: Progress) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT OR REPLACE INTO progress (dog_id, exercise_id, data) VALUES (?, ?, ?)",
                               (p.dog_id, p.exercise_id, json.dumps(asdict(p))))

    # ------------------------------------------------------------------ schedules
    def add_schedule(self, s: Schedule) -> Schedule:
        data = asdict(s)
        data.pop("id")
        with self._lock, self._conn:
            s.id = self._conn.execute("INSERT INTO schedules (data) VALUES (?)", (json.dumps(data),)).lastrowid
        return s

    def schedules(self, dog_id: Optional[int] = None) -> List[Schedule]:
        with self._lock:
            rows = self._conn.execute("SELECT id, data FROM schedules ORDER BY id").fetchall()
        out = [_schedule_from(json.loads(r["data"]), r["id"]) for r in rows]
        return [s for s in out if dog_id is None or s.dog_id == dog_id]

    def schedule(self, schedule_id: int) -> Optional[Schedule]:
        return next((s for s in self.schedules() if s.id == schedule_id), None)

    def update_schedule(self, schedule_id: int, values: Dict) -> Schedule:
        current = self.schedule(schedule_id)
        if current is None:
            raise KeyError(f"Schedule {schedule_id} not found")
        data = {**asdict(current), **values}
        updated = _schedule_from(data, schedule_id)          # validates
        data = asdict(updated)
        data.pop("id")
        with self._lock, self._conn:
            self._conn.execute("UPDATE schedules SET data = ? WHERE id = ?", (json.dumps(data), schedule_id))
        return updated

    def delete_schedule(self, schedule_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))

    # ------------------------------------------------------------------ highlights
    def add_highlight(self, h: Dict) -> int:
        with self._lock, self._conn:
            return self._conn.execute(
                "INSERT INTO highlights (ts, dog_id, kind, title, exercise_id, value, clip_path, duration_s)"
                " VALUES (:ts, :dog_id, :kind, :title, :exercise_id, :value, :clip_path, :duration_s)",
                {"exercise_id": None, "value": None, "clip_path": None, "duration_s": None, **h}).lastrowid

    def set_highlight_clip(self, highlight_id: int, clip_path: str, duration_s: float) -> None:
        with self._lock, self._conn:
            self._conn.execute("UPDATE highlights SET clip_path = ?, duration_s = ? WHERE id = ?",
                               (clip_path, duration_s, highlight_id))

    def highlights(self, dog_id: Optional[int] = None, limit: int = 50) -> List[Dict]:
        sql, params = "SELECT * FROM highlights", []
        if dog_id is not None:
            sql, params = sql + " WHERE dog_id = ?", [dog_id]
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql + " ORDER BY ts DESC LIMIT ?", params + [limit])]

    def highlight(self, highlight_id: int) -> Optional[Dict]:
        with self._lock:
            r = self._conn.execute("SELECT * FROM highlights WHERE id = ?", (highlight_id,)).fetchone()
        return dict(r) if r else None
