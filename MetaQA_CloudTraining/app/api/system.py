from fastapi import APIRouter

from app.core.system_manager import get_system_status, run_environment_checks

router = APIRouter()


@router.get("/status")
async def api_system_status():
    status = get_system_status()
    return {"code": 0, "message": "ok", "data": status}


@router.get("/checks")
async def api_system_checks():
    checks = run_environment_checks()
    return {"code": 0, "message": "ok", "data": {"status": "ready", "checks": checks}}


@router.post("/fix")
async def api_system_fix():
    from app.core.init_manager import auto_fix
    auto_fix()
    checks = run_environment_checks()
    return {"code": 0, "message": "ok", "data": {"status": "ready", "checks": checks}}
