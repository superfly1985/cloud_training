import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import load_config, PROJECT_ROOT
from app.models.database import init_tables, close_connection
from app.utils.logger import get_logger
from app.utils.helpers import ensure_dir
from app.config import get_data_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = get_logger()
    logger.info("启动中，加载配置...")
    load_config()
    for key in ("datasets_path", "runs_path", "pretrained_path", "temp_path", "logs_path", "db_path"):
        get_data_dir(key)
    init_tables()
    logger.info("数据库初始化完成")
    yield
    close_connection()
    logger.info("已关闭")


app = FastAPI(title="MetaQA CloudTraining", version="1.0.0", lifespan=lifespan)

from app.api import datasets, upload, training, packages, system, init as init_router

app.include_router(init_router.router, prefix="/api/v1/init", tags=["init"])
app.include_router(datasets.router, prefix="/api/v1/datasets", tags=["datasets"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(training.router, prefix="/api/v1/training", tags=["training"])
app.include_router(packages.router, prefix="/api/v1/packages", tags=["packages"])
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])

static_dir = os.path.join(PROJECT_ROOT, "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def serve_index():
    index_path = os.path.join(PROJECT_ROOT, "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "MetaQA CloudTraining API running"}
