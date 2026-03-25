"""ML 引擎测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from config import MODEL_DIR
from detection.ml_engine import MLEngine


@pytest.fixture(scope="module")
def ml_engine():
    """加载 nsl-kdd ML 引擎"""
    engine = MLEngine(source="nsl-kdd")
    engine.load()
    return engine


class TestMLEngineLoad:
    """测试模型加载"""

    def test_load_nslkdd_model(self, ml_engine):
        """NSL-KDD 模型应加载成功"""
        model_path = MODEL_DIR / "xgboost_nslkdd.pkl"
        if not model_path.exists():
            pytest.skip("模型文件不存在，跳过")
        assert ml_engine.is_loaded

    def test_model_info(self, ml_engine):
        """加载后应返回模型信息"""
        model_path = MODEL_DIR / "xgboost_nslkdd.pkl"
        if not model_path.exists():
            pytest.skip("模型文件不存在，跳过")
        info = ml_engine.get_model_info()
        assert info["loaded"] is True
        assert info["feature_count"] > 0
        assert len(info["categories"]) > 0

    def test_unloaded_engine_returns_empty(self):
        """未加载模型时应返回安全的空结果"""
        engine = MLEngine(source="nsl-kdd")
        # 不调用 load()
        result = engine.predict({"duration": 0})
        assert result["predicted"] is None
        assert result["confidence"] == 0.0

    def test_load_nonexistent_source(self):
        """不存在的模型文件应返回 False"""
        engine = MLEngine(source="nsl-kdd")
        engine._MODEL_FILES["nsl-kdd"] = "nonexistent.pkl"
        assert engine.load() is False


class TestMLEnginePredict:
    """测试预测"""

    def test_single_predict(self, ml_engine, sample_dos_record):
        """单条预测应返回完整结构"""
        if not ml_engine.is_loaded:
            pytest.skip("模型未加载")
        result = ml_engine.predict(sample_dos_record)
        assert result["predicted"] is not None
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["probabilities"], dict)
        assert len(result["probabilities"]) > 0
        # 概率总和应接近 1
        prob_sum = sum(result["probabilities"].values())
        assert abs(prob_sum - 1.0) < 0.01

    def test_batch_predict(self, ml_engine, sample_dos_record, sample_normal_record):
        """批量预测应返回与输入等长的列表"""
        if not ml_engine.is_loaded:
            pytest.skip("模型未加载")
        records = [sample_dos_record, sample_normal_record]
        results = ml_engine.predict_batch(records)
        assert len(results) == 2
        for r in results:
            assert "predicted" in r
            assert "confidence" in r
            assert "probabilities" in r

    def test_predict_with_missing_features(self, ml_engine):
        """缺少部分特征时预测不应崩溃（reindex 会用 0 填充）"""
        if not ml_engine.is_loaded:
            pytest.skip("模型未加载")
        sparse_record = {"duration": 0, "protocol_type": "tcp", "service": "http"}
        result = ml_engine.predict(sparse_record)
        assert result["predicted"] is not None
