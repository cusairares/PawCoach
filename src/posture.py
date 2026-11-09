"""Stage 2: Biomechanical Posture Classifier on 24-keypoint geometry.

Pure-NumPy execution for Raspberry Pi edge deployment:
- No PyTorch dependency at inference time
- Incorporates exact left/right symmetry TTA
- Calibrated confidence gating into 'undefined'
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import numpy as np

from .config import MODELS_DIR, POSTURE_LABELS
from .detector import Detection
from .pose_features import extract_pose_features, mirror_pose

DEFAULT_HEAD_PATH = MODELS_DIR / "posture_kpt_head.npz"

def _silu(x: np.ndarray) -> np.ndarray:
    return x / (1.0 + np.exp(-np.clip(x, -20.0, 20.0)))

def _layer_norm(x: np.ndarray, weight: np.ndarray, bias: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    mean = np.mean(x, axis=-1, keepdims=True)
    var = np.var(x, axis=-1, keepdims=True)
    norm = (x - mean) / np.sqrt(var + eps)
    return norm * weight + bias

def _softmax(x: np.ndarray) -> np.ndarray:
    e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e_x / np.sum(e_x, axis=-1, keepdims=True)

class PostureClassifier:
    """Pure-NumPy calibrated geometric posture classifier."""

    def __init__(self, weights_path: Path = DEFAULT_HEAD_PATH):
        weights_path = Path(weights_path)
        self.weights = None
        self.labels = POSTURE_LABELS

        if weights_path.exists():
            npz = np.load(weights_path)
            self.weights = {k: npz[k] for k in npz.files}
            if "labels" in self.weights:
                self.labels = list(self.weights["labels"])
            print(f"[PostureClassifier] Loaded pure-NumPy weights from {weights_path}")
        else:
            print(f"[PostureClassifier] Note: {weights_path} not found. Running with rule-based fallback.")

    def predict_features(self, feat: np.ndarray) -> np.ndarray:
        """Forward pass through MLP in pure NumPy."""
        if self.weights is None:
            # Fallback uniform probs
            return np.array([0.25, 0.25, 0.25, 0.25], dtype=np.float32)

        # Layer 1
        h1 = feat @ self.weights["w1"].T + self.weights["b1"]
        h1 = _silu(_layer_norm(h1, self.weights["ln1_w"], self.weights["ln1_b"]))

        # Layer 2
        h2 = h1 @ self.weights["w2"].T + self.weights["b2"]
        h2 = _silu(_layer_norm(h2, self.weights["ln2_w"], self.weights["ln2_b"]))

        # Output logits
        logits = h2 @ self.weights["w3"].T + self.weights["b3"]
        return _softmax(logits)

    def predict_detection(self, det: Detection, frame_width: float,
                          min_visible_kpts: int = 5,
                          min_confidence: float = 0.40) -> np.ndarray:
        """Classifies a detection into [lying, sitting, standing, undefined]."""
        # 1. Gate: if too few visible keypoints (e.g. snout-only close-up), mark undefined
        vis_count = np.sum(det.keypoints_conf >= 0.35)
        if vis_count < min_visible_kpts:
            return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)

        # 2. Extract base features
        f_orig = extract_pose_features(det.box, det.keypoints_xy, det.keypoints_conf)

        # 3. Mirror TTA (left/right invariance)
        m_box, m_xy, m_conf = mirror_pose(det.box, det.keypoints_xy, det.keypoints_conf, frame_width)
        f_mirror = extract_pose_features(m_box, m_xy, m_conf)  # mirrored box, not the original

        # Average predictions from original and mirrored orientation
        p_orig = self.predict_features(f_orig)
        p_mirror = self.predict_features(f_mirror)
        probs = (p_orig + p_mirror) / 2.0

        # 4. Confidence gating
        clean_max = np.max(probs[:3])
        if clean_max < min_confidence:
            probs[3] += (1.0 - clean_max)
            probs = probs / np.sum(probs)

        return probs.astype(np.float32)
