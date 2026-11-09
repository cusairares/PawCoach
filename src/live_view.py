"""Draws the live view: the video stream, snapshots and highlight clips.

Camera mode: the real frame as it is (the app shows no box around the dog).
Mock mode: a simple synthetic room with a soft silhouette of the simulated dog, so there
is something to show without a camera.
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
        return frame.copy()

    box = status.get("box")
    if box:                 # soft silhouette of the simulated dog where its box would be
        x1, y1, x2, y2 = (int(v) for v in box)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.ellipse(img, (cx, cy + (y2 - y1) // 6), ((x2 - x1) // 3, (y2 - y1) // 4), 0, 0, 360,
                    (63, 74, 90), -1, cv2.LINE_AA)
        cv2.circle(img, (cx - (x2 - x1) // 5 if x2 - x1 > y2 - y1 else cx, y1 + (y2 - y1) // 4),
                   max(18, min(x2 - x1, y2 - y1) // 5), (75, 88, 105), -1, cv2.LINE_AA)
    return img


def encode_jpeg(img: np.ndarray, quality: int = 75) -> Optional[bytes]:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else None
