"""混合决策引擎 - 协同规则引擎和 ML 引擎的检测结果"""
import sys
import uuid
from pathlib import Path
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ML_CONFIDENCE_THRESHOLD


@dataclass
class DetectionResult:
    """检测结果"""
    record_id: int
    # 规则检测
    rule_matched: bool
    rule_matches: list = field(default_factory=list)
    rule_predicted: str | None = None
    rule_severity: str | None = None
    # ML 检测
    ml_predicted: str | None = None
    ml_confidence: float = 0.0
    ml_probabilities: dict = field(default_factory=dict)
    # 混合决策
    final_verdict: str = "Normal"
    final_source: str = "NONE"
    # 评估
    actual_label: str = "Normal"
    is_correct: bool = False


@dataclass
class Alert:
    """告警"""
    alert_id: str = ""
    record_id: int = 0
    severity: str = "LOW"
    source: str = "RULE"
    attack_category: str = ""
    rule_details: list = field(default_factory=list)
    ml_confidence: float | None = None
    description: str = ""
    connection_features: dict = field(default_factory=dict)


# 严重级别优先级
SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class HybridEngine:
    """混合决策引擎"""

    def __init__(self, rule_engine, ml_engine):
        self.rule_engine = rule_engine
        self.ml_engine = ml_engine

    def detect(self, record: dict, record_id: int = 0) -> DetectionResult:
        """对单条记录进行混合检测"""
        actual_label = record.get('attack_category', 'Normal')

        # 规则引擎检测
        rule_matches = self.rule_engine.evaluate(record)
        rule_matched = len(rule_matches) > 0
        rule_predicted = None
        rule_severity = None
        if rule_matched:
            # 取最高严重级别的规则结果
            best = max(rule_matches, key=lambda m: SEVERITY_ORDER.get(m.severity, 0))
            rule_predicted = best.predicted_category
            rule_severity = best.severity

        # ML 引擎检测
        ml_result = self.ml_engine.predict(record)
        ml_predicted = ml_result['predicted']
        ml_confidence = ml_result['confidence']
        ml_probabilities = ml_result['probabilities']

        # 混合决策
        final_verdict, final_source = self._make_decision(
            rule_matched, rule_predicted, rule_severity,
            ml_predicted, ml_confidence
        )

        is_correct = (final_verdict == actual_label)

        return DetectionResult(
            record_id=record_id,
            rule_matched=rule_matched,
            rule_matches=[
                {'rule_id': m.rule_id, 'rule_name': m.rule_name,
                 'severity': m.severity, 'predicted_category': m.predicted_category}
                for m in rule_matches
            ],
            rule_predicted=rule_predicted,
            rule_severity=rule_severity,
            ml_predicted=ml_predicted,
            ml_confidence=ml_confidence,
            ml_probabilities=ml_probabilities,
            final_verdict=final_verdict,
            final_source=final_source,
            actual_label=actual_label,
            is_correct=is_correct,
        )

    def detect_batch(self, records: list[dict], start_id: int = 0, start_ids: list[int] | None = None) -> list[DetectionResult]:
        """批量检测

        Args:
            records: 记录列表
            start_id: 兼容旧调用方式，record_id = start_id + i
            start_ids: 优先级高于 start_id，逐条指定 record_id（真实数据库主键）
        """
        # 批量 ML 预测
        ml_results = self.ml_engine.predict_batch(records)

        results = []
        for i, (record, ml_result) in enumerate(zip(records, ml_results)):
            record_id = start_ids[i] if start_ids and i < len(start_ids) else start_id + i
            actual_label = record.get('attack_category', 'Normal')

            # 规则引擎检测
            rule_matches = self.rule_engine.evaluate(record)
            rule_matched = len(rule_matches) > 0
            rule_predicted = None
            rule_severity = None
            if rule_matched:
                best = max(rule_matches, key=lambda m: SEVERITY_ORDER.get(m.severity, 0))
                rule_predicted = best.predicted_category
                rule_severity = best.severity

            ml_predicted = ml_result['predicted']
            ml_confidence = ml_result['confidence']

            final_verdict, final_source = self._make_decision(
                rule_matched, rule_predicted, rule_severity,
                ml_predicted, ml_confidence
            )

            is_correct = (final_verdict == actual_label)

            results.append(DetectionResult(
                record_id=record_id,
                rule_matched=rule_matched,
                rule_matches=[
                    {'rule_id': m.rule_id, 'rule_name': m.rule_name,
                     'severity': m.severity, 'predicted_category': m.predicted_category}
                    for m in rule_matches
                ],
                rule_predicted=rule_predicted,
                rule_severity=rule_severity,
                ml_predicted=ml_predicted,
                ml_confidence=ml_confidence,
                ml_probabilities=ml_result['probabilities'],
                final_verdict=final_verdict,
                final_source=final_source,
                actual_label=actual_label,
                is_correct=is_correct,
            ))

        return results

    def _make_decision(
        self,
        rule_matched: bool, rule_predicted: str | None, rule_severity: str | None,
        ml_predicted: str | None, ml_confidence: float,
    ) -> tuple[str, str]:
        """
        混合决策逻辑:
        - 规则+ML 一致命中 → HYBRID
        - 仅规则命中 → RULE
        - 仅ML命中 (confidence > 0.7) → ML
        - 两者不一致 → 以 ML 为主 (HYBRID)
        - 都未命中 → Normal
        """
        rule_is_attack = rule_matched and rule_predicted and rule_predicted != 'Normal'
        ml_is_attack = ml_predicted and ml_predicted != 'Normal' and ml_confidence > ML_CONFIDENCE_THRESHOLD

        if rule_is_attack and ml_is_attack:
            # 两者都检测到攻击
            return ml_predicted, "HYBRID"
        elif rule_is_attack and not ml_is_attack:
            # 仅规则命中
            return rule_predicted, "RULE"
        elif not rule_is_attack and ml_is_attack:
            # 仅 ML 命中
            return ml_predicted, "ML"
        else:
            # 都未命中
            return "Normal", "NONE"

    def generate_alerts(
        self, results: list[DetectionResult], records: list[dict]
    ) -> list[Alert]:
        """从检测结果生成告警"""
        alerts = []
        for result, record in zip(results, records):
            if result.final_verdict == "Normal":
                continue

            # 确定告警严重级别
            if result.final_source == "HYBRID":
                severity = "CRITICAL" if result.rule_severity in ("HIGH", "CRITICAL") else "HIGH"
            elif result.final_source == "RULE":
                severity = result.rule_severity or "MEDIUM"
            else:
                severity = "MEDIUM" if result.ml_confidence > 0.9 else "LOW"

            # 生成描述
            desc_parts = [f"检测到 {result.final_verdict} 攻击"]
            if result.rule_matches:
                rule_names = [m['rule_name'] for m in result.rule_matches]
                desc_parts.append(f"触发规则: {', '.join(rule_names)}")
            if result.ml_predicted and result.ml_predicted != "Normal":
                desc_parts.append(f"ML预测: {result.ml_predicted} (置信度: {result.ml_confidence:.2%})")
            description = " | ".join(desc_parts)

            # 关键特征快照
            key_features = {
                'protocol_type': record.get('protocol_type'),
                'service': record.get('service'),
                'flag': record.get('flag'),
                'src_bytes': record.get('src_bytes'),
                'dst_bytes': record.get('dst_bytes'),
                'duration': record.get('duration'),
                'count': record.get('count'),
                'serror_rate': record.get('serror_rate'),
            }

            alerts.append(Alert(
                alert_id=str(uuid.uuid4()),
                record_id=result.record_id,
                severity=severity,
                source=result.final_source,
                attack_category=result.final_verdict,
                rule_details=result.rule_matches,
                ml_confidence=result.ml_confidence,
                description=description,
                connection_features=key_features,
            ))

        return alerts
