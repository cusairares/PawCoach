"""Train classification head on extracted MobileNetV3 embeddings.
Evaluates accuracy, generates confusion matrix, and saves posture_head.pt
"""
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from pathlib import Path

from src.posture import build_head, EMBED_DIM
from src.config import POSTURE_LABELS, DATA_DIR, MODELS_DIR

def train():
    processed_dir = DATA_DIR / "processed"
    X = np.load(processed_dir / "embeddings_X.npy")
    Y = np.load(processed_dir / "embeddings_Y.npy")

    print(f"Loaded embeddings: X={X.shape}, Y={Y.shape}")
    X_train, X_val, y_train, y_val = train_test_split(X, Y, test_size=0.2, random_state=42, stratify=Y)

    train_ds = TensorDataset(torch.from_numpy(X_train).float(), torch.from_numpy(y_train).long())
    val_ds = TensorDataset(torch.from_numpy(X_val).float(), torch.from_numpy(y_val).long())

    train_loader = DataLoader(train_ds, batch_size=128, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    head = build_head(kind="mlp", num_classes=len(POSTURE_LABELS), hidden=256, dropout=0.3).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=25)

    print("\nTraining Posture Head...")
    best_val_acc = 0.0
    best_state = None

    for epoch in range(1, 26):
        head.train()
        total_loss, correct, total = 0.0, 0, 0
        for bx, by in train_loader:
            bx, by = bx.to(device), by.to(device)
            optimizer.zero_grad()
            logits = head(bx)
            loss = criterion(logits, by)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(by)
            preds = logits.argmax(dim=1)
            correct += (preds == by).sum().item()
            total += len(by)

        scheduler.step()
        train_acc = correct / total

        # Validation
        head.eval()
        val_correct, val_total = 0, 0
        with torch.no_grad():
            for bx, by in val_loader:
                bx, by = bx.to(device), by.to(device)
                logits = head(bx)
                val_correct += (logits.argmax(dim=1) == by).sum().item()
                val_total += len(by)

        val_acc = val_correct / val_total
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in head.state_dict().items()}

        if epoch % 5 == 0 or epoch == 25:
            print(f"Epoch {epoch:02d}/25 | Train Loss: {total_loss/total:.4f} | Train Acc: {train_acc*100:.1f}% | Val Acc: {val_acc*100:.1f}%")

    print(f"\nBest Validation Accuracy: {best_val_acc*100:.2f}%")

    # Final Evaluation & Confusion Matrix
    head.load_state_dict(best_state)
    head.eval()
    all_preds, all_targets = [], []
    with torch.no_grad():
        for bx, by in val_loader:
            bx = bx.to(device)
            preds = head(bx).argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_targets.extend(by.numpy())

    print("\nClassification Report:")
    print(classification_report(all_targets, all_preds, target_names=POSTURE_LABELS))
    print("Confusion Matrix:")
    print(confusion_matrix(all_targets, all_preds))

    # Save checkpoint
    out_path = MODELS_DIR / "posture_head.pt"
    torch.save({
        "labels": POSTURE_LABELS,
        "head_config": {"kind": "mlp", "num_classes": len(POSTURE_LABELS), "hidden": 256, "dropout": 0.3},
        "state_dict": best_state,
        "metrics": {"best_val_acc": float(best_val_acc)}
    }, out_path)
    print(f"\nModel checkpoint saved to {out_path}")

if __name__ == "__main__":
    train()
