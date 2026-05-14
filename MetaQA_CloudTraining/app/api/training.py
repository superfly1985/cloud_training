from fastapi import APIRouter

from app.core.training_manager import list_tasks, get_task, create_task, stop_task
from app.core.monitor_manager import get_training_log, get_loss_curve, refresh_task_metrics

router = APIRouter()


@router.get("")
async def api_list_tasks():
    tasks = list_tasks()
    return {"code": 0, "message": "ok", "data": {"tasks": tasks, "total": len(tasks)}}


@router.get("/{task_id}")
async def api_get_task(task_id: str):
    task = get_task(task_id)
    if not task:
        return {"code": 404, "message": "任务不存在", "data": None}
    return {"code": 0, "message": "ok", "data": task}


@router.post("")
async def api_create_task(body: dict):
    try:
        task = create_task(body)
        return {"code": 0, "message": "ok", "data": task}
    except ValueError as e:
        return {"code": 400, "message": str(e), "data": None}
    except Exception as e:
        return {"code": 500, "message": str(e), "data": None}


@router.post("/{task_id}/stop")
async def api_stop_task(task_id: str):
    ok = stop_task(task_id)
    if not ok:
        return {"code": 400, "message": "无法停止任务", "data": None}
    return {"code": 0, "message": "ok", "data": None}


@router.get("/{task_id}/log")
async def api_get_log(task_id: str):
    log = get_training_log(task_id)
    return {"code": 0, "message": "ok", "data": {"log": log}}


@router.get("/{task_id}/curve")
async def api_get_curve(task_id: str):
    curve = get_loss_curve(task_id)
    return {"code": 0, "message": "ok", "data": curve}


@router.post("/{task_id}/refresh")
async def api_refresh_metrics(task_id: str):
    metrics = refresh_task_metrics(task_id)
    if not metrics:
        return {"code": 404, "message": "无法刷新指标", "data": None}
    return {"code": 0, "message": "ok", "data": metrics}
