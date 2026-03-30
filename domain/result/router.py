from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import User
from fastapi import HTTPException, Form
from typing import Optional
from domain.token import get_current_user
from . import service


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

@result_router.post("/check_ml_server_ready")
async def check_ml_server_ready(tracking_mode: str = "normal", current_user: User = Depends(get_current_user)):
    try:
        response = service.check_ml_server_ready_service(tracking_mode)

    except HTTPException:
        raise HTTPException(status_code=404, detail="ml server not ready")

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
    tracking_mode: str = Form("normal"),
    drag_box: Optional[List[int]] = Form(None),
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
    key, url = service.init_video_upload_r2_service(filename, current_user.id)

    return {
        "key": key,
        "url": url
    }

@result_router.post("/init_image_upload")
async def init_image_upload(
    filename: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    key, url = service.init_image_upload_r2_service(filename, current_user.id)

    return {
        "key": key,
        "url": url,
    }