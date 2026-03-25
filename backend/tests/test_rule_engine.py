"""规则引擎测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from config import RULES_DIR
from detection.rule_engine import RuleEngine, RuleMatch


class TestRuleEngineLoad:
    """测试规则加载"""

    def test_load_rules_from_directory(self, rule_engine):
        """规则引擎应从 YAML 文件加载规则"""
        assert len(rule_engine.rules) > 0

    def test_rules_have_required_fields(self, rule_engine):
        """每条规则应包含必要字段"""
        for rule in rule_engine.rules:
            assert rule.id, "规则必须有 id"
            assert rule.name, "规则必须有 name"
            assert rule.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            assert rule.attack_category, "规则必须有 attack_category"
            assert isinstance(rule.conditions, dict) and len(rule.conditions) > 0

    def test_load_from_nonexistent_dir(self):
        """不存在的规则目录应产生空规则列表"""
        engine = RuleEngine(Path("/nonexistent/dir"))
        assert len(engine.rules) == 0

    def test_get_rules_info(self, rule_engine):
        """get_rules_info 应返回所有规则信息"""
        info = rule_engine.get_rules_info()
        assert len(info) == len(rule_engine.rules)
        for item in info:
            assert "id" in item
            assert "name" in item
            assert "severity" in item


class TestRuleEngineEvaluate:
    """测试规则匹配"""

    def test_dos_record_triggers_rule(self, rule_engine, sample_dos_record):
        """DoS 特征记录应触发至少一条规则"""
        matches = rule_engine.evaluate(sample_dos_record)
        assert len(matches) > 0
        assert all(isinstance(m, RuleMatch) for m in matches)

    def test_normal_record_may_not_trigger(self, rule_engine, sample_normal_record):
        """正常记录可能不触发任何规则（或触发少量低级别规则）"""
        matches = rule_engine.evaluate(sample_normal_record)
        # 正常流量不应触发高危规则
        high_severity = [m for m in matches if m.severity in ("HIGH", "CRITICAL")]
        assert len(high_severity) == 0

    def test_batch_evaluate(self, rule_engine, sample_dos_record, sample_normal_record):
        """批量评估应逐条返回结果"""
        results = rule_engine.evaluate_batch([sample_dos_record, sample_normal_record])
        assert len(results) == 2
        assert isinstance(results[0], list)
        assert isinstance(results[1], list)

    def test_condition_operators(self, rule_engine):
        """测试各种条件运算符"""
        # 大于运算符
        assert rule_engine._check_conditions({"count": 600}, {"count": {">": 500}})
        assert not rule_engine._check_conditions({"count": 400}, {"count": {">": 500}})

        # 小于运算符
        assert rule_engine._check_conditions({"duration": 0}, {"duration": {"<": 1}})

        # 等值匹配
        assert rule_engine._check_conditions({"flag": "S0"}, {"flag": "S0"})
        assert not rule_engine._check_conditions({"flag": "SF"}, {"flag": "S0"})

        # 列表匹配
        assert rule_engine._check_conditions({"service": "http"}, {"service": ["http", "ftp"]})
        assert not rule_engine._check_conditions({"service": "smtp"}, {"service": ["http", "ftp"]})

    def test_missing_field_returns_false(self, rule_engine):
        """缺少字段时条件不匹配"""
        assert not rule_engine._check_conditions({}, {"count": {">": 0}})
