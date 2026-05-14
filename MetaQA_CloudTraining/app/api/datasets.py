import os
import tempfile
import mimetypes

from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.core.dataset_manager import list_datasets, get_dataset, create_dataset, delete_dataset, list_images, delete_images, import_zip, get_class_names, get_image_labels
from app.config import get_data_dir

router = APIRouter()


@router.get("")
async def api_list_datasets():
    ds_list = list_datasets()
    return {"code": 0, "message": "ok", "data": {"datasets": ds_list, "total": len(ds_list)}}


@router.post("/import")
async def api_import_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    split_ratio: float = Form(0.8),
):
    try:
        ds = create_dataset(name, split_ratio)
        ds_id = ds["id"]

        suffix = os.path.splitext(file.filename)[1] or ".zip"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(tmp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        result = import_zip(ds_id, tmp_path)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        return {"code": 0, "message": "ok", "data": {"dataset_id": ds_id, "imported": result["imported"]}}
    except ValueError as e:
        return {"code": 400, "message": str(e), "data": None}
    except Exception as e:
        return {"code": 500, "message": str(e), "data": None}


@router.get("/{ds_id}")
async def api_get_dataset(ds_id: str):
    ds = get_dataset(ds_id)
    if not ds:
        return {"code": 404, "message": "数据集不存在", "data": None}
    return {"code": 0, "message": "ok", "data": ds}


@router.post("")
async def api_create_dataset(body: dict):
    try:
        ds = create_dataset(body["name"], body.get("split_ratio", 0.8))
        return {"code": 0, "message": "ok", "data": ds}
    except ValueError as e:
        return {"code": 400, "message": str(e), "data": None}


@router.delete("/{ds_id}")
async def api_delete_dataset(ds_id: str):
    ok = delete_dataset(ds_id)
    if not ok:
        return {"code": 404, "message": "数据集不存在", "data": None}
    return {"code": 0, "message": "ok", "data": None}


@router.get("/{ds_id}/class-names")
async def api_class_names(ds_id: str):
    names = get_class_names(ds_id)
    return {"code": 0, "message": "ok", "data": names}


@router.get("/{ds_id}/images")
async def api_list_images(ds_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = list_images(ds_id, page, page_size)
    return {"code": 0, "message": "ok", "data": result}


@router.delete("/{ds_id}/images")
async def api_delete_images(ds_id: str, body: dict):
    image_ids = body.get("image_ids", [])
    count = delete_images(ds_id, image_ids)
    return {"code": 0, "message": "ok", "data": {"deleted": count}}


@router.get("/{ds_id}/images/{filename:path}/labels")
async def api_image_labels(ds_id: str, filename: str):
    labels = get_image_labels(ds_id, filename)
    class_names = get_class_names(ds_id)
    return {"code": 0, "message": "ok", "data": {"labels": labels, "class_names": class_names}}


@router.get("/{ds_id}/images/{filename:path}/file")
async def api_image_file(ds_id: str, filename: str):
    ds_dir = get_data_dir("datasets_path")
    img_path = os.path.join(ds_dir, ds_id, "images", filename)
    if not os.path.isfile(img_path):
        return {"code": 404, "message": "图片不存在", "data": None}
    mime_type, _ = mimetypes.guess_type(img_path)
    return FileResponse(img_path, media_type=mime_type or "image/jpeg")
