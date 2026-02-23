from pydantic import BaseModel, HttpUrl
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


class ErrorResponse(BaseModel):
    error: str
    message: str
    retry_after: Optional[int] = None
    supported: Optional[list[str]] = None
