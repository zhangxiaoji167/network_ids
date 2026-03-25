"""协议分析模块 - 对 NSL-KDD 数据进行协议与服务维度的统计分析"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import get_connection


def get_protocol_distribution(dataset: str | None = None) -> list[dict]:
    """协议类型分布 (TCP/UDP/ICMP)"""
    where = "WHERE dataset = ?" if dataset else ""
    params = (dataset,) if dataset else ()
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT protocol_type, COUNT(*) as count FROM connections {where} "
            "GROUP BY protocol_type ORDER BY count DESC",
            params,
        ).fetchall()
    total = sum(r["count"] for r in rows)
    return [
        {"name": r["protocol_type"], "count": r["count"],
         "percentage": round(r["count"] / total * 100, 2) if total else 0}
        for r in rows
    ]


def get_service_distribution(top_n: int = 15, dataset: str | None = None) -> list[dict]:
    """服务类型分布 (Top N)"""
    where = "WHERE dataset = ?" if dataset else ""
    params: tuple = (dataset, top_n) if dataset else (top_n,)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT service, COUNT(*) as count FROM connections {where} "
            "GROUP BY service ORDER BY count DESC LIMIT ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            f"SELECT COUNT(*) FROM connections {where}",
            (dataset,) if dataset else (),
        ).fetchone()
    total = total_row[0] if total_row else 0
    return [
        {"name": r["service"], "count": r["count"],
         "percentage": round(r["count"] / total * 100, 2) if total else 0}
        for r in rows
    ]


def get_attack_distribution(dataset: str | None = None) -> list[dict]:
    """攻击类型分布 (5 大类)"""
    where = "WHERE dataset = ?" if dataset else ""
    params = (dataset,) if dataset else ()
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT attack_category, COUNT(*) as count FROM connections {where} "
            "GROUP BY attack_category ORDER BY count DESC",
            params,
        ).fetchall()
    total = sum(r["count"] for r in rows)
    return [
        {"name": r["attack_category"], "count": r["count"],
         "percentage": round(r["count"] / total * 100, 2) if total else 0}
        for r in rows
    ]


def get_flag_distribution(dataset: str | None = None) -> list[dict]:
    """连接状态标志分布 (SF/S0/REJ 等)"""
    where = "WHERE dataset = ?" if dataset else ""
    params = (dataset,) if dataset else ()
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT flag, COUNT(*) as count FROM connections {where} "
            "GROUP BY flag ORDER BY count DESC",
            params,
        ).fetchall()
    total = sum(r["count"] for r in rows)
    return [
        {"name": r["flag"], "count": r["count"],
         "percentage": round(r["count"] / total * 100, 2) if total else 0}
        for r in rows
    ]


def get_attack_protocol_cross(dataset: str | None = None) -> list[dict]:
    """攻击类型 × 协议类型 交叉统计"""
    where = "WHERE dataset = ?" if dataset else ""
    params = (dataset,) if dataset else ()
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT attack_category, protocol_type, COUNT(*) as count "
            f"FROM connections {where} "
            "GROUP BY attack_category, protocol_type "
            "ORDER BY attack_category, count DESC",
            params,
        ).fetchall()
    return [dict(r) for r in rows]
