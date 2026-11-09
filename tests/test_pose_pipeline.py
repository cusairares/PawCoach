import numpy as np
import pytest
from pathlib import Path

from src.pose_features import (
    FLIP_IDX_24,
    FEATURE_DIM,
    extract_pose_features,
    mirror_pose,
)
from src.posture import PostureClassifier
from src.detector import DogDetector, Detection
from src.config import POSTURE_LABELS


def test_flip_idx_involution():
    """Verify that FLIP_IDX_24 is a strict mathematical involution: f(f(i)) == i."""
    assert len(FLIP_IDX_24) == 24
    for i, target in enumerate(FLIP_IDX_24):
        assert FLIP_IDX_24[target] == i, f"Keypoint {i} <-> {target} symmetry broken: {FLIP_IDX_24[target]} != {i}"


def test_feature_vector_dimension():
    """Verify that feature extractor returns exactly FEATURE_DIM (86) floats."""
    box = (50.0, 40.0, 250.0, 180.0)
    kpts_xy = np.zeros((24, 2), dtype=np.float32)
    kpts_xy[:, 0] = np.linspace(60, 240, 24)
    kpts_xy[:, 1] = np.linspace(50, 170, 24)
    kpts_conf = np.full(24, 0.85, dtype=np.float32)

    feat = extract_pose_features(box, kpts_xy, kpts_conf)
    assert feat.shape == (FEATURE_DIM,)
    assert not np.isnan(feat).any()
    assert not np.isinf(feat).any()


def test_mirror_pose_involution():
    """Flipping pose geometry twice must return the exact original coordinates and confidences."""
    box = (50.0, 40.0, 250.0, 180.0)
    frame_width = 640.0
    kpts_xy = np.random.uniform(50, 200, (24, 2)).astype(np.float32)
    kpts_conf = np.random.uniform(0.5, 1.0, 24).astype(np.float32)

    f_box, f_xy, f_conf = mirror_pose(box, kpts_xy, kpts_conf, frame_width)
    ff_box, ff_xy, ff_conf = mirror_pose(f_box, f_xy, f_conf, frame_width)

    assert np.allclose(box, ff_box, atol=1e-5), "Double mirror did not recover box"
    assert np.allclose(kpts_xy, ff_xy, atol=1e-5), "Double mirror did not recover keypoint coords"
    assert np.allclose(kpts_conf, ff_conf, atol=1e-5), "Double mirror did not recover keypoint confidences"


def test_posture_classifier_gating():
    """If visible keypoints < min_visible_kpts (5), classifier must return undefined (index 3)."""
    clf = PostureClassifier(weights_path=Path("models/posture_kpt_head.npz"))

    kpts_xy = np.full((24, 2), 100.0, dtype=np.float32)
    kpts_conf = np.zeros(24, dtype=np.float32)
    kpts_conf[:3] = 0.9  # Only 3 visible joints

    det = Detection(
        box=(50.0, 50.0, 150.0, 150.0),
        score=0.9,
        keypoints_xy=kpts_xy,
        keypoints_conf=kpts_conf
    )

    probs = clf.predict_detection(det, frame_width=640.0, min_visible_kpts=5)
    assert probs[3] == 1.0, f"Expected undefined=1.0, got probs={probs}"
    assert np.argmax(probs) == 3


def test_posture_classifier_pure_numpy_inference():
    """Verify that pure-NumPy MLP computes valid probability distribution summing to 1.0."""
    clf = PostureClassifier(weights_path=Path("models/posture_kpt_head.npz"))

    kpts_xy = np.random.uniform(50, 200, (24, 2)).astype(np.float32)
    kpts_conf = np.full(24, 0.85, dtype=np.float32)
    det = Detection(
        box=(30.0, 40.0, 210.0, 190.0),
        score=0.92,
        keypoints_xy=kpts_xy,
        keypoints_conf=kpts_conf
    )

    probs = clf.predict_detection(det, frame_width=640.0)
    assert len(probs) == len(POSTURE_LABELS)
    assert 0.0 <= np.max(probs) <= 1.0
    assert np.isclose(np.sum(probs), 1.0, atol=1e-4)


def test_detector_onnx_inference():
    """Verify that ONNX runtime DogDetector loads and runs without errors."""
    onnx_path = Path("models/dog_pose_320.onnx")
    if not onnx_path.exists():
        pytest.skip("models/dog_pose_320.onnx not found")

    detector = DogDetector(model_path=onnx_path, score_threshold=0.25, imgsz=320)
    synthetic_frame = np.random.randint(0, 255, (320, 320, 3), dtype=np.uint8)

    detections = detector.detect_frame(synthetic_frame)
    assert isinstance(detections, list)
