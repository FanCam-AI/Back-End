import datetime
from pydantic import BaseModel

class ResultOutput(BaseModel):
    id: int
    title: str
    file_type: str
    create_date: datetime.datetime
    owner_url: str
    share_url: str
