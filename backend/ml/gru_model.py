"""GRU 深度学习模型 - 与 XGBoost 集成用于网络入侵检测"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


class GRUClassifier(nn.Module):
    """GRU 分类器：将表格特征视为长度=1 的序列输入 GRU。"""

    def __init__(self, input_dim, hidden_dim=128, num_layers=2,
                 num_classes=5, dropout=0.3):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.gru = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.classifier = nn.Sequential(
            nn.BatchNorm1d(hidden_dim),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(hidden_dim // 2, num_classes),
        )

    def forward(self, x):
        # x: (batch, features) → (batch, 1, features)
        if x.dim() == 2:
            x = x.unsqueeze(1)
        _, h_n = self.gru(x)          # h_n: (num_layers, batch, hidden)
        out = h_n[-1]                  # 取最后一层隐藏状态
        return self.classifier(out)


def _get_device():
    """自动检测可用设备"""
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _compute_class_weights(y, num_classes):
    """计算类别权重用于 CrossEntropyLoss"""
    counts = np.bincount(y.astype(int), minlength=num_classes).astype(float)
    counts[counts == 0] = 1.0
    weights = len(y) / (num_classes * counts)
    return torch.FloatTensor(weights)


def train_gru(X_train, y_train, X_val, y_val, num_classes,
              device=None, epochs=100, batch_size=512, lr=1e-3,
              patience=15, hidden_dim=128, num_layers=2):
    """训练 GRU 模型。

    Returns:
        (model, val_proba): 训练好的模型和验证集概率矩阵
    """
    if device is None:
        device = _get_device()
    print(f"[GRU] 使用设备: {device}")

    input_dim = X_train.shape[1]

    # 转 Tensor
    X_train_t = torch.FloatTensor(np.nan_to_num(X_train, nan=0.0)).to(device)
    y_train_t = torch.LongTensor(y_train.astype(int)).to(device)
    X_val_t = torch.FloatTensor(np.nan_to_num(X_val, nan=0.0)).to(device)
    y_val_t = torch.LongTensor(y_val.astype(int)).to(device)

    train_ds = TensorDataset(X_train_t, y_train_t)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

    # 模型
    model = GRUClassifier(
        input_dim=input_dim, hidden_dim=hidden_dim,
        num_layers=num_layers, num_classes=num_classes,
    ).to(device)

    # 类别加权 Loss
    class_weights = _compute_class_weights(y_train, num_classes).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6,
    )

    # 训练循环
    best_val_loss = float("inf")
    best_state = None
    wait = 0

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_loss += loss.item() * len(xb)
        train_loss /= len(train_ds)

        # 验证
        model.eval()
        with torch.no_grad():
            val_logits = model(X_val_t)
            val_loss = criterion(val_logits, y_val_t).item()
            val_preds = val_logits.argmax(dim=1)
            val_acc = (val_preds == y_val_t).float().mean().item()

        scheduler.step(val_loss)
        current_lr = optimizer.param_groups[0]["lr"]

        if epoch % 10 == 0 or epoch == 1:
            print(f"[GRU] Epoch {epoch:3d}: "
                  f"train_loss={train_loss:.4f} val_loss={val_loss:.4f} "
                  f"val_acc={val_acc:.4f} lr={current_lr:.2e}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                print(f"[GRU] 早停于 Epoch {epoch} (patience={patience})")
                break

    # 加载最优权重
    model.load_state_dict(best_state)
    model.to(device)

    # 计算验证集概率
    val_proba = gru_predict_proba(model, X_val, device=device, batch_size=batch_size)
    final_acc = (val_proba.argmax(axis=1) == y_val.astype(int)).mean()
    print(f"[GRU] 最终验证集准确率: {final_acc:.4f}")

    return model, val_proba


def gru_predict_proba(model, X, device=None, batch_size=1024):
    """批量推理，返回概率矩阵 (n_samples, n_classes)"""
    if device is None:
        device = _get_device()

    model.eval()
    X_t = torch.FloatTensor(np.nan_to_num(X, nan=0.0))

    all_proba = []
    for i in range(0, len(X_t), batch_size):
        batch = X_t[i:i + batch_size].to(device)
        with torch.no_grad():
            logits = model(batch)
            proba = torch.softmax(logits, dim=1)
        all_proba.append(proba.cpu().numpy())

    return np.concatenate(all_proba, axis=0)


def save_gru(model, path, input_dim, num_classes, hidden_dim=128, num_layers=2):
    """保存 GRU 模型：state_dict + 架构参数"""
    torch.save({
        "state_dict": model.cpu().state_dict(),
        "input_dim": input_dim,
        "num_classes": num_classes,
        "hidden_dim": hidden_dim,
        "num_layers": num_layers,
    }, path)
    print(f"[GRU] 模型已保存至 {path}")


def load_gru(path, device=None):
    """加载 GRU 模型"""
    if device is None:
        device = _get_device()

    data = torch.load(path, map_location=device, weights_only=False)
    model = GRUClassifier(
        input_dim=data["input_dim"],
        hidden_dim=data["hidden_dim"],
        num_layers=data["num_layers"],
        num_classes=data["num_classes"],
    ).to(device)
    model.load_state_dict(data["state_dict"])
    model.eval()
    print(f"[GRU] 模型已从 {path} 加载 (device={device})")
    return model
