import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.system_manager import get_system_status, get_environment_check_task, start_environment_check_task
from app.core.init_manager import start_auto_fix_task, get_auto_fix_task, get_auto_fix_log_path

router = APIRouter()


@router.get("/status")
async def api_system_status():
    status = get_system_status()
    return {"code": 0, "message": "ok", "data": status}


@router.get("/checks")
async def api_system_checks():
    task = get_environment_check_task()
    return {"code": 0, "message": "ok", "data": task}


@router.post("/checks")
async def api_start_system_checks():
    task = start_environment_check_task()
    return {"code": 0, "message": "ok", "data": task}


@router.post("/fix")
async def api_system_fix():
    task = start_auto_fix_task()
    return {"code": 0, "message": "ok", "data": task}


@router.get("/fix/current")
async def api_system_fix_current():
    task = get_auto_fix_task()
    return {"code": 0, "message": "ok", "data": task}


@router.get("/fix/{task_id}")
async def api_system_fix_status(task_id: str):
    task = get_auto_fix_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="修复任务不存在")
    return {"code": 0, "message": "ok", "data": task}


@router.get("/fix/{task_id}/log")
async def api_system_fix_log(task_id: str):
    log_path = get_auto_fix_log_path(task_id)
    if not log_path or not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="修复日志不存在")
    return FileResponse(log_path, media_type="text/plain", filename=os.path.basename(log_path))
