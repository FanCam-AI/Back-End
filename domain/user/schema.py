from pydantic import BaseModel

class UserMeResponse(BaseModel):
    username: str
    create_count: int
    app_version: str

class UserMeResponseCheckPlan(BaseModel):
    username: str
    create_count: int
    is_updated: bool