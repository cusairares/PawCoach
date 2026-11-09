"""Demo footage for the simulated dog (mock mode).

Mock mode used to hand the pipeline made-up posture probabilities: the simulated dog "sat"
and the backend got 88 % "sitting" straight away, so every cue succeeded after a short wait
without the classifier ever running.

With ``DemoFootage`` the simulated dog only decides *what it does* (obeys a cue after a
moment, wanders between poses when idle). What the camera "sees" is real video: the player
jumps to a hand-labelled stretch of ``video demo/video demo.mp4`` where a dog is in that
pose, and those frames go through the real ``DogDetector`` + ``PostureClassifier``. Whether a
cue succeeds, how fast, and with what confidence is decided by the models, so a pose the
classifier misreads really does time out.

Segments live in ``video demo/segments.json``: {pose: [[start_s, end_s] or
{"span": [start_s, end_s], "hard": true}, ...]}. "hard" stretches are ones the current
classifier gets wrong; they're skipped unless ``include_hard`` (``--mock-hard``) is set.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .config import ROOT

DEMO_VIDEO = ROOT / "video demo" / "video demo.mp4"
DEMO_SEGMENTS = ROOT / "video demo" / "segments.json"

Segments = Dict[str, List[Tuple[float, float]]]


def crop_portrait(frame: np.ndarray) -> np.ndarray:
    """Phone video saved as landscape with black side bars: keep the portrait middle."""
    h, w = frame.shape[:2]
    if w > h and np.mean(frame[:, :w // 4]) < 15 and np.mean(frame[:, 3 * w // 4:]) < 15:
        crop_w = int(h * 9 / 16)
        x0 = (w - crop_w) // 2
        return frame[int(h * 0.15):int(h * 0.88), x0:x0 + crop_w]
    return frame


def load_segments(path: Path = DEMO_SEGMENTS, include_hard: bool = True) -> Segments:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = data.get("segments", data)
    out: Segments = {}
    for pose, spans in raw.items():
        clean = []
        for item in spans:
            hard = isinstance(item, dict) and bool(item.get("hard"))
            s, e = item["span"] if isinstance(item, dict) else item
            if float(e) > float(s) and (include_hard or not hard):
                clean.append((float(s), float(e)))
        if clean:
            out[pose] = clean
    return out


class DemoFootage:
    """Plays labelled stretches of the demo video, in real time, one pose at a time."""

    def __init__(self, video_path: Path = DEMO_VIDEO, segments_path: Path = DEMO_SEGMENTS,
                 rng: Optional[random.Random] = None, include_hard: bool = False) -> None:
        import cv2
        self._cv2 = cv2
        video_path, segments_path = Path(video_path), Path(segments_path)
        if not video_path.exists():
            raise FileNotFoundError(video_path)
        self.segments = load_segments(segments_path, include_hard=include_hard)
        if not self.segments:
            raise ValueError(f"No segments in {segments_path}")
        self.cap = cv2.VideoCapture(str(video_path))
        if not self.cap.isOpened():
            raise RuntimeError(f"Can't open {video_path}")
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 30.0)
        self.rng = rng or random.Random()
        self.pose: Optional[str] = None          # pose of the segment being played
        self._span: Optional[Tuple[int, int]] = None
        self._t0 = 0.0
        self._pos = 0                            # index of the frame the decoder returns next
        self._frame: Optional[np.ndarray] = None
        self._frame_idx = -1

    @property
    def poses(self) -> List[str]:
        return list(self.segments)

    @property
    def clip_time(self) -> Optional[float]:
        return None if self._frame_idx < 0 else round(self._frame_idx / self.fps, 2)

    def play(self, pose: str, now: float) -> None:
        """Start a random labelled stretch of ``pose`` (``none`` = no dog in view)."""
        if pose not in self.segments:
            self.pose, self._span = None, None
            return
        start, end = self.rng.choice(self.segments[pose])
        self.pose, self._t0 = pose, now
        self._span = (int(round(start * self.fps)), max(int(round(start * self.fps)) + 1,
                                                        int(round(end * self.fps))))

    def read(self, now: float) -> Optional[np.ndarray]:
        """The frame to show at ``now`` (loops inside the segment while the pose is held)."""
        if self._span is None:
            return None
        start, end = self._span
        offset = int(max(0.0, now - self._t0) * self.fps) % (end - start)
        return self._frame_at(start + offset)

    def _frame_at(self, idx: int) -> Optional[np.ndarray]:
        if idx == self._frame_idx:
            return self._frame
        if idx < self._pos or idx - self._pos > 45:          # jump: seek instead of decoding through
            self.cap.set(self._cv2.CAP_PROP_POS_FRAMES, idx)
            self._pos = idx
        while self._pos < idx:                               # small step forward: skip frames cheaply
            self.cap.grab()
            self._pos += 1
        ok, frame = self.cap.read()
        self._pos += 1
        if not ok:
            return self._frame
        self._frame, self._frame_idx = crop_portrait(frame), idx
        return self._frame

    def close(self) -> None:
        self.cap.release()
