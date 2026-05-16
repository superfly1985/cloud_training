from pydantic import BaseModel, Field
from typing import Optional, List


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Optional[dict | list | None] = None


class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    split_ratio: float = Field(default=0.8, ge=0.5, le=0.95)


class DatasetInfo(BaseModel):
    id: str
    name: str
    image_count: int = 0
    annotated_count: int = 0
    classes: List[str] = []
    total_size: int = 0
    created_at: str
    updated_at: str


class ImageInfo(BaseModel):
    id: str
    filename: str
    size: int = 0
    width: int = 0
    height: int = 0
    annotated: bool = False
    split_type: str = ""


class TrainingCreate(BaseModel):
    dataset_id: str
    model_size: str = Field(default="n", pattern="^[nsmxl]$")
    input_size: int = Field(default=640)
    epochs: int = Field(default=100, ge=1, le=1000)
    batch_size: int = Field(default=16)
    learning_rate: float = Field(default=0.01, ge=0.0001, le=1.0)
    device: str = Field(default="cuda:0")


class TrainingInfo(BaseModel):
    id: str
    dataset_name: str
    dataset_id: str
    version: str
    model_size: str = "n"
    input_size: int = 640
    epochs: int = 100
    current_epoch: int = 0
    batch_size: int = 16
    learning_rate: float = 0.01
    device: str = "cuda:0"
    status: str = "pending"
    map50: float = 0
    map50_95: float = 0
    box_loss: float = 0
    cls_loss: float = 0
    dfl_loss: float = 0
    created_at: str
    started_at: str = ""
    completed_at: str = ""


class PackageInfo(BaseModel):
    id: str
    name: str
    dataset_name: str
    version: str
    size: int = 0
    map_val: float = 0
    box_loss: Optional[float] = None
    cls_loss: Optional[float] = None
    dfl_loss: Optional[float] = None
    training_time: str = ""
    created_at: str
    files: List[dict] = []


class UploadInit(BaseModel):
    filename: str
    total_size: int
    chunk_size: int = 5 * 1024 * 1024


class UploadChunk(BaseModel):
    session_id: str
    chunk_index: int


class SystemCheckItem(BaseModel):
    name: str
    status: str
    message: str
    auto_fixable: bool = False
