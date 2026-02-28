import asyncio
import yt_dlp
from app.extractors.base import BaseExtractor, classify_ytdlp_error
from app.stealth import get_stealth_ytdlp_opts
from app.models import MediaInfo
from app.exceptions import (
    ContentNotFoundError,
    ExtractionFailedError,
    ExtractionTimeoutError,
    UpstreamError,
    LoginRequiredError,
)

EXTRACTION_TIMEOUT = 30


class LinkedinExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?linkedin\.com/posts/[\w-]+",
        r"https?://(www\.)?linkedin\.com/feed/update/urn:li:activity:\d+",
        r"https?://(www\.)?linkedin\.com/video/[\w-]+",
        r"https?://(www\.)?linkedin\.com/embed/feed/update/urn:li:ugcPost:\d+",
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

        title = info.get("title") or info.get("description", "LinkedIn Video")
        if len(title) > 80:
            title = title[:77] + "…"

        return MediaInfo(
            platform="linkedin",
            title=title,
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
        ydl_opts = get_stealth_ytdlp_opts("best[ext=mp4]/best")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise ContentNotFoundError()
                return info
        except yt_dlp.utils.DownloadError as e:
            classify_ytdlp_error(e)
