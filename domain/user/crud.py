from sqlalchemy.orm import Session
from models import User, Result, Subscription


def get_user_by_id(db: Session, user_id):
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username):
    return db.query(User).filter(User.username == username).first()


def get_results_by_user(db: Session, user_id):
    return db.query(Result).filter(Result.user_id == user_id).all()


def delete_results_by_user(db: Session, user_id):
    db.query(Result).filter(
        Result.user_id == user_id
    ).delete(synchronize_session=False)


def count_results_by_user(db: Session, user_id):
    return db.query(Result).filter(Result.user_id == user_id).count()


def protect_results_by_user(db: Session, user_id, password):
    return db.query(Result).filter(
        Result.user_id == user_id
    ).update(
        {
            "is_protected": True,
            "password": password,
        },
        synchronize_session=False
    )


def delete_user(db: Session, user: User):
    db.delete(user)

def get_result_count_by_user_id(db: Session, user_id: int) -> int:
    return db.query(Result) \
             .filter(Result.user_id == user_id) \
             .count()

def get_subscription_by_user_id(db: Session, user_id: int):
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()

def delete_subscription_by_user_id(db: Session, user_id: int):
    db.query(Subscription)\
      .filter(Subscription.user_id == user_id)\
      .delete()