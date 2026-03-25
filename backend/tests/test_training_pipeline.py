"""训练流程关键回归测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from ml import train as train_module


def _build_train_df(size: int, attack_a: str, attack_b: str) -> pd.DataFrame:
    rows = []
    half = size // 2
    for i in range(size):
        label = attack_a if i < half else attack_b
        rows.append(
            {
                "duration": i,
                "protocol_type": "tcp" if i % 2 == 0 else "udp",
                "service": "http",
                "flag": "SF",
                "src_bytes": 10 + i,
                "dst_bytes": 20 + i,
                "attack_category": label,
                "label": label.lower(),
                "difficulty": 1,
            }
        )
    return pd.DataFrame(rows)


class _FakeXGBClassifier:
    def __init__(self, *args, **kwargs):
        self.best_iteration = 1

    def fit(self, X, y, eval_set=None, verbose=None, sample_weight=None):
        self._n_classes = len(set(y))
        return self

    def predict_proba(self, X):
        n = X.shape[0] if hasattr(X, 'shape') else len(X)
        nc = getattr(self, '_n_classes', 2)
        proba = np.ones((n, nc)) / nc
        return proba


def _fake_train_gru(*args, **kwargs):
    """Mock GRU 训练：返回 None 模型和均匀概率"""
    X_val = args[2] if len(args) > 2 else kwargs.get('X_val')
    num_classes = kwargs.get('num_classes', 2)
    n = X_val.shape[0] if hasattr(X_val, 'shape') else len(X_val)
    return None, np.ones((n, num_classes)) / num_classes


def _mock_gru_patches(monkeypatch):
    """应用所有 GRU 相关的 mock"""
    monkeypatch.setattr(train_module, "train_gru", _fake_train_gru)
    monkeypatch.setattr(
        train_module, "gru_predict_proba",
        lambda model, X, **kw: np.ones((X.shape[0], 2)) / 2,
    )
    monkeypatch.setattr(train_module, "save_gru", lambda *a, **kw: None)
    monkeypatch.setattr(
        train_module, "_search_ensemble_weights",
        lambda xgb_p, gru_p, y: (0.5, 1.0),
    )


def test_nsl_training_fits_preprocessor_after_split(monkeypatch):
    """NSL 训练应先切分，再在训练子集上拟合预处理器。"""
    fit_sizes = []

    class _SpyPreprocessor:
        def __init__(self, *args, **kwargs):
            from sklearn.preprocessing import LabelEncoder

            self.category_encoder = LabelEncoder()
            self._numeric_columns = ["duration", "src_bytes"]
            self._categorical_columns = ["protocol_type"]

        def fit_transform(self, df):
            fit_sizes.append(len(df))
            y = self.category_encoder.fit_transform(df["attack_category"])
            return np.zeros((len(df), 3)), y

        def transform(self, df):
            return np.zeros((len(df), 3))

        def save(self, path):
            return None

    full_train_df = _build_train_df(10, "Normal", "DoS")
    ext_test_df = _build_train_df(6, "Normal", "DoS")

    monkeypatch.setattr(
        train_module,
        "load_nsl_kdd",
        lambda dataset: full_train_df if dataset == "train" else ext_test_df,
    )
    monkeypatch.setattr(train_module, "DataPreprocessor", _SpyPreprocessor)
    monkeypatch.setattr(train_module, "XGBClassifier", _FakeXGBClassifier)
    monkeypatch.setattr(
        train_module,
        "evaluate_model",
        lambda *args, **kwargs: {
            "accuracy": 1.0,
            "classification_report": {},
            "confusion_matrix": [],
        },
    )
    monkeypatch.setattr(
        train_module, "_save_model_artifacts", lambda *args, **kwargs: None
    )
    _mock_gru_patches(monkeypatch)
    monkeypatch.setattr(train_module, "joblib", type("FakeJoblib", (), {"dump": staticmethod(lambda *a, **kw: None)})())

    train_module._train_nsl_kdd()

    assert fit_sizes
    assert fit_sizes[0] < len(full_train_df)


def test_unsw_training_fits_preprocessor_after_split(monkeypatch):
    """UNSW 训练应先切分，再在训练子集上拟合预处理器。"""
    fit_sizes = []

    class _SpyPreprocessor:
        def __init__(self, *args, **kwargs):
            from sklearn.preprocessing import LabelEncoder

            self.category_encoder = LabelEncoder()
            self._numeric_columns = ["duration", "src_bytes"]
            self._categorical_columns = ["protocol_type"]

        def fit_transform(self, df):
            fit_sizes.append(len(df))
            y = self.category_encoder.fit_transform(df["attack_category"])
            return np.zeros((len(df), 3)), y

        def transform(self, df):
            return np.zeros((len(df), 3))

        def save(self, path):
            return None

    full_train_df = _build_train_df(10, "Normal", "Exploits")
    ext_test_df = _build_train_df(6, "Normal", "Exploits")

    monkeypatch.setattr(
        train_module,
        "load_unsw_nb15",
        lambda dataset: full_train_df if dataset == "train" else ext_test_df,
    )
    monkeypatch.setattr(train_module, "DataPreprocessor", _SpyPreprocessor)
    monkeypatch.setattr(train_module, "XGBClassifier", _FakeXGBClassifier)
    monkeypatch.setattr(
        train_module,
        "evaluate_model",
        lambda *args, **kwargs: {
            "accuracy": 1.0,
            "classification_report": {},
            "confusion_matrix": [],
        },
    )
    monkeypatch.setattr(
        train_module, "_save_model_artifacts", lambda *args, **kwargs: None
    )
    _mock_gru_patches(monkeypatch)
    monkeypatch.setattr(train_module, "joblib", type("FakeJoblib", (), {"dump": staticmethod(lambda *a, **kw: None)})())

    train_module._train_unsw_nb15()

    assert fit_sizes
    assert fit_sizes[0] < len(full_train_df)
