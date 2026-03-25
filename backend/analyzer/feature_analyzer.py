"""特征分析模块 - 对 NSL-KDD 数据进行特征维度的统计分析"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from database import get_connection
from config import NUMERIC_COLUMNS


def get_traffic_stats(dataset: str | None = None) -> dict:
    """流量特征统计 (src_bytes, dst_bytes, duration)"""
    where = "WHERE dataset = ?" if dataset else ""
    params = (dataset,) if dataset else ()
    fields = ["src_bytes", "dst_bytes", "duration"]
    # 单条 SQL 一次性获取所有字段的统计
    agg_parts = []
    for f in fields:
        agg_parts.append(f"AVG({f}), MIN({f}), MAX({f})")
    sql = f"SELECT {', '.join(agg_parts)}, COUNT(*) FROM connections {where}"
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    result = {}
    for i, f in enumerate(fields):
        base = i * 3
        avg_val = row[base]
        result[f] = {
            "mean": round(avg_val, 2) if avg_val is not None else 0,
            "min": row[base + 1] or 0,
            "max": row[base + 2] or 0,
            "count": row[len(fields) * 3] or 0,
        }
    return result


def get_feature_comparison(dataset: str | None = None) -> dict:
    """攻击 vs 正常流量的关键特征均值对比"""
    where = "AND dataset = ?" if dataset else ""
    params_normal = ("Normal", dataset) if dataset else ("Normal",)
    params_attack = ("Normal", dataset) if dataset else ("Normal",)

    key_features = [
        "duration", "src_bytes", "dst_bytes", "count", "srv_count",
        "serror_rate", "rerror_rate", "same_srv_rate", "diff_srv_rate",
        "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    ]

    # 用 2 条 SQL 替代 24 条
    avg_cols = ", ".join(f"AVG({f})" for f in key_features)
    result = {"normal": {}, "attack": {}}

    with get_connection() as conn:
        row_n = conn.execute(
            f"SELECT {avg_cols} FROM connections WHERE attack_category = ? {where}",
            params_normal,
        ).fetchone()
        row_a = conn.execute(
            f"SELECT {avg_cols} FROM connections WHERE attack_category != ? {where}",
            params_attack,
        ).fetchone()

    for i, feat in enumerate(key_features):
        result["normal"][feat] = round(row_n[i], 4) if row_n[i] is not None else 0
        result["attack"][feat] = round(row_a[i], 4) if row_a[i] is not None else 0

    return result


def get_feature_by_attack_type(feature: str, dataset: str | None = None) -> list[dict]:
    """指定特征在各攻击类型中的均值"""
    if feature not in NUMERIC_COLUMNS:
        raise ValueError(f"Invalid feature: {feature}")
    where = "WHERE dataset = ?" if dataset else ""
    params = (dataset,) if dataset else ()
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT attack_category, AVG({feature}) as mean, "
            f"MIN({feature}) as min, MAX({feature}) as max "
            f"FROM connections {where} "
            "GROUP BY attack_category ORDER BY mean DESC",
            params,
        ).fetchall()
    return [
        {"attack_category": r["attack_category"],
         "mean": round(r["mean"], 4) if r["mean"] is not None else 0,
         "min": r["min"] or 0, "max": r["max"] or 0}
        for r in rows
    ]


def get_correlation_matrix(features: list[str] | None = None,
                           dataset: str | None = None) -> dict:
    """特征相关性矩阵"""
    if features is None:
        features = [
            "duration", "src_bytes", "dst_bytes", "count", "srv_count",
            "serror_rate", "rerror_rate", "same_srv_rate",
            "dst_host_count", "dst_host_srv_count",
        ]
    # 验证特征名
    for f in features:
        if f not in NUMERIC_COLUMNS:
            raise ValueError(f"Invalid feature: {f}")

    cols = ", ".join(features)
    where = "WHERE dataset = ?" if dataset else ""
    params = (dataset,) if dataset else ()

    with get_connection() as conn:
        df = pd.read_sql_query(
            f"SELECT {cols} FROM connections {where}", conn, params=params
        )

    if df.empty:
        return {"features": features, "matrix": []}

    corr = df.corr()
    return {
        "features": features,
        "matrix": [[round(v, 4) for v in row] for row in corr.values.tolist()],
    }
