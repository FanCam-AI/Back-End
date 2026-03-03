from . import schema
from sqlalchemy.orm import Session
from models import User

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user_create: schema.UserCreate):
    db_user = User(username=user_create.username,
                   email=user_create.email,
                   create_count=user_create.create_count,
                   apple_refresh_token=user_create.apple_refresh_token)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_id(db: Session, user_id):
    return db.query(User).filter(User.id == user_id).first()
