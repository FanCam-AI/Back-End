from sqlalchemy.orm import Session
import httpx
from . import crud
from infra import r2_client, redis_client
from cryptography.fernet import Fernet
from config import settings, logger
from botocore.exceptions import ClientError
from domain.token import create_result_token
import json
import uuid
import os
from httpx import ReadTimeout, RequestError

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




def save_result_service(db: Session, title, file_path, file_type, user_id):
    crud.save_result(db, title, file_path, file_type, user_id)
    return True





async def make_result_service(video_key, target_image_keys, spot_list, video_or_gif, detection_model_type, tracking_mode, drag_box, user):
    status = await redis_client.get(f"job_status:{user.id}")
    if status == "processing":
        delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
        return {"status": "processing"}

    f = Fernet(settings.FERNET_KEY)
    result_token = await create_result_token(user)
    encrypted_token = f.encrypt(result_token.encode()).decode()
    q_serverless_ready = False
    lb_serverless_ready = False

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}"
    }
    spot_list = json.loads(spot_list)
    input_data = {
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

    if tracking_mode == "normal":
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(
                    f'https://{settings.CPU_LOAD_BALANCER_SERVERLESS_URL}.api.runpod.ai/cpu_ready',
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    ready_value = data['status']
                    if ready_value == "ready":
                        lb_serverless_ready = True

                    elif ready_value == "not_ready":
                        lb_serverless_ready = False
                        raise RequestError("Not ready")

                else:
                    raise RequestError("Not ready")

        except (ReadTimeout, RequestError):
            lb_serverless_ready = False
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.get(
                        f'https://api.runpod.ai/v2/{settings.CPU_QUEUE_SERVERLESS_URL}/health',
                        headers=headers
                    )

                    if response.status_code == 200:
                        q_serverless_ready = True
                    else:
                        q_serverless_ready = False
                        delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
                        return {"status": "busy"}

            except (ReadTimeout, RequestError):
                delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
                return {"status": "busy"}

    if lb_serverless_ready:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f'https://{settings.CPU_LOAD_BALANCER_SERVERLESS_URL}.api.runpod.ai/process_run',
                    headers=headers,
                    json=input_data
                )
                if response.status_code == 200:
                    await redis_client.set(f"job_status:{user.id}", "processing", ex=300)
                    return {"status": "started"}

                else:
                    raise RequestError("Not ready")

        except (ReadTimeout, RequestError):
            delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
            return {"status": "busy"}


    elif q_serverless_ready:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f'https://api.runpod.ai/v2/{settings.CPU_QUEUE_SERVERLESS_URL}/run',
                    headers=headers,
                    json=input_data
                )
            if response.status_code == 200:

                await redis_client.set(f"job_status:{user.id}", "processing", ex=300)
                return {"status": "started"}
            else:
                delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
                return {"status": "busy"}

        except (ReadTimeout, RequestError):
            delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
            return {"status": "busy"}




    elif tracking_mode == "precision":
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(
                    f'https://{settings.GPU_LOAD_BALANCER_SERVERLESS_URL}.api.runpod.ai/gpu_ready',
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    status_value = data['status']
                    if status_value == "ready":
                        lb_serverless_ready = True

                    if status_value == "not_ready":
                        lb_serverless_ready = False
                        raise RequestError("Not ready yet")

                else:
                    raise RequestError("Not ready")

        except (ReadTimeout, RequestError):
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.get(
                        f'https://api.runpod.ai/v2/{settings.GPU_QUEUE_SERVERLESS_URL}/health',
                        headers=headers
                    )

                    if response.status_code == 200:
                        q_serverless_ready = True
                    else:
                        q_serverless_ready = False
                        delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
                        return {"status": "busy"}

            except (ReadTimeout, RequestError):
                delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
                return {"status": "busy"}

        if lb_serverless_ready:
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.post(
                        f'https://{settings.GPU_LOAD_BALANCER_SERVERLESS_URL}.api.runpod.ai/process_run',
                        headers=headers,
                        json=input_data
                    )
                    if response.status_code == 200:
                        await redis_client.set(f"job_status:{user.id}", "processing", ex=300)
                        return {"status": "started"}

                    else:
                        raise RequestError("Not ready")

            except (ReadTimeout, RequestError):
                delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
                return {"status": "busy"}

        if q_serverless_ready:
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.post(
                        f'https://api.runpod.ai/v2/{settings.GPU_QUEUE_SERVERLESS_URL}/run',
                        headers=headers,
                        json=input_data
                    )
                if response.status_code == 200:

                    await redis_client.set(f"job_status:{user.id}", "processing", ex=300)
                    return {"status": "started"}

                else:
                    delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
                    return {"status": "busy"}

            except (ReadTimeout, RequestError):
                delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
                return {"status": "busy"}
            
    delete_init_files_service(video_key, target_image_keys, settings.R2_BUCKET)
    return {"status": "busy"}

def init_video_upload_r2_service(filename, user_id):
    key = f"videos/{user_id}/{uuid.uuid4()}/{filename}"
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext == ".mov":
        content_type = "video/quicktime"
    elif ext == ".mp4":
        content_type = "video/mp4"
    elif ext == ".webm":
        content_type = "video/webm"
    else:
        content_type = "application/octet-stream"


    url = r2_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.R2_BUCKET,
            "ContentType": content_type,
            "Key": key,
        },
        ExpiresIn=200,
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
        ExpiresIn=200,
    )

    return key, url


def delete_init_files_service(video_key, target_image_keys, bucket_name):
    keys = []

    if video_key:
        keys.append(video_key)

    if target_image_keys:
        keys.extend([k for k in target_image_keys if k])

    if not keys:
        return

    try:
        r2_client.delete_objects(
            Bucket=bucket_name,
            Delete={
                "Objects": [{"Key": k} for k in keys],
                "Quiet": True
            }
        )
    except ClientError:
        logger.error("Failed to delete initial files")

async def check_ml_server_ready_service(tracking_mode):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}"
    }

    if tracking_mode == "normal":
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(
                    f'https://{settings.CPU_LOAD_BALANCER_SERVERLESS_URL}.api.runpod.ai/cpu_ready',
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    ready_value = data['status']
                    if ready_value == "ready":
                       return {"status": "ready"}

                    if ready_value == "not_ready":
                        raise RequestError("Not ready")

                else:
                    raise RequestError("Not ready")


        except (ReadTimeout, RequestError):
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.get(
                        f'https://api.runpod.ai/v2/{settings.CPU_QUEUE_SERVERLESS_URL}/health',
                        headers=headers
                    )

                    if response.status_code == 200:
                        return {"status": "ready"}
                    else:
                        return {"status": "not_ready"}

            except (ReadTimeout, RequestError):
                return {"status": "not_ready"}


    elif tracking_mode == "precision":
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(
                    f'https://{settings.GPU_LOAD_BALANCER_SERVERLESS_URL}.api.runpod.ai/gpu_ready',
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    status_value = data['status']
                    if status_value == "ready":
                        return {"status": "ready"}

                    elif status_value == "not_ready":
                        raise RequestError("Not ready")

                else:
                    raise RequestError("Not ready")

        except (ReadTimeout, RequestError):
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.get(
                        f'https://api.runpod.ai/v2/{settings.GPU_QUEUE_SERVERLESS_URL}/health',
                        headers=headers
                    )

                    if response.status_code == 200:
                        return {"status": "ready"}
                    else:
                        return {"status": "not_ready"}

            except (ReadTimeout, RequestError):
                return {"status": "not_ready"}

    return {"status": "not_ready"}