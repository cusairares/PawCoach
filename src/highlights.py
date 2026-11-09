"""Highlights ("golden moments"): short video clips saved automatically at milestones.

The recorder keeps the last few seconds of frames in memory. When a milestone happens
(personal best reaction time, first success, level up, exercise learned / mastered) it
stores a highlight row immediately and writes an MP4 with a few seconds before and after
the moment, on a background thread so the vision loop never waits.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

from .app_store import APP_DIR, AppStore
from .event_log import Event, EventLog

log = logging.getLogger(__name__)

TITLES = {
    "personal_best": "{dog}: “{ex}” in {value:.1f} s, personal best",
    "first_time": "{dog}'s first “{ex}”",
    "level_up": "{dog} holds “{ex}” for {value:g} s",
    "learned": "{dog} learned “{ex}”",
    "mastered": "{dog} mastered “{ex}”",
}


def title(kind: str, dog: str, ex: str, value: Optional[float] = None) -> str:
    return TITLES[kind].format(dog=dog, ex=ex, value=value or 0)


def is_personal_best(event_log: EventLog, event: Event) -> bool:
    """A successful command faster than every previous success of this dog for this pose."""
    if event.kind != "command_success" or event.reaction_s is None:
        return False
    best = event_log.best_reaction(event.target, dog_id=event.dog_id, before_ts=event.ts)
    return best is not None and event.reaction_s < best


def is_first_success(event_log: EventLog, event: Event) -> bool:
    if event.kind not in ("command_success", "passive_capture") or not event.treat:
        return False
    return event_log.count(event.kind, target=event.target, dog_id=event.dog_id) == 1


class HighlightRecorder:
    def __init__(self, store: AppStore, clips_dir: Path = APP_DIR / "highlights", fps: float = 10.0,
                 before_s: float = 4.0, after_s: float = 2.0, enabled: bool = True):
        self.store, self.clips_dir, self.fps = store, Path(clips_dir), fps
        self.enabled = enabled
        self._buffer: Deque = deque(maxlen=max(1, int(fps * before_s)))
        self._after = max(1, int(fps * after_s))
        self._pending: List[Tuple[int, List, int]] = []        # (highlight_id, frames, frames_still_needed)
        self._lock = threading.Lock()

    def push_frame(self, frame) -> None:
        if frame is None or not self.enabled:
            return
        done = []
        with self._lock:
            self._buffer.append(frame)
            still = []
            for hid, frames, needed in self._pending:
                frames.append(frame)
                (done if needed <= 1 else still).append((hid, frames, needed - 1))
            self._pending = still
        for hid, frames, _ in done:
            threading.Thread(target=self._write, args=(hid, frames), daemon=True).start()

    def add(self, ts: float, dog_id: Optional[int], kind: str, dog_name: str, ex_name: str,
            exercise_id: Optional[str] = None, value: Optional[float] = None) -> Dict:
        h = {"ts": ts, "dog_id": dog_id, "kind": kind, "title": title(kind, dog_name, ex_name, value),
             "exercise_id": exercise_id, "value": value}
        h["id"] = self.store.add_highlight(h)
        if self.enabled:
            with self._lock:
                self._pending.append((h["id"], list(self._buffer), self._after))
        log.info("[highlight] %s", h["title"])
        return h

    def _write(self, highlight_id: int, frames: List) -> None:
        if not frames:
            return
        try:
            import cv2
            self.clips_dir.mkdir(parents=True, exist_ok=True)
            path = self.clips_dir / f"highlight_{highlight_id}.mp4"
            h, w = frames[0].shape[:2]
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (w, h))
            for f in frames:
                writer.write(f)
            writer.release()
            self.store.set_highlight_clip(highlight_id, str(path), round(len(frames) / self.fps, 1))
        except Exception:
            log.exception("could not write highlight clip %s", highlight_id)
