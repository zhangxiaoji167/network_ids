"""Detection API - 检测流程与结果查询"""

import sys
import json
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, Query, HTTPException
from fastapi.concurrency import run_in_threadpool
from database import get_connection
from data_loader.loader import load_nsl_kdd, load_unsw_nb15, load_to_database

router = APIRouter(prefix="/api", tags=["detection"])

# 每个数据集独立一把锁，防止同一数据集并发检测
_detect_locks: dict[str, threading.Lock] = {}
_dict_lock = threading.Lock()  # 保护 _detect_locks 字典本身的并发写入


def _safe_load_json(value, default):
    """安全解析 JSON 字符串，解析失败时返回默认值。"""
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _get_detect_lock(source: str) -> threading.Lock:
    with _dict_lock:
        if source not in _detect_locks:
            _detect_locks[source] = threading.Lock()
        return _detect_locks[source]


@router.post("/detection/run")
async def run_detection(
    source: str = Query("nsl-kdd", description="数据集源: nsl-kdd 或 unsw-nb15"),
    dataset: str = Query("test", description="'train' 或 'test'"),
    limit: int = Query(0, ge=0, description="限制记录数，0 表示全部"),
):
    """触发检测分析：加载数据 → 规则+ML → 检测结果 → 告警"""
    from main import get_engines
    from config import DATASET_SOURCES

    if source not in DATASET_SOURCES:
        raise HTTPException(status_code=400, detail=f"无效数据集源: {source}")
    if dataset not in ("train", "test"):
        raise HTTPException(
            status_code=400, detail="dataset 参数仅允许 'train' 或 'test'"
        )

    lock = _get_detect_lock(source)
    if not lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409, detail=f"'{source}' 检测正在进行中，请稍后再试"
        )

    try:
        result = await run_in_threadpool(_do_detection, source, dataset, limit)
    finally:
        lock.release()

    return result


def _do_detection(source: str, dataset: str, limit: int) -> dict:
    """实际检测逻辑（在线程池中执行，避免阻塞 event loop）"""
    from main import get_engines

    rule_engine, ml_engine, hybrid_engine = get_engines(source)
    if hybrid_engine is None:
        raise HTTPException(
            status_code=503,
            detail=f"数据集 '{source}' 的检测引擎未初始化，请先训练模型",
        )

    # 数据库中的标识符，如 nsl-test, unsw-train
    prefix = "nsl" if source == "nsl-kdd" else "unsw"
    db_dataset = f"{prefix}-{dataset}"

    # 加载原始数据
    if source == "nsl-kdd":
        full_df = load_nsl_kdd(dataset)
    else:
        full_df = load_unsw_nb15(dataset)
    df = full_df.head(limit) if limit > 0 else full_df

    # 存入数据库（统一按全量数据入库，避免 limit 造成连接 ID 与数据行错位）
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT COUNT(*) FROM connections WHERE dataset = ?", (db_dataset,)
        ).fetchone()[0]
    finally:
        conn.close()

    if existing != len(full_df):
        # 数量不一致（包括 existing==0）则清除旧数据并重新入库
        if existing > 0:
            conn = get_connection()
            try:
                conn.execute(
                    "DELETE FROM alerts WHERE connection_id IN "
                    "(SELECT id FROM connections WHERE dataset = ?)",
                    (db_dataset,),
                )
                conn.execute(
                    "DELETE FROM detection_results WHERE connection_id IN "
                    "(SELECT id FROM connections WHERE dataset = ?)",
                    (db_dataset,),
                )
                conn.execute(
                    "DELETE FROM connections WHERE dataset = ?", (db_dataset,)
                )
                conn.commit()
            finally:
                conn.close()
        load_to_database(full_df, db_dataset)

    # 获取对应 connection id，用于关联 detection_results
    conn = get_connection()
    try:
        if limit > 0:
            rows = conn.execute(
                "SELECT id FROM connections WHERE dataset = ? ORDER BY id LIMIT ?",
                (db_dataset, len(df)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id FROM connections WHERE dataset = ? ORDER BY id",
                (db_dataset,),
            ).fetchall()
        conn_ids = [r["id"] for r in rows]
    finally:
        conn.close()

    if len(conn_ids) != len(df):
        raise HTTPException(
            status_code=500,
            detail=(
                f"连接记录与检测数据数量不一致: connections={len(conn_ids)}, records={len(df)}"
            ),
        )

    # 转为字典列表
    records = df.to_dict("records")

    # 批量检测（record_id 使用真实 connection id）
    results = hybrid_engine.detect_batch(records, start_ids=conn_ids)

    # 生成告警
    alerts = hybrid_engine.generate_alerts(results, records)

    # 存储检测结果（仅删除同 source+dataset 的旧结果）
    conn = get_connection()
    try:
        # 删除关联的 alerts（通过 connection_id 子查询，无需 JOIN）
        conn.execute(
            "DELETE FROM alerts WHERE connection_id IN "
            "(SELECT connection_id FROM detection_results WHERE dataset_source = ? AND dataset = ?)",
            (source, db_dataset),
        )
        conn.execute(
            "DELETE FROM detection_results WHERE dataset_source = ? AND dataset = ?",
            (source, db_dataset),
        )

        conn.executemany(
            "INSERT INTO detection_results "
            "(connection_id, dataset_source, dataset, rule_matched, rule_predicted, rule_severity, "
            "rule_details_json, ml_predicted, ml_confidence, "
            "ml_probabilities_json, final_verdict, final_source, "
            "actual_label, is_correct) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r.record_id,
                    source,
                    db_dataset,
                    int(r.rule_matched),
                    r.rule_predicted,
                    r.rule_severity,
                    json.dumps(r.rule_matches, ensure_ascii=False),
                    r.ml_predicted,
                    r.ml_confidence,
                    json.dumps(r.ml_probabilities, ensure_ascii=False),
                    r.final_verdict,
                    r.final_source,
                    r.actual_label,
                    int(r.is_correct),
                )
                for r in results
            ],
        )

        conn.executemany(
            "INSERT INTO alerts "
            "(alert_id, connection_id, severity, source, attack_category, "
            "description, features_json, is_read) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            [
                (
                    a.alert_id,
                    a.record_id,
                    a.severity,
                    a.source,
                    a.attack_category,
                    a.description,
                    json.dumps(a.connection_features, ensure_ascii=False),
                )
                for a in alerts
            ],
        )
        conn.commit()
    finally:
        conn.close()

    total = len(results)
    correct = sum(1 for r in results if r.is_correct)

    return {
        "total_records": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0,
        "alert_count": len(alerts),
        "source_distribution": _count_by(results, "final_source"),
        "verdict_distribution": _count_by(results, "final_verdict"),
    }


def _count_by(results, attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        key = getattr(r, attr)
        counts[key] = counts.get(key, 0) + 1
    return counts


@router.get("/detection/results")
def get_detection_results(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    verdict: str | None = Query(None),
    source: str | None = Query(None),
    dataset: str | None = Query(None),
):
    """检测结果列表（分页+过滤）"""
    conditions = []
    params: list = []
    if verdict:
        conditions.append("final_verdict = ?")
        params.append(verdict)
    if source:
        conditions.append("final_source = ?")
        params.append(source)
    if dataset:
        conditions.append("dataset = ?")
        params.append(dataset)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * size

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM detection_results {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM detection_results {where} ORDER BY id LIMIT ? OFFSET ?",
            params + [size, offset],
        ).fetchall()

    items = []
    for r in rows:
        item = dict(r)
        # 解析 JSON 字段
        item["rule_details"] = _safe_load_json(item.get("rule_details_json"), [])
        item["ml_probabilities"] = _safe_load_json(
            item.get("ml_probabilities_json"), {}
        )
        item.pop("rule_details_json", None)
        item.pop("ml_probabilities_json", None)
        items.append(item)

    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/connections")
def get_connections(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    protocol_type: str | None = Query(None),
    service: str | None = Query(None),
    attack_category: str | None = Query(None),
    flag: str | None = Query(None),
    dataset: str | None = Query(None),
):
    """连接记录列表（分页+过滤）"""
    conditions = []
    params: list = []
    for col, val in [
        ("protocol_type", protocol_type),
        ("service", service),
        ("attack_category", attack_category),
        ("flag", flag),
        ("dataset", dataset),
    ]:
        if val:
            conditions.append(f"{col} = ?")
            params.append(val)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * size

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM connections {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM connections {where} ORDER BY id LIMIT ? OFFSET ?",
            params + [size, offset],
        ).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/connections/{conn_id}")
def get_connection_detail(conn_id: int):
    """单条连接详情（含检测结果）"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM connections WHERE id = ?", (conn_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="连接记录不存在")

        det_row = conn.execute(
            "SELECT * FROM detection_results WHERE connection_id = ?",
            (conn_id,),
        ).fetchone()

    result = dict(row)
    if det_row:
        det = dict(det_row)
        det["rule_details"] = _safe_load_json(det.get("rule_details_json"), [])
        det["ml_probabilities"] = _safe_load_json(det.get("ml_probabilities_json"), {})
        det.pop("rule_details_json", None)
        det.pop("ml_probabilities_json", None)
        result["detection"] = det

    return result


@router.get("/alerts")
def get_alerts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    severity: str | None = Query(None),
    attack_category: str | None = Query(None),
    is_read: int | None = Query(None),
    source: str | None = Query(None, description="数据集源: nsl-kdd 或 unsw-nb15"),
    dataset: str | None = Query(None, description="精确数据集标识，如 nsl-test"),
):
    """告警列表（分页+过滤+按严重级别排序）"""
    conditions = []
    params: list = []
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if attack_category:
        conditions.append("attack_category = ?")
        params.append(attack_category)
    if is_read is not None:
        conditions.append("is_read = ?")
        params.append(is_read)
    if source or dataset:
        det_conditions = []
        det_params = []
        if source:
            det_conditions.append("dataset_source = ?")
            det_params.append(source)
        if dataset:
            det_conditions.append("dataset = ?")
            det_params.append(dataset)
        sub_where = " AND ".join(det_conditions)
        conditions.append(
            "connection_id IN (SELECT connection_id FROM detection_results WHERE "
            + sub_where
            + ")"
        )
        params.extend(det_params)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * size

    with get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM alerts {where}", params).fetchone()[
            0
        ]

        rows = conn.execute(
            f"SELECT * FROM alerts {where} "
            "ORDER BY CASE severity "
            "  WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 "
            "  WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 END, "
            "created_at DESC "
            f"LIMIT ? OFFSET ?",
            params + [size, offset],
        ).fetchall()

    items = []
    for r in rows:
        item = dict(r)
        item["features"] = _safe_load_json(item.get("features_json"), {})
        item.pop("features_json", None)
        items.append(item)

    return {"items": items, "total": total, "page": page, "size": size}


@router.put("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: str):
    """标记告警已读"""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE alerts SET is_read = 1 WHERE alert_id = ?", (alert_id,)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="告警不存在")
        conn.commit()
    return {"message": "已标记为已读"}
