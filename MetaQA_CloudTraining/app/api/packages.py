from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.package_manager import list_packages, get_package, create_package, delete_package, download_package

router = APIRouter()


@router.get("")
async def api_list_packages():
    pkgs = list_packages()
    return {"code": 0, "message": "ok", "data": {"packages": pkgs, "total": len(pkgs)}}


@router.get("/{pkg_id}")
async def api_get_package(pkg_id: str):
    pkg = get_package(pkg_id)
    if not pkg:
        return {"code": 404, "message": "产物包不存在", "data": None}
    return {"code": 0, "message": "ok", "data": pkg}


@router.post("")
async def api_create_package(body: dict):
    try:
        pkg = create_package(body["task_id"])
        return {"code": 0, "message": "ok", "data": pkg}
    except ValueError as e:
        return {"code": 400, "message": str(e), "data": None}
    except Exception as e:
        return {"code": 500, "message": str(e), "data": None}


@router.delete("/{pkg_id}")
async def api_delete_package(pkg_id: str):
    ok = delete_package(pkg_id)
    if not ok:
        return {"code": 404, "message": "产物包不存在", "data": None}
    return {"code": 0, "message": "ok", "data": None}


@router.get("/{pkg_id}/download")
async def api_download_package(pkg_id: str):
    file_path = download_package(pkg_id)
    if not file_path:
        return {"code": 404, "message": "文件不存在", "data": None}
    return FileResponse(file_path, filename=file_path.split("/")[-1].split("\\")[-1])
