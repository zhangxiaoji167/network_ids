"""Analysis API - 协议分析与特征统计"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, Query, HTTPException
from analyzer.protocol_analyzer import (
    get_protocol_distribution,
    get_service_distribution,
    get_attack_distribution,
    get_flag_distribution,
    get_attack_protocol_cross,
)
from analyzer.feature_analyzer import (
    get_traffic_stats,
    get_feature_comparison,
    get_feature_by_attack_type,
    get_correlation_matrix,
)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/protocol-distribution")
def protocol_distribution(dataset: str | None = Query(None)):
    """协议类型分布 (TCP/UDP/ICMP)"""
    return get_protocol_distribution(dataset)


@router.get("/service-distribution")
def service_distribution(
    top_n: int = Query(15, ge=1, le=100),
    dataset: str | None = Query(None),
):
    """服务类型分布 (Top N)"""
    return get_service_distribution(top_n, dataset)


@router.get("/attack-distribution")
def attack_distribution(dataset: str | None = Query(None)):
    """攻击类型分布"""
    return get_attack_distribution(dataset)


@router.get("/flag-distribution")
def flag_distribution(dataset: str | None = Query(None)):
    """连接标志分布"""
    return get_flag_distribution(dataset)


@router.get("/feature-stats")
def feature_stats(dataset: str | None = Query(None)):
    """流量特征统计"""
    return get_traffic_stats(dataset)


@router.get("/feature-comparison")
def feature_comparison(dataset: str | None = Query(None)):
    """攻击 vs 正常流量特征对比"""
    return get_feature_comparison(dataset)


@router.get("/feature-by-attack")
def feature_by_attack(
    feature: str = Query(..., description="特征名"),
    dataset: str | None = Query(None),
):
    """指定特征在各攻击类型中的统计"""
    try:
        return get_feature_by_attack_type(feature, dataset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/correlation-matrix")
def correlation_matrix(dataset: str | None = Query(None)):
    """特征相关性矩阵"""
    return get_correlation_matrix(dataset=dataset)


@router.get("/attack-protocol-cross")
def attack_protocol_cross(dataset: str | None = Query(None)):
    """攻击类型 × 协议类型交叉统计"""
    return get_attack_protocol_cross(dataset)
