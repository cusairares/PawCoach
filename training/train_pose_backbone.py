"""Train yolo11n-pose on dog-pose.yaml with smart-feeder camera augmentations.
Uses local NVIDIA GPU (RTX 4060) to train 24 canine keypoint backbone.
"""
from pathlib import Path
from ultralytics import YOLO
import torch

def train():
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"[Train] Initializing YOLO11-Pose on device: {device}")
    if torch.cuda.is_available():
        print(f"[Train] GPU: {torch.cuda.get_device_name(0)}")

    data_yaml = str(Path(__file__).parent / "dog_pose_fixed.yaml")
    
    # Load official COCO-pretrained nano pose model
    model = YOLO("yolo11n-pose.pt")

    # Feeder-specific augmentations:
    # perspective: downward feeder camera tilt (20-40 deg)
    # fliplr: 50% left/right mirror with our fixed 24-joint flip_idx
    # erasing: simulates treat bowl blocking lower front paws
    # workers=0: prevents Windows multiprocessing spawn paging file exhaustion
    results = model.train(
        data=data_yaml,
        epochs=80,
        imgsz=384,             # compact resolution matching Raspberry Pi deployment
        batch=16,              # conservative batch size
        workers=0,             # single-process loader (essential on Windows to avoid WinError 1455)
        device=device,
        patience=20,
        save=True,
        plots=True,
        fliplr=0.5,
        degrees=10.0,
        scale=0.4,
        perspective=0.0005,
        erasing=0.2,
        project="models",
        name="dog_pose_train",
        exist_ok=True
    )

    best_weights = Path("models/dog_pose_train/weights/best.pt")
    target_weights = Path("models/dog_pose_best.pt")
    if best_weights.exists():
        import shutil
        shutil.copy(best_weights, target_weights)
        print(f"[Train] Saved best pose model to {target_weights}")

if __name__ == "__main__":
    train()
