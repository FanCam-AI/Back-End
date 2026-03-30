from sqlalchemy.orm import Session
from models import Result
from datetime import datetime


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
