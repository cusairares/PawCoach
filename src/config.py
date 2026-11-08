"""Configuration objects for the smart feeder.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"

# Canonical posture labels (order == Stage-2 output order).
POSTURE_LABELS: List[str] = ["lying", "sitting", "standing", "undefined"]
POSE_LABELS: List[str] = ["lying", "sitting", "standing"]
NO_DOG = "no_dog"

# Pose label -> audio cue key
POSE_TO_CUE: Dict[str, str] = {"sitting": "sit", "lying": "down", "standing": "stand"}
CUE_TO_POSE: Dict[str, str] = {v: k for k, v in POSE_TO_CUE.items()}

@dataclass
class EngineConfig:
    # Stage 1 (YOLO-pose detector)
    detector_score_threshold: float = 0.45
    pose_imgsz: int = 320
    detect_every_n_frames: int = 1          # >1 reuses keypoints across frames for Pi 4/Zero
    box_padding: float = 0.15
    box_max_age_s: float = 0.5

    # Stage 2 (biomechanical posture head)
    min_visible_keypoints: int = 5          # below -> counts as 'undefined'
    posture_min_confidence: float = 0.40    # below -> frame counts as 'undefined'

    # Consensus buffer
    window_s: float = 1.0                   # T_w
    min_fill: float = 0.7                   # fraction of T_w that must be covered
    min_entries: int = 5

    # Confirmation thresholds / dwell per mode
    passive_threshold: float = 0.70
    passive_dwell_s: float = 1.5
    active_threshold: float = 0.60
    active_dwell_s: float = 1.0
    exit_threshold: float = 0.40

@dataclass
class AppSettings:
    """Settings controlled by the mobile app and stored locally in app_settings.json."""
    passive_enabled: bool = True
    passive_poses: List[str] = field(default_factory=lambda: list(POSE_LABELS))
    passive_pose_cooldown_s: float = 30.0
    passive_sound_when_treat_blocked: bool = False
    
    # Active command settings
    active_command_timeout_s: float = 8.0
    active_command_play_cue: bool = True
    active_command_reward: bool = True
    
    # Treat limits
    daily_treat_limit: int = 20
    min_seconds_between_treats: float = 10.0
    volume: float = 1.0

    def update(self, values: Dict) -> None:
        names = {f.name for f in fields(self)}
        for key, value in values.items():
            if key not in names:
                raise KeyError(f"Unknown setting: {key}")
            setattr(self, key, value)

    def to_dict(self) -> Dict:
        return asdict(self)

class SettingsStore:
    def __init__(self, path: Path = DATA_DIR / "app_settings.json"):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._settings = AppSettings()
        if self.path.exists():
            self._settings.update(json.loads(self.path.read_text(encoding="utf-8")))

    @property
    def current(self) -> AppSettings:
        with self._lock:
            return AppSettings(**self._settings.to_dict())

    def update(self, values: Dict) -> AppSettings:
        with self._lock:
            self._settings.update(values)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._settings.to_dict(), indent=2), encoding="utf-8")
            return AppSettings(**self._settings.to_dict())

@dataclass
class CommandRequest:
    pose: str
    command_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = "app"

    def __post_init__(self) -> None:
        if self.pose in CUE_TO_POSE:
            self.pose = CUE_TO_POSE[self.pose]
        if self.pose not in POSE_LABELS:
            raise ValueError(f"Unknown pose '{self.pose}'. Expected one of {POSE_LABELS}")
