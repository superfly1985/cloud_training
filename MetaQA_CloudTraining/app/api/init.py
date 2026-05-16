from fastapi import APIRouter

from app.core.init_manager import run_init, start_auto_fix_task, get_auto_fix_task

router = APIRouter()


@router.post("/run")
async def api_run_init():
    result = run_init()
    return {"code": 0, "message": "ok", "data": result}


@router.post("/auto-fix")
async def api_auto_fix():
    result = start_auto_fix_task()
    return {"code": 0, "message": "ok", "data": result}


@router.get("/auto-fix/{task_id}")
async def api_auto_fix_status(task_id: str):
    result = get_auto_fix_task(task_id)
    return {"code": 0, "message": "ok", "data": result}
