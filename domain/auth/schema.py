from pydantic import BaseModel, field_validator, EmailStr

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