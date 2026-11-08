"""Extract multi-crop augmented feature embeddings from dog-pose-cv using frozen MobileNetV3-Large.
Augmentations:
1. Original image
2. Horizontal flip (invariance to dog facing left vs right)
3. Center / slight scale crop (invariance to distance)
Also stores whether sample is clean posture (lying/sitting/standing) or undefined.
"""
import glob
import os
import cv2
import numpy as np
import pandas as pd
import torch
from pathlib import Path
from tqdm import tqdm

from src.posture import Backbone, preprocess
from src.config import POSTURE_LABELS, DATA_DIR, MODELS_DIR

def prepare_augmented_embeddings(raw_dir: Path, output_dir: Path, max_per_class: int = 3000):
    output_dir.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/3] Parsing label CSVs...")
    label_files = [f for f in glob.glob(str(raw_dir / "labels" / "*.csv")) if not os.path.basename(f).startswith("._")]
    records = [pd.read_csv(f) for f in label_files]
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

    print("Class distribution before sampling:")
    print(full_df["clean_label"].value_counts())

    # Sample up to max_per_class
    sampled_dfs = []
    for lbl in POSTURE_LABELS:
        sub = full_df[full_df["clean_label"] == lbl]
        if len(sub) > max_per_class:
            sub = sub.sample(n=max_per_class, random_state=42)
        sampled_dfs.append(sub)

    balanced_df = pd.concat(sampled_dfs, ignore_index=True).sample(frac=1.0, random_state=42).reset_index(drop=True)
    print(f"\nBalanced base dataset: {len(balanced_df)} samples")

    device = torch.device("cpu")
    print(f"[2/3] Extracting multi-crop augmented embeddings on CPU...")
    backbone = Backbone().to(device).eval()

    label_to_idx = {lbl: idx for idx, lbl in enumerate(POSTURE_LABELS)}
    images_root = raw_dir / "images"

    embeddings = []
    targets = []
    batch_tensors = []
    batch_labels = []
    batch_size = 64

    for i, row in tqdm(balanced_df.iterrows(), total=len(balanced_df), desc="Augmenting & Extracting"):
        img_id = row["id"]
        lbl = row["clean_label"]
        matches = list(images_root.glob(f"*/{img_id}"))
        if not matches:
            continue

        img_path = str(matches[0])
        img = cv2.imread(img_path)
        if img is None:
            continue

        # 1. Base image
        t1 = preprocess(img)
        batch_tensors.append(t1)
        batch_labels.append(label_to_idx[lbl])

        # 2. Horizontal flip (crucial for posture pose invariance)
        flipped = cv2.flip(img, 1)
        t2 = preprocess(flipped)
        batch_tensors.append(t2)
        batch_labels.append(label_to_idx[lbl])

        if len(batch_tensors) >= batch_size:
            x = torch.from_numpy(np.stack(batch_tensors)).to(device)
            with torch.no_grad():
                feats = backbone(x).cpu().numpy()
            embeddings.append(feats)
            targets.extend(batch_labels)
            batch_tensors = []
            batch_labels = []

    if batch_tensors:
        x = torch.from_numpy(np.stack(batch_tensors)).to(device)
        with torch.no_grad():
            feats = backbone(x).cpu().numpy()
        embeddings.append(feats)
        targets.extend(batch_labels)

    X = np.concatenate(embeddings, axis=0)
    Y = np.array(targets, dtype=np.int64)

    print(f"\n[3/3] Saving augmented embeddings: X={X.shape}, Y={Y.shape}")
    np.save(output_dir / "aug_embeddings_X.npy", X)
    np.save(output_dir / "aug_embeddings_Y.npy", Y)
    print("Multi-crop augmented feature extraction complete!")

if __name__ == "__main__":
    prepare_augmented_embeddings(DATA_DIR / "raw", DATA_DIR / "processed")
