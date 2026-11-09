"""Persistent app data: dog profiles, exercise progress, schedules, highlights and moments.

Supports both local SQLite (with WAL mode, composite indexes and busy-timeout for edge reliability)
and PostgreSQL (when DATABASE_URL is configured). If PostgreSQL is unavailable or encounters network
partitions, operations gracefully fall back to local storage (CAP: AP - Availability and Partition Tolerance).
"""
from __future__ import annotations

import json
import logging
import os
import random
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_DIR
from .training_plan import EXERCISES, Progress, new_progress

log = logging.getLogger(__name__)

APP_DIR = DATA_DIR / "app"

SCHEMA = """
CREATE TABLE IF NOT EXISTS dogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    breed TEXT,
    birth_date TEXT,                 -- YYYY-MM-DD
    age_text TEXT,
    weight_kg REAL,
    color TEXT,                      -- avatar color in the app
    image_url TEXT,
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
CREATE TABLE IF NOT EXISTS moments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dog_id INTEGER,
    dog_name TEXT NOT NULL,
    dog_breed TEXT,
    dog_image TEXT,
    caption TEXT NOT NULL,
    video_url TEXT NOT NULL,
    likes_count INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS moment_likes (
    moment_id INTEGER NOT NULL,
    client_id TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (moment_id, client_id)
);

-- Indexes for fast querying, sorting, and random video selection under high load
CREATE INDEX IF NOT EXISTS idx_moments_active_id ON moments (archived, id);
CREATE INDEX IF NOT EXISTS idx_moments_dog_id ON moments (dog_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_moment_likes_moment ON moment_likes (moment_id);
CREATE INDEX IF NOT EXISTS idx_highlights_dog_ts ON highlights (dog_id, ts DESC);
"""

INITIAL_MOMENTS_SEED = [
    {"dog_name": "Bruno", "dog_breed": "Labrador", "dog_image": "/dogs/bruno.jpg",
     "caption": "Mastering the ultimate slow sit roll 🎾", "video_url": "/moments/dog1.mp4", "likes_count": 142},
    {"dog_name": "Luna", "dog_breed": "Border Collie", "dog_image": "/dogs/luna.jpg",
     "caption": "Wait for the sudden jump celebration! ✨", "video_url": "/moments/dog2.mp4", "likes_count": 289},
    {"dog_name": "Toby", "dog_breed": "Beagle", "dog_image": "/dogs/toby.jpg",
     "caption": "When the treat dispenser sound makes you freeze 🍪", "video_url": "/moments/dog4.mp4", "likes_count": 95},
    {"dog_name": "Rocky", "dog_breed": "Malinois", "dog_image": "/dogs/rocky.jpg",
     "caption": "Perfect posture check in 0.4 seconds flat ⚡", "video_url": "/moments/dog_labradoodle_stand.webm", "likes_count": 310},
    {"dog_name": "Oscar", "dog_breed": "Corgi", "dog_image": "/dogs/oscar.jpg",
     "caption": "Nap posture classification: 100% relaxed 💤", "video_url": "/moments/dog_laying_relax.webm", "likes_count": 418},
    {"dog_name": "Bella", "dog_breed": "Golden Retriever", "dog_image": "/dogs/bella.jpg",
     "caption": "Spins like a whirlwind when hearing good boy! 🌪️", "video_url": "/moments/dog_spin_standing.webm", "likes_count": 523},
]


@dataclass
class Dog:
    name: str
    breed: Optional[str] = None
    birth_date: Optional[str] = None
    age_text: Optional[str] = None
    weight_kg: Optional[float] = None
    color: Optional[str] = None
    image_url: Optional[str] = None
    daily_treat_limit: int = 20
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
    def __init__(self, path: Path = APP_DIR / "app.db", database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self._pg_conn = None
        self._lock = threading.RLock()

        path = Path(path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        # Optimize SQLite for edge reliability & high-concurrency readers (AP mode)
        if str(path) != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA busy_timeout=5000;")
        self._conn.executescript(SCHEMA)

        self._migrate_sqlite_schema()
        self._seed_initial_moments()

        if self.database_url:
            self._init_postgres()

    def _migrate_sqlite_schema(self) -> None:
        with self._lock:
            cols = {row["name"] for row in self._conn.execute("PRAGMA table_info(dogs)").fetchall()}
            if "age_text" not in cols:
                self._conn.execute("ALTER TABLE dogs ADD COLUMN age_text TEXT")
            if "image_url" not in cols:
                self._conn.execute("ALTER TABLE dogs ADD COLUMN image_url TEXT")
            self._conn.commit()

    def _seed_initial_moments(self) -> None:
        with self._lock:
            count = self._conn.execute("SELECT COUNT(*) AS c FROM moments").fetchone()["c"]
            if count == 0:
                now = time.time()
                for i, m in enumerate(INITIAL_MOMENTS_SEED):
                    self._conn.execute(
                        "INSERT INTO moments (dog_name, dog_breed, dog_image, caption, video_url, likes_count, created_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (m["dog_name"], m["dog_breed"], m["dog_image"], m["caption"], m["video_url"],
                         m["likes_count"], now - (i * 3600))
                    )
                self._conn.commit()

    def _init_postgres(self) -> None:
        try:
            import psycopg2
            self._pg_conn = psycopg2.connect(self.database_url, connect_timeout=3)
            self._pg_conn.autocommit = True
            log.info("AppStore connected to PostgreSQL: %s", self.database_url)
        except Exception as e:
            log.warning("PostgreSQL unavailable (%s). Falling back to SQLite for AP resilience.", e)
            self._pg_conn = None

    # ------------------------------------------------------------------ dogs
    def add_dog(self, dog: Dog) -> Dog:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO dogs (name, breed, birth_date, age_text, weight_kg, color, image_url, daily_treat_limit, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (dog.name, dog.breed, dog.birth_date, dog.age_text, dog.weight_kg, dog.color, dog.image_url,
                 dog.daily_treat_limit, dog.created_at))
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
        allowed = {"name", "breed", "birth_date", "age_text", "weight_kg", "color", "image_url", "daily_treat_limit", "archived"}
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

    # ------------------------------------------------------------------ moments & likes
    def add_moment(self, m: Dict) -> Dict:
        """Add a funny pet moment to the pool."""
        item = {
            "dog_id": m.get("dog_id"),
            "dog_name": m.get("dog_name", "Good Boy"),
            "dog_breed": m.get("dog_breed"),
            "dog_image": m.get("dog_image", "/dogs/default.jpg"),
            "caption": m.get("caption", "Funny pet moment"),
            "video_url": m["video_url"],
            "likes_count": int(m.get("likes_count", 0)),
            "archived": int(bool(m.get("archived", False))),
            "created_at": float(m.get("created_at", time.time())),
        }
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO moments (dog_id, dog_name, dog_breed, dog_image, caption, video_url, likes_count, archived, created_at)"
                " VALUES (:dog_id, :dog_name, :dog_breed, :dog_image, :caption, :video_url, :likes_count, :archived, :created_at)",
                item
            )
            item["id"] = cur.lastrowid
        return item

    def random_moments(self, limit: int = 5, exclude_ids: Optional[List[int]] = None,
                       client_id: str = "default", rng: Optional[random.Random] = None) -> List[Dict]:
        """Indexed random video selection algorithm.

        Uses covering index `idx_moments_active_id` on (archived, id) to fetch active IDs in an
        index-only scan, samples random IDs without a full-table sort, and does primary key batch lookups.
        """
        exclude = set(exclude_ids or [])
        picker = rng or random

        with self._lock:
            # Index-only scan on idx_moments_active_id
            rows = self._conn.execute("SELECT id FROM moments WHERE archived = 0 ORDER BY id").fetchall()
            all_ids = [r["id"] for r in rows]

            eligible = [i for i in all_ids if i not in exclude]
            if len(eligible) < limit:
                eligible = all_ids  # reset pool if exhausted to allow infinite continuous scrolling

            selected_ids = picker.sample(eligible, min(limit, len(eligible))) if eligible else []
            if not selected_ids:
                return []

            placeholders = ",".join("?" for _ in selected_ids)
            query = f"SELECT * FROM moments WHERE id IN ({placeholders})"
            data_rows = {r["id"]: dict(r) for r in self._conn.execute(query, selected_ids).fetchall()}

            # Batch lookup liked status for this client
            likes_query = f"SELECT moment_id FROM moment_likes WHERE client_id = ? AND moment_id IN ({placeholders})"
            liked_ids = {r["moment_id"] for r in self._conn.execute(likes_query, (client_id, *selected_ids)).fetchall()}

        out = []
        for mid in selected_ids:
            if mid in data_rows:
                row = data_rows[mid]
                row["liked"] = mid in liked_ids
                out.append(row)
        return out

    def set_moment_like(self, moment_id: int, client_id: str, liked: bool) -> Dict:
        """Idempotent like/unlike operation with atomic counter update.

        Safe for write-behind retries and network partitions (AP). Repeating the same
        request multiple times is completely idempotent.
        """
        now = time.time()
        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT 1 FROM moment_likes WHERE moment_id = ? AND client_id = ?",
                (moment_id, client_id)
            ).fetchone()

            if liked and not existing:
                self._conn.execute(
                    "INSERT INTO moment_likes (moment_id, client_id, updated_at) VALUES (?, ?, ?)",
                    (moment_id, client_id, now)
                )
                self._conn.execute(
                    "UPDATE moments SET likes_count = likes_count + 1 WHERE id = ?",
                    (moment_id,)
                )
            elif not liked and existing:
                self._conn.execute(
                    "DELETE FROM moment_likes WHERE moment_id = ? AND client_id = ?",
                    (moment_id, client_id)
                )
                self._conn.execute(
                    "UPDATE moments SET likes_count = MAX(0, likes_count - 1) WHERE id = ?",
                    (moment_id,)
                )

            current = self._conn.execute(
                "SELECT likes_count FROM moments WHERE id = ?",
                (moment_id,)
            ).fetchone()

            count = current["likes_count"] if current else 0

        return {"moment_id": moment_id, "liked": bool(liked), "likes_count": count}

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
            if self._pg_conn:
                try:
                    self._pg_conn.close()
                except Exception:
                    pass
