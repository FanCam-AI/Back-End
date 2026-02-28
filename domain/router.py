from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette import status
from fastapi.responses import RedirectResponse
from fastapi.responses import HTMLResponse
from typing import List
from authlib.jose import jwt
from passlib.hash import bcrypt
from database import get_db
from domain import schema, crud
from models import Result, User
from authlib.jose import JoseError
from urllib.parse import urlencode
import httpx
from fastapi import Request, Header, HTTPException, Form
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import os, secrets
from typing import Optional
import uuid
from config import settings
from infra import r2_client, client_secret, redis_client, oauth_google, oauth_apple
from .token import get_current_user, create_refresh_token, create_access_token, hash_token, create_auth_code, validate_code
import json
from cryptography.fernet import Fernet
router = APIRouter(prefix="/api")

@router.post("/result/init_image_upload")
async def init_image_upload(
    filename: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    key = f"images/{current_user.id}/{uuid.uuid4()}/{filename}"

    url = r2_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.R2_BUCKET,
            "Key": key,
        },
        ExpiresIn=600,
    )

    return {
        "key": key,
        "url": url,
    }


@router.post("/result/init_video_upload")
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
            "ContentType": content_type,
            "Key": key,
        },
        ExpiresIn=600,  # 10분
    )

    return {
        "key": key,
        "url": url,
    }


@router.get("/auth/apple")
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
        response_mode="form_post",  # Apple 권장
    )


@router.post("/auth/apple/callback")
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

    user = await oauth_apple.apple.parse_id_token(token, nonce=expected_nonce)

    request.session["user"] = dict(user)
    apple_user = dict(user)
    email = apple_user.get("email")
    if email is None:
        email = "example@email.com"
    username = email.split("@")[0]

    user = crud.get_user_by_email(db, email=email)
    if not user:
        user = crud.create_user(db, schema.UserCreate(
            username=username,
            email=email,
            create_count=0,
            apple_refresh_token=apple_refresh_token,

        ))

    access_token =  await create_access_token(user)
    refresh_token = await create_refresh_token(user)

    if platform == "app":
        code = await create_auth_code(user.id, code_challenge)
        params = urlencode({"code": code})

        return RedirectResponse(
            url=f"fancamai://callback?{params}"
        )

    else:
        response = RedirectResponse(url="/")
        response.set_cookie("access_token", access_token, httponly=True, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, secure=True, samesite="strict")
        response.set_cookie("refresh_token", refresh_token, httponly=True, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, secure=True, samesite="strict")

        return response




@router.get("/auth/google")
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


@router.get("/auth/google/callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth_google.google.authorize_access_token(request)
    nonce = request.session.get("nonce")
    platform = request.session.get("platform", "web")
    code_challenge = request.session.get("code_challenge", "")

    if "id_token" not in token:
        raise HTTPException(status_code=400, detail="Missing id_token")

    user_info = await oauth_google.google.parse_id_token(token, nonce=nonce)
    email = user_info['email']
    username = user_info.get('name', email.split('@')[0])

    user = crud.get_user_by_email(db, email=email)
    if not user:
        user = crud.create_user(db, schema.UserCreate(
            username=username,
            email=email,
            create_count=0,
            apple_refresh_token="",
        ))

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
        response.set_cookie("access_token", access_token, httponly=True, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, secure=True, samesite="strict")
        response.set_cookie("refresh_token", refresh_token, httponly=True, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, secure=True, samesite="strict")

        return response


@router.post("/auth/exchange")
async def exchange(
    code: str = Form(...),
    code_verifier: str = Form(...),
    db: Session = Depends(get_db)
):

    user_id = await validate_code(code, code_verifier)

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid code")
    user = crud.get_user(db, str(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = await create_access_token(user)
    refresh_token = await create_refresh_token(user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }


@router.post("/user/logout")
async def logout(request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await redis_client.delete(f"refresh_token:{refresh_token}")
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@router.post("/user/refresh_token")
async def refresh_access_token(
    request: Request,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    # 1) 쿠키에서 토큰 시도
    old_refresh_token = request.cookies.get("refresh_token")

    # 2) 쿠키 없으면 Authorization 헤더 시도
    if not old_refresh_token and authorization and authorization.startswith("Bearer "):
        old_refresh_token = authorization[7:]

    if not old_refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    # 이후 기존 로직 유지
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
        user = crud.get_user(db, user_id=user_id)
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

        response = JSONResponse(content={"user_id": user.id})

        # 웹용 쿠키 세팅 (웹일 때만 의미 있음)
        if not authorization:
            response.set_cookie("access_token", access_token, httponly=True, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, secure=True, samesite="strict")
            response.set_cookie("refresh_token", new_refresh_token, httponly=True, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, secure=True, samesite="strict")

        # 앱은 토큰은 JSON 등으로 전달하면 됨 (필요시 추가)
        else:
            response = JSONResponse(content={
                "username": user.username,
                "access_token": access_token,
                "refresh_token": new_refresh_token,
            })

        return response

    except JoseError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")



@router.get("/result/result_list", response_model=list[schema.ResultOutput])
async def result_list(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    base_url = "https://cdn.fancamai.com"

    # DB에서 결과 리스트 가져오기
    _result_list = crud.get_result_list_by_user_id(db, user_id=current_user.id)

    protected_result = next((r for r in _result_list if r.is_protected), None)

    if protected_result:
        # 보호된 결과가 하나라도 있으면 -> 보호 안된 것들만 업데이트
        updated = db.query(Result).filter(
            Result.user_id == current_user.id,
            Result.is_protected == False
        ).update(
            {
                "is_protected": True,
                "password": protected_result.password,  # 같은 비번으로 맞춤
            },
            synchronize_session=False
        )
        if updated:
            db.commit()
            # 다시 최신화된 결과 불러오기
            _result_list = crud.get_result_list_by_user_id(db, user_id=current_user.id)

        for result in _result_list:
            if result.file_path:
                result.owner_url = f"{base_url}/{result.file_path}"
                result.share_url = f"{base_url}/preview/{result.public_id}"

    else:
        for result in _result_list:
            if result.file_path:
                result.owner_url = f"{base_url}/{result.file_path}"
                result.share_url = f"{base_url}/{result.file_path}"
                print(f"{base_url}/{result.file_path}")



    return _result_list


@router.get("/result/get_current_user_id")
async def get_current_user_id(current_user: User = Depends(get_current_user)):
    current_user_id = current_user.id
    return {"current_user_id": current_user_id}


@router.post("/result/make_result")
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
    try:
        spot_list = json.loads(spot_list)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in spot_list"}

    f = Fernet(settings.FERNET_KEY)
    access_token = await create_access_token(current_user)
    encrypted_token = f.encrypt(access_token.encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.RUNPOD_API_KEY}"
    }
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
            'https://api.runpod.ai/v2/alf0t6f0cq1imw/run',
            headers=headers,
            json=data
        )


    await redis_client.set(f"job_status:{current_user.id}", "processing", ex=25200)

    return {"status": "started"}

@router.post("/result/save_result")
async def save_result(
    title: str = Form(""),
    file_path: str = Form(...),
    file_type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result_success = crud.save_result(db, title, file_path, file_type, current_user.id)

    return {
        "success": result_success
    }



@router.delete("/result/{result_id}")
async def delete_result(result_id: int, db: Session = Depends(get_db)):
    print("ID:", result_id)
    result = db.query(Result).filter(Result.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    if result.file_path:
        try:
            r2_client.delete_object(
                Bucket=settings.R2_BUCKET,
                Key=result.file_path
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail="error")

    db.delete(result)
    db.commit()
    return {"message": "Done"}



@router.get("/result/status")
async def get_processing_status(current_user: User = Depends(get_current_user)):
    status = await redis_client.get(f"job_status:{current_user.id}")
    progress = await redis_client.get(f"job_progress:{current_user.id}")
    return {"status": status or "none",
            "progress": progress or "none",
            }


@router.post("/result/reset_status")
async def reset_status(current_user: User = Depends(get_current_user)):
    await redis_client.delete(f"job_status:{current_user.id}")
    await redis_client.delete(f"job_progress:{current_user.id}")
    return {"status": "cleared"}



@router.get("/user/me", response_model=schema.UserMeResponse)
async def read_user_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user: User | None = db.query(User).filter(User.username == current_user.username).first()
    if not user:
        raise HTTPException(404, "User not found")
    return {
        "username": current_user.username,
        "create_count": current_user.create_count,
        "app_version": settings.APP_VERSION,
    }

@router.get("/app/version")
async def get_app_version():
    return {"app_version": settings.APP_VERSION}

@router.post("/user/me_check_premium", response_model=schema.UserMeResponseCheckPlan)
async def check_user_premium(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_plan: str = Form(...)
):
    user: User | None = db.query(User).filter(User.username == current_user.username).first()
    fancam_ai_password = "sucWqIPOW41ZFAIMi7c9NVcEelq7Qz"
    hashed_fancam_ai_pw = bcrypt.hash(fancam_ai_password)
    is_updated = False
    if not user:
        raise HTTPException(404, "User not found")

    if current_plan == "FREE" or current_plan == "":
        updated = db.query(Result).filter(
            Result.user_id == current_user.id
        ).update(
            {
                "is_protected": True,
                "password": hashed_fancam_ai_pw,  # 같은 비번으로 맞춤
            },
            synchronize_session=False
        )
        if updated:
            db.commit()
            count = db.query(Result).filter(Result.user_id == current_user.id).count()
            if count > 0:
                is_updated = True


    return {
        "username": current_user.username,
        "create_count": current_user.create_count,
        "is_updated": is_updated,
    }



@router.get("/preview/{public_id}", response_class=HTMLResponse)
async def preview_file(public_id: str, db: Session = Depends(get_db)):
    result = db.query(Result).filter(Result.public_id == public_id).first()

    if not result:
        return crud.file_not_found_form("❌ File not found.")
    base_url = "https://fancamai.com"
    parts = result.file_path.lstrip('/').split(os.sep)
    result_file_path = os.path.join(parts[-2], parts[-1])
    file_url = f"{base_url}/fancam-ai-gallery/{result_file_path}"  # 슬래시 중복 방지


    if not result.is_protected:
        return RedirectResponse(url=file_url, status_code=303)

    else:
        thumbnail_url = "https://fancamai.com/fancam-ai-gallery/gif/fancamai_logo_last.png"
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta property="og:title" content="Protected File"/>
          <meta property="og:description" content="This file is password protected. Enter password to access."/>
          <meta property="og:image" content="{thumbnail_url}"/>
          <meta property="og:url" content="https://example.com/protected/{public_id}"/>
          <meta name="twitter:card" content="summary_large_image"/>
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Protected File Preview</title>
          <style>
            body {{
              margin: 0;
              font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
              background: #f9f9f9;
              display: flex;
              justify-content: center;
              align-items: center;
              height: 100vh;
              color: #111;
            }}
            .card {{
              background: #fff;
              border-radius: 20px;
              box-shadow: 0 6px 20px rgba(0,0,0,0.15);
              max-width: 400px;
              width: 90%;
              padding: 2rem;
              text-align: center;
              animation: fadeIn 0.6s ease-in-out;
              border: 1px solid #e5e5e5;
            }}
            .card h2 {{
              margin-bottom: 1rem;
              font-size: 1.6rem;
              font-weight: 700;
              color: #000;
            }}
            .card p {{
              margin-bottom: 2rem;
              font-size: 1rem;
              color: #555;
              line-height: 1.5;
            }}
            /* 버튼 전용 스타일 */
            .btn {{
              display: inline-block;
              padding: 0.85rem 1.5rem;
              border-radius: 12px;
              text-decoration: none;
              font-weight: 600;
              background: #000;
              color: #fff;
              transition: all 0.3s ease;
              margin-top: 0.5rem;
            }}
            .btn:hover {{
              background: #333;
              transform: translateY(-2px);
            }}
            /* 작은 텍스트 링크 */
            .small-link {{
              font-size: 0.9rem;
              color: #555;
              text-decoration: underline;
            }}
            @keyframes fadeIn {{
              from {{ opacity: 0; transform: translateY(20px); }}
              to {{ opacity: 1; transform: translateY(0); }}
            }}
          </style>
        </head>
        <body>
          <div class="card">
            <h2>🔒 This file is password protected</h2>
            <p>You need to enter the correct password to view the content.</p>
            <a href="https://fancamai.com/protected/{public_id}" class="btn">Enter Password</a>
            <br><br>
            <p>
              <a href="https://apps.apple.com/kr/app/fancam-ai/id6752274658" target="_blank" class="small-link">
                Click here to download FanCam AI!
              </a>
            </p>
          </div>
        </body>
        </html>
        """)


@router.get("/protected/{public_id}", response_class=HTMLResponse)
async def get_protected_form(public_id: str, db: Session = Depends(get_db)):
    result = db.query(Result).filter(Result.public_id == public_id).first()
    if not result:
        return crud.file_not_found_form("❌ File not found.")

    base_url = "https://fancamai.com"
    parts = result.file_path.lstrip('/').split(os.sep)
    result_file_path = os.path.join(parts[-2], parts[-1])
    file_url = f"{base_url}/fancam-ai-gallery/{result_file_path}"  # 슬래시 중복 방지

    if not result.is_protected:
        return RedirectResponse(url=file_url, status_code=303)

    return HTMLResponse(f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f9f9f9;
                    color: #111;
                }}
                .container {{
                    background: #fff;
                    padding: 2.5rem 2rem;
                    border-radius: 16px;
                    box-shadow: 0 6px 24px rgba(0,0,0,0.12);
                    text-align: center;
                    max-width: 360px;
                    width: 90%;
                    border: 1px solid #e5e5e5;
                    animation: fadeIn 0.5s ease-in-out;
                }}
                h3 {{
                    margin-bottom: 1.5rem;
                    font-size: 1.3rem;
                    font-weight: 600;
                    color: #000;
                }}
                input[type="password"] {{
                    padding: 0.75rem 1rem;
                    border-radius: 10px;
                    border: 1px solid #ccc;
                    margin-bottom: 1.2rem;
                    width: 100%;
                    max-width: 260px;
                    font-size: 1rem;
                    transition: border-color 0.2s, box-shadow 0.2s;
                }}
                input[type="password"]:focus {{
                    outline: none;
                    border-color: #000;
                    box-shadow: 0 0 0 2px rgba(0,0,0,0.1);
                }}
                button {{
                    padding: 0.75rem 1.5rem;
                    border-radius: 10px;
                    border: none;
                    background-color: #000;
                    color: #fff;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background-color 0.3s, transform 0.2s;
                }}
                button:hover {{
                    background-color: #333;
                    transform: translateY(-2px);
                }}
                @keyframes fadeIn {{
                    from {{ opacity: 0; transform: translateY(20px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h3>🔒 Enter password to view the file</h3>
                <form action="" method="post">
                    <input type="password" name="password" placeholder="Password" required/>
                    <br/>
                    <button type="submit">Submit</button>
                </form>
            </div>
        </body>
        </html>
    """)



@router.post("/protected/{public_id}")
async def check_password(public_id: str, password: str = Form(...), db: Session = Depends(get_db)):
    result = db.query(Result).filter(Result.public_id == public_id).first()
    base_url = "https://fancamai.com"
    parts = result.file_path.lstrip('/').split(os.sep)
    result_file_path = os.path.join(parts[-2], parts[-1])
    file_url= f"{base_url}/fancam-ai-gallery/{result_file_path}"  # 슬래시 중복 방지
    if not result:
        return crud.file_not_found_form("❌ File not found.")

    if not result.is_protected:
        return RedirectResponse(url=file_url, status_code=303)

    if not bcrypt.verify(password, result.password):
        return crud.password_form("❌ Wrong password, try again.")


    return RedirectResponse(url=file_url, status_code=303)


@router.post("/result/set_all_public")
async def set_all_public(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # bulk update → 성능 좋음
    updated = db.query(Result).filter(
        Result.user_id == current_user.id
    ).update(
        {"is_protected": False, "password": None},
        synchronize_session=False
    )
    db.commit()
    return {"updated_count": updated, "status": "all set to public"}




@router.post("/result/set_all_private")
async def set_all_private(
    password: str = Form(...),  # 사용자 입력값
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # bcrypt 해시 생성
    hashed_pw = bcrypt.hash(password)

    # bulk update
    updated = db.query(Result).filter(
        Result.user_id == current_user.id
    ).update(
        {"is_protected": True, "password": hashed_pw},
        synchronize_session=False
    )
    db.commit()

    return {"updated_count": updated, "status": "all set to private"}


@router.post("/user/delete_account")
async def delete_my_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 1. Apple 연동 해제
        if current_user.apple_refresh_token:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://appleid.apple.com/auth/revoke",
                    data={
                        "client_id": settings.APPLE_CLIENT_ID,
                        "client_secret": client_secret,
                        "token": current_user.apple_refresh_token,
                        "token_type_hint": "refresh_token"
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

            if resp.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Apple revoke failed: {resp.text}"
                )

            # DB에서 refresh_token 제거
            current_user.apple_refresh_token = ""
            db.add(current_user)
            db.commit()

        # 2. 사용자와 연관된 Result 가져오기
        results = db.query(Result).filter(Result.user_id == current_user.id).all()

        # 3. 파일 삭제
        for result in results:
            file_path = result.file_path
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Failed to delete file {file_path}: {e}")

        # 4. Result DB 삭제
        db.query(Result).filter(Result.user_id == current_user.id).delete(synchronize_session=False)

        # 5. User 삭제
        db.delete(current_user)
        db.commit()

        return {"message": "Account and all associated files deleted successfully."}

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {str(e)}"
        )