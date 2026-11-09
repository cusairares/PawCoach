"""App runtime: runs the vision + behavior pipeline together with the app features.

Per frame (``AppRuntime.step``):

    frame -> posture probabilities (camera + models, or the simulated dog in mock mode)
          -> ConsensusBuffer -> passive / active StateTracker -> BehaviorController
          -> exercise progress (learn -> train -> mastered, hold levels)
          -> highlights (clips at milestones) -> status snapshot (for a future app API)

Around it: the active dog, learning windows and training sessions from schedules,
and treat limits per dog and per schedule (``_treat_guard``).

Modes
    mock    no camera / torch: a simulated dog produces the posture probabilities, everything
            after that is the real backend logic. Good for development and demos.
    camera  real camera + DogDetector + PostureClassifier.

Try it (mock, prints events):  python -m src.app_runtime
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from . import scheduler, training_plan as plan
from .app_store import AppStore, Dog, Schedule
from .behavior import BehaviorController
from .config import DATA_DIR, POSE_LABELS, POSTURE_LABELS, EngineConfig, SettingsStore
from .consensus import ConsensusBuffer, StateTracker
from .event_log import Event, EventLog, start_of_day
from .feeder import MockFeeder
from .highlights import HighlightRecorder, is_first_success, is_personal_best
from .live_view import render_frame

log = logging.getLogger(__name__)

SIM_CHOICES = ("sitting", "standing", "lying", "none", "auto")
SESSION_PAUSE_S = 3.0          # pause between reps of an automatic training session


class Busy(Exception):
    """A command is already running."""


class LoggingAudio:
    """Audio stand-in for mock mode: records the keys instead of playing files."""

    def __init__(self) -> None:
        self.history: List[str] = []

    def play(self, keys) -> None:
        keys = list(keys)
        self.history.extend(keys)
        log.info("[audio] (mock) %s", " + ".join(keys))


class MockDog:
    """Simulated dog. Changes pose now and then and obeys commands after a short delay."""

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()
        self.pose = "standing"
        self.forced = False
        self._pending: Optional[tuple] = None
        self._next_change = 0.0

    def set_pose(self, pose: str) -> None:
        if pose not in SIM_CHOICES:
            raise ValueError(f"Unknown simulated pose '{pose}'. Expected one of {SIM_CHOICES}")
        self.forced = pose != "auto"
        if self.forced:
            self.pose, self._pending = pose, None

    def on_command(self, target: str, now: float) -> None:
        if self.forced:
            return
        if self.pose == target:                      # the backend needs a transition into the pose
            self.pose = "standing" if target != "standing" else "sitting"
        self._pending = (target, now + self.rng.uniform(0.8, 2.2))

    def step(self, now: float) -> None:
        if self.forced:
            return
        if self._pending:
            target, at = self._pending
            if now >= at:
                self.pose, self._pending = target, None
                self._next_change = now + self.rng.uniform(8, 14)
            return
        if now >= self._next_change:
            self.pose = self.rng.choice(POSE_LABELS)
            self._next_change = now + self.rng.uniform(6, 12)

    def probs(self) -> Optional[np.ndarray]:
        if self.pose == "none":
            return None
        p = np.full(len(POSTURE_LABELS), 0.03, dtype=np.float32)
        p[POSTURE_LABELS.index(self.pose)] = 0.88
        return p / p.sum()


class AppRuntime:
    def __init__(self, mode: str = "mock", camera_source: str = "0", data_dir: Path = DATA_DIR,
                 fps: float = 10.0, clock: Callable[[], float] = time.monotonic,
                 wall: Callable[[], float] = time.time, rng: Optional[random.Random] = None,
                 highlights: bool = True, demo: bool = False) -> None:
        if mode not in ("mock", "camera"):
            raise ValueError("mode must be 'mock' or 'camera'")
        self.mode, self.fps, self.clock, self.wall = mode, fps, clock, wall
        data_dir = self.data_dir = Path(data_dir)

        self.config = EngineConfig()
        self.settings = SettingsStore(data_dir / "app_settings.json")
        self.event_log = EventLog(data_dir / "events.db")
        self.store = AppStore(data_dir / "app" / "app.db")
        self.feeder = self._make_feeder()
        self.audio = self._make_audio()
        self.behavior = BehaviorController(self.audio, self.feeder, self.event_log, self.settings,
                                           self.config, wall_clock=wall, treat_guard=self._treat_guard)
        c = self.config
        self.buffer = ConsensusBuffer(POSTURE_LABELS, c.window_s, c.min_fill, c.min_entries)
        self.passive = StateTracker(c.passive_threshold, c.exit_threshold)
        self.active = StateTracker(c.active_threshold, c.exit_threshold)
        self.highlights = HighlightRecorder(self.store, data_dir / "app" / "highlights", fps=fps,
                                            enabled=highlights)
        self.sessions = scheduler.SessionClock()

        if demo and not self.store.dogs():
            now_wall = wall()
            seed_demo(self.store, self.settings, now_wall)
            seed_history(self.store, self.event_log, now_wall)
        dogs = self.store.dogs()
        self.dog_id: Optional[int] = dogs[0].id if dogs else None

        self.sim = MockDog(rng) if mode == "mock" else None
        self._camera_source = camera_source
        self._camera = self._detector = self._classifier = None
        self._prev_box = None

        self._session: Optional[Dict] = None         # running automatic training session
        self._command_exercise: Dict[str, str] = {}   # command_id -> exercise_id
        self._schedules_cache = (0.0, [])
        self._lock = threading.Lock()                 # guards the status snapshot
        self._engine_lock = threading.RLock()         # one frame step OR one app action at a time
        self._status: Dict = {}
        self._frame = None
        self._recent: List[Dict] = []
        self._fps = 0.0
        self._running = False

    # ------------------------------------------------------------------ setup
    def _make_feeder(self):
        port = os.getenv("FEEDER_PORT")              # e.g. COM3 or /dev/ttyUSB0
        if port:
            from .feeder import SerialFeeder
            return SerialFeeder(port)
        return MockFeeder()

    def _make_audio(self):
        if self.mode == "camera":
            from .audio import AudioPlayer
            return AudioPlayer(volume=self.settings.current.volume)
        return LoggingAudio()

    def _ensure_camera(self) -> None:
        if self._camera is not None:
            return
        import cv2
        from .detector import DogDetector
        from .posture import PostureClassifier
        src = int(self._camera_source) if self._camera_source.isdigit() else self._camera_source
        self._camera = cv2.VideoCapture(src)
        kwargs = {"imgsz": self.config.pose_imgsz} if hasattr(self.config, "pose_imgsz") else {}
        self._detector = DogDetector(score_threshold=self.config.detector_score_threshold, **kwargs)
        self._classifier = PostureClassifier()

    # ------------------------------------------------------------------ loop
    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._run, daemon=True, name="engine").start()

    def stop(self) -> None:
        self._running = False
        if self._camera is not None:
            self._camera.release()
        if hasattr(self, 'store'):
            self.store.close()
        if hasattr(self, 'event_log'):
            self.event_log.close()

    def _run(self) -> None:
        interval = 1.0 / self.fps
        while self._running:
            t0 = time.perf_counter()
            try:
                self.step()
            except Exception:
                log.exception("engine step failed")
            dt = time.perf_counter() - t0
            self._fps = 0.9 * self._fps + 0.1 * (1.0 / max(dt, interval))
            time.sleep(max(0.0, interval - dt))

    def _sense(self, now: float):
        """(frame or None, posture probabilities or None, box or None)."""
        if self.mode == "mock":
            self.sim.step(now)
            return None, self.sim.probs(), _mock_box(self.sim.pose)
        self._ensure_camera()
        ok, frame = self._camera.read()
        if not ok:
            return None, None, None
        det = self._detector.detect(frame, previous=self._prev_box)
        if det is None:
            return frame, None, None
        self._prev_box = det.box
        if hasattr(self._classifier, "predict_detection"):          # keypoint posture model
            probs = self._classifier.predict_detection(
                det, frame_width=float(frame.shape[1]),
                min_visible_kpts=getattr(self.config, "min_visible_keypoints", 5),
                min_confidence=self.config.posture_min_confidence)
        else:                                                        # crop classifier
            from .detector import square_crop
            probs = self._classifier.predict(square_crop(frame, det.box, padding=self.config.box_padding))
        return frame, probs, det.box

    def step(self, now: Optional[float] = None) -> List[Dict]:
        with self._engine_lock:
            return self._step(now)

    def _step(self, now: Optional[float]) -> List[Dict]:
        now = self.clock() if now is None else now
        frame, probs, box = self._sense(now)
        self._apply_schedules(now)

        self.buffer.push(now, probs)
        vote = self.buffer.vote(now)
        self.passive.update(vote, now)
        self.active.update(vote, now)
        events = self.behavior.update(now, self.passive, self.active)
        out = [_event_dict(e) for e in events] + self._after_events(events)
        self._advance_session(now)

        status = self._build_status(now, probs, box)
        if self.highlights.enabled:
            self.highlights.push_frame(render_frame(frame, status))
        with self._lock:
            self._status, self._frame = status, frame
            if out:
                self._recent = (list(reversed(out)) + self._recent)[:30]
        return out

    # ------------------------------------------------------------------ app rules
    def _schedules(self) -> List[Schedule]:
        t, cached = self._schedules_cache
        if self.clock() - t > 2.0:
            cached = self.store.schedules()
            self._schedules_cache = (self.clock(), cached)
        return cached

    def invalidate_schedules(self) -> None:
        self._schedules_cache = (0.0, [])

    def _apply_schedules(self, now: float) -> None:
        """Sets the behavior context: active dog, learning window or training session."""
        ctx: Dict = {"dog_id": self.dog_id}
        if self.dog_id is not None:
            dt = datetime.fromtimestamp(self.wall())
            schedules = [s for s in self._schedules() if s.dog_id == self.dog_id]
            if self._session is None:
                for s, slot in self.sessions.due(schedules, dt):
                    self._start_session(s, slot)
                    break
            if self._session is not None:
                s = self._session["schedule"]
                ctx.update(schedule_id=s.id, schedule_max_treats=s.max_treats, schedule_scope="all",
                           schedule_since=self._session["since"], passive_enabled=False)
            else:
                window = scheduler.learning_window(schedules, self.dog_id, dt)
                if window is not None:
                    poses = [plan.EXERCISES[e].pose for e in window.exercise_ids
                             if self.store.progress(self.dog_id, e).stage == "learn"]
                    ctx.update(schedule_id=window.id, schedule_max_treats=window.max_treats,
                               schedule_scope="passive",               # cues from the app don't count
                               schedule_since=scheduler.window_start(window, dt),
                               schedule_min_interval_s=window.min_interval_s,
                               passive_enabled=bool(poses), passive_poses=poses)
                elif scheduler.has_learning_schedules(schedules, self.dog_id):
                    ctx["passive_enabled"] = False       # learning happens only inside its windows
        self.behavior.context = ctx

    def _treat_guard(self, now: float, ctx: Dict):
        wall = self.wall()
        dog = self.store.dog(ctx["dog_id"]) if ctx.get("dog_id") else None
        if dog and self.event_log.treats_since(start_of_day(wall), dog_id=dog.id) >= dog.daily_treat_limit:
            return False, "dog_daily_limit"
        sid = ctx.get("schedule_id")
        applies = ctx.get("schedule_scope", "all") == "all" or ctx.get("source") == "passive"
        if sid is not None and applies:
            if self.event_log.treats_since(ctx["schedule_since"], schedule_id=sid) >= ctx["schedule_max_treats"]:
                return False, "schedule_limit"
            gap = ctx.get("schedule_min_interval_s")
            last = self.event_log.last_treat_ts(schedule_id=sid)
            if gap and last is not None and wall - last < gap:
                return False, "schedule_interval"
        return True, "ok"

    def _after_events(self, events: List[Event]) -> List[Dict]:
        """Exercise progress + highlights for the behavior events of this frame."""
        out: List[Dict] = []
        for e in events:
            if e.dog_id is None:
                continue
            dog = self.store.dog(e.dog_id)
            ex_id = None
            plan_events: List[Dict] = []
            if e.kind == "passive_capture" and not (e.detail or "").startswith("silent"):
                ex_id = next((p.exercise_id for p in self.store.all_progress(e.dog_id)
                              if p.stage == "learn" and p.exercise.pose == e.target), None)
                if ex_id:
                    p = self.store.progress(e.dog_id, ex_id)
                    plan_events = plan.on_capture(p)
                    self.store.save_progress(p)
            elif e.kind in ("command_success", "command_fail"):
                ex_id = self._command_exercise.pop(e.command_id, None)
                if ex_id:
                    p = self.store.progress(e.dog_id, ex_id)
                    plan_events = plan.on_attempt(p, e.kind == "command_success")
                    self.store.save_progress(p)
                    if p.stage == "mastered":
                        self._unlock_after(e.dog_id, ex_id)
            if not ex_id:
                continue
            ex = plan.EXERCISES[ex_id]
            for pe in plan_events:
                out.append({**pe, "dog_id": e.dog_id, "ts": e.ts})
                kind = {"level_up": "level_up", "train": "learned", "mastered": "mastered"}.get(
                    pe.get("stage") or pe["type"])
                if kind:
                    h = self.highlights.add(e.ts, e.dog_id, kind, dog.name, ex.name, ex_id, pe.get("hold_s"))
                    out.append({"type": "highlight", **h})
            if is_first_success(self.event_log, e):
                h = self.highlights.add(e.ts, e.dog_id, "first_time", dog.name, ex.name, ex_id)
                out.append({"type": "highlight", **h})
            elif is_personal_best(self.event_log, e):
                h = self.highlights.add(e.ts, e.dog_id, "personal_best", dog.name, ex.name, ex_id, e.reaction_s)
                out.append({"type": "highlight", **h})
        return out

    def _unlock_after(self, dog_id: int, mastered_id: str) -> None:
        for ex in plan.EXERCISES.values():
            if ex.requires == mastered_id:
                p = self.store.progress(dog_id, ex.id)
                if plan.start(p, self.wall()):
                    self.store.save_progress(p)

    # ------------------------------------------------------------------ sessions
    def _start_session(self, s: Schedule, slot: str) -> None:
        exercises = [e for e in s.exercise_ids
                     if plan.EXERCISES[e].detectable
                     and self.store.progress(s.dog_id, e).stage in ("train", "mastered")]
        if not exercises:
            log.info("[session] %s %s skipped: nothing in the training stage", s.id, slot)
            return
        self._session = {"schedule": s, "slot": slot, "exercises": exercises, "done": 0,
                         "since": self.wall(), "next_at": 0.0}
        log.info("[session] schedule %s started (%s)", s.id, slot)

    def _advance_session(self, now: float) -> None:
        sess = self._session
        if sess is None or self.behavior.active is not None:
            return
        s = sess["schedule"]
        capped = self.event_log.treats_since(sess["since"], schedule_id=s.id) >= s.max_treats
        if sess["done"] >= s.reps or capped:
            log.info("[session] schedule %s finished (%d reps)", s.id, sess["done"])
            self._session = None
            return
        if sess["next_at"] == 0.0:
            sess["next_at"] = now
        if now >= sess["next_at"]:
            ex_id = sess["exercises"][sess["done"] % len(sess["exercises"])]
            self._submit(ex_id, schedule_id=s.id)
            sess["done"] += 1
            sess["next_at"] = float("inf")            # set when the command finishes
        elif sess["next_at"] == float("inf"):
            sess["next_at"] = now + SESSION_PAUSE_S

    # ------------------------------------------------------------------ app actions
    # App actions come from the API threads, so they take the engine lock.
    def select_dog(self, dog_id: int) -> None:
        if self.store.dog(dog_id) is None:
            raise KeyError(f"Dog {dog_id} not found")
        with self._engine_lock:
            self.dog_id = dog_id
            self._apply_schedules(self.clock())

    def archive_dog(self, dog_id: int) -> None:
        if self.store.dog(dog_id) is None:
            raise KeyError(f"Dog {dog_id} not found")
        with self._engine_lock:
            self.store.update_dog(dog_id, {"archived": 1})
            if self.dog_id == dog_id:
                self.behavior.cancel()
                self._session = None
                remaining = self.store.dogs()
                self.dog_id = remaining[0].id if remaining else None
                self._apply_schedules(self.clock())

    def submit_command(self, exercise: str) -> str:
        """``exercise``: an exercise id (sit, down, stand, stay) or a posture label (sitting, lying...)."""
        if self.dog_id is None:
            raise ValueError("Add a dog first")
        by_pose = {"sitting": "sit", "lying": "down", "standing": "stand"}
        exercise_id = by_pose.get(exercise, exercise)
        if exercise_id not in plan.EXERCISES:
            raise ValueError(f"Unknown exercise '{exercise}'")
        with self._engine_lock:
            return self._submit(exercise_id)

    def _submit(self, exercise_id: str, schedule_id: Optional[int] = None) -> str:
        # also busy while a submitted command waits for the next frame to pick it up
        if self.behavior.active is not None or not self.behavior._commands.empty():
            raise Busy("A command is already running")
        p = self.store.progress(self.dog_id, exercise_id)
        cmd = plan.command_for(exercise_id, hold_s=p.hold_s, dog_id=self.dog_id, schedule_id=schedule_id)
        self._command_exercise[cmd.command_id] = exercise_id
        if self.sim is not None:
            self.sim.on_command(cmd.pose, self.clock())
        return self.behavior.submit(cmd)

    def cancel_command(self) -> None:
        with self._engine_lock:
            self.behavior.cancel()
            self._session = None

    def manual_treat(self) -> Dict:
        with self._engine_lock:
            self._apply_schedules(self.clock())           # make sure limits use the current dog
            ok, reason = self.behavior.give_treat(self.clock())
        dog = self.store.dog(self.dog_id) if self.dog_id else None
        return {"ok": ok, "reason": None if ok else reason, **self._treat_counts(dog)}

    def test_treat(self) -> bool:
        """Feeder test from the app: dispenses once, not counted for any dog."""
        with self._engine_lock:
            return bool(self.feeder.dispense())

    def set_sim_pose(self, pose: str) -> None:
        if self.sim is None:
            raise RuntimeError("Simulation is only available in mock mode")
        with self._engine_lock:
            self.sim.set_pose(pose)

    # ------------------------------------------------------------------ read models
    def _treat_counts(self, dog: Optional[Dog]) -> Dict:
        since = start_of_day(self.wall())
        if dog is None:
            return {"treats_today": self.event_log.treats_since(since), "daily_limit": None}
        return {"treats_today": self.event_log.treats_since(since, dog_id=dog.id),
                "daily_limit": dog.daily_treat_limit}

    def _build_status(self, now: float, probs, box) -> Dict:
        top = None
        if probs is not None:
            i = int(np.argmax(probs))
            top = {"label": POSTURE_LABELS[i], "confidence": round(float(probs[i]), 3)}
        dog = self.store.dog(self.dog_id) if self.dog_id else None
        sess = self._session
        return {
            "mode": self.mode,
            "fps": round(self._fps, 1),
            "dog": dog.to_dict() if dog else None,
            **self._treat_counts(dog),
            "dog_present": probs is not None,
            "frame_posture": top,
            "posture": {"state": self.active.state, "held_s": round(self.active.held_for(now), 2),
                        "vote": None if not top else top["label"]},
            "box": [round(v, 1) for v in box] if box else None,
            "behavior": self.behavior.status(now),
            "session": None if not sess else {"schedule_id": sess["schedule"].id, "slot": sess["slot"],
                                              "rep": sess["done"], "reps": sess["schedule"].reps},
            "context": {k: v for k, v in self.behavior.context.items() if k != "schedule_since"},
        }

    def status(self) -> Dict:
        with self._lock:
            return dict(self._status, recent_events=list(self._recent[:8]))

    def latest_frame(self):
        with self._lock:
            return self._frame, dict(self._status)

    def dog_summary(self, dog: Dog) -> Dict:
        since = start_of_day(self.wall())
        progress = self.store.all_progress(dog.id)
        week = self.event_log.daily(7, dog_id=dog.id)
        done = [d for d in week if d["commands"]]
        rate = (sum(d["successes"] for d in done) / sum(d["commands"] for d in done)) if done else None
        today = self.event_log.stats(since, dog_id=dog.id)
        return {
            **dog.to_dict(),
            "treats_today": self.event_log.treats_since(since, dog_id=dog.id),
            "successes_today": sum(p["successes"] + p["captures"] for p in today["per_pose"].values()),
            "success_rate_7d": rate,
            "streak_days": self.event_log.streak_days(dog_id=dog.id),
            "learning": [p.exercise.name for p in progress if p.stage == "learn"],
            "training": [p.exercise.name for p in progress if p.stage == "train"],
            "mastered": [p.exercise.name for p in progress if p.stage == "mastered"],
        }

    def dog_detail(self, dog: Dog) -> Dict:
        week = self.event_log.daily(7, dog_id=dog.id)
        rts = [d["avg_reaction_s"] for d in week if d["avg_reaction_s"]]
        since = start_of_day(self.wall())
        caught = [{"ts": e["ts"], "target": e["target"], "treat": bool(e["treat"])}
                  for e in self.event_log.recent(200, dog_id=dog.id)
                  if e["kind"] == "passive_capture" and e["ts"] >= since
                  and not (e["detail"] or "").startswith("silent")]
        return {**self.dog_summary(dog),
                "avg_reaction_s": round(sum(rts) / len(rts), 2) if rts else None,
                "exercises": [p.to_dict() for p in self.store.all_progress(dog.id)],
                "week": week,
                "caught_today": caught[:10]}


def _mock_box(pose: str):
    boxes = {"sitting": (0.36, 0.22, 0.64, 0.86), "standing": (0.22, 0.32, 0.78, 0.86),
             "lying": (0.16, 0.56, 0.84, 0.88)}
    if pose not in boxes:
        return None
    x1, y1, x2, y2 = boxes[pose]
    return (x1 * 640, y1 * 480, x2 * 640, y2 * 480)


def _event_dict(e: Event) -> Dict:
    return {"type": e.kind, "ts": e.ts, "target": e.target, "reaction_s": None if e.reaction_s is None
            else round(e.reaction_s, 2), "treat": bool(e.treat), "detail": e.detail, "dog_id": e.dog_id,
            "schedule_id": e.schedule_id}


def seed_demo(store: AppStore, settings: SettingsStore, wall: Optional[float] = None) -> None:
    """Creates the three demo dogs and schedules shown in the app mockup."""
    now_wall = time.time() if wall is None else wall
    # device-wide cap (per-dog limits apply below) and a short gap so live demos aren't blocked
    settings.update({"daily_treat_limit": 100, "min_seconds_between_treats": 3})
    bruno = store.add_dog(Dog("Bruno", "Labrador", "2023-09-14", 31, "#F29E6D", 35, age_text="3 yrs", image_url="/dogs/bruno.jpg"))
    luna = store.add_dog(Dog("Luna", "Border Collie", "2024-06-02", 17, "#A9C9A4", 24, pronoun="she", age_text="2 yrs", image_url="/dogs/luna.jpg"))
    toby = store.add_dog(Dog("Toby", "Beagle", "2026-03-01", 9, "#B9CFE6", 18, age_text="8 mos", image_url="/dogs/toby.jpg"))
    days = 86400
    stages = {   # exercise: (stage, moments caught, hold seconds, successes in the last 10, started days ago)
        bruno.id: {"down": ("learn", 18, None, 0, 4), "sit": ("train", 0, 2.5, 9, 20),
                   "stand": ("train", 0, 1.5, 9, 15)},
        luna.id: {"paw": ("learn", 7, None, 0, 2), "down": ("train", 0, 2.0, 9, 18),
                  "stay": ("train", 0, 7.0, 8, 10), "sit": ("mastered", 0, 3.0, 10, 40)},
        toby.id: {"sit": ("learn", 24, None, 0, 6)},
    }
    for dog_id, exs in stages.items():
        for ex_id, (stage, moments, hold, wins, ago) in exs.items():
            p = store.progress(dog_id, ex_id)
            p.stage, p.moments, p.started_at = stage, moments, now_wall - ago * days
            if hold:
                p.hold_s = p.best_hold_s = hold
                p.recent = [0] * (10 - wins) + [1] * wins
            store.save_progress(p)
    for s in [
        Schedule(bruno.id, "learn", ["down"], start="10:00", end="17:00", max_treats=10),
        Schedule(toby.id, "learn", ["sit"], days=[0, 1, 2, 3, 4], start="09:00", end="18:00", max_treats=12),
        Schedule(bruno.id, "train", ["sit", "stand"], times=["08:00", "18:30"], max_treats=10),
        Schedule(luna.id, "train", ["down", "stay"], times=["18:30"], max_treats=10),
        Schedule(luna.id, "learn", ["paw"], days=[5, 6], start="12:00", end="16:00", max_treats=8, enabled=False),
    ]:
        store.add_schedule(s)


# Demo history: (success rate per day for the last 6 days, streak days, events earlier today)
DEMO_HISTORY = {
    "Bruno": ([0.62, 0.68, 0.66, 0.72, 0.76, 0.80], 12, {"sit": 6, "stand": 4, "down": 3}),
    "Luna": ([0.80, 0.78, 0.85, 0.83, 0.88, 0.91], 21, {"down": 5, "stay": 4, "sit": 2}),
    "Toby": ([0.40, 0.44, 0.51, 0.49, 0.55, 0.58], 5, {"sit": 3}),
}


def seed_history(store: AppStore, event_log: EventLog, wall: float, seed: int = 7) -> None:
    """Past training events for the demo dogs, so charts, streaks and "today" aren't empty."""
    rng = random.Random(seed)
    today = start_of_day(wall)
    for dog in store.dogs():
        if dog.name not in DEMO_HISTORY:
            continue
        rates, streak, today_counts = DEMO_HISTORY[dog.name]
        trained = [p for p in store.all_progress(dog.id) if p.stage in ("train", "mastered")]
        for days_ago in range(streak - 1, 0, -1):
            day = today - days_ago * 86400 + 9 * 3600                  # from 09:00
            rate = rates[-days_ago] if days_ago <= len(rates) else rates[0] - 0.05
            for i in range(10 if days_ago <= len(rates) else 4):
                p = trained[i % len(trained)] if trained else None
                ok = rng.random() < rate
                event_log.add(Event("command_success" if ok else "command_fail", ts=day + i * 900,
                                    target=p.exercise.pose if p else "sitting", detected=None,
                                    reaction_s=round(rng.uniform(0.6, 1.6), 2) if ok else None,
                                    treat=ok, detail=None if ok else "timeout", dog_id=dog.id))
        # earlier today: commands for trained exercises, captures for the ones being learned
        end = max(today, wall - 60)
        t = min(today + 8 * 3600, max(today, end - 3600))
        span = max(0.0, end - t)
        n = sum(today_counts.values())
        k = 0
        for ex_id, count in today_counts.items():
            p = store.progress(dog.id, ex_id)
            for _ in range(count):
                ts = t + span * k / max(1, n)
                k += 1
                if p.stage == "learn":
                    event_log.add(Event("passive_capture", ts=ts, target=p.exercise.pose,
                                        detected=p.exercise.pose, treat=True, dog_id=dog.id))
                else:
                    ok = k % 5 != 0                                    # about 80% today
                    event_log.add(Event("command_success" if ok else "command_fail", ts=ts,
                                        target=p.exercise.pose, treat=ok,
                                        reaction_s=round(rng.uniform(0.5, 1.3), 2) if ok else None,
                                        detail=None if ok else "timeout", dog_id=dog.id))


if __name__ == "__main__":
    # Demo: simulated dog with the demo dogs and schedules. Prints events for ~30 seconds.
    import tempfile
    logging.basicConfig(level=logging.WARNING)
    rt = AppRuntime(mode="mock", data_dir=Path(tempfile.mkdtemp()), demo=True)
    rt.start()
    seen = set()
    for second in range(30):
        time.sleep(1)
        if second % 8 == 1 and rt.behavior.active is None:
            rt.submit_command("sit")
        for ev in reversed(rt.status().get("recent_events", [])):
            key = (ev.get("ts"), ev.get("type"), ev.get("id"))
            if key not in seen:
                seen.add(key)
                print(f"{second:2d}s  {ev.get('type'):16s} {ev.get('title') or ev.get('target') or ''}"
                      f"{'  + treat' if ev.get('treat') else ''}")
    rt.stop()
