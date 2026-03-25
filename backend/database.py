"""SQLite 数据库初始化和操作"""

import sqlite3
import json
from pathlib import Path
from config import DB_PATH


ALLOWED_TABLES = {"connections", "detection_results", "alerts", "model_metrics"}


def get_connection(timeout: int = 60) -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def init_db():
    """初始化数据库表"""
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            duration INTEGER,
            protocol_type TEXT,
            service TEXT,
            flag TEXT,
            src_bytes INTEGER,
            dst_bytes INTEGER,
            land INTEGER,
            wrong_fragment INTEGER,
            urgent INTEGER,
            hot INTEGER,
            num_failed_logins INTEGER,
            logged_in INTEGER,
            num_compromised INTEGER,
            root_shell INTEGER,
            su_attempted INTEGER,
            num_root INTEGER,
            num_file_creations INTEGER,
            num_shells INTEGER,
            num_access_files INTEGER,
            num_outbound_cmds INTEGER,
            is_host_login INTEGER,
            is_guest_login INTEGER,
            count INTEGER,
            srv_count INTEGER,
            serror_rate REAL,
            srv_serror_rate REAL,
            rerror_rate REAL,
            srv_rerror_rate REAL,
            same_srv_rate REAL,
            diff_srv_rate REAL,
            srv_diff_host_rate REAL,
            dst_host_count INTEGER,
            dst_host_srv_count INTEGER,
            dst_host_same_srv_rate REAL,
            dst_host_diff_srv_rate REAL,
            dst_host_same_src_port_rate REAL,
            dst_host_srv_diff_host_rate REAL,
            dst_host_serror_rate REAL,
            dst_host_srv_serror_rate REAL,
            dst_host_rerror_rate REAL,
            dst_host_srv_rerror_rate REAL,
            label TEXT,
            attack_category TEXT,
            difficulty INTEGER,
            dataset TEXT
        );

        CREATE TABLE IF NOT EXISTS detection_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id INTEGER REFERENCES connections(id),
            dataset_source TEXT,
            dataset TEXT,
            rule_matched INTEGER,
            rule_predicted TEXT,
            rule_severity TEXT,
            rule_details_json TEXT,
            ml_predicted TEXT,
            ml_confidence REAL,
            ml_probabilities_json TEXT,
            final_verdict TEXT,
            final_source TEXT,
            actual_label TEXT,
            is_correct INTEGER,
            created_at REAL DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id TEXT UNIQUE,
            connection_id INTEGER REFERENCES connections(id),
            severity TEXT,
            source TEXT,
            attack_category TEXT,
            description TEXT,
            features_json TEXT,
            is_read INTEGER DEFAULT 0,
            created_at REAL DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS model_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT,
            metric_value TEXT,
            created_at REAL
        );
        """)
        conn.commit()

        # 迁移：对旧库补充 dataset_source 列（必须在建索引之前）
        cols = {row[1] for row in conn.execute("PRAGMA table_info(detection_results)")}
        if "dataset_source" not in cols:
            conn.execute("ALTER TABLE detection_results ADD COLUMN dataset_source TEXT")
            conn.commit()
        if "dataset" not in cols:
            conn.execute("ALTER TABLE detection_results ADD COLUMN dataset TEXT")
            conn.commit()

        # 建索引（逐条执行，避免 executescript 中途失败导致全部回滚）
        _INDEXES = [
            "CREATE INDEX IF NOT EXISTS idx_connections_protocol ON connections(protocol_type)",
            "CREATE INDEX IF NOT EXISTS idx_connections_attack ON connections(attack_category)",
            "CREATE INDEX IF NOT EXISTS idx_connections_dataset ON connections(dataset)",
            "CREATE INDEX IF NOT EXISTS idx_connections_service ON connections(service)",
            "CREATE INDEX IF NOT EXISTS idx_detection_results_verdict ON detection_results(final_verdict)",
            "CREATE INDEX IF NOT EXISTS idx_detection_results_source ON detection_results(dataset_source)",
            "CREATE INDEX IF NOT EXISTS idx_detection_results_dataset ON detection_results(dataset)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_category ON alerts(attack_category)",
        ]
        for stmt in _INDEXES:
            conn.execute(stmt)
        conn.commit()


def clear_table(table_name: str):
    """清空指定表"""
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table name: {table_name}")
    with get_connection() as conn:
        conn.execute(f"DELETE FROM {table_name}")
        conn.commit()


def get_table_count(table_name: str) -> int:
    """获取表记录数"""
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table name: {table_name}")
    with get_connection() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
