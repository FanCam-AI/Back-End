from models import Result
from fastapi.templating import Jinja2Templates
from . import crud
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from passlib.hash import bcrypt
from config import settings, logger
from sqlalchemy.exc import SQLAlchemyError
from infra import r2_client
from botocore.exceptions import ClientError


templates = Jinja2Templates(directory="domain/share/templates")
base_url = "https://fancamai.com"
cdn_base_url = "https://cdn.fancamai.com"


def get_result_list_service(db: Session, user_id) -> Result:

    _result_list = crud.get_result_list_by_user_id(db, user_id=user_id)

    for result in _result_list:
        if result.file_path:
            result.owner_url = f"{cdn_base_url}/{result.file_path}"

            if result.is_protected:
                result.share_url = f"{base_url}/share/preview/{result.public_id}"
            else:
                result.share_url = f"{cdn_base_url}/{result.file_path}"

    return _result_list




def password_form(request, error_message: str = ""):
    return templates.TemplateResponse(
        "password_form.html",
        {
            "request": request,
            "error_message": error_message,
        },
    )


def file_not_found_form(request, error_message: str = ""):
    return templates.TemplateResponse(
        "file_not_found.html",
        {
            "request": request,
            "error_message": error_message,
        },
    )


def preview_file_service(db: Session, request, public_id):
    result = crud.get_result_by_public_id(db, public_id)
    if not result:
        return file_not_found_form(request, "❌ File not found.")
    file_cdn_url = f"{cdn_base_url}/{result.file_path}"
    appstore_url = "https://apps.apple.com/kr/app/fancam-ai/id6752274658"
    chrome_extension_store_url = "https://chromewebstore.google.com/detail/dragtogif/egnckhoidbiojmhdkjndgidhfjkknfim?authuser=0&hl=en"

    if not result.is_protected:
        return RedirectResponse(url=file_cdn_url, status_code=303)

    else:
        thumbnail_url = "https://cdn.fancamai.com/logo/fancamai_logo.png"
        return templates.TemplateResponse(
            "protected_preview.html",
            {
                "request": request,
                "thumbnail_url": thumbnail_url,
                "og_url": f"{base_url}/share/preview/{public_id}",
                "protected_url": f"{base_url}/share/protected/{public_id}",
                "appstore_url": appstore_url,
                "chrome_extension_store_url": chrome_extension_store_url,
            },
        )

def get_protected_form(db: Session, request, public_id):
    result = crud.get_result_by_public_id(db, public_id)
    if not result:
        return file_not_found_form(request, "❌ File not found.")

    file_cdn_url = f"{cdn_base_url}/{result.file_path}"

    if not result.is_protected:
        return RedirectResponse(url=file_cdn_url, status_code=303)

    return templates.TemplateResponse(
        "protected_form.html",
        {"request": request}
    )



def check_password(db: Session, request, public_id, password):
    result = crud.get_result_by_public_id(db, public_id)
    file_url = f"{cdn_base_url}/{result.file_path}"

    if not result:
        return file_not_found_form(request, "❌ File not found.")

    if not result.is_protected:
        return RedirectResponse(url=file_url, status_code=303)

    if not bcrypt.verify(password, result.password):
        return password_form(request, "❌ Wrong password, try again.")

    return RedirectResponse(url=file_url, status_code=303)


def set_all_private_service(db: Session, user_id, password):
    hashed_pw = bcrypt.hash(password)
    updated = crud.make_all_results_private(db, user_id, hashed_pw)
    db.commit()
    return {"updated_count": updated, "status": "all set to private"}


def set_all_public_service(db: Session, user_id):
    updated = crud.make_all_results_public(db, user_id)
    db.commit()
    return {"updated_count": updated, "status": "all set to public"}


def set_private_service(db: Session, user_id, result_id, password):
    hashed_pw = bcrypt.hash(password)
    updated = crud.make_result_private(db, user_id, result_id, hashed_pw)
    db.commit()
    return {"updated_count": updated, "status": "set to private"}


def set_public_service(db: Session, user_id, result_id):
    updated = crud.make_result_public(db, user_id, result_id)
    db.commit()
    return {"updated_count": updated, "status": "set to public"}



def delete_result_by_id(db: Session, result_id, user_id):
    try:
        result = crud.get_result_by_id(db, result_id, user_id)
        if not result:
            logger.warning(f"Result not found: {result_id}")
    except Exception:
        raise

    try:
        crud.delete_result(db, result)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    if result.file_path:
        try:
            r2_client.delete_object(
                Bucket=settings.R2_BUCKET,
                Key=result.file_path
            )
        except ClientError:
            logger.warning(f"Failed to delete r2 object, key: {result.file_path}")

    return {"message": "Done"}