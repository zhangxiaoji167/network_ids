"""检测链路关键回归测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

import main as main_module
from api import routes_detection
from database import get_connection, init_db
from detection.hybrid_engine import DetectionResult


class _FakeHybridEngine:
    def detect_batch(self, records, start_id=0, start_ids=None):
        results = []
        for i, record in enumerate(records):
            record_id = start_ids[i] if start_ids else (start_id + i)
            label = record.get("attack_category", "Normal")
            results.append(
                DetectionResult(
                    record_id=record_id,
                    rule_matched=False,
                    rule_matches=[],
                    rule_predicted=None,
                    rule_severity=None,
                    ml_predicted="Normal",
                    ml_confidence=0.1,
                    ml_probabilities={"Normal": 1.0},
                    final_verdict=label,
                    final_source="ML",
                    actual_label=label,
                    is_correct=True,
                )
            )
        return results

    def generate_alerts(self, results, records):
        return []


def _build_nsl_df(size: int, attack: str = "Normal") -> pd.DataFrame:
    rows = []
    for i in range(size):
        rows.append(
            {
                "duration": i,
                "protocol_type": "tcp",
                "service": "http",
                "flag": "SF",
                "src_bytes": 10 + i,
                "dst_bytes": 20 + i,
                "count": 1 + i,
                "serror_rate": 0.0,
                "label": attack.lower(),
                "attack_category": attack,
                "difficulty": 1,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture()
def clean_tables():
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM alerts")
        conn.execute("DELETE FROM detection_results")
        conn.execute("DELETE FROM connections")
        conn.commit()


def test_connection_id_alignment_with_limit(clean_tables, monkeypatch):
    """同一数据集重复检测时，limit 结果应对应最前面的连接 ID。"""

    def fake_load_nsl_kdd(dataset):
        return _build_nsl_df(5, "DoS")

    monkeypatch.setattr(routes_detection, "load_nsl_kdd", fake_load_nsl_kdd)
    monkeypatch.setattr(
        main_module, "get_engines", lambda source: (None, None, _FakeHybridEngine())
    )

    routes_detection._do_detection("nsl-kdd", "test", 0)
    routes_detection._do_detection("nsl-kdd", "test", 2)

    with get_connection() as conn:
        expected_rows = conn.execute(
            "SELECT id FROM connections WHERE dataset = ? ORDER BY id LIMIT 2",
            ("nsl-test",),
        ).fetchall()
        rows = conn.execute(
            "SELECT connection_id FROM detection_results ORDER BY id"
        ).fetchall()

    assert [r[0] for r in rows] == [r[0] for r in expected_rows]


def test_results_isolated_by_source_and_dataset(clean_tables, monkeypatch):
    """同 source 的 train/test 检测结果应并存。"""

    def fake_load_nsl_kdd(dataset):
        if dataset == "train":
            return _build_nsl_df(3, "Probe")
        return _build_nsl_df(3, "DoS")

    monkeypatch.setattr(routes_detection, "load_nsl_kdd", fake_load_nsl_kdd)
    monkeypatch.setattr(
        main_module, "get_engines", lambda source: (None, None, _FakeHybridEngine())
    )

    routes_detection._do_detection("nsl-kdd", "test", 0)
    routes_detection._do_detection("nsl-kdd", "train", 0)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT c.dataset, COUNT(*) as cnt "
            "FROM detection_results d "
            "JOIN connections c ON c.id = d.connection_id "
            "GROUP BY c.dataset"
        ).fetchall()

    counts = {r[0]: r[1] for r in rows}
    assert counts.get("nsl-test") == 3
    assert counts.get("nsl-train") == 3


def test_detection_result_dataset_column_persisted(clean_tables, monkeypatch):
    """检测结果应写入 dataset 字段，便于 source+dataset 隔离查询。"""

    monkeypatch.setattr(
        routes_detection, "load_nsl_kdd", lambda dataset: _build_nsl_df(2, "DoS")
    )
    monkeypatch.setattr(
        main_module, "get_engines", lambda source: (None, None, _FakeHybridEngine())
    )

    routes_detection._do_detection("nsl-kdd", "test", 0)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT DISTINCT dataset FROM detection_results WHERE dataset_source = ?",
            ("nsl-kdd",),
        ).fetchone()

    assert row is not None
    assert row[0] == "nsl-test"
