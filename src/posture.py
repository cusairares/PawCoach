"""Stage 2: posture classification on the dog crop.

MobileNetV3-Large (ImageNet-pretrained, frozen) produces a 1280-d embedding
(features -> avgpool -> classifier[0] -> hardswish). A small head trained on
``stockeh/dog-pose-cv`` maps it to POSTURE_LABELS.

``preprocess`` is the single preprocessing function used for BOTH training and
inference (the reference repo had a train/inference mismatch here).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import cv2
import numpy as np
import torch
from torch import nn
from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large

from .config import MODELS_DIR, POSTURE_LABELS

INPUT_SIZE = 224
EMBED_DIM = 1280
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
DEFAULT_HEAD_PATH = MODELS_DIR / "posture_head.pt"


def preprocess(crop_bgr: np.ndarray) -> np.ndarray:
    """BGR uint8 crop -> normalized float32 CHW (3, 224, 224)."""
    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)
    x = (rgb.astype(np.float32) / 255.0 - _MEAN) / _STD
    return np.ascontiguousarray(x.transpose(2, 0, 1))


class Backbone(nn.Module):
    """Frozen MobileNetV3-Large up to the 1280-d penultimate activation."""

    def __init__(self) -> None:
        super().__init__()
        base = mobilenet_v3_large(weights=MobileNet_V3_Large_Weights.IMAGENET1K_V2)
        self.features = base.features
        self.avgpool = base.avgpool
        self.proj = base.classifier[0]   # Linear(960, 1280), pretrained
        self.act = base.classifier[1]    # Hardswish
        for p in self.parameters():
            p.requires_grad_(False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.avgpool(self.features(x)).flatten(1)
        return self.act(self.proj(x))


class DeepResidualHead(nn.Module):
    def __init__(self, in_features: int = EMBED_DIM, hidden: int = 512, num_classes: int = 4, dropout: float = 0.25):
        super().__init__()
        self.in_proj = nn.Sequential(
            nn.Linear(in_features, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(dropout)
        )
        self.res_block = nn.Sequential(
            nn.Linear(hidden, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(dropout)
        )
        self.out_proj = nn.Linear(hidden, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.in_proj(x)
        h = h + self.res_block(h)
        return self.out_proj(h)


def build_head(kind: str = "linear", num_classes: int = len(POSTURE_LABELS),
               hidden: int = 256, dropout: float = 0.3) -> nn.Module:
    if kind == "linear":
        return nn.Sequential(nn.Dropout(dropout), nn.Linear(EMBED_DIM, num_classes))
    if kind == "mlp":
        return nn.Sequential(nn.Linear(EMBED_DIM, hidden), nn.Hardswish(),
                             nn.Dropout(dropout), nn.Linear(hidden, num_classes))
    if kind == "residual_mlp":
        return DeepResidualHead(in_features=EMBED_DIM, hidden=hidden, num_classes=num_classes, dropout=dropout)
    raise ValueError(f"Unknown head kind: {kind}")


class PostureModel(nn.Module):
    """Backbone + head, image tensor -> logits. Used for ONNX export."""

    def __init__(self, head: nn.Module) -> None:
        super().__init__()
        self.backbone = Backbone()
        self.head = head

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.backbone(x))


class PostureClassifier:
    def __init__(self, head_path: Path = DEFAULT_HEAD_PATH, device: Optional[str] = None):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        head_path = Path(head_path)
        if not head_path.exists():
            raise FileNotFoundError(
                f"Posture head not found at {head_path}. Train it first:\n"
                "  python -m training.prepare_dataset\n  python -m training.train_head")
        ckpt = torch.load(head_path, map_location="cpu", weights_only=False)
        self.labels: List[str] = ckpt["labels"]
        head = build_head(**ckpt["head_config"])
        head.load_state_dict(ckpt["state_dict"])
        self.model = PostureModel(head).to(self.device).eval()
        self.metrics: Dict = ckpt.get("metrics", {})

    @torch.inference_mode()
    def predict_batch(self, crops_bgr: Sequence[np.ndarray]) -> np.ndarray:
        x = torch.from_numpy(np.stack([preprocess(c) for c in crops_bgr])).to(self.device)
        return torch.softmax(self.model(x), dim=1).cpu().numpy()

    def predict(self, crop_bgr: np.ndarray) -> np.ndarray:
        return self.predict_batch([crop_bgr])[0]
