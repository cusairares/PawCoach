"""Advanced fine-tuning for posture classification head:
1. Label smoothing + class weighting (penalizes confusing sit with lie down)
2. Cosine annealing schedule with warmup
3. Layer-norm + residual projection MLP head
4. Evaluates both:
   a) 4-class accuracy (including 'undefined' reject class)
   b) 3-class clean posture accuracy (lying vs sitting vs standing)
"""
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from pathlib import Path

from src.posture import EMBED_DIM
from src.config import POSTURE_LABELS, DATA_DIR, MODELS_DIR

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

def train_finetuned():
    processed_dir = DATA_DIR / "processed"
    x_file = processed_dir / "aug_embeddings_X.npy"
    if not x_file.exists():
        x_file = processed_dir / "embeddings_X.npy"
        y_file = processed_dir / "embeddings_Y.npy"
    else:
        y_file = processed_dir / "aug_embeddings_Y.npy"

    print(f"Loading embeddings from {x_file.name}...")
    X = np.load(x_file)
    Y = np.load(y_file)
    print(f"Embeddings shape: X={X.shape}, Y={Y.shape}")

    # Stratified split
    X_train, X_val, y_train, y_val = train_test_split(X, Y, test_size=0.15, random_state=42, stratify=Y)

    train_ds = TensorDataset(torch.from_numpy(X_train).float(), torch.from_numpy(y_train).long())
    val_ds = TensorDataset(torch.from_numpy(X_val).float(), torch.from_numpy(y_val).long())

    train_loader = DataLoader(train_ds, batch_size=128, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False)

    device = torch.device("cpu")
    head = DeepResidualHead(in_features=EMBED_DIM, hidden=512, num_classes=len(POSTURE_LABELS), dropout=0.25).to(device)

    # Class weights: give extra weight to 'sitting' since it is the hardest posture to differentiate
    # [lying, sitting, standing, undefined]
    weights = torch.tensor([1.0, 1.25, 1.0, 0.85], dtype=torch.float32).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights, label_smoothing=0.08)

    optimizer = torch.optim.AdamW(head.parameters(), lr=8e-4, weight_decay=1e-3)
    epochs = 30
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    print("\nTraining Enhanced Residual Posture Head...")
    best_clean_acc = 0.0
    best_state = None

    for epoch in range(1, epochs + 1):
        head.train()
        total_loss, correct, total = 0.0, 0, 0
        for bx, by in train_loader:
            optimizer.zero_grad()
            logits = head(bx)
            loss = criterion(logits, by)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(by)
            correct += (logits.argmax(dim=1) == by).sum().item()
            total += len(by)

        scheduler.step()
        train_acc = correct / total

        # Validation
        head.eval()
        val_preds, val_targets = [], []
        with torch.no_grad():
            for bx, by in val_loader:
                logits = head(bx)
                val_preds.extend(logits.argmax(dim=1).numpy())
                val_targets.extend(by.numpy())

        val_preds = np.array(val_preds)
        val_targets = np.array(val_targets)
        overall_val_acc = (val_preds == val_targets).mean()

        # Clean 3-class accuracy (excluding undefined samples)
        clean_mask = val_targets != 3
        clean_acc = (val_preds[clean_mask] == val_targets[clean_mask]).mean() if clean_mask.sum() > 0 else 0.0

        if clean_acc > best_clean_acc:
            best_clean_acc = clean_acc
            best_state = {k: v.cpu().clone() for k, v in head.state_dict().items()}

        if epoch % 5 == 0 or epoch == epochs:
            print(f"Epoch {epoch:02d}/{epochs} | Loss: {total_loss/total:.4f} | Overall Acc: {overall_val_acc*100:.1f}% | Clean Posture Acc: {clean_acc*100:.1f}%")

    print(f"\nBest Clean Posture (Sit/Stand/Lie) Accuracy: {best_clean_acc*100:.2f}%")

    # Evaluation with Best Checkpoint
    head.load_state_dict(best_state)
    head.eval()
    all_preds, all_targets = [], []
    with torch.no_grad():
        for bx, by in val_loader:
            preds = head(bx).argmax(dim=1).numpy()
            all_preds.extend(preds)
            all_targets.extend(by.numpy())

    all_preds = np.array(all_preds)
    all_targets = np.array(all_targets)

    print("\n--- 4-Class Classification Report ---")
    print(classification_report(all_targets, all_preds, target_names=POSTURE_LABELS))
    print("Confusion Matrix:")
    print(confusion_matrix(all_targets, all_preds))

    # Evaluate 3-class clean subset
    clean_idx = all_targets != 3
    print("\n--- 3-Class Clean Posture (Excluding Undefined) ---")
    print(classification_report(all_targets[clean_idx], all_preds[clean_idx],
                                target_names=["lying", "sitting", "standing"],
                                labels=[0, 1, 2]))

    # Save to models/posture_head.pt
    out_path = MODELS_DIR / "posture_head.pt"
    torch.save({
        "labels": POSTURE_LABELS,
        "head_config": {"kind": "residual_mlp", "num_classes": len(POSTURE_LABELS), "hidden": 512, "dropout": 0.25},
        "state_dict": best_state,
        "metrics": {"best_clean_acc": float(best_clean_acc), "best_val_acc": float(overall_val_acc)}
    }, out_path)
    print(f"\n[SUCCESS] Enhanced model saved to {out_path}")

if __name__ == "__main__":
    train_finetuned()
