from sqlalchemy.orm import Session
from models import Result
from sqlalchemy import desc

def get_result_list_by_user_id(db: Session, user_id: int):
    return db.query(Result) \
        .filter(Result.user_id == user_id) \
        .order_by(desc(Result.id)) \
        .all()



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


def make_result_public(db: Session, user_id: int, result_id: int):
    return db.query(Result).filter(
        Result.user_id == user_id,
        Result.id == result_id
    ).update(
        {"is_protected": False, "password": None},
        synchronize_session=False
    )


def make_result_private(db: Session, user_id: int, result_id: int, password: str):
    return db.query(Result).filter(
        Result.user_id == user_id,
        Result.id == result_id
    ).update(
        {"is_protected": True, "password": password},
        synchronize_session=False
    )

def get_result_by_id(db: Session, result_id, user_id):
    return db.query(Result).filter(Result.id == result_id, Result.user_id == user_id).first()

def delete_result(db: Session, result):
    db.delete(result)
    db.commit()
