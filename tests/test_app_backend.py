"""Tests for the app features of the backend (dogs, exercises, schedules, treat limits,
highlights). Mock mode only: no camera, no torch.

Run from the repo root:  python -m pytest tests/test_app_backend.py   (or python -m unittest)
"""
import random
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from src import training_plan as plan
from src.app_runtime import AppRuntime
from src.app_store import AppStore, Dog, Schedule
from src.event_log import Event, EventLog
from src.scheduler import SessionClock, learning_window

MONDAY_1030 = datetime(2026, 11, 9, 10, 30).timestamp()      # a Monday


class Clock:
    """Drives both the engine clock and the wall clock."""

    def __init__(self, wall_start=MONDAY_1030):
        self.t, self.wall0 = 1000.0, wall_start

    def mono(self):
        return self.t

    def wall(self):
        return self.wall0 + (self.t - 1000.0)


def run(engine, clock, seconds, step=0.1):
    out = []
    for _ in range(round(seconds / step)):
        clock.t += step
        out += engine.step()
    return out


def kinds(events):
    return [e["type"] for e in events]


class TrainingPlanTest(unittest.TestCase):
    def test_learn_stage_finishes_after_goal(self):
        p = plan.new_progress(1, "down")
        plan.start(p, 0)
        p.moments = plan.MOMENTS_GOAL - 1
        self.assertEqual(plan.on_capture(p)[0]["stage"], "train")
        self.assertEqual(p.stage, "train")

    def test_hold_grows_after_streak_and_shrinks_after_failures(self):
        p = plan.new_progress(1, "sit")
        p.stage = "train"
        for _ in range(3):
            ev = plan.on_attempt(p, True)
        self.assertEqual(ev[0]["type"], "level_up")
        self.assertEqual(p.hold_s, 1.5)
        plan.on_attempt(p, False)
        self.assertEqual(plan.on_attempt(p, False)[0]["type"], "level_down")
        self.assertEqual(p.hold_s, 1.0)

    def test_mastery_needs_top_level_and_high_rate(self):
        p = plan.new_progress(1, "stand")
        p.stage, p.hold_s = "train", 2.0
        for _ in range(10):
            ev = plan.on_attempt(p, True)
        self.assertEqual(p.stage, "mastered")
        self.assertIn("stage_up", kinds(ev))

    def test_stay_is_not_learnable_and_has_long_hold(self):
        p = plan.new_progress(1, "stay")
        plan.start(p, 0)
        self.assertEqual(p.stage, "train")
        self.assertEqual(plan.command_for("stay").hold_s, 3.0)
        with self.assertRaises(ValueError):
            plan.command_for("paw")


class StoreAndLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = AppStore(Path(self.tmp.name) / "app.db")
        self.log = EventLog(Path(self.tmp.name) / "events.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_dog_gets_progress_for_every_exercise(self):
        dog = self.store.add_dog(Dog("Rex", daily_treat_limit=15))
        self.assertEqual(len(self.store.all_progress(dog.id)), len(plan.EXERCISES))
        self.assertEqual(self.store.update_dog(dog.id, {"daily_treat_limit": 9}).daily_treat_limit, 9)

    def test_schedule_validation_and_update(self):
        with self.assertRaises(ValueError):
            Schedule(1, "learn", ["sit"])                       # no window
        s = self.store.add_schedule(Schedule(1, "train", ["sit"], times=["08:00", "18:00"], max_treats=6))
        self.assertEqual(s.treats_per_day, 12)
        self.assertFalse(self.store.update_schedule(s.id, {"enabled": False}).enabled)

    def test_event_log_per_dog_and_daily(self):
        self.log.add(Event("manual_treat", treat=True, dog_id=1))
        self.log.add(Event("command_success", target="sitting", reaction_s=0.8, treat=True, dog_id=2))
        self.assertEqual(self.log.treats_since(0, dog_id=1), 1)
        self.assertEqual(self.log.treats_since(0), 2)
        days = self.log.daily(7, dog_id=2)
        self.assertEqual(len(days), 7)
        self.assertEqual(days[-1]["success_rate"], 1.0)
        self.assertEqual(self.log.streak_days(dog_id=2), 1)

    def test_old_event_database_is_migrated(self):
        import sqlite3
        path = Path(self.tmp.name) / "old.db"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, ts REAL NOT NULL, kind TEXT NOT NULL,"
                     " target TEXT, detected TEXT, reaction_s REAL, treat INTEGER NOT NULL DEFAULT 0,"
                     " confidence REAL, command_id TEXT, detail TEXT)")
        conn.commit()
        conn.close()
        EventLog(path).add(Event("manual_treat", treat=True, dog_id=3))


class SchedulerTest(unittest.TestCase):
    def test_learning_window_and_session_slots(self):
        learn = Schedule(1, "learn", ["down"], start="10:00", end="17:00", id=1)
        train = Schedule(1, "train", ["sit"], times=["10:29"], id=2)
        now = datetime.fromtimestamp(MONDAY_1030)
        self.assertEqual(learning_window([learn, train], 1, now).id, 1)
        self.assertIsNone(learning_window([learn], 2, now))
        clock = SessionClock()
        self.assertEqual(len(clock.due([train], now)), 1)
        self.assertEqual(clock.due([train], now), [])              # once per slot


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.engine = AppRuntime(mode="mock", data_dir=self.tmp.name, clock=self.clock.mono, wall=self.clock.wall,
                             rng=random.Random(3))
        self.store = self.engine.store
        self.dog = self.store.add_dog(Dog("Bruno", daily_treat_limit=30))
        self.engine.select_dog(self.dog.id)
        self.engine.settings.update({"daily_treat_limit": 100, "min_seconds_between_treats": 0})

    def tearDown(self):
        self.engine.highlights.enabled = False
        time.sleep(0.2)                                              # let clip writers finish
        self.tmp.cleanup()

    def set_stage(self, ex_id, stage, **kw):
        p = self.store.progress(self.dog.id, ex_id)
        p.stage = stage
        for k, v in kw.items():
            setattr(p, k, v)
        self.store.save_progress(p)

    def command(self, ex_id, seconds=6):
        self.engine.set_sim_pose("standing")
        run(self.engine, self.clock, 1.5)
        self.engine.set_sim_pose("auto")
        self.engine.submit_command(ex_id)
        return run(self.engine, self.clock, seconds)

    def test_command_updates_progress_and_creates_highlights(self):
        self.set_stage("sit", "train")
        out = []
        for _ in range(3):
            out += self.command("sit")
        self.assertEqual(kinds(out).count("command_success"), 3)
        self.assertEqual(self.store.progress(self.dog.id, "sit").hold_s, 1.5)    # level up
        titles = [h["title"] for h in self.store.highlights(self.dog.id)]
        self.assertTrue(any("first" in t for t in titles))
        self.assertTrue(any("holds" in t for t in titles))

    def test_stay_needs_the_longer_hold(self):
        self.set_stage("stay", "train")
        self.engine.set_sim_pose("standing")
        run(self.engine, self.clock, 1.5)
        self.engine.submit_command("stay")
        self.engine.set_sim_pose("sitting")
        early = run(self.engine, self.clock, 2.5)                    # sat ~1.5 s: not enough for 3 s
        self.assertNotIn("command_success", kinds(early))
        self.assertIn("command_success", kinds(run(self.engine, self.clock, 3)))

    def test_dog_daily_limit_blocks_treats(self):
        self.store.update_dog(self.dog.id, {"daily_treat_limit": 1})
        self.assertTrue(self.engine.manual_treat()["ok"])
        r = self.engine.manual_treat()
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "dog_daily_limit")

    def test_learning_window_counts_moments_and_spaces_treats(self):
        self.set_stage("down", "learn", moments=5)
        self.store.add_schedule(Schedule(self.dog.id, "learn", ["down"], start="10:00", end="17:00",
                                         max_treats=10, min_interval_s=1800))
        self.engine.set_sim_pose("lying")
        out = run(self.engine, self.clock, 4)
        self.engine.set_sim_pose("standing")
        run(self.engine, self.clock, 31)                             # past the per-pose cooldown (30 s)
        self.engine.set_sim_pose("lying")
        out += run(self.engine, self.clock, 4)
        captures = [e for e in out if e["type"] == "passive_capture"]
        self.assertEqual([c["treat"] for c in captures], [True, False])       # second within 30 min
        self.assertEqual(captures[1]["detail"], "silent:schedule_interval")
        self.assertEqual(self.store.progress(self.dog.id, "down").moments, 6)

    def test_no_passive_capture_outside_learning_windows(self):
        self.set_stage("down", "learn")
        self.store.add_schedule(Schedule(self.dog.id, "learn", ["down"], start="14:00", end="15:00"))
        self.engine.set_sim_pose("lying")
        self.assertNotIn("passive_capture", kinds(run(self.engine, self.clock, 4)))

    def test_training_session_runs_reps_and_respects_max_treats(self):
        self.set_stage("sit", "train")
        self.store.add_schedule(Schedule(self.dog.id, "train", ["sit"], times=["10:30"], reps=5, max_treats=2))
        self.engine.invalidate_schedules()
        out = run(self.engine, self.clock, 40)
        successes = [e for e in out if e["type"] == "command_success"]
        self.assertGreaterEqual(len(successes), 2)
        self.assertEqual(sum(e["treat"] for e in successes), 2)
        self.assertIsNone(self.engine._session)


class DemoDataTest(unittest.TestCase):
    def test_demo_matches_the_app_mockup(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = AppRuntime(mode="mock", data_dir=tmp, demo=True, highlights=False)
            dogs = rt.store.dogs()
            self.assertEqual([d.name for d in dogs], ["Bruno", "Luna", "Toby"])
            summary = rt.dog_detail(dogs[0])
            self.assertEqual(summary["learning"], ["Down"])
            sit = next(e for e in summary["exercises"] if e["exercise_id"] == "sit")
            self.assertEqual((sit["stage"], sit["hold_s"], sit["level"]), ("train", 2.5, 5))
            per_day = {d.id: 0 for d in dogs}
            for s in rt.store.schedules():
                if s.enabled:
                    per_day[s.dog_id] += s.treats_per_day
            self.assertEqual(list(per_day.values()), [30, 10, 12])      # "Treats per day" in the app


if __name__ == "__main__":
    unittest.main()
