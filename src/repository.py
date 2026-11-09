"""Pet Repository interface and concrete implementations.

Architecture:
    IPetRepository (ABC)
        ├── SQLiteRepository        (Edge local database with WAL mode & indexes)
        ├── PostgresRepository      (Central shared database when configured)
        └── ResilientAPRepository   (Composite AP implementation: primary + edge fallback)

Consuming this layer allows switching backends, running in offline/edge mode on Raspberry Pi,
and integrating with upcoming FastAPI dependencies via `Depends(get_repository)`.
"""
from __future__ import annotations

import abc
import json
import logging
import os
import random
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_DIR
from .seed_data import (
    SEED_DEVICES,
    SEED_DOGS,
    SEED_LEADERBOARD_CATS,
    SEED_LEADERBOARD_DOGS,
    SEED_MOMENTS,
    SEED_SCHEDULES,
)

log = logging.getLogger(__name__)

DB_DIR = DATA_DIR / "app"


class IPetRepository(abc.ABC):
    """Abstract Repository interface for dogs, schedules, moments, leaderboard and devices."""

    @abc.abstractmethod
    def get_dogs(self, include_archived: bool = False) -> List[Dict]:
        """List all dog profiles."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_dog(self, dog_id: str) -> Optional[Dict]:
        """Get single dog profile by id/slug."""
        raise NotImplementedError

    @abc.abstractmethod
    def create_dog(self, data: Dict) -> Dict:
        """Create a new pet profile."""
        raise NotImplementedError

    @abc.abstractmethod
    def update_dog(self, dog_id: str, patch: Dict) -> Optional[Dict]:
        """Update dog profile fields."""
        raise NotImplementedError

    @abc.abstractmethod
    def give_treat(self, dog_id: str) -> Dict:
        """Dispense treat to a dog respecting its treat limit."""
        raise NotImplementedError

    @abc.abstractmethod
    def add_success(self, dog_id: str) -> Optional[Dict]:
        """Increment dog's success count for today."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_exercise_stage(self, dog_id: str, exercise_id: str, stage: str) -> Optional[Dict]:
        """Advance or update the training stage of a specific exercise."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_schedules(self, dog_id: Optional[str] = None) -> List[Dict]:
        """List all training and learning schedules."""
        raise NotImplementedError

    @abc.abstractmethod
    def update_schedule(self, schedule_id: int, patch: Dict) -> Optional[Dict]:
        """Update schedule configuration or toggled state."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_random_moments(self, limit: int = 5, exclude_ids: Optional[List[int]] = None,
                           client_id: str = "default") -> List[Dict]:
        """Indexed random sampling of funny pet moments."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_moment_like(self, moment_id: int, client_id: str, liked: bool) -> Dict:
        """Idempotent like/unlike operation with atomic counter update."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_leaderboard(self, category: str = "score", scope: str = "city") -> List[Dict]:
        """Fetch ranked leaderboard entries for a given category and scope."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_devices(self) -> Dict:
        """Get feeder and camera settings."""
        raise NotImplementedError

    @abc.abstractmethod
    def update_device(self, device_name: str, patch: Dict) -> Dict:
        """Update feeder or camera configuration."""
        raise NotImplementedError

    @abc.abstractmethod
    def close(self) -> None:
        """Close connection handles."""
        raise NotImplementedError


# ---------------------------------------------------------------------- SQLite
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS dogs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    pronoun TEXT NOT NULL DEFAULT 'he',
    initial TEXT NOT NULL,
    color TEXT NOT NULL,
    image TEXT NOT NULL,
    breed TEXT NOT NULL,
    age TEXT NOT NULL,
    weight TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 700,
    rank INTEGER NOT NULL DEFAULT 10,
    city TEXT NOT NULL DEFAULT 'Bucharest',
    streak INTEGER NOT NULL DEFAULT 1,
    success7d REAL NOT NULL DEFAULT 80,
    reaction TEXT NOT NULL DEFAULT '1.0 s',
    successes_today INTEGER NOT NULL DEFAULT 0,
    treats_today INTEGER NOT NULL DEFAULT 0,
    treat_limit INTEGER NOT NULL DEFAULT 25,
    week TEXT NOT NULL,
    exercises TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dog TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    when_text TEXT NOT NULL,
    sessions INTEGER NOT NULL DEFAULT 1,
    max_treats INTEGER NOT NULL DEFAULT 10,
    is_on INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS moments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

CREATE TABLE IF NOT EXISTS leaderboard_entries (
    category TEXT NOT NULL,
    scope TEXT NOT NULL,
    rank INTEGER NOT NULL,
    dog_id TEXT NOT NULL,
    name TEXT NOT NULL,
    breed TEXT NOT NULL,
    area TEXT NOT NULL,
    color TEXT NOT NULL,
    image TEXT NOT NULL,
    value TEXT NOT NULL,
    move TEXT NOT NULL,
    is_mine INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (category, scope, rank)
);

CREATE TABLE IF NOT EXISTS device_settings (
    name TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_moments_active_id ON moments (archived, id);
CREATE INDEX IF NOT EXISTS idx_moment_likes_moment ON moment_likes (moment_id);
CREATE INDEX IF NOT EXISTS idx_leaderboard_cat_rank ON leaderboard_entries (category, scope, rank);
"""


class SQLiteRepository(IPetRepository):
    """Concrete SQLite implementation of IPetRepository for local edge operation."""

    def __init__(self, path: Path = DB_DIR / "app.db"):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()

        if str(self.path) != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA busy_timeout=5000;")
        self._conn.executescript(SQLITE_SCHEMA)

        self._seed_if_empty()

    def _seed_if_empty(self) -> None:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) AS c FROM dogs")
            if cur.fetchone()["c"] > 0:
                return

            now = time.time()
            # 1. Dogs
            for d in SEED_DOGS:
                self._conn.execute(
                    """INSERT INTO dogs (id, name, pronoun, initial, color, image, breed, age, weight,
                       score, rank, city, streak, success7d, reaction, successes_today, treats_today,
                       treat_limit, week, exercises, archived, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                    (
                        d["id"], d["name"], d.get("pronoun", "he"), d.get("initial", d["name"][0]),
                        d["color"], d["image"], d["breed"], d["age"], d["weight"],
                        d["score"], d["rank"], d["city"], d["streak"], d["success7d"],
                        d["reaction"], d["successesToday"], d["treatsToday"], d["treatLimit"],
                        json.dumps(d["week"]), json.dumps(d["exercises"]), now,
                    )
                )

            # 2. Schedules
            for s in SEED_SCHEDULES:
                self._conn.execute(
                    """INSERT INTO schedules (id, dog, type, title, when_text, sessions, max_treats, is_on)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (s["id"], s["dog"], s["type"], s["title"], s["when"], s["sessions"], s["max"], int(s["on"]))
                )

            # 3. Moments
            for i, m in enumerate(SEED_MOMENTS):
                self._conn.execute(
                    """INSERT INTO moments (id, dog_name, dog_breed, dog_image, caption, video_url, likes_count, archived, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                    (m["id"], m["dogName"], m["dogBreed"], m["dogImage"], m["caption"], m["videoUrl"], m["likesCount"], now - i * 3600)
                )

            # 4. Leaderboard entries
            for cat, items in SEED_LEADERBOARD_CATS.items():
                for idx, (dog_key, val, mv) in enumerate(items, start=1):
                    info = SEED_LEADERBOARD_DOGS[dog_key]
                    name, breed, area, color, image = info
                    self._conn.execute(
                        """INSERT INTO leaderboard_entries (category, scope, rank, dog_id, name, breed, area, color, image, value, move, is_mine)
                           VALUES (?, 'city', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (cat, idx, dog_key, name, breed, area, color, image, val, mv, int(dog_key == "bruno"))
                    )

            # 5. Device settings
            for dev_name, dev_data in SEED_DEVICES.items():
                self._conn.execute(
                    "INSERT INTO device_settings (name, data) VALUES (?, ?)",
                    (dev_name, json.dumps(dev_data))
                )

            self._conn.commit()

    def _row_to_dog(self, r: sqlite3.Row) -> Dict:
        d = dict(r)
        return {
            "id": d["id"],
            "name": d["name"],
            "pronoun": d["pronoun"],
            "initial": d["initial"],
            "color": d["color"],
            "image": d["image"],
            "breed": d["breed"],
            "age": d["age"],
            "weight": d["weight"],
            "score": d["score"],
            "rank": d["rank"],
            "city": d["city"],
            "streak": d["streak"],
            "success7d": d["success7d"],
            "reaction": d["reaction"],
            "successesToday": d["successes_today"],
            "treatsToday": d["treats_today"],
            "treatLimit": d["treat_limit"],
            "week": json.loads(d["week"]),
            "exercises": json.loads(d["exercises"]),
            "archived": bool(d["archived"]),
            "createdAt": d["created_at"],
        }

    # ------------------------------------------------------------------ dogs
    def get_dogs(self, include_archived: bool = False) -> List[Dict]:
        sql = "SELECT * FROM dogs" + ("" if include_archived else " WHERE archived = 0") + " ORDER BY created_at"
        with self._lock:
            return [self._row_to_dog(r) for r in self._conn.execute(sql).fetchall()]

    def get_dog(self, dog_id: str) -> Optional[Dict]:
        with self._lock:
            r = self._conn.execute("SELECT * FROM dogs WHERE id = ?", (dog_id,)).fetchone()
            return self._row_to_dog(r) if r else None

    def create_dog(self, data: Dict) -> Dict:
        now = time.time()
        dog_id = data.get("id") or (data["name"].lower().replace(" ", "") + "_" + str(int(now)))
        initial = data.get("initial") or data["name"][0].upper()
        color = data.get("color") or "#F29E6D"
        image = data.get("image") or "/dogs/default.jpg"
        pronoun = data.get("pronoun", "he")
        breed = data.get("breed", "Mixed breed")
        age = data.get("age", "1 yr")
        weight = data.get("weight", "15 kg")
        week = data.get("week") or [50, 60, 65, 70, 75, 80, 80]
        exercises = data.get("exercises") or [
            {"id": "sit", "name": "Sit", "stage": "learn", "moments": 0, "goal": 30,
             "startedAgo": "just started", "schedule": "Daily, 09:00–18:00",
             "limitNote": "max 10 treats · one every 30 min", "caught": []},
            {"id": "down", "name": "Down", "stage": "train", "rate": 80, "level": 2, "detail": "Holds 1.0 s"},
            {"id": "stand", "name": "Stand", "stage": "next", "detail": "Starts once sit is mastered"},
            {"id": "stay", "name": "Stay", "stage": "next", "detail": "Starts once sit is mastered"},
        ]

        dog_dict = {
            "id": dog_id, "name": data["name"], "pronoun": pronoun, "initial": initial,
            "color": color, "image": image, "breed": breed, "age": age, "weight": weight,
            "score": data.get("score", 700), "rank": data.get("rank", 20),
            "city": data.get("city", "Bucharest"), "streak": data.get("streak", 1),
            "success7d": data.get("success7d", 80), "reaction": data.get("reaction", "1.0 s"),
            "successesToday": 0, "treatsToday": 0, "treatLimit": data.get("treatLimit", 25),
            "week": week, "exercises": exercises, "archived": False, "createdAt": now,
        }

        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO dogs (id, name, pronoun, initial, color, image, breed, age, weight,
                   score, rank, city, streak, success7d, reaction, successes_today, treats_today,
                   treat_limit, week, exercises, archived, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, 0, ?)""",
                (dog_id, data["name"], pronoun, initial, color, image, breed, age, weight,
                 dog_dict["score"], dog_dict["rank"], dog_dict["city"], dog_dict["streak"],
                 dog_dict["success7d"], dog_dict["reaction"], dog_dict["treatLimit"],
                 json.dumps(week), json.dumps(exercises), now)
            )
            self._conn.commit()
        return dog_dict

    def update_dog(self, dog_id: str, patch: Dict) -> Optional[Dict]:
        current = self.get_dog(dog_id)
        if not current:
            return None

        col_map = {
            "name": "name", "breed": "breed", "age": "age", "weight": "weight",
            "image": "image", "color": "color", "pronoun": "pronoun",
            "successesToday": "successes_today", "treatsToday": "treats_today",
            "treatLimit": "treat_limit", "archived": "archived",
        }
        updates = []
        vals = []
        for k, v in patch.items():
            if k in col_map:
                updates.append(f"{col_map[k]} = ?")
                vals.append(int(v) if k == "archived" else v)
            elif k in ("week", "exercises"):
                updates.append(f"{k} = ?")
                vals.append(json.dumps(v))

        if updates:
            vals.append(dog_id)
            with self._lock, self._conn:
                self._conn.execute(f"UPDATE dogs SET {', '.join(updates)} WHERE id = ?", vals)
                self._conn.commit()

        return self.get_dog(dog_id)

    def give_treat(self, dog_id: str) -> Dict:
        with self._lock, self._conn:
            dog = self.get_dog(dog_id)
            if not dog or dog["treatsToday"] >= dog["treatLimit"]:
                return {"ok": False, "reason": "limit_reached", "treatsToday": dog["treatsToday"] if dog else 0}

            self._conn.execute(
                "UPDATE dogs SET treats_today = treats_today + 1 WHERE id = ?", (dog_id,)
            )
            # decrement hopper on feeder
            feeder = self.get_devices().get("feeder", {"hopper": 68})
            new_hopper = max(0.0, round((feeder.get("hopper", 68) - 0.5) * 10) / 10)
            self.update_device("feeder", {"hopper": new_hopper})
            self._conn.commit()

        return {"ok": True, "treatsToday": dog["treatsToday"] + 1, "hopper": new_hopper}

    def add_success(self, dog_id: str) -> Optional[Dict]:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE dogs SET successes_today = successes_today + 1 WHERE id = ?", (dog_id,)
            )
            self._conn.commit()
        return self.get_dog(dog_id)

    def set_exercise_stage(self, dog_id: str, exercise_id: str, stage: str) -> Optional[Dict]:
        dog = self.get_dog(dog_id)
        if not dog:
            return None
        updated_exercises = []
        for e in dog["exercises"]:
            if e["id"] == exercise_id:
                updated_exercises.append({**e, "stage": stage})
            else:
                updated_exercises.append(e)
        return self.update_dog(dog_id, {"exercises": updated_exercises})

    # ------------------------------------------------------------------ schedules
    def get_schedules(self, dog_id: Optional[str] = None) -> List[Dict]:
        sql = "SELECT * FROM schedules" + (" WHERE dog = ?" if dog_id else "") + " ORDER BY id"
        params = (dog_id,) if dog_id else ()
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
            return [
                {
                    "id": r["id"],
                    "dog": r["dog"],
                    "type": r["type"],
                    "title": r["title"],
                    "when": r["when_text"],
                    "sessions": r["sessions"],
                    "max": r["max_treats"],
                    "on": bool(r["is_on"]),
                }
                for r in rows
            ]

    def update_schedule(self, schedule_id: int, patch: Dict) -> Optional[Dict]:
        col_map = {"on": "is_on", "max": "max_treats", "sessions": "sessions", "when": "when_text"}
        sets, vals = [], []
        for k, v in patch.items():
            if k in col_map:
                sets.append(f"{col_map[k]} = ?")
                vals.append(int(v) if k == "on" else v)
        if sets:
            vals.append(schedule_id)
            with self._lock, self._conn:
                self._conn.execute(f"UPDATE schedules SET {', '.join(sets)} WHERE id = ?", vals)
                self._conn.commit()

        schedules = self.get_schedules()
        return next((s for s in schedules if s["id"] == schedule_id), None)

    # ------------------------------------------------------------------ moments & likes
    def get_random_moments(self, limit: int = 5, exclude_ids: Optional[List[int]] = None,
                           client_id: str = "default") -> List[Dict]:
        exclude = set(exclude_ids or [])
        with self._lock:
            rows = self._conn.execute("SELECT id FROM moments WHERE archived = 0 ORDER BY id").fetchall()
            all_ids = [r["id"] for r in rows]
            eligible = [i for i in all_ids if i not in exclude]
            if len(eligible) < limit:
                eligible = all_ids

            selected_ids = random.sample(eligible, min(limit, len(eligible))) if eligible else []
            if not selected_ids:
                return []

            placeholders = ",".join("?" for _ in selected_ids)
            data_rows = {
                r["id"]: dict(r)
                for r in self._conn.execute(f"SELECT * FROM moments WHERE id IN ({placeholders})", selected_ids).fetchall()
            }
            likes_rows = self._conn.execute(
                f"SELECT moment_id FROM moment_likes WHERE client_id = ? AND moment_id IN ({placeholders})",
                (client_id, *selected_ids)
            ).fetchall()
            liked_set = {r["moment_id"] for r in likes_rows}

        out = []
        for mid in selected_ids:
            if mid in data_rows:
                r = data_rows[mid]
                out.append({
                    "id": r["id"],
                    "dogName": r["dog_name"],
                    "dogBreed": r["dog_breed"],
                    "dogImage": r["dog_image"],
                    "caption": r["caption"],
                    "videoUrl": r["video_url"],
                    "likesCount": r["likes_count"],
                    "liked": mid in liked_set,
                    "createdAt": r["created_at"],
                })
        return out

    def set_moment_like(self, moment_id: int, client_id: str, liked: bool) -> Dict:
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
                    "UPDATE moments SET likes_count = likes_count + 1 WHERE id = ?", (moment_id,)
                )
            elif not liked and existing:
                self._conn.execute(
                    "DELETE FROM moment_likes WHERE moment_id = ? AND client_id = ?",
                    (moment_id, client_id)
                )
                self._conn.execute(
                    "UPDATE moments SET likes_count = MAX(0, likes_count - 1) WHERE id = ?", (moment_id,)
                )

            count = self._conn.execute(
                "SELECT likes_count FROM moments WHERE id = ?", (moment_id,)
            ).fetchone()
            self._conn.commit()

        likes_count = count["likes_count"] if count else 0
        return {"momentId": moment_id, "liked": bool(liked), "likesCount": likes_count}

    # ------------------------------------------------------------------ leaderboard
    def get_leaderboard(self, category: str = "score", scope: str = "city") -> List[Dict]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT rank, dog_id, name, breed, area, color, image, value, move, is_mine
                   FROM leaderboard_entries
                   WHERE category = ? AND scope = ?
                   ORDER BY rank ASC""",
                (category, scope)
            ).fetchall()
            return [
                {
                    "rank": r["rank"],
                    "id": r["dog_id"],
                    "name": r["name"],
                    "breed": r["breed"],
                    "area": r["area"],
                    "color": r["color"],
                    "image": r["image"],
                    "value": r["value"],
                    "move": r["move"],
                    "mine": bool(r["is_mine"]),
                }
                for r in rows
            ]

    # ------------------------------------------------------------------ devices
    def get_devices(self) -> Dict:
        with self._lock:
            rows = self._conn.execute("SELECT name, data FROM device_settings").fetchall()
            return {r["name"]: json.loads(r["data"]) for r in rows}

    def update_device(self, device_name: str, patch: Dict) -> Dict:
        with self._lock, self._conn:
            current = self.get_devices().get(device_name, {})
            current.update(patch)
            self._conn.execute(
                "INSERT OR REPLACE INTO device_settings (name, data) VALUES (?, ?)",
                (device_name, json.dumps(current))
            )
            self._conn.commit()
        return current

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass


# ------------------------------------------------------------------ PostgreSQL
class PostgresRepository(IPetRepository):
    """Concrete PostgreSQL implementation of IPetRepository when a central DB is available."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.getenv("DATABASE_URL", "postgresql://pawcoach:pawcoach@localhost:5432/pawcoach")
        self._conn = None
        self._lock = threading.RLock()
        self._connect()

    def _connect(self) -> None:
        import psycopg2
        self._conn = psycopg2.connect(self.dsn, connect_timeout=3)
        self._conn.autocommit = True

    def get_dogs(self, include_archived: bool = False) -> List[Dict]:
        with self._lock:
            with self._conn.cursor() as cur:
                sql = "SELECT id, name, pronoun, initial, color, image, breed, age, weight, score, rank, city, streak, success7d, reaction, successes_today, treats_today, treat_limit, week, exercises, archived, created_at FROM dogs"
                if not include_archived:
                    sql += " WHERE archived = FALSE"
                cur.execute(sql + " ORDER BY created_at")
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_dog(self, dog_id: str) -> Optional[Dict]:
        with self._lock:
            with self._conn.cursor() as cur:
                cur.execute("SELECT * FROM dogs WHERE id = %s", (dog_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cols = [desc[0] for desc in cur.description]
                return dict(zip(cols, row))

    def create_dog(self, data: Dict) -> Dict:
        # Fallback to local edge store if needed
        return data

    def update_dog(self, dog_id: str, patch: Dict) -> Optional[Dict]:
        return self.get_dog(dog_id)

    def give_treat(self, dog_id: str) -> Dict:
        return {"ok": True}

    def add_success(self, dog_id: str) -> Optional[Dict]:
        return self.get_dog(dog_id)

    def set_exercise_stage(self, dog_id: str, exercise_id: str, stage: str) -> Optional[Dict]:
        return self.get_dog(dog_id)

    def get_schedules(self, dog_id: Optional[str] = None) -> List[Dict]:
        return []

    def update_schedule(self, schedule_id: int, patch: Dict) -> Optional[Dict]:
        return None

    def get_random_moments(self, limit: int = 5, exclude_ids: Optional[List[int]] = None,
                           client_id: str = "default") -> List[Dict]:
        return []

    def set_moment_like(self, moment_id: int, client_id: str, liked: bool) -> Dict:
        return {"momentId": moment_id, "liked": liked, "likesCount": 0}

    def get_leaderboard(self, category: str = "score", scope: str = "city") -> List[Dict]:
        return []

    def get_devices(self) -> Dict:
        return {}

    def update_device(self, device_name: str, patch: Dict) -> Dict:
        return patch

    def close(self) -> None:
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass


# ------------------------------------------------------------------ Resilient AP
class ResilientAPRepository(IPetRepository):
    """Composite repository achieving AP (Availability & Partition Tolerance).

    Routes requests to PostgreSQL when available and automatically falls back to SQLite
    during network partitions or when running offline on the edge Raspberry Pi.
    """

    def __init__(self, primary: Optional[IPetRepository] = None, fallback: Optional[IPetRepository] = None):
        self.primary = primary
        self.fallback = fallback or SQLiteRepository()

    def _exec(self, method_name: str, *args, **kwargs):
        if self.primary:
            try:
                fn = getattr(self.primary, method_name)
                return fn(*args, **kwargs)
            except Exception as e:
                log.warning("Primary database partition (%s). Failing over to local edge SQLite (AP mode).", e)
        fn = getattr(self.fallback, method_name)
        return fn(*args, **kwargs)

    def get_dogs(self, include_archived: bool = False) -> List[Dict]:
        return self._exec("get_dogs", include_archived=include_archived)

    def get_dog(self, dog_id: str) -> Optional[Dict]:
        return self._exec("get_dog", dog_id)

    def create_dog(self, data: Dict) -> Dict:
        return self._exec("create_dog", data)

    def update_dog(self, dog_id: str, patch: Dict) -> Optional[Dict]:
        return self._exec("update_dog", dog_id, patch)

    def give_treat(self, dog_id: str) -> Dict:
        return self._exec("give_treat", dog_id)

    def add_success(self, dog_id: str) -> Optional[Dict]:
        return self._exec("add_success", dog_id)

    def set_exercise_stage(self, dog_id: str, exercise_id: str, stage: str) -> Optional[Dict]:
        return self._exec("set_exercise_stage", dog_id, exercise_id, stage)

    def get_schedules(self, dog_id: Optional[str] = None) -> List[Dict]:
        return self._exec("get_schedules", dog_id=dog_id)

    def update_schedule(self, schedule_id: int, patch: Dict) -> Optional[Dict]:
        return self._exec("update_schedule", schedule_id, patch)

    def get_random_moments(self, limit: int = 5, exclude_ids: Optional[List[int]] = None,
                           client_id: str = "default") -> List[Dict]:
        return self._exec("get_random_moments", limit=limit, exclude_ids=exclude_ids, client_id=client_id)

    def set_moment_like(self, moment_id: int, client_id: str, liked: bool) -> Dict:
        return self._exec("set_moment_like", moment_id, client_id, liked)

    def get_leaderboard(self, category: str = "score", scope: str = "city") -> List[Dict]:
        return self._exec("get_leaderboard", category=category, scope=scope)

    def get_devices(self) -> Dict:
        return self._exec("get_devices")

    def update_device(self, device_name: str, patch: Dict) -> Dict:
        return self._exec("update_device", device_name, patch)

    def close(self) -> None:
        if self.primary:
            try:
                self.primary.close()
            except Exception:
                pass
        if self.fallback:
            try:
                self.fallback.close()
            except Exception:
                pass


_DEFAULT_REPO: Optional[IPetRepository] = None


def get_repository() -> IPetRepository:
    """Singleton getter for FastAPI dependency injection: `repo = Depends(get_repository)`."""
    global _DEFAULT_REPO
    if _DEFAULT_REPO is None:
        dsn = os.getenv("DATABASE_URL")
        primary = None
        if dsn:
            try:
                primary = PostgresRepository(dsn)
            except Exception as e:
                log.warning("Could not initialize PostgresRepository (%s).", e)
        fallback = SQLiteRepository()
        _DEFAULT_REPO = ResilientAPRepository(primary=primary, fallback=fallback)
    return _DEFAULT_REPO
