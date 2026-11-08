"""Shared biomechanical feature extraction and keypoint geometric utilities.

Computes a scale-, translation-, and facing-invariant 86-d feature vector
from canine keypoints (supports both 24-keypoint canine layout and 17-keypoint fallback).
"""
from __future__ import annotations

from typing import List, Tuple
import numpy as np

CANINE_KEYPOINTS = 24
FEATURE_DIM = 86

# Exact horizontal symmetry permutation for 24 canine keypoints:
FLIP_IDX_24 = [6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 4, 5, 12, 13, 15, 14, 16, 17, 19, 18, 21, 20, 22, 23]

# Visual skeleton connection pairs for 24 keypoints
SKELETON_EDGES_24 = [
    # Front left leg
    (0, 1), (1, 2), (2, 22),
    # Rear left leg
    (3, 4), (4, 5), (5, 12),
    # Front right leg
    (6, 7), (7, 8), (8, 22),
    # Rear right leg
    (9, 10), (10, 11), (11, 12),
    # Spine & tail
    (12, 22), (12, 13),
    # Head & neck
    (22, 23), (23, 17), (17, 16),
    (14, 18), (15, 19), (14, 20), (15, 21), (20, 16), (21, 16)
]
SKELETON_EDGES = SKELETON_EDGES_24

# Fallback COCO-17 connections
SKELETON_EDGES_17 = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16)
]
FLIP_IDX_17 = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]

def get_skeleton_edges(n_kpts: int) -> List[Tuple[int, int]]:
    return SKELETON_EDGES_24 if n_kpts >= 24 else SKELETON_EDGES_17

def mirror_pose(box: Tuple[float, float, float, float], kpts_xy: np.ndarray,
                kpts_conf: np.ndarray, frame_width: float) -> Tuple[Tuple[float, float, float, float], np.ndarray, np.ndarray]:
    """Horizontally mirror bounding box and keypoints with symmetry permutation."""
    x1, y1, x2, y2 = box
    flipped_box = (frame_width - x2, y1, frame_width - x1, y2)

    n_kpts = len(kpts_xy)
    flip_idx = FLIP_IDX_24 if n_kpts >= 24 else FLIP_IDX_17[:n_kpts]

    flipped_xy = kpts_xy.copy()
    flipped_xy[:, 0] = frame_width - flipped_xy[:, 0]
    flipped_xy = flipped_xy[flip_idx]
    flipped_conf = kpts_conf[flip_idx]

    return flipped_box, flipped_xy, flipped_conf

def _calc_angle_cos(p_a: np.ndarray, p_b: np.ndarray, p_c: np.ndarray) -> float:
    """Cosine of angle formed at vertex p_b by points p_a-p_b-p_c."""
    v1 = p_a - p_b
    v2 = p_c - p_b
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 < 1e-4 or norm2 < 1e-4:
        return 0.0
    cos_val = np.dot(v1, v2) / (norm1 * norm2)
    return float(np.clip(cos_val, -1.0, 1.0))

def extract_pose_features(box: Tuple[float, float, float, float],
                          kpts_xy: np.ndarray,
                          kpts_conf: np.ndarray,
                          vis_thresh: float = 0.35) -> np.ndarray:
    """Extract an 86-dimensional normalized geometric feature vector."""
    x1, y1, x2, y2 = box
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    diag = np.sqrt(w * w + h * h)

    n_kpts = len(kpts_xy)
    norm_kpts = np.zeros(CANINE_KEYPOINTS * 3, dtype=np.float32)

    for i in range(min(CANINE_KEYPOINTS, n_kpts)):
        conf = float(kpts_conf[i])
        norm_kpts[i * 3 + 2] = conf
        if conf >= 0.10:
            norm_kpts[i * 3 + 0] = (kpts_xy[i, 0] - cx) / diag
            norm_kpts[i * 3 + 1] = (kpts_xy[i, 1] - cy) / diag

    bio = np.zeros(14, dtype=np.float32)
    bio[0] = float(np.log(w / h))
    bio[1] = float(w / (w + h))

    vis_mask = kpts_conf >= vis_thresh
    bio[2] = float(np.mean(vis_mask))

    if n_kpts >= 24:
        bio[3] = float(np.mean(kpts_conf[:12]))
        bio[4] = float(np.mean(kpts_conf[[12, 22, 23]]))

        dy_spine = (kpts_xy[12, 1] - kpts_xy[22, 1]) / diag
        dx_spine = abs(kpts_xy[12, 0] - kpts_xy[22, 0]) / diag
        bio[5] = float(dy_spine)
        bio[6] = float(dx_spine)

        front_paws_y = np.mean([kpts_xy[0, 1], kpts_xy[6, 1]])
        front_elbows_y = np.mean([kpts_xy[2, 1], kpts_xy[8, 1]])
        rear_paws_y = np.mean([kpts_xy[3, 1], kpts_xy[9, 1]])

        bio[7] = float((front_paws_y - front_elbows_y) / diag)
        bio[8] = float((front_paws_y - kpts_xy[22, 1]) / diag)
        bio[9] = float((rear_paws_y - kpts_xy[12, 1]) / diag)

        bio[10] = _calc_angle_cos(kpts_xy[2], kpts_xy[1], kpts_xy[0])
        bio[11] = _calc_angle_cos(kpts_xy[5], kpts_xy[4], kpts_xy[3])
        bio[12] = _calc_angle_cos(kpts_xy[8], kpts_xy[7], kpts_xy[6])
        bio[13] = _calc_angle_cos(kpts_xy[11], kpts_xy[10], kpts_xy[9])
    else:
        # Fallback approximation for 17 keypoints
        bio[3] = float(np.mean(kpts_conf))
        bio[4] = float(np.mean(kpts_conf[:5]))

    return np.concatenate([norm_kpts, bio]).astype(np.float32)
