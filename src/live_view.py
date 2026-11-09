"""Draws the live view: the video stream, snapshots and highlight clips.

Camera mode: the real frame as it is (the app shows no box around the dog).
Mock mode, classifier source: the demo-video frame the models just read, with the detector box
and what the classifier says vs. what the simulated dog is doing - so you can see it's real.
Mock mode, synthetic source: a simple synthetic room with a soft silhouette of the simulated
dog, so there is something to show without a camera.
"""
from __future__ import annotations

from typing import Dict, Optional

import cv2
import numpy as np

LABELS = {"sitting": "Sitting", "standing": "Standing", "lying": "Lying down", "undefined": "Unsure"}


def render_frame(frame: Optional[np.ndarray], status: Dict) -> np.ndarray:
    if frame is None:
        img = np.full((480, 640, 3), (33, 38, 46), dtype=np.uint8)          # warm dark room
        cv2.rectangle(img, (0, 340), (640, 480), (41, 48, 58), -1)          # floor
        if not status.get("dog_present"):
            cv2.putText(img, "No dog in view", (230, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (170, 180, 190), 2, cv2.LINE_AA)
    else:
        img = frame.copy()
        sim = status.get("sim") or {}
        if sim.get("source") == "classifier":
            _draw_classifier_hud(img, status, sim)
        return img

    box = status.get("box")
    if box:                 # soft silhouette of the simulated dog where its box would be
        x1, y1, x2, y2 = (int(v) for v in box)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.ellipse(img, (cx, cy + (y2 - y1) // 6), ((x2 - x1) // 3, (y2 - y1) // 4), 0, 0, 360,
                    (63, 74, 90), -1, cv2.LINE_AA)
        cv2.circle(img, (cx - (x2 - x1) // 5 if x2 - x1 > y2 - y1 else cx, y1 + (y2 - y1) // 4),
                   max(18, min(x2 - x1, y2 - y1) // 5), (75, 88, 105), -1, cv2.LINE_AA)
    return img


def _draw_classifier_hud(img: np.ndarray, status: Dict, sim: Dict) -> None:
    h, w = img.shape[:2]
    scale = max(0.6, w / 700)
    top = status.get("frame_posture") or {}
    label, conf = top.get("label"), top.get("confidence", 0.0)
    intent = sim.get("intent")
    ok = label == intent
    color = (90, 180, 90) if ok else (60, 110, 230)                 # BGR: green match / orange miss
    box = status.get("box")
    if box:
        x1, y1, x2, y2 = (int(v) for v in box)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, max(2, int(3 * scale)), cv2.LINE_AA)
    lines = [f"classifier: {LABELS.get(label, 'no dog')} {conf:.0%}" if label else "classifier: no dog",
             f"simulated dog: {LABELS.get(intent, 'out of view')}"]
    confirmed = (status.get("posture") or {}).get("state")
    lines.append(f"confirmed: {LABELS.get(confirmed, '-')}")
    y = int(28 * scale)
    for i, text in enumerate(lines):
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6 * scale, 1)
        yy = y + i * int(th * 1.9)
        cv2.rectangle(img, (6, yy - th - 6), (14 + tw, yy + 6), (25, 25, 25), -1)
        cv2.putText(img, text, (10, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.6 * scale,
                    color if i == 0 else (235, 235, 235), max(1, int(1.5 * scale)), cv2.LINE_AA)


def encode_jpeg(img: np.ndarray, quality: int = 75) -> Optional[bytes]:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else None
