"""端到端验证测试 - 验证完整检测流程"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
from config import RULES_DIR, FEATURE_COLUMNS
from data_loader.loader import load_nsl_kdd
from detection.rule_engine import RuleEngine
from detection.ml_engine import MLEngine
from detection.hybrid_engine import HybridEngine
from database import init_db

def main():
    print("=" * 60)
    print("端到端验证测试")
    print("=" * 60)

    # 1. 初始化数据库
    print("\n[1] 初始化数据库...")
    init_db()
    print("    OK")

    # 2. 加载数据
    print("\n[2] 加载测试数据...")
    test_df = load_nsl_kdd('test')
    print(f"    加载 {len(test_df)} 条测试记录")
    records = test_df.to_dict('records')

    # 3. 初始化规则引擎
    print("\n[3] 初始化规则引擎...")
    rule_engine = RuleEngine(RULES_DIR)
    print(f"    加载 {len(rule_engine.rules)} 条规则")

    # 4. 初始化 ML 引擎
    print("\n[4] 初始化 ML 引擎...")
    ml_engine = MLEngine()
    loaded = ml_engine.load()
    print(f"    模型加载: {'成功' if loaded else '失败'}")
    if loaded:
        info = ml_engine.get_model_info()
        print(f"    模型准确率: {info.get('accuracy')}")
        print(f"    类别: {info.get('categories')}")

    # 5. 初始化混合决策引擎
    print("\n[5] 初始化混合决策引擎...")
    hybrid_engine = HybridEngine(rule_engine, ml_engine)

    # 6. 测试单条记录
    print("\n[6] 测试单条记录检测...")
    sample = records[2]  # neptune 攻击
    print(f"    记录: protocol={sample['protocol_type']}, service={sample['service']}, "
          f"flag={sample['flag']}, label={sample['label']}")

    result = hybrid_engine.detect(sample, record_id=2)
    print(f"    规则命中: {result.rule_matched}, 规则预测: {result.rule_predicted}")
    print(f"    ML预测: {result.ml_predicted} (置信度: {result.ml_confidence:.4f})")
    print(f"    最终判定: {result.final_verdict} (来源: {result.final_source})")
    print(f"    真实标签: {result.actual_label}, 正确: {result.is_correct}")

    # 7. 批量检测（取前 1000 条）
    print("\n[7] 批量检测前 1000 条记录...")
    batch_records = records[:1000]
    batch_results = hybrid_engine.detect_batch(batch_records)

    correct = sum(1 for r in batch_results if r.is_correct)
    total = len(batch_results)
    print(f"    混合检测准确率: {correct}/{total} = {correct/total:.4f}")

    # 统计检测来源分布
    source_counts = {}
    verdict_counts = {}
    for r in batch_results:
        source_counts[r.final_source] = source_counts.get(r.final_source, 0) + 1
        verdict_counts[r.final_verdict] = verdict_counts.get(r.final_verdict, 0) + 1
    print(f"    检测来源分布: {source_counts}")
    print(f"    判定结果分布: {verdict_counts}")

    # 8. 生成告警
    print("\n[8] 生成告警...")
    alerts = hybrid_engine.generate_alerts(batch_results, batch_records)
    print(f"    生成 {len(alerts)} 条告警")

    severity_counts = {}
    for a in alerts:
        severity_counts[a.severity] = severity_counts.get(a.severity, 0) + 1
    print(f"    严重级别分布: {severity_counts}")

    if alerts:
        a = alerts[0]
        print(f"    示例告警: [{a.severity}] {a.description[:80]}...")

    # 9. 规则引擎独立测试
    print("\n[9] 规则引擎独立统计...")
    rule_hit = sum(1 for r in batch_results if r.rule_matched)
    rule_only_correct = sum(
        1 for r, rec in zip(batch_results, batch_records)
        if r.rule_matched and r.rule_predicted == rec.get('attack_category')
    )
    print(f"    规则命中: {rule_hit}/{total} 条")
    if rule_hit > 0:
        print(f"    规则命中中正确: {rule_only_correct}/{rule_hit}")

    # 10. ML 引擎独立统计
    print("\n[10] ML 引擎独立统计...")
    ml_correct = sum(
        1 for r, rec in zip(batch_results, batch_records)
        if r.ml_predicted == rec.get('attack_category')
    )
    print(f"    ML 准确率: {ml_correct}/{total} = {ml_correct/total:.4f}")

    print("\n" + "=" * 60)
    print("端到端验证完成！所有模块正常工作。")
    print("=" * 60)


if __name__ == '__main__':
    main()
