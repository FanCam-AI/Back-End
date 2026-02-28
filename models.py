from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from database import Base
from sqlalchemy.orm import relationship
from uuid import uuid4

class Result(Base):
    __tablename__ = "result"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    public_id = Column(String, unique=True, default=lambda: str(uuid4()))
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    status = Column(String, default="processing")
    create_date = Column(DateTime, nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    user = relationship("User", backref="result_users")
    is_protected = Column(Boolean, default=False)
    password = Column(String, nullable=True)
    owner_url = Column(String, nullable=True)
    share_url = Column(String, nullable=True)



class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    create_count = Column(Integer, nullable=False)
    apple_refresh_token = Column(String, nullable=True)  # Apple이 발급한 refresh_token

