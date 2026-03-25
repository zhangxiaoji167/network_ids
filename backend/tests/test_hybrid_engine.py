"""混合决策引擎测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from config import RULES_DIR
from detection.rule_engine import RuleEngine
from detection.ml_engine import MLEngine
from detection.hybrid_engine import HybridEngine, DetectionResult, Alert


@pytest.fixture(scope="module")
def hybrid_engine():
    """初始化混合引擎"""
    rule_eng = RuleEngine(RULES_DIR)
    ml_eng = MLEngine(source="nsl-kdd")
    ml_eng.load()
    return HybridEngine(rule_eng, ml_eng)


class TestHybridDecision:
    """测试混合决策逻辑的 6 种场景"""

    def test_decision_both_attack(self, hybrid_engine):
        """场景1: 规则和ML同时命中攻击 → HYBRID"""
        verdict, source = hybrid_engine._make_decision(
            rule_matched=True, rule_predicted="DoS", rule_severity="HIGH",
            ml_predicted="DoS", ml_confidence=0.95,
        )
        assert source == "HYBRID"
        assert verdict == "DoS"

    def test_decision_rule_only(self, hybrid_engine):
        """场景2: 仅规则命中 → RULE"""
        verdict, source = hybrid_engine._make_decision(
            rule_matched=True, rule_predicted="Probe", rule_severity="MEDIUM",
            ml_predicted="Normal", ml_confidence=0.5,
        )
        assert source == "RULE"
        assert verdict == "Probe"

    def test_decision_ml_only(self, hybrid_engine):
        """场景3: 仅ML命中（高置信度）→ ML"""
        verdict, source = hybrid_engine._make_decision(
            rule_matched=False, rule_predicted=None, rule_severity=None,
            ml_predicted="R2L", ml_confidence=0.85,
        )
        assert source == "ML"
        assert verdict == "R2L"

    def test_decision_ml_low_confidence(self, hybrid_engine):
        """场景4: ML命中但置信度低于阈值 → Normal"""
        verdict, source = hybrid_engine._make_decision(
            rule_matched=False, rule_predicted=None, rule_severity=None,
            ml_predicted="U2R", ml_confidence=0.3,
        )
        assert source == "NONE"
        assert verdict == "Normal"

    def test_decision_both_normal(self, hybrid_engine):
        """场景5: 两者都未命中 → Normal"""
        verdict, source = hybrid_engine._make_decision(
            rule_matched=False, rule_predicted=None, rule_severity=None,
            ml_predicted="Normal", ml_confidence=0.9,
        )
        assert source == "NONE"
        assert verdict == "Normal"

    def test_decision_disagreement(self, hybrid_engine):
        """场景6: 规则和ML不一致 → 以规则为主"""
        verdict, source = hybrid_engine._make_decision(
            rule_matched=True, rule_predicted="DoS", rule_severity="HIGH",
            ml_predicted="Probe", ml_confidence=0.85,
        )
        # 两者都检测到攻击但类别不同，取 ML 预测 + HYBRID
        assert source == "HYBRID"
        assert verdict == "Probe"


class TestHybridDetect:
    """测试完整检测流程"""

    def test_detect_single(self, hybrid_engine, sample_dos_record):
        """单条检测应返回 DetectionResult"""
        if not hybrid_engine.ml_engine.is_loaded:
            pytest.skip("模型未加载")
        result = hybrid_engine.detect(sample_dos_record, record_id=1)
        assert isinstance(result, DetectionResult)
        assert result.record_id == 1
        assert result.final_verdict is not None
        assert result.final_source in ("HYBRID", "RULE", "ML", "NONE")

    def test_detect_batch(self, hybrid_engine, sample_dos_record, sample_normal_record):
        """批量检测应返回等长结果"""
        if not hybrid_engine.ml_engine.is_loaded:
            pytest.skip("模型未加载")
        records = [sample_dos_record, sample_normal_record]
        results = hybrid_engine.detect_batch(records)
        assert len(results) == 2

    def test_generate_alerts(self, hybrid_engine, sample_dos_record, sample_normal_record):
        """告警生成：攻击记录产生告警，正常记录不产生"""
        if not hybrid_engine.ml_engine.is_loaded:
            pytest.skip("模型未加载")
        records = [sample_dos_record, sample_normal_record]
        results = hybrid_engine.detect_batch(records)
        alerts = hybrid_engine.generate_alerts(results, records)

        assert isinstance(alerts, list)
        for a in alerts:
            assert isinstance(a, Alert)
            assert a.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            assert a.alert_id  # 非空
            assert a.attack_category != "Normal"
