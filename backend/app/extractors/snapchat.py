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


class SnapchatExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?snapchat\.com/spotlight/[\w-]+",
        r"https?://(www\.)?snapchat\.com/t/[\w-]+",
        r"https?://story\.snapchat\.com/s/[\w-]+",
        r"https?://story\.snapchat\.com/o/[\w-]+",
        r"https?://(www\.)?snapchat\.com/add/[\w.-]+/[\w-]+",
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

        return MediaInfo(
            platform="snapchat",
            title=info.get("title", "Snapchat Story")[:80],
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
        ydl_opts = get_stealth_ytdlp_opts("best[ext=mp4]/best")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise ContentNotFoundError()
                return info
        except yt_dlp.utils.DownloadError as e:
            classify_ytdlp_error(e)
