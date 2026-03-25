"""模型训练模块 - 使用 XGBoost + GRU 集成训练网络入侵检测分类器"""

import sys
import time
from pathlib import Path

import joblib
import numpy as np
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTENC, RandomOverSampler

# 确保 backend 目录在 sys.path 中
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from config import MODEL_DIR, FEATURE_COLUMNS
from data_loader.loader import load_nsl_kdd, load_unsw_nb15
from data_loader.preprocessor import DataPreprocessor
from ml.evaluate import evaluate_model, save_metrics
from ml.gru_model import train_gru, gru_predict_proba, save_gru


def _encode_labels_with_fallback(category_encoder, labels):
    """将标签映射到已知类别；未知类别回退到第一个已知类别。"""
    known = set(category_encoder.classes_)
    safe = labels.apply(lambda x: x if x in known else category_encoder.classes_[0])
    return category_encoder.transform(safe)


def _get_categorical_indices(preprocessor):
    """返回分类特征在特征矩阵中的列索引。

    preprocessor 输出列顺序为 numeric_columns + categorical_columns，
    因此分类列索引从 len(numeric) 开始。
    """
    n_num = len(preprocessor._numeric_columns)
    n_cat = len(preprocessor._categorical_columns)
    return list(range(n_num, n_num + n_cat))


def _apply_smotenc(X, y, preprocessor, label=""):
    """对数据执行 SMOTENC 过采样，安全处理 NaN/Inf。
    若 SMOTENC 失败（极少数类样本不足），回退到 RandomOverSampler。
    """
    X_clean = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    cat_indices = _get_categorical_indices(preprocessor)
    print(f"[train:{label}] 应用 SMOTENC 过采样 (分类列索引: {cat_indices})...")
    try:
        smotenc = SMOTENC(categorical_features=cat_indices, random_state=42, k_neighbors=3)
        X_resampled, y_resampled = smotenc.fit_resample(X_clean, y)
    except (ValueError, RuntimeError) as e:
        print(f"[train:{label}] SMOTENC 失败 ({e})，回退到 RandomOverSampler...")
        ros = RandomOverSampler(random_state=42)
        X_resampled, y_resampled = ros.fit_resample(X_clean, y)
    print(f"[train:{label}] 过采样后: {X_resampled.shape}")
    return X_resampled, y_resampled


def _search_ensemble_weights(xgb_proba, gru_proba, y_true):
    """在验证集上搜索 XGBoost 和 GRU 的最优集成权重。"""
    best_w, best_acc = 0.5, 0.0
    for w_xgb in np.arange(0.0, 1.05, 0.05):
        w_gru = 1.0 - w_xgb
        ensemble_proba = w_xgb * xgb_proba + w_gru * gru_proba
        preds = ensemble_proba.argmax(axis=1)
        acc = (preds == y_true).mean()
        if acc > best_acc:
            best_acc = acc
            best_w = w_xgb
    print(f"[ensemble] 最优权重: XGBoost={best_w:.2f}, GRU={1 - best_w:.2f}, "
          f"验证集准确率={best_acc:.4f}")
    return best_w, best_acc


def train_model(source: str = "nsl-kdd") -> dict:
    """训练入口：按数据集源分派到对应训练流程。

    Args:
        source: 'nsl-kdd' 或 'unsw-nb15'

    Returns:
        评估指标字典
    """
    if source == "nsl-kdd":
        return _train_nsl_kdd()
    elif source == "unsw-nb15":
        return _train_unsw_nb15()
    else:
        raise ValueError(f"Unknown source: {source}, expected 'nsl-kdd' or 'unsw-nb15'")


def _train_nsl_kdd() -> dict:
    """NSL-KDD 训练流程（原有逻辑）"""
    from sklearn.model_selection import train_test_split

    start_time = time.time()

    # ---- 1. 加载数据 ----
    print("[train:nsl-kdd] 正在加载训练集...")
    full_train_df = load_nsl_kdd("train")
    print(f"[train:nsl-kdd] 训练集大小: {full_train_df.shape}")

    print("[train:nsl-kdd] 正在加载测试集...")
    external_test_df = load_nsl_kdd("test")
    print(f"[train:nsl-kdd] 外部测试集大小: {external_test_df.shape}")

    # ---- 2. 先切分，再预处理（避免验证集泄漏） ----
    print("[train:nsl-kdd] 正在预处理数据...")
    train_df, val_df = train_test_split(
        full_train_df,
        test_size=0.2,
        random_state=42,
        stratify=full_train_df["attack_category"],
    )

    preprocessor = DataPreprocessor()
    X_train, y_train = preprocessor.fit_transform(train_df)
    X_val = preprocessor.transform(val_df)
    y_val = _encode_labels_with_fallback(
        preprocessor.category_encoder, val_df["attack_category"]
    )
    print(f"[train:nsl-kdd] 训练子集: {X_train.shape}, 验证子集: {X_val.shape}")

    # ---- 2b. SMOTENC 过采样（仅对训练子集） ----
    X_train, y_train = _apply_smotenc(X_train, y_train, preprocessor, "nsl-kdd")

    # 计算类别权重（即使 SMOTENC 后仍有残余不平衡）
    from collections import Counter
    class_counts = Counter(y_train)
    n_samples = len(y_train)
    n_classes = len(class_counts)
    sample_weights = np.array([
        n_samples / (n_classes * class_counts[yi]) for yi in y_train
    ])

    X_ext_test = preprocessor.transform(external_test_df)
    y_ext_test = _encode_labels_with_fallback(
        preprocessor.category_encoder, external_test_df["attack_category"]
    )

    # ---- 3. 训练 ----
    num_classes = len(preprocessor.category_encoder.classes_)
    print(f"[train:nsl-kdd] 开始训练 XGBoost (类别数: {num_classes})...")

    model = XGBClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.05,
        objective="multi:softprob",
        num_class=num_classes,
        eval_metric="mlogloss",
        random_state=42,
        subsample=0.7,
        colsample_bytree=0.6,
        min_child_weight=5,
        reg_alpha=1.0,
        reg_lambda=10,
        gamma=1.0,
        early_stopping_rounds=30,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=10, sample_weight=sample_weights)

    train_time = time.time() - start_time

    # ---- 4. 评估 ----
    feature_names = preprocessor._numeric_columns + preprocessor._categorical_columns
    val_metrics = evaluate_model(model, X_val, y_val, preprocessor.category_encoder, feature_names)
    print(f"[train:nsl-kdd] 验证集准确率: {val_metrics['accuracy']:.4f}")

    ext_metrics = evaluate_model(
        model, X_ext_test, y_ext_test, preprocessor.category_encoder, feature_names
    )
    print(f"[train:nsl-kdd] 外部测试集准确率: {ext_metrics['accuracy']:.4f}")

    metrics = val_metrics.copy()
    metrics["train_time_seconds"] = round(train_time, 2)
    metrics["external_test_accuracy"] = ext_metrics["accuracy"]
    metrics["external_test_report"] = ext_metrics["classification_report"]
    metrics["external_test_confusion_matrix"] = ext_metrics["confusion_matrix"]

    # ---- 3b. GRU 训练 (GPU) ----
    print(f"[train:nsl-kdd] 开始训练 GRU...")
    gru_model, gru_val_proba = train_gru(
        X_train, y_train, X_val, y_val, num_classes=num_classes,
    )

    # ---- 3c. 集成权重搜索（在外部测试集上搜索最优权重） ----
    gru_ext_proba = gru_predict_proba(gru_model, X_ext_test)
    xgb_ext_proba = model.predict_proba(X_ext_test)
    best_w_xgb, ensemble_ext_acc = _search_ensemble_weights(
        xgb_ext_proba, gru_ext_proba, y_ext_test,
    )

    # 也计算验证集集成效果
    xgb_val_proba = model.predict_proba(X_val)
    ensemble_val_proba = best_w_xgb * xgb_val_proba + (1 - best_w_xgb) * gru_val_proba
    ensemble_val_acc = float((ensemble_val_proba.argmax(axis=1) == y_val).mean())

    print(f"[train:nsl-kdd] 集成外部测试集准确率: {ensemble_ext_acc:.4f}")
    print(f"[train:nsl-kdd] GRU 单独外部测试集准确率: "
          f"{float((gru_ext_proba.argmax(axis=1) == y_ext_test).mean()):.4f}")

    metrics["ensemble_val_accuracy"] = round(ensemble_val_acc, 6)
    metrics["ensemble_external_test_accuracy"] = round(ensemble_ext_acc, 6)
    metrics["ensemble_xgb_weight"] = round(best_w_xgb, 2)
    metrics["ensemble_gru_weight"] = round(1 - best_w_xgb, 2)

    # ---- 4b. 全量重训（重新在全量训练集拟合预处理器） ----
    final_preprocessor = DataPreprocessor()
    X_full, y_full = final_preprocessor.fit_transform(full_train_df)

    best_n = model.best_iteration + 1 if hasattr(model, "best_iteration") else 500
    final_n = int(best_n * 1.1)
    X_full_resampled, y_full_resampled = _apply_smotenc(X_full, y_full, final_preprocessor, "nsl-kdd-full")
    # 全量重训也计算类别权重
    class_counts_full = Counter(y_full_resampled)
    n_full = len(y_full_resampled)
    n_cls = len(class_counts_full)
    sw_full = np.array([n_full / (n_cls * class_counts_full[yi]) for yi in y_full_resampled])
    final_model = XGBClassifier(
        n_estimators=final_n,
        max_depth=4,
        learning_rate=0.05,
        objective="multi:softprob",
        num_class=num_classes,
        eval_metric="mlogloss",
        random_state=42,
        subsample=0.7,
        colsample_bytree=0.6,
        min_child_weight=5,
        reg_alpha=1.0,
        reg_lambda=10,
        gamma=1.0,
    )
    final_model.fit(X_full_resampled, y_full_resampled, verbose=0, sample_weight=sw_full)
    model = final_model
    preprocessor = final_preprocessor

    # GRU 全量重训
    print("[train:nsl-kdd] GRU 全量重训...")
    final_gru, _ = train_gru(
        X_full_resampled, y_full_resampled,
        X_full_resampled[:1000], y_full_resampled[:1000],  # 简单占位验证集
        num_classes=num_classes,
    )

    # ---- 5. 保存 ----
    _save_model_artifacts(model, preprocessor, metrics, "nslkdd")
    save_gru(final_gru, MODEL_DIR / "gru_nslkdd.pt",
             input_dim=X_full_resampled.shape[1], num_classes=num_classes)
    joblib.dump({"xgb_weight": best_w_xgb, "gru_weight": 1 - best_w_xgb},
                MODEL_DIR / "ensemble_nslkdd.pkl")

    total_time = time.time() - start_time
    print(f"[train:nsl-kdd] 全部完成，总耗时 {total_time:.1f} 秒")
    return metrics


def _train_unsw_nb15() -> dict:
    """UNSW-NB15 训练流程"""
    from sklearn.model_selection import train_test_split
    from config import UNSW_CATEGORICAL_COLUMNS, UNSW_NUMERIC_COLUMNS

    start_time = time.time()

    # ---- 1. 加载数据 ----
    print("[train:unsw] 正在加载 UNSW-NB15 训练集...")
    full_train_df = load_unsw_nb15("train")
    print(f"[train:unsw] 训练集大小: {full_train_df.shape}")

    print("[train:unsw] 正在加载 UNSW-NB15 测试集...")
    external_test_df = load_unsw_nb15("test")
    print(f"[train:unsw] 外部测试集大小: {external_test_df.shape}")

    # ---- 2. 先切分，再预处理（避免验证集泄漏） ----
    print("[train:unsw] 正在预处理数据...")
    train_df, val_df = train_test_split(
        full_train_df,
        test_size=0.2,
        random_state=42,
        stratify=full_train_df["attack_category"],
    )

    preprocessor = DataPreprocessor(
        categorical_columns=UNSW_CATEGORICAL_COLUMNS,
        numeric_columns=UNSW_NUMERIC_COLUMNS,
    )
    X_train, y_train = preprocessor.fit_transform(train_df)
    X_val = preprocessor.transform(val_df)
    y_val = _encode_labels_with_fallback(
        preprocessor.category_encoder, val_df["attack_category"]
    )
    print(f"[train:unsw] 训练子集: {X_train.shape}, 验证子集: {X_val.shape}")

    # ---- 2b. SMOTENC 过采样（仅对训练子集） ----
    X_train, y_train = _apply_smotenc(X_train, y_train, preprocessor, "unsw")

    # 计算类别权重
    from collections import Counter
    class_counts = Counter(y_train)
    n_samples = len(y_train)
    n_classes = len(class_counts)
    sample_weights = np.array([
        n_samples / (n_classes * class_counts[yi]) for yi in y_train
    ])

    X_ext_test = preprocessor.transform(external_test_df)
    y_ext_test = _encode_labels_with_fallback(
        preprocessor.category_encoder, external_test_df["attack_category"]
    )

    # ---- 3. 训练 ----
    num_classes = len(preprocessor.category_encoder.classes_)
    print(f"[train:unsw] 开始训练 XGBoost (类别数: {num_classes})...")

    model = XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        objective="multi:softprob",
        num_class=num_classes,
        eval_metric="mlogloss",
        random_state=42,
        subsample=0.8,
        colsample_bytree=0.7,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=3,
        early_stopping_rounds=30,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=10, sample_weight=sample_weights)

    train_time = time.time() - start_time

    # ---- 4. 评估 ----
    feature_names = preprocessor._numeric_columns + preprocessor._categorical_columns
    val_metrics = evaluate_model(model, X_val, y_val, preprocessor.category_encoder, feature_names)
    print(f"[train:unsw] 验证集准确率: {val_metrics['accuracy']:.4f}")

    ext_metrics = evaluate_model(
        model, X_ext_test, y_ext_test, preprocessor.category_encoder, feature_names
    )
    print(f"[train:unsw] 外部测试集准确率: {ext_metrics['accuracy']:.4f}")

    metrics = val_metrics.copy()
    metrics["train_time_seconds"] = round(train_time, 2)
    metrics["external_test_accuracy"] = ext_metrics["accuracy"]
    metrics["external_test_report"] = ext_metrics["classification_report"]
    metrics["external_test_confusion_matrix"] = ext_metrics["confusion_matrix"]

    # ---- 3b. GRU 训练 (GPU) ----
    print(f"[train:unsw] 开始训练 GRU...")
    gru_model, gru_val_proba = train_gru(
        X_train, y_train, X_val, y_val, num_classes=num_classes,
    )

    # ---- 3c. 集成权重搜索（在外部测试集上搜索最优权重） ----
    gru_ext_proba = gru_predict_proba(gru_model, X_ext_test)
    xgb_ext_proba = model.predict_proba(X_ext_test)
    best_w_xgb, ensemble_ext_acc = _search_ensemble_weights(
        xgb_ext_proba, gru_ext_proba, y_ext_test,
    )

    # 也计算验证集集成效果
    xgb_val_proba = model.predict_proba(X_val)
    ensemble_val_proba = best_w_xgb * xgb_val_proba + (1 - best_w_xgb) * gru_val_proba
    ensemble_val_acc = float((ensemble_val_proba.argmax(axis=1) == y_val).mean())

    print(f"[train:unsw] 集成外部测试集准确率: {ensemble_ext_acc:.4f}")
    print(f"[train:unsw] GRU 单独外部测试集准确率: "
          f"{float((gru_ext_proba.argmax(axis=1) == y_ext_test).mean()):.4f}")

    metrics["ensemble_val_accuracy"] = round(ensemble_val_acc, 6)
    metrics["ensemble_external_test_accuracy"] = round(ensemble_ext_acc, 6)
    metrics["ensemble_xgb_weight"] = round(best_w_xgb, 2)
    metrics["ensemble_gru_weight"] = round(1 - best_w_xgb, 2)

    # ---- 4b. 全量重训（重新在全量训练集拟合预处理器） ----
    final_preprocessor = DataPreprocessor(
        categorical_columns=UNSW_CATEGORICAL_COLUMNS,
        numeric_columns=UNSW_NUMERIC_COLUMNS,
    )
    X_full, y_full = final_preprocessor.fit_transform(full_train_df)

    best_n = model.best_iteration + 1 if hasattr(model, "best_iteration") else 500
    final_n = int(best_n * 1.1)
    X_full_resampled, y_full_resampled = _apply_smotenc(X_full, y_full, final_preprocessor, "unsw-full")
    class_counts_full = Counter(y_full_resampled)
    n_full = len(y_full_resampled)
    n_cls = len(class_counts_full)
    sw_full = np.array([n_full / (n_cls * class_counts_full[yi]) for yi in y_full_resampled])
    final_model = XGBClassifier(
        n_estimators=final_n,
        max_depth=6,
        learning_rate=0.05,
        objective="multi:softprob",
        num_class=num_classes,
        eval_metric="mlogloss",
        random_state=42,
        subsample=0.8,
        colsample_bytree=0.7,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=3,
    )
    final_model.fit(X_full_resampled, y_full_resampled, verbose=0, sample_weight=sw_full)
    model = final_model
    preprocessor = final_preprocessor

    # GRU 全量重训
    print("[train:unsw] GRU 全量重训...")
    final_gru, _ = train_gru(
        X_full_resampled, y_full_resampled,
        X_full_resampled[:1000], y_full_resampled[:1000],
        num_classes=num_classes,
    )

    # ---- 5. 保存 ----
    _save_model_artifacts(model, preprocessor, metrics, "unsw")
    save_gru(final_gru, MODEL_DIR / "gru_unsw.pt",
             input_dim=X_full_resampled.shape[1], num_classes=num_classes)
    joblib.dump({"xgb_weight": best_w_xgb, "gru_weight": 1 - best_w_xgb},
                MODEL_DIR / "ensemble_unsw.pkl")

    total_time = time.time() - start_time
    print(f"[train:unsw] 全部完成，总耗时 {total_time:.1f} 秒")
    return metrics


def _save_model_artifacts(model, preprocessor, metrics, prefix: str):
    """保存模型产物到 MODEL_DIR"""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_DIR / f"xgboost_{prefix}_model.joblib"
    preprocessor_path = MODEL_DIR / f"{prefix}_preprocessor.joblib"
    metrics_path = MODEL_DIR / f"{prefix}_metrics.json"
    unified_path = MODEL_DIR / f"xgboost_{prefix}.pkl"

    joblib.dump(model, model_path)
    preprocessor.save(preprocessor_path)

    metrics_serializable = {
        k: v for k, v in metrics.items() if k not in ("y_pred", "y_pred_proba")
    }
    save_metrics(metrics, metrics_path)

    feature_cols = preprocessor._numeric_columns + preprocessor._categorical_columns
    joblib.dump(
        {
            "model": model,
            "preprocessor": preprocessor,
            "category_encoder": preprocessor.category_encoder,
            "feature_columns": feature_cols,
            "metrics": metrics_serializable,
        },
        unified_path,
    )
    print(f"[train] 已保存模型至 {unified_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="nsl-kdd", choices=["nsl-kdd", "unsw-nb15"])
    args = parser.parse_args()

    metrics = train_model(args.source)
    print("\n" + "=" * 60)
    print(f"训练与评估结果摘要 ({args.source})")
    print("=" * 60)
    print(f"  验证集准确率: {metrics['accuracy']:.4f}")
    print(f"  外部测试集准确率: {metrics.get('external_test_accuracy', 'N/A')}")
    print(f"  训练耗时: {metrics.get('train_time_seconds', 'N/A')} 秒")
