"""ML 检测引擎 - 加载 XGBoost + GRU 集成模型进行推理"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import MODEL_DIR, FEATURE_COLUMNS


class MLEngine:
    """ML 检测引擎

    支持按数据集源加载不同模型（nsl-kdd / unsw-nb15）。
    可选加载 GRU 模型进行集成推理。
    """

    # 数据集 → 模型文件名
    _MODEL_FILES = {
        "nsl-kdd": "xgboost_nslkdd.pkl",
        "unsw-nb15": "xgboost_unsw.pkl",
    }
    _GRU_FILES = {
        "nsl-kdd": "gru_nslkdd.pt",
        "unsw-nb15": "gru_unsw.pt",
    }
    _ENSEMBLE_FILES = {
        "nsl-kdd": "ensemble_nslkdd.pkl",
        "unsw-nb15": "ensemble_unsw.pkl",
    }

    def __init__(self, source: str = "nsl-kdd"):
        self.source = source
        self.model = None
        self.preprocessor = None
        self.category_encoder = None
        self.feature_columns = None
        self.metrics = None
        self._loaded = False
        # GRU 集成
        self.gru_model = None
        self.xgb_weight = 1.0
        self.gru_weight = 0.0

    def load(self) -> bool:
        """加载训练好的模型（XGBoost + 可选 GRU）"""
        filename = self._MODEL_FILES.get(self.source, "xgboost_nslkdd.pkl")
        model_path = MODEL_DIR / filename
        if not model_path.exists():
            print(f"[MLEngine:{self.source}] 模型文件不存在: {model_path}")
            return False

        try:
            data = joblib.load(model_path)
            self.model = data['model']
            self.preprocessor = data['preprocessor']
            self.category_encoder = data['category_encoder']
            self.feature_columns = data['feature_columns']
            self.metrics = data.get('metrics', {})
            self._loaded = True
            print(f"[MLEngine:{self.source}] XGBoost 模型加载成功，准确率: {self.metrics.get('accuracy', 'N/A')}")
        except Exception as e:
            print(f"[MLEngine:{self.source}] 模型加载失败: {e}")
            return False

        # 尝试加载 GRU 模型（可选，向后兼容）
        gru_filename = self._GRU_FILES.get(self.source)
        gru_path = MODEL_DIR / gru_filename if gru_filename else None
        if gru_path and gru_path.exists():
            try:
                from ml.gru_model import load_gru
                self.gru_model = load_gru(gru_path)
                # 加载集成权重
                ens_filename = self._ENSEMBLE_FILES.get(self.source)
                ens_path = MODEL_DIR / ens_filename if ens_filename else None
                if ens_path and ens_path.exists():
                    weights = joblib.load(ens_path)
                    self.xgb_weight = weights.get("xgb_weight", 0.5)
                    self.gru_weight = weights.get("gru_weight", 0.5)
                else:
                    self.xgb_weight = 0.5
                    self.gru_weight = 0.5
                print(f"[MLEngine:{self.source}] GRU 集成加载成功 "
                      f"(XGB={self.xgb_weight:.2f}, GRU={self.gru_weight:.2f})")
            except Exception as e:
                print(f"[MLEngine:{self.source}] GRU 加载失败，回退到纯 XGBoost: {e}")
                self.gru_model = None
                self.xgb_weight = 1.0
                self.gru_weight = 0.0
        else:
            print(f"[MLEngine:{self.source}] 未找到 GRU 模型，使用纯 XGBoost")

        return True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _ensemble_proba(self, X):
        """计算集成概率：XGBoost + GRU 加权融合"""
        xgb_proba = self.model.predict_proba(X)
        if self.gru_model is not None:
            from ml.gru_model import gru_predict_proba
            gru_proba = gru_predict_proba(self.gru_model, X)
            return self.xgb_weight * xgb_proba + self.gru_weight * gru_proba
        return xgb_proba

    def predict(self, record: dict) -> dict:
        """对单条记录进行预测"""
        if not self._loaded:
            return {'predicted': None, 'confidence': 0.0, 'probabilities': {}}

        feature_cols = self.feature_columns or FEATURE_COLUMNS
        df = pd.DataFrame([record]).reindex(columns=feature_cols, fill_value=0)

        # 使用预处理器转换
        X = self.preprocessor.transform(df)

        # 集成预测
        pred_proba = self._ensemble_proba(X)[0]
        pred_idx = int(pred_proba.argmax())
        predicted_class = self.category_encoder.inverse_transform([pred_idx])[0]
        confidence = float(pred_proba.max())

        categories = self.category_encoder.classes_
        probabilities = {cat: float(prob) for cat, prob in zip(categories, pred_proba)}

        return {
            'predicted': predicted_class,
            'confidence': confidence,
            'probabilities': probabilities,
        }

    def predict_batch(self, records: list[dict]) -> list[dict]:
        """批量预测"""
        if not self._loaded:
            return [{'predicted': None, 'confidence': 0.0, 'probabilities': {}} for _ in records]

        feature_cols = self.feature_columns or FEATURE_COLUMNS
        df = pd.DataFrame(records).reindex(columns=feature_cols, fill_value=0)
        X = self.preprocessor.transform(df)

        # 集成预测
        pred_probas = self._ensemble_proba(X)
        pred_indices = pred_probas.argmax(axis=1)

        categories = self.category_encoder.classes_
        results = []
        for idx, proba in zip(pred_indices, pred_probas):
            predicted_class = self.category_encoder.inverse_transform([int(idx)])[0]
            results.append({
                'predicted': predicted_class,
                'confidence': float(proba.max()),
                'probabilities': {cat: float(p) for cat, p in zip(categories, proba)},
            })
        return results

    def get_model_info(self) -> dict:
        """获取模型信息"""
        if not self._loaded:
            return {'loaded': False}
        return {
            'loaded': True,
            'accuracy': self.metrics.get('accuracy'),
            'feature_count': len(self.feature_columns) if self.feature_columns else 0,
            'categories': list(self.category_encoder.classes_) if self.category_encoder else [],
            'ensemble': self.gru_model is not None,
            'xgb_weight': self.xgb_weight,
            'gru_weight': self.gru_weight,
        }
