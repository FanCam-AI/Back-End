from sqlalchemy.orm import Session
from models import Result
from datetime import datetime


def get_result_by_id(db: Session, result_id, user_id):
    return db.query(Result).filter(Result.id == result_id, Result.user_id == user_id)


def delete_result(db: Session, result):
    db.delete(result)
    db.commit()


def save_result(db: Session,title, file_path, file_type, user_id):
    result = Result(
        title=title,
        file_path=file_path,
        file_type=file_type,
        create_date=datetime.now(),
        user_id=user_id
    )

    db.add(result)
    db.commit()
    db.refresh(result)
