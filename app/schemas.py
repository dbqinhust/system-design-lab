from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class URLCreate(BaseModel):
    short_code: str = Field(max_length=16)
    long_url: str


class URLRead(URLCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None
