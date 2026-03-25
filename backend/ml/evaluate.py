"""模型评估模块 - 计算分类指标、混淆矩阵、ROC曲线数据"""

import sys
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_curve,
    auc,
)
from sklearn.preprocessing import label_binarize

# 确保 backend 目录在 sys.path 中
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from config import FEATURE_COLUMNS, ATTACK_CATEGORIES


def evaluate_model(
    model: Any,
    X_test: np.ndarray,
    y_test: np.ndarray,
    category_encoder: Any,
    feature_names: list[str] | None = None,
) -> dict:
    """对模型进行全面评估，返回各项指标。

    Parameters
    ----------
    model : trained XGBClassifier
        已训练的 XGBoost 分类器。
    X_test : np.ndarray
        测试集特征矩阵。
    y_test : np.ndarray
        测试集编码后的标签（整数）。
    category_encoder : LabelEncoder
        攻击类别的 LabelEncoder，用于还原类别名。
    feature_names : list[str] | None
        特征列名列表。若为 None 则 fallback 到 FEATURE_COLUMNS。

    Returns
    -------
    dict
        包含 accuracy、classification_report、confusion_matrix、
        feature_importance、roc_data、y_pred、y_pred_proba 的字典。
    """
    # 预测
    y_pred: np.ndarray = model.predict(X_test)
    y_pred_proba: np.ndarray = model.predict_proba(X_test)

    # 类别名称
    class_names: list[str] = list(category_encoder.classes_)
    num_classes: int = len(class_names)

    # ---- 基础指标 ----
    acc: float = float(accuracy_score(y_test, y_pred))

    report: dict = classification_report(
        y_test, y_pred,
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )

    cm: list[list[int]] = confusion_matrix(y_test, y_pred).tolist()

    # ---- 特征重要性 (Top 15) ----
    importances = model.feature_importances_
    _names = feature_names or FEATURE_COLUMNS
    if len(importances) <= len(_names):
        feat_names = _names[: len(importances)]
    else:
        feat_names = [
            _names[i] if i < len(_names) else f"feature_{i}"
            for i in range(len(importances))
        ]

    feat_imp_pairs = sorted(
        zip(feat_names, importances.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )
    feature_importance: dict[str, float] = {
        name: round(value, 6) for name, value in feat_imp_pairs[:15]
    }

    # ---- ROC 曲线数据 (One-vs-Rest) ----
    y_test_bin = label_binarize(y_test, classes=list(range(num_classes)))
    # 当只有 2 个类别时 label_binarize 返回 (n, 1)，需要特殊处理
    if y_test_bin.shape[1] == 1:
        y_test_bin = np.hstack([1 - y_test_bin, y_test_bin])

    roc_data: dict[str, dict[str, list[float]]] = {}
    for i, cls_name in enumerate(class_names):
        fpr, tpr, _ = roc_curve(y_test_bin[:, i], y_pred_proba[:, i])
        roc_auc = float(auc(fpr, tpr))
        roc_data[cls_name] = {
            "fpr": [round(float(v), 6) for v in fpr],
            "tpr": [round(float(v), 6) for v in tpr],
            "auc": round(roc_auc, 6),
        }

    return {
        "accuracy": round(acc, 6),
        "classification_report": report,
        "confusion_matrix": cm,
        "feature_importance": feature_importance,
        "roc_data": roc_data,
        "y_pred": y_pred,
        "y_pred_proba": y_pred_proba,
    }


class _NumpyEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 numpy 类型。"""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def save_metrics(metrics: dict, path: Path) -> None:
    """将评估指标保存为 JSON 文件。

    Parameters
    ----------
    metrics : dict
        evaluate_model 返回的指标字典。
    path : Path
        JSON 文件保存路径。
    """
    # 过滤掉不可序列化的 ndarray 字段
    serializable = {
        k: v for k, v in metrics.items()
        if k not in ("y_pred", "y_pred_proba")
    }

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, cls=_NumpyEncoder, indent=2, ensure_ascii=False)

    print(f"[evaluate] 指标已保存至 {path}")


def load_metrics(path: Path) -> dict:
    """从 JSON 文件加载评估指标。

    Parameters
    ----------
    path : Path
        JSON 文件路径。

    Returns
    -------
    dict
        评估指标字典。
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
