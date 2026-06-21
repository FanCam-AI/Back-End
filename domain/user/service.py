from infra import client_secret, r2_client
from models import User
from . import crud
from config import settings
from sqlalchemy.orm import Session
from fastapi import HTTPException
import httpx
from config import logger
from sqlalchemy.exc import SQLAlchemyError
from botocore.exceptions import ClientError


async def delete_user_account(db: Session, user: User):
    try:
        if user.apple_refresh_token:
            await revoke_apple_token(user)
            user.apple_refresh_token = ""

        results = crud.get_results_by_user(db, user.id)
        crud.delete_results_by_user(db, user.id)
        crud.delete_user(db, user)

        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    for result in results:
        file_path = result.file_path
        try:
            r2_client.delete_object(
                Bucket=settings.R2_BUCKET,
                Key=file_path
            )
        except ClientError:
            logger.warning(f"Failed to delete r2 object, key: {file_path}")


async def revoke_apple_token(user: User):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://appleid.apple.com/auth/revoke",
            data={
                "client_id": settings.APPLE_CLIENT_ID,
                "client_secret": client_secret,
                "token": user.apple_refresh_token,
                "token_type_hint": "refresh_token"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Internal server error")


def read_user_me_srvice(db: Session, user_id):
    try:
        user = crud.get_user_by_id(db, user_id)
        if not user:
            logger.error(f"user not found, user_id: {user_id}")
        subscription = crud.get_subscription_by_user_id(db, user_id)
        result_count = crud.get_result_count_by_user_id(db, user_id)

    except Exception:
        logger.error(f"user not found error")
        raise

    return {
        "username": user.username,
        "user_id": user_id,
        "subscription_plan":subscription.plan,
        "result_count": result_count,
        "app_version": settings.APP_VERSION,
    }


def check_user_premium_service(db: Session, current_plan, user_id):
    user = crud.get_user_by_id(db, user_id)
    protection_password = settings.PROTECTION_PASSWORD
    is_updated = False
    if not user:
        raise

    if current_plan == "FREE" or current_plan == "":
        updated = crud.protect_results_by_user(
            db,
            user_id,
            protection_password
        )

        if updated:
            db.commit()
            count = crud.count_results_by_user(db, user_id)
            if count > 0:
                is_updated = True

    return {
        "username": user.username,
        "create_count": user.create_count,
        "is_updated": is_updated,
    }