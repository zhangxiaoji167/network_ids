"""System API - 系统管理与数据集信息"""
import sys
import logging
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, HTTPException, Query
from config import DATA_DIR, UNSW_DATA_DIR, MODEL_DIR, DATASET_SOURCES
from database import get_connection, get_table_count, clear_table, ALLOWED_TABLES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])

# 训练锁：防止并发训练
_train_lock = threading.Lock()
_training_in_progress = False

# 缓存数据集文件行数（文件内容不变）
_record_count_cache: dict[str, int] = {}


def _count_file_lines(filepath: Path) -> int:
    """缓存文件行数，避免每次请求都遍历文件"""
    key = str(filepath)
    if key not in _record_count_cache:
        with open(filepath, "r") as f:
            _record_count_cache[key] = sum(1 for _ in f)
    return _record_count_cache[key]


@router.get("/dataset-info")
def get_dataset_info():
    """多数据集基本信息"""
    # NSL-KDD
    nsl_train = DATA_DIR / "KDDTrain+.txt"
    nsl_test = DATA_DIR / "KDDTest+.txt"
    # UNSW-NB15
    unsw_train = UNSW_DATA_DIR / "UNSW_NB15_training-set.csv"
    unsw_test = UNSW_DATA_DIR / "UNSW_NB15_testing-set.csv"

    info = {
        "sources": DATASET_SOURCES,
        "nsl-kdd": {
            "train_exists": nsl_train.exists(),
            "test_exists": nsl_test.exists(),
            "train_records": _count_file_lines(nsl_train) if nsl_train.exists() else 0,
            "test_records": _count_file_lines(nsl_test) if nsl_test.exists() else 0,
            "model_exists": (MODEL_DIR / "xgboost_nslkdd.pkl").exists(),
        },
        "unsw-nb15": {
            "train_exists": unsw_train.exists(),
            "test_exists": unsw_test.exists(),
            "train_records": _count_file_lines(unsw_train) - 1 if unsw_train.exists() else 0,  # 减去表头
            "test_records": _count_file_lines(unsw_test) - 1 if unsw_test.exists() else 0,
            "model_exists": (MODEL_DIR / "xgboost_unsw.pkl").exists(),
        },
        "db_connections": get_table_count("connections"),
        "db_detection_results": get_table_count("detection_results"),
        "db_alerts": get_table_count("alerts"),
    }
    return info


@router.post("/train")
def trigger_training(source: str = Query("nsl-kdd", description="数据集源: nsl-kdd 或 unsw-nb15")):
    """触发模型重新训练（后台执行）"""
    global _training_in_progress

    if source not in DATASET_SOURCES:
        raise HTTPException(status_code=400, detail=f"无效数据集源: {source}")

    with _train_lock:
        if _training_in_progress:
            raise HTTPException(status_code=409, detail="模型训练正在进行中，请稍后再试")
        _training_in_progress = True

    def _train():
        global _training_in_progress
        try:
            from ml.train import train_model
            train_model(source)
        except Exception:
            logger.exception("模型训练过程中发生异常")
        finally:
            with _train_lock:
                _training_in_progress = False

    thread = threading.Thread(target=_train, daemon=True)
    thread.start()

    return {
        "message": f"模型训练已在后台启动 ({source})",
        "source": source,
    }


@router.post("/load-data")
def load_dataset(
    source: str = Query("nsl-kdd", description="数据集源: nsl-kdd 或 unsw-nb15"),
    dataset: str = Query("test", description="'train' 或 'test'"),
):
    """将数据集加载到数据库"""
    if source not in DATASET_SOURCES:
        raise HTTPException(status_code=400, detail=f"无效数据集源: {source}")
    if dataset not in ("train", "test"):
        raise HTTPException(status_code=400, detail="dataset 参数仅允许 'train' 或 'test'")

    from data_loader.loader import load_nsl_kdd, load_unsw_nb15, load_to_database

    # dataset 标识: 如 nsl-test, unsw-train
    prefix = "nsl" if source == "nsl-kdd" else "unsw"
    db_dataset = f"{prefix}-{dataset}"

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) FROM connections WHERE dataset = ?", (db_dataset,)
        ).fetchone()[0]

    if existing > 0:
        return {"message": f"数据集 '{db_dataset}' 已存在 {existing} 条记录", "loaded": False}

    if source == "nsl-kdd":
        df = load_nsl_kdd(dataset)
    else:
        df = load_unsw_nb15(dataset)

    load_to_database(df, db_dataset)

    return {"message": f"已加载 {len(df)} 条 {db_dataset} 数据", "loaded": True, "count": len(df)}


@router.delete("/clear-data")
def clear_data(table: str = Query(..., description="要清空的表名")):
    """清空指定表的数据"""
    if table not in ALLOWED_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的表名: '{table}'，允许的表: {', '.join(sorted(ALLOWED_TABLES))}",
        )
    clear_table(table)
    return {"message": f"表 '{table}' 已清空"}
