"""Temporal consensus over per-frame posture results.

Every frame is classified exactly once. The buffer stores the *results*
(probability vectors) with their timestamps, and keeps only the last ``window_s``
seconds - so the effective N adapts to whatever FPS the pipeline achieves:

    N ~= f_eff * window_s

A frame without a detected dog is stored as a one-hot ``no_dog`` vector, so the
dog leaving the frame also wins the vote eventually.

``StateTracker`` turns the soft vote into a confirmed state with hysteresis
(enter at ``enter_threshold``, drop to uncertain below ``exit_threshold``) and
tracks how long the state has been held (dwell) and an ``entry_id`` that increments
on every new entry - used to require a *transition into* a pose.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .config import NO_DOG


@dataclass
class Vote:
    label: Optional[str]           # top class (may be 'no_dog' / 'undefined'); None if not ready
    score: float                   # averaged probability of the top class
    distribution: Dict[str, float]
    fill: float                    # fraction of the window covered by entries
    n_entries: int
    ready: bool


class ConsensusBuffer:
    def __init__(self, labels: Sequence[str], window_s: float = 1.0,
                 min_fill: float = 0.7, min_entries: int = 5):
        if window_s <= 0:
            raise ValueError("window_s must be > 0")
        self.labels: List[str] = list(labels) + [NO_DOG]
        self.window_s = window_s
        self.min_fill = min_fill
        self.min_entries = min_entries
        self._entries: Deque[Tuple[float, np.ndarray]] = deque()
        self._no_dog_vec = np.zeros(len(self.labels), dtype=np.float32)
        self._no_dog_vec[-1] = 1.0

    def clear(self) -> None:
        self._entries.clear()

    def push(self, t: float, probs: Optional[np.ndarray]) -> None:
        """Add one frame result. ``probs=None`` means no dog in the frame."""
        if probs is None:
            vec = self._no_dog_vec
        else:
            probs = np.asarray(probs, dtype=np.float32)
            if probs.shape != (len(self.labels) - 1,):
                raise ValueError(f"Expected {len(self.labels) - 1} probabilities, got {probs.shape}")
            vec = np.append(probs, 0.0).astype(np.float32)
        if self._entries and t < self._entries[-1][0]:
            raise ValueError("Timestamps must be non-decreasing")
        self._entries.append((t, vec))
        self._evict(t)

    def _evict(self, now: float) -> None:
        cutoff = now - self.window_s
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()

    def effective_fps(self) -> float:
        if len(self._entries) < 2:
            return 0.0
        span = self._entries[-1][0] - self._entries[0][0]
        return (len(self._entries) - 1) / span if span > 0 else 0.0

    def vote(self, now: float) -> Vote:
        self._evict(now)
        n = len(self._entries)
        if n == 0:
            return Vote(None, 0.0, {}, 0.0, 0, False)
        span = now - self._entries[0][0]
        fill = min(1.0, span / self.window_s) if n > 1 else 0.0
        mean = np.mean([v for _, v in self._entries], axis=0)
        dist = {label: float(p) for label, p in zip(self.labels, mean)}
        idx = int(np.argmax(mean))
        ready = fill >= self.min_fill and n >= self.min_entries
        return Vote(self.labels[idx] if ready else None, float(mean[idx]), dist, fill, n, ready)


class StateTracker:
    """Confirmed-state tracker with hysteresis and dwell timing."""

    def __init__(self, enter_threshold: float, exit_threshold: float = 0.4):
        if not 0 < exit_threshold <= enter_threshold <= 1:
            raise ValueError("Require 0 < exit_threshold <= enter_threshold <= 1")
        self.enter_threshold = enter_threshold
        self.exit_threshold = exit_threshold
        self.state: Optional[str] = None      # None == uncertain / not ready
        self.since: float = 0.0
        self.entry_id: int = 0

    def reset(self) -> None:
        self.state = None
        self.since = 0.0

    def update(self, vote: Vote, now: float) -> bool:
        """Apply a vote. Returns True if the confirmed state changed."""
        if not vote.ready:
            return False
        # Leave current state when its own support collapses.
        if self.state is not None and vote.distribution.get(self.state, 0.0) < self.exit_threshold:
            self.state = None
            self.since = now
            changed = True
        else:
            changed = False
        if vote.label is not None and vote.label != self.state and vote.score >= self.enter_threshold:
            self.state = vote.label
            self.since = now
            self.entry_id += 1
            changed = True
        return changed

    def held_for(self, now: float) -> float:
        return now - self.since if self.state is not None else 0.0
