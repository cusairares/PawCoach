"""Exercises and their three stages, as shown in the app.

    learn    - "Learns on his own": passive capture. The dog does the move by itself, hears the
               cue word + marker and gets a treat. After ``moments_goal`` captures it moves on.
    train    - "Trains on cue": active commands. The hold time grows after a streak of
               successes (level up) and shrinks after repeated failures (level down).
    mastered - top hold level reached with a high success rate over the recent attempts.
    next     - not started yet (e.g. Stay starts once Sit is mastered).

This module only holds the rules; progress is stored by ``src.app_store.AppStore``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import CommandRequest

STAGES = ("next", "learn", "train", "mastered")
MOMENTS_GOAL = 30                 # passive captures needed to finish the learn stage
LEVEL_UP_AFTER = 3                # successes in a row
LEVEL_DOWN_AFTER = 2              # failures in a row
MASTERY_WINDOW = 10               # recent attempts considered for mastery
MASTERY_RATE = 0.9
LEVELS = 6                        # the app shows 6 level pips


@dataclass(frozen=True)
class Exercise:
    id: str
    name: str
    pose: str                     # posture label from POSE_LABELS
    base_hold_s: float
    max_hold_s: float
    step_s: float
    learnable: bool = True        # False -> starts directly in "train" (e.g. Stay)
    requires: Optional[str] = None
    detectable: bool = True       # False -> needs a model that does not exist yet

    def level(self, hold_s: float) -> int:
        if self.max_hold_s <= self.base_hold_s:
            return LEVELS
        frac = (hold_s - self.base_hold_s) / (self.max_hold_s - self.base_hold_s)
        return max(1, min(LEVELS, 1 + round(frac * (LEVELS - 1))))


EXERCISES: Dict[str, Exercise] = {e.id: e for e in [
    Exercise("sit", "Sit", "sitting", 1.0, 3.0, 0.5),
    Exercise("down", "Down", "lying", 1.0, 3.0, 0.5),
    Exercise("stand", "Stand", "standing", 1.0, 2.0, 0.5),
    Exercise("stay", "Stay", "sitting", 3.0, 15.0, 2.0, learnable=False, requires="sit"),
    Exercise("paw", "Paw", "paw", 1.0, 1.0, 0.0, detectable=False),
]}


@dataclass
class TrainingCommand(CommandRequest):
    """A command from the app with training context. Extends CommandRequest without changing it."""
    hold_s: Optional[float] = None
    dog_id: Optional[int] = None
    schedule_id: Optional[int] = None
    exercise_id: Optional[str] = None


def command_for(exercise_id: str, hold_s: Optional[float] = None, **kw) -> TrainingCommand:
    ex = EXERCISES[exercise_id]
    if not ex.detectable:
        raise ValueError(f"'{ex.name}' can't be detected yet")
    return TrainingCommand(pose=ex.pose, hold_s=hold_s or ex.base_hold_s, exercise_id=ex.id, **kw)


@dataclass
class Progress:
    """Per dog, per exercise."""
    dog_id: int
    exercise_id: str
    stage: str = "next"
    moments: int = 0
    moments_goal: int = MOMENTS_GOAL
    hold_s: float = 0.0
    best_hold_s: float = 0.0
    streak: int = 0
    fail_streak: int = 0
    recent: List[int] = field(default_factory=list)     # 1/0 for the last attempts
    started_at: Optional[float] = None

    @property
    def exercise(self) -> Exercise:
        return EXERCISES[self.exercise_id]

    def to_dict(self) -> Dict:
        ex = self.exercise
        attempts = len(self.recent)
        return {"exercise_id": ex.id, "name": ex.name, "pose": ex.pose, "stage": self.stage,
                "moments": self.moments, "moments_goal": self.moments_goal,
                "hold_s": self.hold_s, "best_hold_s": self.best_hold_s, "max_hold_s": ex.max_hold_s,
                "level": ex.level(self.hold_s), "levels": LEVELS,
                "success_rate": (sum(self.recent) / attempts) if attempts else None,
                "requires": ex.requires, "detectable": ex.detectable, "started_at": self.started_at}


def new_progress(dog_id: int, exercise_id: str) -> Progress:
    ex = EXERCISES[exercise_id]
    return Progress(dog_id, exercise_id, hold_s=ex.base_hold_s, best_hold_s=ex.base_hold_s)


def start(p: Progress, now: float) -> List[Dict]:
    """next -> learn (or straight to train for non-learnable exercises)."""
    if p.stage != "next":
        return []
    p.stage = "learn" if p.exercise.learnable else "train"
    p.started_at = now
    return [{"type": "stage_up", "exercise_id": p.exercise_id, "stage": p.stage}]


def on_capture(p: Progress) -> List[Dict]:
    """A passive capture of this exercise's pose."""
    if p.stage != "learn":
        return []
    p.moments += 1
    if p.moments >= p.moments_goal:
        p.stage = "train"
        return [{"type": "stage_up", "exercise_id": p.exercise_id, "stage": "train"}]
    return []


def on_attempt(p: Progress, success: bool) -> List[Dict]:
    """Result of an active command for this exercise. Adapts the hold time."""
    if p.stage not in ("train", "mastered"):
        return []
    ex, out = p.exercise, []
    p.recent = (p.recent + [1 if success else 0])[-MASTERY_WINDOW:]
    if success:
        p.streak, p.fail_streak = p.streak + 1, 0
        if p.streak >= LEVEL_UP_AFTER and p.hold_s < ex.max_hold_s:
            p.hold_s = min(ex.max_hold_s, round(p.hold_s + ex.step_s, 2))
            p.best_hold_s = max(p.best_hold_s, p.hold_s)
            p.streak = 0
            out.append({"type": "level_up", "exercise_id": ex.id, "hold_s": p.hold_s})
    else:
        p.fail_streak, p.streak = p.fail_streak + 1, 0
        if p.fail_streak >= LEVEL_DOWN_AFTER and p.hold_s > ex.base_hold_s:
            p.hold_s = max(ex.base_hold_s, round(p.hold_s - ex.step_s, 2))
            p.fail_streak = 0
            out.append({"type": "level_down", "exercise_id": ex.id, "hold_s": p.hold_s})
    if (p.stage == "train" and p.hold_s >= ex.max_hold_s and len(p.recent) >= MASTERY_WINDOW
            and sum(p.recent) / len(p.recent) >= MASTERY_RATE):
        p.stage = "mastered"
        out.append({"type": "stage_up", "exercise_id": ex.id, "stage": "mastered"})
    return out
