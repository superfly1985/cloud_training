import os

from fastapi import APIRouter, UploadFile, File

from app.core.upload_manager import init_upload, upload_chunk, complete_upload, get_upload_status
from app.core.dataset_manager import import_zip, merge_dataset

router = APIRouter()


@router.post("/init")
async def api_upload_init(body: dict):
    try:
        result = init_upload(
            filename=body["filename"],
            total_size=body["total_size"],
            chunk_size=body.get("chunk_size", 5 * 1024 * 1024),
        )
        return {"code": 0, "message": "ok", "data": result}
    except Exception as e:
        return {"code": 500, "message": str(e), "data": None}


@router.post("/chunk")
async def api_upload_chunk(
    session_id: str,
    chunk_index: int,
    file: UploadFile = File(...),
):
    try:
        chunk_data = await file.read()
        result = upload_chunk(session_id, chunk_index, chunk_data)
        return {"code": 0, "message": "ok", "data": result}
    except ValueError as e:
        return {"code": 400, "message": str(e), "data": None}
    except Exception as e:
        return {"code": 500, "message": str(e), "data": None}


@router.post("/complete")
async def api_upload_complete(body: dict):
    try:
        session_id = body["session_id"]
        file_path = complete_upload(session_id)

        ds_id = body.get("dataset_id")
        action = body.get("action", "create")

        if ds_id:
            if action == "merge":
                result = merge_dataset(ds_id, file_path)
            else:
                result = import_zip(ds_id, file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
            return {"code": 0, "message": "ok", "data": result}

        return {"code": 0, "message": "ok", "data": {"file_path": file_path}}
    except ValueError as e:
        return {"code": 400, "message": str(e), "data": None}
    except Exception as e:
        return {"code": 500, "message": str(e), "data": None}


@router.get("/status/{session_id}")
async def api_upload_status(session_id: str):
    status = get_upload_status(session_id)
    if not status:
        return {"code": 404, "message": "上传会话不存在", "data": None}
    return {"code": 0, "message": "ok", "data": status}
