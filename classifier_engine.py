import collections
import time
from typing import Optional, Tuple
import cv2
import numpy as np
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image

class ConsensusBuffer:
    """
    Temporal majority voting buffer (salvaged and enhanced from canine-embedded-ml).
    Smooths noisy single-frame predictions.
    """
    def __init__(self, buffer_len: int = 20, consensus_threshold: float = 0.60):
        self.buffer_len = buffer_len
        self.consensus_threshold = consensus_threshold
        self.buffer = collections.deque(maxlen=buffer_len)
        self.last_confirmed_state: Optional[str] = None
        self.last_confirmed_time: float = 0.0

    def add(self, state: str) -> None:
        self.buffer.append(state)

    def evaluate(self) -> Tuple[Optional[str], float, dict]:
        """
        Returns:
            confirmed_state: Name of state if consensus >= threshold, else None
            confidence: Proportion of votes
            distribution: Count of each state in the buffer
        """
        if len(self.buffer) < (self.buffer_len // 2):
            return None, 0.0, {}

        counts = collections.Counter(self.buffer)
        total = len(self.buffer)
        distribution = {k: round(v / total, 2) for k, v in counts.items()}

        most_common_state, count = counts.most_common(1)[0]
        ratio = count / total

        if ratio >= self.consensus_threshold and most_common_state != "unknown":
            self.last_confirmed_state = most_common_state
            self.last_confirmed_time = time.time()
            return most_common_state, ratio, distribution

        return None, ratio, distribution


class CanineClassifier:
    """
    Edge inference classifier with pre-trained MobileNetV3 backbone.
    """
    LABELS = {
        0: "lying",
        1: "sitting",
        2: "standing"
    }

    def __init__(self, weights_path: Optional[str] = None, device: Optional[str] = None):
        self.device = torch.device(device if device else ("cuda" if torch.cuda.is_available() else "cpu"))
        print(f"[CanineClassifier] Initializing on device: {self.device}")

        # MobileNetV3 Large (Apache 2.0 license, optimized for low-latency edge devices)
        self.model = models.mobilenet_v3_large(weights=models.MobileNet_V3_Large_Weights.DEFAULT)
        
        # Replace the final linear head for our 3 custom posture classes
        in_features = self.model.classifier[3].in_features
        self.model.classifier[3] = torch.nn.Linear(in_features, len(self.LABELS))

        if weights_path:
            state_dict = torch.load(weights_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            print(f"[CanineClassifier] Loaded custom weights from {weights_path}")
        else:
            print("[CanineClassifier] Running with initialized transfer head (Ready for fine-tuning / demo mode)")

        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def predict_frame(self, frame_bgr: np.ndarray, min_confidence: float = 0.40) -> Tuple[str, float, np.ndarray]:
        """
        Classifies a single BGR camera frame.
        Returns:
            predicted_label: 'lying', 'sitting', 'standing', or 'unknown'
            confidence: Probability float [0, 1]
            all_probs: Probabilities array for all 3 classes
        """
        rgb_image = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_image)
        tensor = self.transform(pil_img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            outputs = self.model(tensor)
            probs = torch.softmax(outputs, dim=1).cpu().numpy()[0]

        class_idx = int(np.argmax(probs))
        confidence = float(probs[class_idx])

        if confidence < min_confidence:
            return "unknown", confidence, probs

        return self.LABELS[class_idx], confidence, probs


class FeederMockController:
    """
    Controls treat dispensing with rate-limiting and mock/hardware dispatch.
    """
    def __init__(self, cooldown_seconds: float = 10.0):
        self.cooldown_seconds = cooldown_seconds
        self.last_dispense_time = 0.0
        self.daily_treat_count = 0

    def trigger(self, reason: str = "Target behavior confirmed") -> bool:
        now = time.time()
        if now - self.last_dispense_time < self.cooldown_seconds:
            remaining = int(self.cooldown_seconds - (now - self.last_dispense_time))
            print(f"[Feeder] Cooldown active. Wait {remaining}s")
            return False

        self.last_dispense_time = now
        self.daily_treat_count += 1
        print("="*50)
        print(f"[TREAT DISPENSED!] Reason: {reason} | Total Today: {self.daily_treat_count}")
        print("="*50)
        return True
