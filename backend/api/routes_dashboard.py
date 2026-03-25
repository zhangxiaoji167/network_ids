"""Dashboard API - 概览统计"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, Query
from database import get_connection

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_dashboard_stats(
    source: str | None = Query(None, description="数据集源: nsl-kdd 或 unsw-nb15"),
    dataset: str | None = Query(None, description="精确数据集标识，如 nsl-test"),
):
    """概览统计：总连接数、攻击数、检测准确率、高危告警数

    不传参数：全量总览（connections 全表 + detection_results 全表）。
    传 source：仅统计该 source 实际检测过的记录（基于 detection_results）。
    """
    with get_connection() as conn:
        if source:
            det_conditions = ["dataset_source = ?"]
            det_params: list = [source]
            if dataset:
                det_conditions.append("dataset = ?")
                det_params.append(dataset)
            det_where = " AND ".join(det_conditions)

            # ── 按 source 过滤：统计基于 detection_results（实际检测的记录）──
            det_total = conn.execute(
                f"SELECT COUNT(*) FROM detection_results WHERE {det_where}",
                det_params,
            ).fetchone()[0]
            det_correct = conn.execute(
                f"SELECT COUNT(*) FROM detection_results WHERE {det_where} AND is_correct = 1",
                det_params,
            ).fetchone()[0]

            # 连接数 = 检测结果数，攻击数 = final_verdict != Normal
            total = det_total
            attack_count = conn.execute(
                f"SELECT COUNT(*) FROM detection_results WHERE {det_where} AND final_verdict != 'Normal'",
                det_params,
            ).fetchone()[0]

            # 告警：通过 connection_id 关联
            alert_total = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE connection_id IN "
                f"(SELECT connection_id FROM detection_results WHERE {det_where})",
                det_params,
            ).fetchone()[0]
            alert_high = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE severity IN ('HIGH', 'CRITICAL') "
                "AND connection_id IN "
                f"(SELECT connection_id FROM detection_results WHERE {det_where})",
                det_params,
            ).fetchone()[0]
            alert_unread = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE is_read = 0 "
                "AND connection_id IN "
                f"(SELECT connection_id FROM detection_results WHERE {det_where})",
                det_params,
            ).fetchone()[0]

        else:
            # ── 全量总览：基于 connections 全表 ──
            if dataset:
                conn_where = "WHERE dataset = ?"
                conn_params = [dataset]
            else:
                conn_where = ""
                conn_params = []

            total = conn.execute(
                f"SELECT COUNT(*) FROM connections {conn_where}", conn_params
            ).fetchone()[0]

            if conn_where:
                attack_where = conn_where + " AND attack_category != 'Normal'"
            else:
                attack_where = "WHERE attack_category != 'Normal'"
            attack_count = conn.execute(
                f"SELECT COUNT(*) FROM connections {attack_where}", conn_params
            ).fetchone()[0]

            det_total = conn.execute(
                "SELECT COUNT(*) FROM detection_results"
            ).fetchone()[0]
            det_correct = conn.execute(
                "SELECT COUNT(*) FROM detection_results WHERE is_correct = 1"
            ).fetchone()[0]

            alert_total = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            alert_high = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE severity IN ('HIGH', 'CRITICAL')"
            ).fetchone()[0]
            alert_unread = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE is_read = 0"
            ).fetchone()[0]

        accuracy = round(det_correct / det_total, 4) if det_total > 0 else None

    return {
        "total_connections": total,
        "attack_connections": attack_count,
        "normal_connections": total - attack_count,
        "detection_accuracy": accuracy,
        "detection_count": det_total,
        "alert_total": alert_total,
        "alert_high": alert_high,
        "alert_unread": alert_unread,
    }
