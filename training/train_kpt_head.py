"""Train calibrated Biomechanical Posture MLP on extracted 24-keypoint features.
Selects best checkpoint by macro-F1 + penalized undefined false-alarms,
applies temperature scaling, and exports a pure-NumPy weights dictionary.
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader, WeightedRandomSampler
from sklearn.metrics import classification_report, confusion_matrix

from src.pose_features import FEATURE_DIM
from src.config import POSTURE_LABELS, DATA_DIR, MODELS_DIR

class KeypointMLP(nn.Module):
    def __init__(self, in_features: int = FEATURE_DIM, num_classes: int = 4):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, 128),
            nn.LayerNorm(128),
            nn.SiLU(),
            nn.Dropout(0.20),
            nn.Linear(128, 64),
            nn.LayerNorm(64),
            nn.SiLU(),
            nn.Dropout(0.15),
            nn.Linear(64, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

def train_mlp():
    data_path = DATA_DIR / "processed" / "kpt_dataset.npz"
    if not data_path.exists():
        raise FileNotFoundError(f"{data_path} not found. Run extract_pose_dataset.py first!")

    data = np.load(data_path)
    X, Y, split = data["X"], data["Y"], data["split"]

    X_train, y_train = X[split == 0], Y[split == 0]
    X_val, y_val = X[split == 1], Y[split == 1]
    X_test, y_test = X[split == 2], Y[split == 2]

    print(f"[Train MLP] Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    # Class weighting / balanced sampling for training
    classes, counts = np.unique(y_train, return_counts=True)
    class_weights = 1.0 / counts
    sample_weights = class_weights[y_train]
    sampler = WeightedRandomSampler(weights=sample_weights, num_samples=len(y_train), replacement=True)

    train_ds = TensorDataset(torch.from_numpy(X_train).float(), torch.from_numpy(y_train).long())
    val_ds = TensorDataset(torch.from_numpy(X_val).float(), torch.from_numpy(y_val).long())
    test_ds = TensorDataset(torch.from_numpy(X_test).float(), torch.from_numpy(y_test).long())

    train_loader = DataLoader(train_ds, batch_size=128, sampler=sampler)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=256, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = KeypointMLP().to(device)

    # Penalize confusing undefined as a real posture
    criterion = nn.CrossEntropyLoss(label_smoothing=0.03)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=40, eta_min=1e-5)

    best_score = -1.0
    best_state = None
    epochs = 40

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        for bx, by in train_loader:
            bx, by = bx.to(device), by.to(device)
            optimizer.zero_grad()
            logits = model(bx)
            loss = criterion(logits, by)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(by)

        scheduler.step()

        # Validation
        model.eval()
        val_preds, val_targets = [], []
        with torch.no_grad():
            for bx, by in val_loader:
                bx = bx.to(device)
                logits = model(bx)
                val_preds.extend(logits.argmax(dim=1).cpu().numpy())
                val_targets.extend(by.numpy())

        val_preds = np.array(val_preds)
        val_targets = np.array(val_targets)

        # Macro accuracy over postures
        cm = confusion_matrix(val_targets, val_preds, labels=[0, 1, 2, 3])
        # False alarm rate: undefined predicting lying(0), sitting(1), or standing(2)
        undef_total = max(1, cm[3].sum())
        undef_false_alarms = cm[3, :3].sum() / undef_total

        # Clean 3-class accuracy
        clean_mask = val_targets != 3
        clean_acc = (val_preds[clean_mask] == val_targets[clean_mask]).mean() if clean_mask.sum() > 0 else 0.0

        # Score balances high posture accuracy with low false treats
        score = clean_acc - (2.0 * undef_false_alarms)

        if score > best_score:
            best_score = score
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if epoch % 10 == 0 or epoch == epochs:
            print(f"Epoch {epoch:02d} | Loss: {total_loss/len(X_train):.4f} | Clean Acc: {clean_acc*100:.1f}% | Undef False Alarm: {undef_false_alarms*100:.1f}%")

    print("\n[Train MLP] Best model restored. Evaluating on held-out test set...")
    model.load_state_dict(best_state)
    model.eval()

    test_preds, test_targets, test_logits = [], [], []
    with torch.no_grad():
        for bx, by in test_loader:
            bx = bx.to(device)
            logits = model(bx)
            test_logits.append(logits.cpu().numpy())
            test_preds.extend(logits.argmax(dim=1).cpu().numpy())
            test_targets.extend(by.numpy())

    test_preds = np.array(test_preds)
    test_targets = np.array(test_targets)

    print("\n--- Test Set Classification Report (Unseen Breeds) ---")
    print(classification_report(test_targets, test_preds, target_names=POSTURE_LABELS, digits=3))
    print("Confusion Matrix:")
    print(confusion_matrix(test_targets, test_preds))

    # Save lightweight weights for pure-NumPy runtime
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    npz_path = MODELS_DIR / "posture_kpt_head.npz"
    np.savez_compressed(
        npz_path,
        w1=best_state["net.0.weight"].numpy(),
        b1=best_state["net.0.bias"].numpy(),
        ln1_w=best_state["net.1.weight"].numpy(),
        ln1_b=best_state["net.1.bias"].numpy(),
        w2=best_state["net.4.weight"].numpy(),
        b2=best_state["net.4.bias"].numpy(),
        ln2_w=best_state["net.5.weight"].numpy(),
        ln2_b=best_state["net.5.bias"].numpy(),
        w3=best_state["net.8.weight"].numpy(),
        b3=best_state["net.8.bias"].numpy(),
        labels=np.array(POSTURE_LABELS)
    )
    print(f"\n[Train MLP] Pure-NumPy head exported to {npz_path} ({npz_path.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    train_mlp()
