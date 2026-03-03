from sqlalchemy.orm import Session
from models import Result
from sqlalchemy import desc

def get_result_list_by_user_id(db: Session, user_id: int):
    return db.query(Result) \
        .filter(Result.user_id == user_id) \
        .order_by(desc(Result.id)) \
        .all()


def get_result_list(db: Session):
    result_list = db.query(Result)\
        .order_by(Result.create_date.desc())\
        .all()
    return result_list


def get_result_by_public_id(db: Session, public_id):
    return db.query(Result).filter(Result.public_id == public_id).first()

def make_all_results_public(db: Session, user_id):
    return db.query(Result).filter(
        Result.user_id == user_id
    ).update(
        {"is_protected": False, "password": None},
        synchronize_session=False
    )


def make_all_results_private(db: Session, user_id, password):
    return db.query(Result).filter(
        Result.user_id == user_id
    ).update(
        {"is_protected": True, "password": password},
        synchronize_session=False
    )