"""FastAPI 端点集成测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from main import app
from config import UNSW_DATA_DIR
from database import get_connection
import uuid


@pytest.fixture(scope="module")
def client():
    """FastAPI 测试客户端"""
    with TestClient(app) as c:
        yield c


class TestDashboardAPI:
    """Dashboard 端点"""

    def test_get_stats(self, client):
        """GET /api/dashboard/stats 应返回 200"""
        resp = client.get("/api/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_connections" in data
        assert "detection_accuracy" in data
        assert "alert_total" in data


class TestModelAPI:
    """Model 端点"""

    def test_get_metrics(self, client):
        """GET /api/model/metrics 应返回 200 或 404（模型不存在时）"""
        resp = client.get("/api/model/metrics")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "accuracy" in data

    def test_get_metrics_invalid_source(self, client):
        """无效数据集源应返回 400"""
        resp = client.get("/api/model/metrics", params={"source": "invalid"})
        assert resp.status_code == 400

    def test_get_feature_importance(self, client):
        """GET /api/model/feature-importance 应返回 200 或 404"""
        resp = client.get("/api/model/feature-importance")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)

    def test_get_confusion_matrix(self, client):
        """GET /api/model/confusion-matrix 应返回 200 或 404"""
        resp = client.get("/api/model/confusion-matrix")
        assert resp.status_code in (200, 404)

    def test_get_roc_data(self, client):
        """GET /api/model/roc-data 应返回 200 或 404"""
        resp = client.get("/api/model/roc-data")
        assert resp.status_code in (200, 404)

    def test_get_comparison(self, client):
        """GET /api/model/comparison 应返回 200"""
        resp = client.get("/api/model/comparison")
        assert resp.status_code == 200


class TestSystemAPI:
    """System 端点"""

    def test_get_dataset_info(self, client):
        """GET /api/system/dataset-info 应返回 200"""
        resp = client.get("/api/system/dataset-info")
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        assert "nsl-kdd" in data
        assert "unsw-nb15" in data

    def test_clear_invalid_table(self, client):
        """清空无效表名应返回 400"""
        resp = client.delete("/api/system/clear-data", params={"table": "users"})
        assert resp.status_code == 400

    def test_train_invalid_source(self, client):
        """训练无效数据集应返回 400"""
        resp = client.post("/api/system/train", params={"source": "invalid"})
        assert resp.status_code == 400

    def test_load_unsw_test_data(self, client):
        """UNSW 测试集应可成功加载到数据库（不应抛 500）"""
        unsw_test = UNSW_DATA_DIR / "UNSW_NB15_testing-set.csv"
        if not unsw_test.exists():
            pytest.skip("UNSW 测试集文件不存在，跳过")

        resp = client.post(
            "/api/system/load-data",
            params={"source": "unsw-nb15", "dataset": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "loaded" in data


class TestDetectionAPI:
    """Detection 端点"""

    def test_get_detection_results(self, client):
        """GET /api/detection/results 应返回 200"""
        resp = client.get("/api/detection/results")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_get_detection_results_with_dataset_filter(self, client):
        """GET /api/detection/results 支持 dataset 过滤参数"""
        resp = client.get(
            "/api/detection/results",
            params={"dataset": "nsl-test", "page": 1, "size": 20},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_get_connections(self, client):
        """GET /api/connections 应返回 200"""
        resp = client.get("/api/connections")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_get_alerts(self, client):
        """GET /api/alerts 应返回 200"""
        resp = client.get("/api/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_get_alerts_with_source_dataset_filters(self, client):
        """GET /api/alerts 支持 source+dataset 过滤。"""
        resp = client.get(
            "/api/alerts",
            params={"source": "nsl-kdd", "dataset": "nsl-test", "page": 1, "size": 20},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_connection_not_found(self, client):
        """不存在的连接 ID 应返回 404"""
        resp = client.get("/api/connections/999999999")
        assert resp.status_code == 404

    def test_alert_not_found(self, client):
        """不存在的告警 ID 应返回 404"""
        resp = client.put("/api/alerts/nonexistent-uuid/read")
        assert resp.status_code == 404

    def test_detection_results_tolerate_invalid_json(self, client):
        """检测结果中的坏 JSON 不应导致接口 500。"""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO connections (dataset, attack_category) VALUES (?, ?)",
                ("nsl-test", "Normal"),
            )
            conn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO detection_results "
                "(connection_id, dataset_source, dataset, rule_matched, rule_predicted, rule_severity, "
                "rule_details_json, ml_predicted, ml_confidence, ml_probabilities_json, "
                "final_verdict, final_source, actual_label, is_correct) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    conn_id,
                    "nsl-kdd",
                    "nsl-test",
                    0,
                    None,
                    None,
                    "{bad-json",
                    "Normal",
                    0.1,
                    "{bad-json",
                    "Normal",
                    "NONE",
                    "Normal",
                    1,
                ),
            )
            conn.commit()

        resp = client.get("/api/detection/results", params={"dataset": "nsl-test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_alerts_tolerate_invalid_json(self, client):
        """告警中的坏 JSON 不应导致接口 500。"""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO connections (dataset, attack_category) VALUES (?, ?)",
                ("nsl-test", "Normal"),
            )
            conn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO alerts (alert_id, connection_id, severity, source, attack_category, description, features_json, is_read) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    conn_id,
                    "LOW",
                    "RULE",
                    "DoS",
                    "bad json test",
                    "{bad-json",
                    0,
                ),
            )
            conn.commit()

        resp = client.get("/api/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
