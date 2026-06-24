from sqlalchemy.orm import Session
from models import User, Result, Subscription


def get_user_by_id(db: Session, user_id):
    return db.query(User).filter(User.id == user_id).first()


def get_subscription_by_user_id(db: Session, user_id):
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()


def sync_subscription(db: Session, subscription: Subscription, expires_at, plan):
    subscription.plan = plan
    subscription.expires_at = expires_at

    db.commit()
    db.refresh(subscription)

    return subscription


def get_results_by_user(db: Session, user_id):
    return db.query(Result).filter(Result.user_id == user_id).all()


def delete_results_by_user(db: Session, user_id):
    db.query(Result).filter(
        Result.user_id == user_id
    ).delete(synchronize_session=False)