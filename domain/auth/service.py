from infra import client_secret, oauth_google, oauth_apple, redis_client
from . import crud, schema
from config import settings
from sqlalchemy.orm import Session
from fastapi import HTTPException
import httpx
from authlib.jose import jwt
from authlib.jose import JoseError
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
from domain.token import create_refresh_token, create_access_token, create_auth_code, validate_code, hash_token


async def apple_callback_service(db: Session, code, expected_nonce):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://appleid.apple.com/auth/token",
            data={
                "client_id": settings.APPLE_CLIENT_ID,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.APPLE_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    token = token_resp.json()
    apple_refresh_token = token.get("refresh_token")

    user_oauth = await oauth_apple.apple.parse_id_token(token, nonce=expected_nonce)
    username, email, user = get_user_info(db, user_oauth)
    if not user:
        user = crud.create_user(db, schema.UserCreate(
            username=username,
            email=email,
            create_count=0,
            apple_refresh_token=apple_refresh_token,

        ))

    return user


async def oauth_callback_return(platform, code_challenge, user):
    access_token = await create_access_token(user)
    refresh_token = await create_refresh_token(user)

    if platform == "app":
        code = await create_auth_code(user.id, code_challenge)
        params = urlencode({"code": code})

        return RedirectResponse(
            url=f"fancamai://callback?{params}"
        )

    else:
        response = RedirectResponse(url="/")
        response.set_cookie("access_token", access_token, httponly=True,
                            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, secure=True, samesite="strict")
        response.set_cookie("refresh_token", refresh_token, httponly=True,
                            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, secure=True, samesite="strict")

        return response


async def google_callback_service(db: Session, id_token, nonce):
    user_oauth = await oauth_google.google.parse_id_token(id_token, nonce=nonce)
    username, email, user = get_user_info(db, user_oauth)
    if not user:
        user = crud.create_user(db, schema.UserCreate(
            username=username,
            email=email,
            create_count=0,
            apple_refresh_token="",
        ))

    return user


def get_user_info(db: Session, user_oauth):
    user_info = dict(user_oauth)
    email = user_info.get("email")
    if email is None:
        email = "example@email.com"
    username = email.split("@")[0]

    user = crud.get_user_by_email(db, email=email)

    return username, email, user



async def logout_user(refresh_token):
    if refresh_token:
        refresh_token_hash = hash_token(refresh_token)
        await redis_client.delete(f"refresh_token:{refresh_token_hash}")


async def code_exchange_service(db: Session, code, code_verifier):
    user_id = await validate_code(code, code_verifier)

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid code")
    user = crud.get_user_by_id(db, str(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = await create_access_token(user)
    refresh_token = await create_refresh_token(user)


    return access_token, refresh_token


async def refresh_user_token(db: Session, old_refresh_token: str):
    try:
        payload = jwt.decode(old_refresh_token, settings.SECRET_KEY)
        payload.validate()
        user_id = payload.get("sub")
        old_refresh_token_hash = hash_token(old_refresh_token)
        saved_user = await redis_client.get(f"refresh_token:{old_refresh_token_hash}")

        if not saved_user:
            raise HTTPException(status_code=401, detail="Token not found")


        if saved_user != str(user_id):
            raise HTTPException(status_code=401, detail="Token reuse detected")
        await redis_client.delete(f"refresh_token:{old_refresh_token_hash}")
        user = crud.get_user_by_id(db, user_id=user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        access_token = await create_access_token(user)
        new_refresh_token = await create_refresh_token(user)
        new_refresh_token_hash = hash_token(new_refresh_token)

        await redis_client.set(
            f"refresh_token:{new_refresh_token_hash}",
            user.id,
            ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )

        return access_token, new_refresh_token, user

    except JoseError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
