import asyncio
import yt_dlp
from app.extractors.base import BaseExtractor, classify_ytdlp_error
from app.models import MediaInfo
from app.exceptions import (
    ContentNotFoundError,
    ExtractionFailedError,
    ExtractionTimeoutError,
    UpstreamError,
    LoginRequiredError,
)

EXTRACTION_TIMEOUT = 30


class RedditExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?reddit\.com/r/\w+/comments/[\w-]+",
        r"https?://(old\.)?reddit\.com/r/\w+/comments/[\w-]+",
        r"https?://redd\.it/[\w-]+",
        r"https?://(www\.)?reddit\.com/r/\w+/s/[\w-]+",
        r"https?://v\.redd\.it/[\w-]+",
        r"https?://i\.redd\.it/[\w-]+",
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
                LoginRequiredError):
            raise
        except Exception:
            raise ExtractionFailedError()

        ext = info.get("ext", "mp4")
        is_image = ext in ("jpg", "jpeg", "png", "webp", "gif")
        media_type = "image" if is_image else "video"

        title = info.get("title", "Reddit Post")
        if len(title) > 80:
            title = title[:77] + "…"

        return MediaInfo(
            platform="reddit",
            title=title,
            thumbnail=info.get("thumbnail", ""),
            media_type=media_type,
            format=ext,
            quality=f"{info.get('height', 0)}p" if info.get("height") else "original",
            file_size=info.get("filesize") or info.get("filesize_approx") or 0,
            download_url=info["url"],
            duration=info.get("duration"),
            author=info.get("uploader"),
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
