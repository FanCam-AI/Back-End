from fastapi import APIRouter, Depends, Request, Header
from sqlalchemy.orm import Session
from database import get_db
from models import User
from fastapi import HTTPException, Form
from botocore.exceptions import ClientError
from sqlalchemy.exc import SQLAlchemyError
from config import settings, logger
from infra import r2_client
from . import service, crud
from datetime import datetime, timezone


subscribe_router = APIRouter(prefix="/subscribe")


@subscribe_router.post("/revenuecat/webhook")
async def revenuecat_webhook(
    request: Request,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
):
    if authorization != settings.REVENUECAT_WEBHOOK_SECRET:
        raise HTTPException(401)

    payload = await request.json()
    event = payload["event"]

    event_type = event["type"]
    user_id = int(event["app_user_id"])
    user = crud.get_user_by_id(db, user_id)
    subscription = crud.get_subscription_by_user_id(db, user_id)

    expiration_at_ms = event.get("expiration_at_ms")
    if expiration_at_ms:
        expires_at = datetime.fromtimestamp(expiration_at_ms / 1000, tz=timezone.utc)
    else:
        expires_at = subscription.expires_at

    if not user:
        raise HTTPException(404, "User not found")

    if event_type == "INITIAL_PURCHASE":
        plan = "premium"
        crud.sync_subscription(db, subscription, expires_at, plan)

    elif event_type == "EXPIRATION":
        plan = "free"
        crud.sync_subscription(db, subscription, expires_at, plan)

        try:
            results = crud.get_results_by_user(db, user.id)

            crud.delete_results_by_user(db, user.id)
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


    elif event_type == "RENEWAL":
        plan = "premium"
        crud.sync_subscription(db, subscription, expires_at, plan)

    return {"ok": True}
