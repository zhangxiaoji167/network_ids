"""数据预处理模块 - 编码与缩放（支持多数据集）"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import LabelEncoder, StandardScaler
from config import CATEGORICAL_COLUMNS, NUMERIC_COLUMNS

logger = logging.getLogger(__name__)


class DataPreprocessor:
    """数据预处理器：分类编码 + 数值缩放

    支持通过构造参数指定不同数据集的列名。
    """

    def __init__(self,
                 categorical_columns: list[str] | None = None,
                 numeric_columns: list[str] | None = None):
        self._categorical_columns = categorical_columns or CATEGORICAL_COLUMNS
        self._numeric_columns = numeric_columns or NUMERIC_COLUMNS
        self.label_encoders: dict[str, LabelEncoder] = {}
        self.scaler: StandardScaler = StandardScaler()
        self.category_encoder: LabelEncoder = LabelEncoder()
        self._is_fitted: bool = False

    def __setstate__(self, state):
        """反序列化兼容：旧版 pkl 可能缺少 _categorical_columns/_numeric_columns"""
        self.__dict__.update(state)
        if '_categorical_columns' not in state:
            self._categorical_columns = CATEGORICAL_COLUMNS
        if '_numeric_columns' not in state:
            self._numeric_columns = NUMERIC_COLUMNS

    def fit_transform(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """拟合并转换数据"""
        df_processed = df.copy()

        for col in self._categorical_columns:
            le = LabelEncoder()
            df_processed[col] = le.fit_transform(df_processed[col].astype(str))
            self.label_encoders[col] = le

        df_processed[self._numeric_columns] = self.scaler.fit_transform(
            df_processed[self._numeric_columns].astype(float)
        )

        y = self.category_encoder.fit_transform(df_processed['attack_category'])

        feature_cols = self._numeric_columns + self._categorical_columns
        X = df_processed[feature_cols].values.astype(float)

        self._is_fitted = True
        return X, y

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """使用已拟合的编码器转换数据"""
        if not self._is_fitted:
            raise RuntimeError("预处理器尚未拟合，请先调用 fit_transform()")

        df_processed = df.copy()

        for col in self._categorical_columns:
            le = self.label_encoders[col]
            known = set(le.classes_)
            unknown_mask = ~df_processed[col].astype(str).isin(known)
            n_unknown = unknown_mask.sum()
            if n_unknown > 0:
                logger.warning(
                    f"特征 '{col}' 中有 {n_unknown} 个未知类别值，"
                    f"将映射为 '{le.classes_[0]}'"
                )
            df_processed[col] = df_processed[col].astype(str).apply(
                lambda x: x if x in known else le.classes_[0]
            )
            df_processed[col] = le.transform(df_processed[col])

        df_processed[self._numeric_columns] = self.scaler.transform(
            df_processed[self._numeric_columns].astype(float)
        )

        feature_cols = self._numeric_columns + self._categorical_columns
        return df_processed[feature_cols].values.astype(float)

    def save(self, path: Path) -> None:
        """保存预处理器到文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            'label_encoders': self.label_encoders,
            'scaler': self.scaler,
            'category_encoder': self.category_encoder,
            'categorical_columns': self._categorical_columns,
            'numeric_columns': self._numeric_columns,
        }, path)

    def load(self, path: Path) -> None:
        """从文件加载预处理器"""
        path = Path(path)
        data = joblib.load(path)
        self.label_encoders = data['label_encoders']
        self.scaler = data['scaler']
        self.category_encoder = data['category_encoder']
        self._categorical_columns = data.get('categorical_columns', CATEGORICAL_COLUMNS)
        self._numeric_columns = data.get('numeric_columns', NUMERIC_COLUMNS)
        self._is_fitted = True
