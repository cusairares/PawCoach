"""Stage 1: dog detection with SSDLite320-MobileNetV3-Large (COCO-pretrained, torchvision).

Returns a single dog box per frame:
* candidates = COCO class 'dog' with score >= threshold
* if we tracked a box last frame, prefer the candidate overlapping it most (IoU),
  so we don't jump between two dogs / a dog and a dog-like object
* otherwise highest score, ties broken by larger area
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np
import torch
from torchvision.models.detection import (SSDLite320_MobileNet_V3_Large_Weights,
                                          ssdlite320_mobilenet_v3_large)

Box = Tuple[float, float, float, float]  # x1, y1, x2, y2 (pixels)


@dataclass
class Detection:
    box: Box
    score: float


def iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def area(b: Box) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def select_box(candidates: Sequence[Detection], previous: Optional[Box],
               min_iou: float = 0.3) -> Optional[Detection]:
    if not candidates:
        return None
    if previous is not None:
        best = max(candidates, key=lambda d: iou(d.box, previous))
        if iou(best.box, previous) >= min_iou:
            return best
    return max(candidates, key=lambda d: (round(d.score, 2), area(d.box)))


def square_crop(frame: np.ndarray, box: Box, padding: float = 0.15) -> np.ndarray:
    """Pad the box, make it square (around its center), clip to the image, crop."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    side = max(x2 - x1, y2 - y1) * (1 + 2 * padding)
    side = min(side, max(h, w))
    nx1 = int(round(max(0, cx - side / 2)))
    ny1 = int(round(max(0, cy - side / 2)))
    nx2 = int(round(min(w, cx + side / 2)))
    ny2 = int(round(min(h, cy + side / 2)))
    if nx2 - nx1 < 2 or ny2 - ny1 < 2:
        return frame
    return frame[ny1:ny2, nx1:nx2]


class DogDetector:
    def __init__(self, score_threshold: float = 0.5, device: Optional[str] = None):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        weights = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
        self.model = ssdlite320_mobilenet_v3_large(weights=weights).to(self.device).eval()
        categories = weights.meta["categories"]
        self.dog_label = categories.index("dog")
        self.score_threshold = score_threshold

    def _to_tensor(self, frame_bgr: np.ndarray) -> torch.Tensor:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        return torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255.0).to(self.device)

    @torch.inference_mode()
    def detect_all(self, frames_bgr: Sequence[np.ndarray]) -> List[List[Detection]]:
        """All dog detections above threshold, for a batch of frames."""
        outputs = self.model([self._to_tensor(f) for f in frames_bgr])
        results: List[List[Detection]] = []
        for out in outputs:
            keep = (out["labels"] == self.dog_label) & (out["scores"] >= self.score_threshold)
            boxes = out["boxes"][keep].cpu().numpy()
            scores = out["scores"][keep].cpu().numpy()
            results.append([Detection(tuple(map(float, b)), float(s)) for b, s in zip(boxes, scores)])
        return results

    def detect(self, frame_bgr: np.ndarray, previous: Optional[Box] = None) -> Optional[Detection]:
        return select_box(self.detect_all([frame_bgr])[0], previous)
