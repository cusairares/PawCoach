"""Extract 24-keypoint geometry from all 20,423 dog-pose-cv images using trained YOLO11-Pose.
Partitions data into leak-free Train / Val / Test splits grouped by breed.
"""
import glob
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import pandas as pd
import torch
from tqdm import tqdm
from ultralytics import YOLO

from src.pose_features import extract_pose_features, mirror_pose, FEATURE_DIM
from src.config import POSTURE_LABELS, DATA_DIR, MODELS_DIR

def extract_all():
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"[Extract] Using device: {device}")

    weights_path = MODELS_DIR / "dog_pose_best.pt"
    if not weights_path.exists():
        # Fallback to base pretrained pose model if fine-tuned is not yet built
        weights_path = Path("yolo11n-pose.pt")
        print(f"[Extract] Using base model: {weights_path}")
    else:
        print(f"[Extract] Loading trained weights: {weights_path}")

    model = YOLO(str(weights_path))

    # 1. Parse all 119 CSV label files (no 2500 cap!)
    raw_dir = DATA_DIR / "raw"
    label_files = [f for f in glob.glob(str(raw_dir / "labels" / "*.csv")) if not os.path.basename(f).startswith("._")]
    
    records = []
    for f in label_files:
        df = pd.read_csv(f)
        breed_name = os.path.basename(f).replace(".csv", "")
        df["breed"] = breed_name
        records.append(df)
    
    full_df = pd.concat(records, ignore_index=True)
    label_map = {
        "lying down": "lying",
        "lying": "lying",
        "sitting": "sitting",
        "standing": "standing",
        "undefined": "undefined"
    }
    full_df["clean_label"] = full_df["label"].map(label_map)
    full_df = full_df.dropna(subset=["clean_label"])

    print(f"\n[Extract] Full dataset parsed: {len(full_df)} samples across {full_df['breed'].nunique()} breeds")
    print(full_df["clean_label"].value_counts())

    # 2. Leak-free Train / Val / Test Split
    # We partition by whole breed so test metrics reflect true unseen-breed generalization
    all_breeds = np.array(sorted(full_df["breed"].unique()))
    np.random.seed(42)
    shuffled_breeds = np.random.permutation(all_breeds)
    
    n_total_breeds = len(shuffled_breeds)
    n_val_breeds = max(10, int(n_total_breeds * 0.10))
    n_test_breeds = max(10, int(n_total_breeds * 0.10))

    val_breeds = set(shuffled_breeds[:n_val_breeds])
    test_breeds = set(shuffled_breeds[n_val_breeds:n_val_breeds + n_test_breeds])
    train_breeds = set(shuffled_breeds[n_val_breeds + n_test_breeds:])

    def assign_split(breed):
        if breed in val_breeds:
            return 1  # val
        elif breed in test_breeds:
            return 2  # test
        return 0      # train

    full_df["split"] = full_df["breed"].apply(assign_split)

    label_to_idx = {lbl: i for i, lbl in enumerate(POSTURE_LABELS)}
    images_root = raw_dir / "images"

    features_list = []
    labels_list = []
    splits_list = []
    skipped = 0

    print("\n[Extract] Running keypoint extraction...")
    batch_size = 32
    rows_batch = []
    imgs_batch = []

    for idx, row in tqdm(full_df.iterrows(), total=len(full_df), desc="Extracting Keypoints"):
        img_id = row["id"]
        matches = list(images_root.glob(f"*/{img_id}"))
        if not matches:
            skipped += 1
            continue

        img_path = str(matches[0])
        img = cv2.imread(img_path)
        if img is None:
            skipped += 1
            continue

        rows_batch.append(row)
        imgs_batch.append(img)

        if len(imgs_batch) >= batch_size:
            _process_batch(model, imgs_batch, rows_batch, label_to_idx, features_list, labels_list, splits_list)
            imgs_batch = []
            rows_batch = []

    if imgs_batch:
        _process_batch(model, imgs_batch, rows_batch, label_to_idx, features_list, labels_list, splits_list)

    X = np.array(features_list, dtype=np.float32)
    Y = np.array(labels_list, dtype=np.int64)
    S = np.array(splits_list, dtype=np.int32)

    out_file = DATA_DIR / "processed" / "kpt_dataset.npz"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_file, X=X, Y=Y, split=S, labels=POSTURE_LABELS)

    print(f"\n[Extract] Done! Saved {len(X)} samples to {out_file} (skipped {skipped})")
    print(f"  Train: {(S == 0).sum()} | Val: {(S == 1).sum()} | Test: {(S == 2).sum()}")

def _process_batch(model, imgs, rows, label_to_idx, features_list, labels_list, splits_list):
    # Run YOLO-pose batch inference
    results = model(imgs, verbose=False, imgsz=384)
    for res, row, img in zip(results, rows, imgs):
        h, w = img.shape[:2]
        if res.boxes is None or len(res.boxes) == 0:
            # Fallback: full frame box with zero keypoints
            box = (0.0, 0.0, float(w), float(h))
            kpts_xy = np.zeros((24, 2), dtype=np.float32)
            kpts_conf = np.zeros(24, dtype=np.float32)
        else:
            # Pick highest confidence dog detection
            best_i = int(res.boxes.conf.argmax().item())
            b = res.boxes.xyxy[best_i].cpu().numpy()
            box = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
            
            if res.keypoints is not None:
                kpts_xy = res.keypoints.xy[best_i].cpu().numpy()
                kpts_conf = res.keypoints.conf[best_i].cpu().numpy() if res.keypoints.conf is not None else np.ones(24, dtype=np.float32)
            else:
                kpts_xy = np.zeros((24, 2), dtype=np.float32)
                kpts_conf = np.zeros(24, dtype=np.float32)

        feat = extract_pose_features(box, kpts_xy, kpts_conf)
        features_list.append(feat)
        labels_list.append(label_to_idx[row["clean_label"]])
        splits_list.append(row["split"])

if __name__ == "__main__":
    extract_all()
