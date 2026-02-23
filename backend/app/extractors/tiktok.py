import asyncio
import yt_dlp
from app.extractors.base import BaseExtractor, classify_ytdlp_error
from app.models import MediaInfo
from app.exceptions import (
    ContentNotFoundError,
    ExtractionFailedError,
    ExtractionTimeoutError,
    UpstreamError,
    AgeRestrictedError,
    LoginRequiredError,
)

EXTRACTION_TIMEOUT = 30


class TiktokExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?tiktok\.com/@[\w.-]+/video/\d+",
        r"https?://(www\.)?tiktok\.com/t/[\w-]+",
        r"https?://vm\.tiktok\.com/[\w-]+",
        r"https?://(www\.)?tiktok\.com/@[\w.-]+/photo/\d+",
        r"https?://m\.tiktok\.com/v/\d+",
    ]

    async def extract(self, url: str) -> MediaInfo:
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(self._extract_sync, url),
                timeout=EXTRACTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, UpstreamError, ExtractionFailedError,
                AgeRestrictedError, LoginRequiredError):
            raise
        except Exception:
            raise ExtractionFailedError()

        is_image = info.get("ext") in ("jpg", "jpeg", "png", "webp")
        media_type = "image" if is_image else "video"

        return MediaInfo(
            platform="tiktok",
            title=info.get("title") or info.get("description", "TikTok Video")[:80],
            thumbnail=info.get("thumbnail", ""),
            media_type=media_type,
            format=info.get("ext", "mp4"),
            quality=f"{info.get('height', 0)}p" if info.get("height") else "original",
            file_size=info.get("filesize") or info.get("filesize_approx") or 0,
            download_url=info["url"],
            duration=info.get("duration"),
            author=info.get("uploader") or info.get("creator"),
        )

    def _extract_sync(self, url: str) -> dict:
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 15,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise ContentNotFoundError()
                return info
        except yt_dlp.utils.DownloadError as e:
            classify_ytdlp_error(e)
