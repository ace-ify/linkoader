from pydantic import BaseModel, HttpUrl, field_validator
from typing import Literal, Optional


class ExtractRequest(BaseModel):
    url: HttpUrl


class MediaInfo(BaseModel):
    platform: str
    title: str
    thumbnail: str
    media_type: Literal["video", "audio", "image", "document"]
    format: str
    quality: str
    file_size: int
    download_url: str
    duration: Optional[int] = None
    author: Optional[str] = None

    @field_validator("duration", mode="before")
    @classmethod
    def coerce_duration(cls, v):
        if v is None:
            return None
        return int(v)


class ErrorResponse(BaseModel):
    error: str
    message: str
    retry_after: Optional[int] = None
    supported: Optional[list[str]] = None
