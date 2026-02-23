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


class FacebookExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?facebook\.com/watch\?v=\d+",
        r"https?://(www\.)?facebook\.com/.+/videos/\d+",
        r"https?://(www\.)?facebook\.com/reel/\d+",
        r"https?://(www\.)?facebook\.com/.+/posts/.+",
        r"https?://fb\.watch/[\w-]+",
        r"https?://(www\.)?facebook\.com/share/v/[\w-]+",
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

        return MediaInfo(
            platform="facebook",
            title=info.get("title", info.get("description", "Facebook Video")[:80]),
            thumbnail=info.get("thumbnail", ""),
            media_type="video",
            format=info.get("ext", "mp4"),
            quality=f"{info.get('height', 0)}p" if info.get("height") else "best",
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
