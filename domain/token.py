from fastapi import Depends
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from authlib.jose import jwt
from database import get_db
import user.crud as crud
from models import User
from authlib.jose import JoseError
from fastapi import Request, Header, HTTPException
from config import settings
from infra import redis_client
import hashlib
import secrets
import json
import base64

def _resolve_user_and_token(
    request: Request,
    db: Session,
    authorization: str | None
):
    token = request.cookies.get("access_token")

    # 2. Authorization 헤더 (앱)
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if not token:
        raise HTTPException(status_code=401, detail="Access token missing")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY)
        payload.validate()
        user_id = payload.get("sub")
    except JoseError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = crud.get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user, token


def get_current_user_and_token(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    user, token = _resolve_user_and_token(request, db, authorization)
    return user, token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    user, _ = _resolve_user_and_token(request, db, authorization)
    return user



def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()



async def create_result_token(user: User):
    header = {
        "alg": settings.ALGORITHM,
        "typ": "JWT"
    }

    access_payload = {
        "sub": user.id,
        "type": "result",
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )).timestamp())
    }

    result_token = jwt.encode(
        header,
        access_payload,
        settings.SECRET_KEY
    ).decode("utf-8")

    return result_token



async def create_refresh_token(user: User):
    header = {
        "alg": settings.ALGORITHM,
        "typ": "JWT"
    }

    refresh_payload = {
        "sub": user.id,
        "type": "refresh",
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )).timestamp())
    }


    refresh_token = jwt.encode(
        header,
        refresh_payload,
        settings.SECRET_KEY
    ).decode("utf-8")

    token_hash = hash_token(refresh_token)
    await redis_client.set(f"refresh_token:{token_hash}", user.id, ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    return refresh_token


async def create_access_token(user: User):
    header = {
        "alg": settings.ALGORITHM,
        "typ": "JWT"
    }

    access_payload = {
        "sub": user.id,
        "type": "access",
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )).timestamp())
    }

    access_token = jwt.encode(
        header,
        access_payload,
        settings.SECRET_KEY
    ).decode("utf-8")

    return access_token


async def create_auth_code(user_id, code_challenge):
    code = secrets.token_urlsafe(32)

    data = {
        "user_id": user_id,
        "code_challenge": code_challenge
    }

    await redis_client.set(f"auth_code:{code}", json.dumps(data), ex=60)
    return code


async def validate_code(code, code_verifier):
    key = f"auth_code:{code}"

    data = await redis_client.get(key)
    if not data:
        return None


    data = json.loads(data)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()


    if challenge != data["code_challenge"]:
        return None

    await redis_client.delete(key)

    return data["user_id"]