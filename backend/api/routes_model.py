"""Model API - 模型评估指标"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, HTTPException, Query
from config import MODEL_DIR, DATASET_SOURCES
from ml.evaluate import load_metrics
from database import get_connection

router = APIRouter(prefix="/api/model", tags=["model"])

# 数据集 → 指标文件名
_METRICS_FILES = {
    "nsl-kdd": "nslkdd_metrics.json",
    "unsw-nb15": "unsw_metrics.json",
}


def _load_saved_metrics(source: str = "nsl-kdd") -> dict:
    """加载指定数据集的模型评估指标

    兼容逻辑：若 nslkdd_metrics.json 不存在但旧版 metrics.json 存在，
    则使用 metrics.json 作为 fallback。
    """
    if source not in DATASET_SOURCES:
        raise HTTPException(status_code=400, detail=f"无效数据集源: {source}")
    filename = _METRICS_FILES[source]
    metrics_path = MODEL_DIR / filename
    if not metrics_path.exists():
        # Fallback: nsl-kdd 的旧版指标文件名为 metrics.json
        if source == "nsl-kdd":
            fallback_path = MODEL_DIR / "metrics.json"
            if fallback_path.exists():
                return load_metrics(fallback_path)
        raise HTTPException(
            status_code=404, detail=f"模型指标文件不存在，请先训练 {source} 模型"
        )
    return load_metrics(metrics_path)


@router.get("/metrics")
def get_model_metrics(
    source: str = Query("nsl-kdd", description="数据集源: nsl-kdd 或 unsw-nb15"),
):
    """模型评估指标概要"""
    metrics = _load_saved_metrics(source)
    return {
        "accuracy": metrics.get("accuracy"),
        "external_test_accuracy": metrics.get("external_test_accuracy"),
        "train_time_seconds": metrics.get("train_time_seconds"),
        "classification_report": metrics.get("classification_report"),
    }


@router.get("/feature-importance")
def get_feature_importance(
    source: str = Query("nsl-kdd", description="数据集源: nsl-kdd 或 unsw-nb15"),
):
    """特征重要性排名 (Top 15)"""
    metrics = _load_saved_metrics(source)
    importance = metrics.get("feature_importance", {})
    sorted_items = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    return [{"feature": name, "importance": value} for name, value in sorted_items]


@router.get("/confusion-matrix")
def get_confusion_matrix(
    source: str = Query("nsl-kdd", description="数据集源: nsl-kdd 或 unsw-nb15"),
):
    """混淆矩阵数据"""
    metrics = _load_saved_metrics(source)
    cm = metrics.get("confusion_matrix", [])
    report = metrics.get("classification_report", {})
    categories = [
        k for k in report if k not in ("accuracy", "macro avg", "weighted avg")
    ]
    return {
        "categories": categories,
        "matrix": cm,
    }


@router.get("/roc-data")
def get_roc_data(
    source: str = Query("nsl-kdd", description="数据集源: nsl-kdd 或 unsw-nb15"),
):
    """ROC 曲线数据"""
    metrics = _load_saved_metrics(source)
    return metrics.get("roc_data", {})


@router.get("/comparison")
def get_method_comparison(
    source: str | None = Query(None, description="数据集源: nsl-kdd 或 unsw-nb15"),
    dataset: str | None = Query(None, description="精确数据集标识，如 nsl-test"),
):
    """规则 vs ML vs 混合检测方式对比"""
    conditions = []
    params: list = []
    if source:
        conditions.append("dataset_source = ?")
        params.append(source)
    if dataset:
        conditions.append("dataset = ?")
        params.append(dataset)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM detection_results {where}",
            params,
        ).fetchone()[0]

        if total == 0:
            return {"message": "暂无检测结果，请先运行检测"}

        rows = conn.execute(
            "SELECT final_source, "
            "COUNT(*) as count, "
            "SUM(is_correct) as correct "
            "FROM detection_results "
            f"{where} "
            "GROUP BY final_source",
            params,
        ).fetchall()

        category_rows = conn.execute(
            "SELECT actual_label, "
            "COUNT(*) as total, "
            "SUM(is_correct) as correct "
            "FROM detection_results "
            f"{where} "
            "GROUP BY actual_label",
            params,
        ).fetchall()

    source_stats = {}
    for r in rows:
        count = r["count"]
        correct = r["correct"] or 0
        source_stats[r["final_source"]] = {
            "count": count,
            "correct": correct,
            "accuracy": round(correct / count, 4) if count else 0,
        }

    category_stats = {}
    for r in category_rows:
        t = r["total"]
        c = r["correct"] or 0
        category_stats[r["actual_label"]] = {
            "total": t,
            "correct": c,
            "accuracy": round(c / t, 4) if t else 0,
        }

    overall_correct = sum(s["correct"] for s in source_stats.values())
    return {
        "total": total,
        "overall_accuracy": round(overall_correct / total, 4) if total else 0,
        "by_source": source_stats,
        "by_category": category_stats,
    }
