"""规则检测引擎 - 基于 YAML 规则对 NSL-KDD 连接记录做条件匹配"""
import logging
import yaml
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_VALID_OPS = {">", "<", ">=", "<=", "!=", "=="}


@dataclass
class RuleMatch:
    """规则匹配结果"""
    rule_id: str
    rule_name: str
    severity: str
    predicted_category: str


@dataclass
class RuleDefinition:
    """规则定义"""
    id: str
    name: str
    description: str
    conditions: dict
    severity: str
    attack_category: str


class RuleEngine:
    """规则检测引擎"""

    def __init__(self, rules_dir: Path):
        self.rules: list[RuleDefinition] = []
        self._load_rules(rules_dir)

    def _load_rules(self, rules_dir: Path):
        """从 YAML 文件加载所有规则"""
        self.rules = []
        if not rules_dir.exists():
            print(f"[RuleEngine] 规则目录不存在: {rules_dir}")
            return

        for yaml_file in sorted(rules_dir.glob("*.yaml")):
            with open(yaml_file, 'r', encoding='utf-8') as f:
                rule_list = yaml.safe_load(f)
            if not rule_list:
                continue
            for rule_data in rule_list:
                self.rules.append(RuleDefinition(
                    id=rule_data['id'],
                    name=rule_data['name'],
                    description=rule_data.get('description', ''),
                    conditions=rule_data['conditions'],
                    severity=rule_data['severity'],
                    attack_category=rule_data['attack_category'],
                ))
        print(f"[RuleEngine] 已加载 {len(self.rules)} 条规则")

    def evaluate(self, record: dict) -> list[RuleMatch]:
        """对单条连接记录（dict 形式）逐条规则匹配"""
        matches = []
        for rule in self.rules:
            if self._check_conditions(record, rule.conditions):
                matches.append(RuleMatch(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    predicted_category=rule.attack_category,
                ))
        return matches

    def evaluate_batch(self, records: list[dict]) -> list[list[RuleMatch]]:
        """批量评估"""
        return [self.evaluate(r) for r in records]

    def _check_conditions(self, record: dict, conditions: dict) -> bool:
        """
        条件匹配，支持：
        - 等值匹配: field: value
        - 比较运算: field: {">": 10}  field: {"<": 5}  field: {">=": 0.5}
        - 列表匹配: field: ["val1", "val2"]
        - 非零检测: field: {"!=": 0}
        """
        for field_name, expected in conditions.items():
            value = record.get(field_name)
            if value is None:
                return False

            if isinstance(expected, dict):
                # 比较运算符
                for op, threshold in expected.items():
                    if op not in _VALID_OPS:
                        logger.warning("未知运算符 '%s' (字段: %s)，条件视为不匹配", op, field_name)
                        return False
                    if op == ">" and not (value > threshold):
                        return False
                    elif op == "<" and not (value < threshold):
                        return False
                    elif op == ">=" and not (value >= threshold):
                        return False
                    elif op == "<=" and not (value <= threshold):
                        return False
                    elif op == "!=" and not (value != threshold):
                        return False
                    elif op == "==" and not (value == threshold):
                        return False
            elif isinstance(expected, list):
                # 列表 in 匹配
                if value not in expected:
                    return False
            else:
                # 等值匹配
                if value != expected:
                    return False

        return True

    def get_rules_info(self) -> list[dict]:
        """返回所有规则的信息"""
        return [
            {
                'id': r.id,
                'name': r.name,
                'description': r.description,
                'severity': r.severity,
                'attack_category': r.attack_category,
                'conditions': r.conditions,
            }
            for r in self.rules
        ]
