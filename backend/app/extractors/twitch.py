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


class TwitchExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?twitch\.tv/\w+/clip/[\w-]+",
        r"https?://clips\.twitch\.tv/[\w-]+",
        r"https?://(www\.)?twitch\.tv/videos/\d+",
        r"https?://(www\.)?twitch\.tv/\w+/video/\d+",
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

        # Determine if this is a clip or VOD
        is_clip = "clip" in url.lower() or "clips.twitch.tv" in url.lower()

        title = info.get("title", "Twitch Clip" if is_clip else "Twitch VOD")
        if len(title) > 80:
            title = title[:77] + "…"

        return MediaInfo(
            platform="twitch",
            title=title,
            thumbnail=info.get("thumbnail", ""),
            media_type="video",
            format=info.get("ext", "mp4"),
            quality=f"{info.get('height', 0)}p" if info.get("height") else "best",
            file_size=info.get("filesize") or info.get("filesize_approx") or 0,
            download_url=info["url"],
            duration=info.get("duration"),
            author=info.get("uploader") or info.get("creator"),
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
