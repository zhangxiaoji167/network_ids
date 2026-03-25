"""数据集加载模块 - 支持 NSL-KDD 和 UNSW-NB15"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from config import (
    DATA_DIR,
    ALL_COLUMNS,
    ATTACK_MAP,
    UNSW_DATA_DIR,
    UNSW_FEATURE_COLUMNS,
    UNSW_ATTACK_CATEGORIES,
)
from database import get_connection

logger = logging.getLogger(__name__)


def load_nsl_kdd(dataset: str = "train") -> pd.DataFrame:
    """加载 NSL-KDD 数据集

    Args:
        dataset: 'train' 或 'test'，对应 KDDTrain+.txt 或 KDDTest+.txt

    Returns:
        包含 41 个特征 + label + attack_category + difficulty 的 DataFrame
    """
    if dataset not in ("train", "test"):
        raise ValueError(f"dataset must be 'train' or 'test', got '{dataset}'")
    filename = "KDDTrain+.txt" if dataset == "train" else "KDDTest+.txt"
    filepath = DATA_DIR / filename

    df = pd.read_csv(filepath, header=None, names=ALL_COLUMNS)

    # 将具体攻击类型映射到 5 大类
    df["attack_category"] = df["label"].str.lower().map(ATTACK_MAP).fillna("Unknown")

    return df


def load_unsw_nb15(dataset: str = "train") -> pd.DataFrame:
    """加载 UNSW-NB15 数据集

    Args:
        dataset: 'train' 或 'test'

    Returns:
        包含特征列 + label + attack_cat 的 DataFrame
    """
    if dataset not in ("train", "test"):
        raise ValueError(f"dataset must be 'train' or 'test', got '{dataset}'")
    filename = (
        "UNSW_NB15_training-set.csv"
        if dataset == "train"
        else "UNSW_NB15_testing-set.csv"
    )
    filepath = UNSW_DATA_DIR / filename

    df = pd.read_csv(filepath)

    # UNSW-NB15 的 attack_cat 列已经是类别名，只需统一列名
    # 确保 label 列是二值标签（0=Normal, 1=Attack），attack_cat 是类别名
    if "attack_cat" in df.columns:
        df["attack_category"] = df["attack_cat"].str.strip()
        # 空白或 NaN 视为 Normal
        df["attack_category"] = (
            df["attack_category"].replace("", "Normal").fillna("Normal")
        )
    elif "label" in df.columns:
        df["attack_category"] = df["label"].apply(
            lambda x: "Normal" if x == 0 else "Attack"
        )

    # 将 label 列统一为攻击类别名（兼容通用逻辑）
    df["label"] = df["attack_category"]

    # 填充缺失值
    for col in UNSW_FEATURE_COLUMNS:
        if col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].fillna("-")
            else:
                df[col] = df[col].fillna(0)

    return df


def load_to_database(df: pd.DataFrame, dataset: str = "train") -> None:
    """将 DataFrame 存入 SQLite connections 表

    Args:
        df: 包含数据的 DataFrame
        dataset: 数据集标识（如 'nsl-train', 'nsl-test', 'unsw-train', 'unsw-test'）
    """
    df_to_store = df.copy()
    df_to_store["dataset"] = dataset

    # 兼容 UNSW-NB15 列名，映射到 connections 表可视化字段
    if "duration" not in df_to_store.columns and "dur" in df_to_store.columns:
        df_to_store["duration"] = df_to_store["dur"]
    if "protocol_type" not in df_to_store.columns and "proto" in df_to_store.columns:
        df_to_store["protocol_type"] = df_to_store["proto"]
    if "flag" not in df_to_store.columns and "state" in df_to_store.columns:
        df_to_store["flag"] = df_to_store["state"]
    if "src_bytes" not in df_to_store.columns and "sbytes" in df_to_store.columns:
        df_to_store["src_bytes"] = df_to_store["sbytes"]
    if "dst_bytes" not in df_to_store.columns and "dbytes" in df_to_store.columns:
        df_to_store["dst_bytes"] = df_to_store["dbytes"]

    conn = get_connection()
    try:
        table_cols = [
            row[1] for row in conn.execute("PRAGMA table_info(connections)").fetchall()
        ]

        # 由数据库自增主键生成 id，避免外部数据集自带 id 干扰
        if "id" in df_to_store.columns:
            df_to_store = df_to_store.drop(columns=["id"])

        # 补齐缺失列并按表结构筛选，避免出现未知列插入失败
        for col in table_cols:
            if col == "id":
                continue
            if col not in df_to_store.columns:
                df_to_store[col] = None

        insert_cols = [c for c in table_cols if c != "id"]
        df_to_store[insert_cols].to_sql(
            "connections", conn, if_exists="append", index=False
        )
    finally:
        conn.close()
