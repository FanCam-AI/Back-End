from fastapi import APIRouter, Depends, Request, Header
from sqlalchemy.orm import Session
from database import get_db
from models import User
from fastapi import HTTPException, Form
from sqlalchemy.exc import SQLAlchemyError
from config import settings
from domain.token import get_current_user
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

    elif event_type == "RENEWAL":
        plan = "premium"
        crud.sync_subscription(db, subscription, expires_at, plan)

    return {"ok": True}



# 처리 할 이벤트? 첫번째 구독, 두번째 취소, 세번째 재구독, 네번째 환불 정도 애초에 이벤트 최대한 대응하게 if로 다 만들어도 될 듯?
# 그리고 이제 이거 해서 만약 구독 취소 이벤트나 환불 들어오면 해당 날짜에 맞춰서 Result 잠그고 삭제하는 로직까지

# 레비뉴켓에서 웹훅 받아서 DB 업데이트 하는 거 하고. 이제 그 구독 상태에 따라 결과물 잠그고 삭제 하는 거 추가하고, 또 user/me에서 id도 보내고 또 구독 정보도 보내게
# 그런데 user/me에서 안하고 새롭게 만들까 생각중 그러면 이제 좀 느려지긴 하지.
# 아 왜케 아직도 방어기재가 깔려있지 건들기가 싫어 기존 코드를.. 하지만 바꿔야해 변해야해 적용해야해