from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User
from fastapi import HTTPException, Form
from sqlalchemy.exc import SQLAlchemyError
from config import settings
from domain.token import get_current_user
from . import service, schema

user_router = APIRouter(prefix="/user")

@user_router.get("/me")
async def read_user_me(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    try:
        response = service.read_user_me_srvice(db, current_user.id)
    except Exception:
        raise HTTPException(404, "User not found")
    return response


@user_router.post("/delete_account")
async def delete_my_account(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    try:
        await service.delete_user_account(db, current_user)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(500, "Database error")
    return {"message": "Deleted successfully."}


@user_router.post("/me_check_premium", response_model=schema.UserMeResponseCheckPlan)
async def check_user_premium(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        current_plan: str = Form(...)
):
    try:
        response = service.check_user_premium_service(db, current_plan, current_user.id)
    except Exception:
        raise HTTPException(404, "User not found")
    return response


@user_router.get("/app_version")
async def get_app_version():
    return {"app_version": settings.APP_VERSION}


@user_router.get("/get_current_user_id")
async def get_current_user_id(current_user: User = Depends(get_current_user)):
    current_user_id = current_user.id
    return {"current_user_id": current_user_id}