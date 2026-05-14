from fastapi import APIRouter

from app.core.init_manager import run_init, auto_fix

router = APIRouter()


@router.post("/run")
async def api_run_init():
    result = run_init()
    return {"code": 0, "message": "ok", "data": result}


@router.post("/auto-fix")
async def api_auto_fix():
    result = auto_fix()
    return {"code": 0, "message": "ok", "data": result}
