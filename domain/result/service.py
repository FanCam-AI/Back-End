from sqlalchemy.orm import Session
import httpx
from sqlalchemy.exc import SQLAlchemyError
from . import crud
from infra import r2_client, redis_client
from cryptography.fernet import Fernet
from config import settings, logger
from botocore.exceptions import ClientError
from domain.token import create_result_token
import json
import uuid
import os

async def result_reset_status(user_id):
    await redis_client.delete(f"job_status:{user_id}")
    await redis_client.delete(f"job_progress:{user_id}")
    return {"status": "cleared"}


async def result_status(user_id):
    status = await redis_client.get(f"job_status:{user_id}")
    progress = await redis_client.get(f"job_progress:{user_id}")
    return {
            "status": status or "none",
            "progress": progress or "none",
            }


def delete_result_by_id(db: Session, result_id, user_id):
    try:
        result = crud.get_result_by_id(db, result_id, user_id)
        if not result:
            logger.warning(f"Result not found: {result_id}")
    except Exception:
        raise

    try:
        crud.delete_result(db, result)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    if result.file_path:
        try:
            r2_client.delete_object(
                Bucket=settings.R2_BUCKET,
                Key=result.file_path
            )
        except ClientError:
            logger.warning(f"Failed to delete r2 object, key: {result.file_path}")

    return {"message": "Done"}


def save_result_service(db: Session, title, file_path, file_type, user_id):
    crud.save_result(db, title, file_path, file_type, user_id)
    return True


async def make_result_service(video_key, target_image_keys, spot_list, video_or_gif, detection_model_type, tracking_mode, drag_box, user):
    f = Fernet(settings.FERNET_KEY)
    result_token = await create_result_token(user)
    encrypted_token = f.encrypt(result_token.encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}"
    }
    spot_list = json.loads(spot_list)
    data = {
        "input": {
            "video_key": video_key,
            "target_image_keys": target_image_keys,
            "spot_list": spot_list,
            "video_or_gif": video_or_gif,
            "detection_model_name": detection_model_type,
            "tracking_mode": tracking_mode,
            "drag_box": drag_box,
            "encrypted_token": encrypted_token
        }
    }


    async with httpx.AsyncClient() as client:
        response = await client.post(
            f'https://api.runpod.ai/v2/{settings.RUNPOD_URL}/run',
            headers=headers,
            json=data
        )

    await redis_client.set(f"job_status:{user.id}", "processing", ex=25200)

    return {"status": "started"}


def init_video_upload_r2_service(filename, user_id):
    key = f"videos/{user_id}/{uuid.uuid4()}/{filename}"
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
            "ContentType": content_type,
            "Key": key,
        },
        ExpiresIn=600,  # 10분
    )
    return key, url


def init_image_upload_r2_service(filename, user_id):
    key = f"images/{user_id}/{uuid.uuid4()}/{filename}"
    url = r2_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.R2_BUCKET,
            "Key": key,
        },
        ExpiresIn=600,
    )

    return key, url