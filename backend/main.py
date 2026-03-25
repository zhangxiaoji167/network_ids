"""FastAPI 应用入口"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# 确保 backend 目录在 sys.path 中
_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import API_HOST, API_PORT, RULES_DIR, DATASET_SOURCES
from database import init_db
from detection.rule_engine import RuleEngine
from detection.ml_engine import MLEngine
from detection.hybrid_engine import HybridEngine
from api.routes_dashboard import router as dashboard_router
from api.routes_analysis import router as analysis_router
from api.routes_detection import router as detection_router
from api.routes_model import router as model_router
from api.routes_system import router as system_router


# 全局引擎实例（按数据集源索引）
rule_engine: RuleEngine | None = None
_ml_engines: dict[str, MLEngine] = {}
_hybrid_engines: dict[str, HybridEngine] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库和引擎"""
    global rule_engine

    # 初始化数据库
    print("[main] 初始化数据库...")
    init_db()

    # 初始化规则引擎（规则引擎与数据集无关，共用一个）
    print("[main] 加载规则引擎...")
    rule_engine = RuleEngine(RULES_DIR)

    # 为每个数据集加载 ML 引擎和混合引擎
    for source in DATASET_SOURCES:
        print(f"[main] 加载 ML 引擎 ({source})...")
        ml_eng = MLEngine(source=source)
        if ml_eng.load():
            _ml_engines[source] = ml_eng
            _hybrid_engines[source] = HybridEngine(rule_engine, ml_eng)
            print(f"[main] {source} 引擎初始化完成")
        else:
            print(f"[main] {source} 模型不存在，跳过")

    print(f"[main] 引擎初始化完成，可用数据集: {list(_ml_engines.keys())}")

    yield

    print("[main] 应用关闭")


app = FastAPI(
    title="网络协议分析与入侵检测系统",
    description="基于 NSL-KDD / UNSW-NB15 数据集的混合入侵检测系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件：默认允许本地前端，可通过环境变量 ALLOWED_ORIGINS 扩展
_allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(dashboard_router)
app.include_router(analysis_router)
app.include_router(detection_router)
app.include_router(model_router)
app.include_router(system_router)

# 生产环境：挂载前端 dist 静态文件
_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_DIST_DIR), html=True), name="static")


def get_engines(source: str = "nsl-kdd"):
    """获取指定数据集的引擎实例（供 API 路由使用）"""
    ml_eng = _ml_engines.get(source)
    hybrid_eng = _hybrid_engines.get(source)
    return rule_engine, ml_eng, hybrid_eng


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
