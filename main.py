from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from config import settings
from domain import auth_router, user_router, share_router, result_router
from starlette.middleware.trustedhost import TrustedHostMiddleware
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

origins = [
    "https://fancamai.com",
]

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,  # 안전한 문자열
    session_cookie="session",
    https_only=True,               # 배포 HTTPS 환경에서는 True
    same_site="none",              # form_post 방식에서 필수
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["fancamai.com", "*.fancamai.com", settings.CLOUD_RUN_URL]
)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(share_router)
app.include_router(result_router)