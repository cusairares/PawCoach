"""Extract feature embeddings from dog-pose-cv using frozen MobileNetV3-Large.
Outputs cached tensors for lightning-fast training of the classification head.
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

def prepare_and_cache_embeddings(raw_dir: Path, output_dir: Path, max_samples_per_class: int = 2500):
    output_dir.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/3] Parsing label CSVs...")
    label_files = glob.glob(str(raw_dir / "labels" / "*.csv"))
    # Filter out macOS hidden metadata files
    label_files = [f for f in label_files if not os.path.basename(f).startswith("._")]
    
    records = []
    for f in label_files:
        df = pd.read_csv(f)
        records.append(df)
    
    full_df = pd.concat(records, ignore_index=True)
    # Standardize label strings
    label_map = {
        "lying down": "lying",
        "lying": "lying",
        "sitting": "sitting",
        "standing": "standing",
        "undefined": "undefined"
    }
    full_df["clean_label"] = full_df["label"].map(label_map)
    full_df = full_df.dropna(subset=["clean_label"])

    print("Class distribution in raw dataset:")
    print(full_df["clean_label"].value_counts())

    # Balance/cap classes so training is rapid and balanced
    sampled_dfs = []
    for lbl in POSTURE_LABELS:
        sub = full_df[full_df["clean_label"] == lbl]
        if len(sub) > max_samples_per_class:
            sub = sub.sample(n=max_samples_per_class, random_state=42)
        sampled_dfs.append(sub)
    
    balanced_df = pd.concat(sampled_dfs, ignore_index=True).sample(frac=1.0, random_state=42).reset_index(drop=True)
    print(f"\nBalanced dataset for embedding extraction: {len(balanced_df)} samples")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[2/3] Extracting embeddings on {device} using frozen MobileNetV3...")
    backbone = Backbone().to(device).eval()

    label_to_idx = {lbl: idx for idx, lbl in enumerate(POSTURE_LABELS)}
    
    embeddings = []
    targets = []
    batch_tensors = []
    batch_labels = []
    batch_size = 64

    # Search for image file paths
    images_root = raw_dir / "images"

    for i, row in tqdm(balanced_df.iterrows(), total=len(balanced_df), desc="Extracting"):
        img_id = row["id"]
        lbl = row["clean_label"]

        # find image file
        matches = list(images_root.glob(f"*/{img_id}"))
        if not matches:
            continue
        
        img_path = str(matches[0])
        img = cv2.imread(img_path)
        if img is None:
            continue

        tensor = preprocess(img)
        batch_tensors.append(tensor)
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

    print(f"\n[3/3] Saving extracted embeddings: X={X.shape}, Y={Y.shape}")
    np.save(output_dir / "embeddings_X.npy", X)
    np.save(output_dir / "embeddings_Y.npy", Y)
    print("Feature extraction complete!")

if __name__ == "__main__":
    raw_dir = DATA_DIR / "raw"
    output_dir = DATA_DIR / "processed"
    prepare_and_cache_embeddings(raw_dir, output_dir)
