"""Draws the live view (detection box over the frame). Used for highlight clips.

Camera mode: the real frame + detection box + confirmed posture.
Mock mode: a simple synthetic room with the simulated dog's box, so the Live screen
has something to show without a camera.
"""
from __future__ import annotations

from typing import Dict, Optional

import cv2
import numpy as np

LABELS = {"sitting": "Sitting", "standing": "Standing", "lying": "Lying down", "undefined": "Unsure"}
BOX_COLOR = (107, 190, 245)      # honey (BGR) - matches the app palette


def render_frame(frame: Optional[np.ndarray], status: Dict) -> np.ndarray:
    if frame is None:
        img = np.full((480, 640, 3), (33, 38, 46), dtype=np.uint8)          # warm dark room
        cv2.rectangle(img, (0, 340), (640, 480), (41, 48, 58), -1)          # floor
        if not status.get("dog_present"):
            cv2.putText(img, "No dog in view", (230, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (170, 180, 190), 2, cv2.LINE_AA)
        h_scale = w_scale = 1.0
    else:
        img = frame.copy()
        h_scale, w_scale = 1.0, 1.0

    box = status.get("box")
    if box:
        x1, y1, x2, y2 = (int(v) for v in box)
        x1, x2 = int(x1 * w_scale), int(x2 * w_scale)
        y1, y2 = int(y1 * h_scale), int(y2 * h_scale)
        if frame is None:   # draw a soft silhouette for the simulated dog
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.ellipse(img, (cx, cy + (y2 - y1) // 6), ((x2 - x1) // 3, (y2 - y1) // 4), 0, 0, 360,
                        (63, 74, 90), -1, cv2.LINE_AA)
            cv2.circle(img, (cx - (x2 - x1) // 5 if x2 - x1 > y2 - y1 else cx, y1 + (y2 - y1) // 4),
                       max(18, min(x2 - x1, y2 - y1) // 5), (75, 88, 105), -1, cv2.LINE_AA)
        cv2.rectangle(img, (x1, y1), (x2, y2), BOX_COLOR, 3, cv2.LINE_AA)
    return img


def encode_jpeg(img: np.ndarray, quality: int = 75) -> Optional[bytes]:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else None
