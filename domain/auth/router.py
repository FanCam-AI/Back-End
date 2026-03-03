from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from fastapi import Request, Header, HTTPException, Form
from fastapi.responses import JSONResponse
import os, secrets
from config import settings
from . import service
from infra import oauth_google, oauth_apple

auth_router = APIRouter(prefix="/auth")


@auth_router.get("/apple")
async def auth_apple(request: Request, platform: str = "web", code_challenge: str = ""):
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    request.session["apple_state"] = state
    request.session["apple_nonce"] = nonce
    request.session["platform"] = platform
    request.session["code_challenge"] = code_challenge

    return await oauth_apple.apple.authorize_redirect(
        request,
        settings.APPLE_REDIRECT_URI,
        state=state,
        nonce=nonce,
        response_mode="form_post",
    )


@auth_router.post("/apple/callback")
async def apple_callback(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    code = form.get("code")
    state = form.get("state")
    platform = request.session.get("platform", "web")
    code_challenge = request.session.get("code_challenge", "")
    expected_state = request.session.pop("apple_state", None)
    expected_nonce = request.session.pop("apple_nonce", None)

    if state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid state")

    user = await service.apple_callback_service(db, code, expected_nonce)
    response = await service.oauth_callback_return(platform, code_challenge, user)

    return response


@auth_router.get("/google")
async def auth_google(request: Request, platform: str = "web", code_challenge: str = ""):
    nonce = os.urandom(12).hex()
    request.session["nonce"] = nonce
    request.session["platform"] = platform
    request.session["code_challenge"] = code_challenge

    return await oauth_google.google.authorize_redirect(
        request,
        settings.GOOGLE_REDIRECT_URI,
        nonce=nonce,
        prompt='select_account'
    )


@auth_router.get("/google/callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth_google.google.authorize_access_token(request)
    nonce = request.session.get("nonce")
    platform = request.session.get("platform", "web")
    code_challenge = request.session.get("code_challenge", "")

    if "id_token" not in token:
        raise HTTPException(status_code=400, detail="Missing id_token")

    user = await service.google_callback_service(db, token, nonce)
    response = await service.oauth_callback_return(platform, code_challenge, user)

    return response


@auth_router.post("/logout")
async def logout(request: Request):
    refresh_token = request.cookies.get("refresh_token")

    await service.logout_user(refresh_token)

    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return response


@auth_router.post("/exchange")
async def exchange(
        code: str = Form(...),
        code_verifier: str = Form(...),
        db: Session = Depends(get_db)
):
    access_token, refresh_token = await service.code_exchange_service(db, code, code_verifier)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }


@auth_router.post("/refresh_token")
async def refresh_access_token(
    request: Request,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    old_refresh_token = request.cookies.get("refresh_token")

    if not old_refresh_token and authorization and authorization.startswith("Bearer "):
        old_refresh_token = authorization[7:]

    if not old_refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    access_token, refresh_token, user = service.refresh_user_token(db, old_refresh_token)

    response_data = {
        "username": user.username,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

    response = JSONResponse(content=response_data)

    if not authorization:
        response.set_cookie(
            "access_token",
            access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        response.set_cookie(
            "refresh_token",
            refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        )

    return response