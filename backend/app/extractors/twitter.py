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


class TwitterExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?twitter\.com/\w+/status/\d+",
        r"https?://(www\.)?x\.com/\w+/status/\d+",
        r"https?://t\.co/[\w-]+",
        r"https?://(mobile\.)?twitter\.com/\w+/status/\d+",
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
        is_image = ext in ("jpg", "jpeg", "png", "webp")
        media_type = "image" if is_image else "video"

        title = info.get("title") or info.get("description", "")
        if title:
            title = title[:80] + ("…" if len(title) > 80 else "")
        else:
            title = "Twitter Post"

        return MediaInfo(
            platform="twitter",
            title=title,
            thumbnail=info.get("thumbnail", ""),
            media_type=media_type,
            format=ext,
            quality=f"{info.get('height', 0)}p" if info.get("height") else "original",
            file_size=info.get("filesize") or info.get("filesize_approx") or 0,
            download_url=info["url"],
            duration=info.get("duration"),
            author=info.get("uploader") or info.get("uploader_id"),
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
