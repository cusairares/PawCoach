"""Stage 1: Dog detection & 24 anatomical keypoint estimation.

Supports YOLO11-Pose via ONNX Runtime (default on Raspberry Pi & desktop)
or Ultralytics PyTorch (.pt).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple
import cv2
import numpy as np

Box = Tuple[float, float, float, float]  # x1, y1, x2, y2 (pixels)

@dataclass
class Detection:
    box: Box
    score: float
    keypoints_xy: np.ndarray    # (24, 2) float32 in frame pixels
    keypoints_conf: np.ndarray  # (24,) float32 in [0, 1]

def iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)

def select_box(candidates: Sequence[Detection], previous: Optional[Box],
               min_iou: float = 0.3) -> Optional[Detection]:
    if not candidates:
        return None
    if previous is not None:
        best = max(candidates, key=lambda d: iou(d.box, previous))
        if iou(best.box, previous) >= min_iou:
            return best
    return max(candidates, key=lambda d: (round(d.score, 2), (d.box[2]-d.box[0])*(d.box[3]-d.box[1])))

def letterbox(img: np.ndarray, target_size: int = 320) -> Tuple[np.ndarray, float, float, float]:
    """Pads image to square target_size while keeping aspect ratio."""
    h, w = img.shape[:2]
    scale = target_size / max(h, w)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)

    pad_w = target_size - nw
    pad_h = target_size - nh
    top = pad_h // 2
    bottom = pad_h - top
    left = pad_w // 2
    right = pad_w - left

    padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
    return padded, scale, float(left), float(top)

class DogDetector:
    """YOLO11-Pose canine keypoint detector with ONNX / PyTorch backends."""

    def __init__(self, model_path: Optional[Path] = None, score_threshold: float = 0.45,
                 imgsz: int = 320):
        self.score_threshold = score_threshold
        self.imgsz = imgsz
        self.ort_session = None
        self.yolo_model = None

        root = Path(__file__).resolve().parent.parent
        if model_path is None:
            onnx_path = root / "models" / "dog_pose_320.onnx"
            pt_path = root / "models" / "dog_pose_best.pt"
            if onnx_path.exists():
                model_path = onnx_path
            elif pt_path.exists():
                model_path = pt_path
            else:
                model_path = Path("yolo11n-pose.pt")

        model_path = Path(model_path)
        if model_path.suffix == ".onnx":
            import onnxruntime as ort
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if ort.get_device() == "GPU" else ["CPUExecutionProvider"]
            self.ort_session = ort.InferenceSession(str(model_path), providers=providers)
            self.input_name = self.ort_session.get_inputs()[0].name
            print(f"[DogDetector] Loaded ONNX model from {model_path}")
        else:
            from ultralytics import YOLO
            self.yolo_model = YOLO(str(model_path))
            print(f"[DogDetector] Loaded YOLO PyTorch model from {model_path}")

    def detect_frame(self, frame_bgr: np.ndarray) -> List[Detection]:
        h_orig, w_orig = frame_bgr.shape[:2]

        if self.ort_session is not None:
            # Standalone ONNX forward pass
            padded, scale, pad_x, pad_y = letterbox(frame_bgr, self.imgsz)
            rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            blob = np.transpose(rgb, (2, 0, 1))[np.newaxis, ...]

            preds = self.ort_session.run(None, {self.input_name: blob})[0]
            # Output shape: (1, 4 + 1 + 24*3, 2100) -> (1, 77, 2100)
            preds = preds[0]  # (77, 2100)
            
            boxes_xywh = preds[:4, :] # cx, cy, w, h
            scores = preds[4, :]
            kpts_raw = preds[5:, :]   # 72 rows (24 x 3)

            keep = np.where(scores >= self.score_threshold)[0]
            if len(keep) == 0:
                return []

            detections = []
            for idx in keep:
                sc = float(scores[idx])
                cx, cy, bw, bh = boxes_xywh[:, idx]
                
                # Unpad to original frame coords
                x1 = (cx - bw / 2.0 - pad_x) / scale
                y1 = (cy - bh / 2.0 - pad_y) / scale
                x2 = (cx + bw / 2.0 - pad_x) / scale
                y2 = (cy + bh / 2.0 - pad_y) / scale

                x1 = float(np.clip(x1, 0, w_orig))
                y1 = float(np.clip(y1, 0, h_orig))
                x2 = float(np.clip(x2, 0, w_orig))
                y2 = float(np.clip(y2, 0, h_orig))

                kpts_col = kpts_raw[:, idx].reshape(24, 3)
                kx = (kpts_col[:, 0] - pad_x) / scale
                ky = (kpts_col[:, 1] - pad_y) / scale
                kconf = kpts_col[:, 2]

                detections.append(Detection(
                    box=(x1, y1, x2, y2),
                    score=sc,
                    keypoints_xy=np.stack([kx, ky], axis=-1).astype(np.float32),
                    keypoints_conf=kconf.astype(np.float32)
                ))
            return detections
        else:
            # Fallback via Ultralytics
            res = self.yolo_model(frame_bgr, verbose=False, imgsz=self.imgsz, conf=self.score_threshold)[0]
            if res.boxes is None or len(res.boxes) == 0:
                return []

            dets = []
            for i in range(len(res.boxes)):
                b = res.boxes.xyxy[i].cpu().numpy()
                sc = float(res.boxes.conf[i].cpu().item())
                kpts_xy = res.keypoints.xy[i].cpu().numpy()
                kpts_conf = res.keypoints.conf[i].cpu().numpy() if res.keypoints.conf is not None else np.ones(24, dtype=np.float32)

                dets.append(Detection(
                    box=(float(b[0]), float(b[1]), float(b[2]), float(b[3])),
                    score=sc,
                    keypoints_xy=kpts_xy,
                    keypoints_conf=kpts_conf
                ))
            return dets

    def detect(self, frame_bgr: np.ndarray, previous: Optional[Box] = None) -> Optional[Detection]:
        candidates = self.detect_frame(frame_bgr)
        return select_box(candidates, previous)
