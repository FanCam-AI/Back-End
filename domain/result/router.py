from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import User
from fastapi import HTTPException, Form
from typing import Optional
from domain.token import get_current_user
from . import service
from infra import r2_client
from config import settings, logger
import uuid, os

result_router = APIRouter(prefix="/result")


@result_router.post("/reset_status")
async def reset_status(current_user: User = Depends(get_current_user)):
    try:
        status = await service.result_reset_status(user_id=current_user.id)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to reset status")
    return status


@result_router.get("/status")
async def get_processing_status(current_user: User = Depends(get_current_user)):
    status = await service.result_status(user_id=current_user.id)
    return status

@result_router.delete("/{result_id}")
async def delete_result(result_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        response = service.delete_result_by_id(db, result_id, current_user.id)

    except HTTPException:
        raise HTTPException(status_code=404, detail="Result not found")

    return response


@result_router.post("/save_result")
async def save_result(
    title: str = Form(""),
    file_path: str = Form(...),
    file_type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = service.save_result_service(db, title, file_path, file_type, current_user.id)
    return {
        "success": success
    }


@result_router.post("/make_result")
async def make_result_video_or_gif(
    video_key: str = Form(...),
    target_image_keys: Optional[List[str]] = Form(None),
    spot_list: str = Form(...),
    video_or_gif: str = Form(...),
    detection_model_type: str = Form(...),
    tracking_mode: str = Form("precision"),
    drag_box: Optional[List[str]] = Form(None),
    current_user: User = Depends(get_current_user)
):
    status = await service.make_result_service(video_key=video_key, target_image_keys=target_image_keys,
                                               spot_list=spot_list, video_or_gif=video_or_gif,
                                               detection_model_type=detection_model_type,tracking_mode=tracking_mode,
                                               drag_box=drag_box, user=current_user)

    return status


@result_router.post("/init_video_upload")
async def init_video_upload(
    filename: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    key = f"videos/{current_user.id}/{uuid.uuid4()}/{filename}"
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext == ".mov":
        content_type = "video/quicktime"
    elif ext == ".mp4":
        content_type = "video/mp4"
    else:
        content_type = "application/octet-stream"

    url = r2_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.R2_BUCKET,
            "Key": key,
        },
        ExpiresIn=600,  # 10분
    )

    logger.info(f"Generated content_type: {content_type} for filename: {filename}")

    return {
        "key": key,
        "url": url
    }

@result_router.post("/init_image_upload")
async def init_image_upload(
    filename: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    try:
        key = f"images/{current_user.id}/{uuid.uuid4()}/{filename}"

        url = r2_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": settings.R2_BUCKET,
                "Key": key,
            },
            ExpiresIn=600,
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "key": key,
        "url": url,
    }