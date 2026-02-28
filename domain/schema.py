import datetime
from pydantic import BaseModel, field_validator, EmailStr, Field

class ResultCreate(BaseModel):
    id: int
    title: str
    file_path: str
    file_type: str
    create_date: datetime.datetime

class ResultOutput(BaseModel):
    id: int
    title: str
    file_type: str
    create_date: datetime.datetime
    owner_url: str
    share_url: str


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    create_count: int
    apple_refresh_token: str


    @field_validator('username','email')
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('빈 값은 허용되지 않습니다.')
        return v

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    username: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserMeResponse(BaseModel):
    username: str
    create_count: int
    app_version: str

class UserMeResponseCheckPlan(BaseModel):
    username: str
    create_count: int
    is_updated: bool