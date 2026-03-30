from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse
from database import get_db
from models import User
from fastapi import Request, Form
from domain.token import get_current_user
from . import service, schema


share_router = APIRouter(prefix="/share")


@share_router.get("/result_list", response_model=list[schema.ResultOutput])
async def result_list(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _result_list = service.get_result_list_service(db, current_user.id)
    return _result_list


@share_router.get("/preview/{public_id}", response_class=HTMLResponse)
async def preview_file(request: Request, public_id: str, db: Session = Depends(get_db)):
    response = service.preview_file_service(db, request, public_id)
    return response


@share_router.get("/protected/{public_id}", response_class=HTMLResponse)
async def get_protected_form(request: Request, public_id: str, db: Session = Depends(get_db)):
    response = service.get_protected_form(db, request, public_id)
    return response



@share_router.post("/protected/{public_id}")
async def check_password(request: Request, public_id: str, password: str = Form(...), db: Session = Depends(get_db)):
    response = service.check_password(db, request, public_id, password)
    return response


@share_router.post("/set_all_private")
async def set_all_private(
    password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
   response = service.set_all_private_service(db, current_user.id, password)
   return response


@share_router.post("/set_all_public")
async def set_all_public(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
   response = service.set_all_public_service(db, current_user.id)
   return response


@share_router.post("/set_private/{result_id}")
async def set_private(
    result_id: int,
    password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return service.set_private_service(db, current_user.id, result_id, password)


@share_router.post("/set_public/{result_id}")
async def set_public(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return service.set_public_service(db, current_user.id, result_id)


@share_router.delete("/{result_id}")
async def delete_result(result_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        response = service.delete_result_by_id(db, result_id, current_user.id)

    except HTTPException:
        raise HTTPException(status_code=404, detail="Result not found")

    return response