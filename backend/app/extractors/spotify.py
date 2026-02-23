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


class SpotifyExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://open\.spotify\.com/episode/[\w-]+",
        r"https?://open\.spotify\.com/show/[\w-]+",
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

        title = info.get("title", "Spotify Episode")
        if len(title) > 80:
            title = title[:77] + "…"

        return MediaInfo(
            platform="spotify",
            title=title,
            thumbnail=info.get("thumbnail", ""),
            media_type="audio",
            format=info.get("ext", "m4a"),
            quality="original",
            file_size=info.get("filesize") or info.get("filesize_approx") or 0,
            download_url=info["url"],
            duration=info.get("duration"),
            author=info.get("uploader") or info.get("artist"),
        )

    def _extract_sync(self, url: str) -> dict:
        ydl_opts = {
            "format": "best",
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
            error_msg = str(e).lower()
            # Spotify music tracks are DRM-protected
            if "drm" in error_msg or "premium" in error_msg or "not a podcast" in error_msg:
                raise ContentNotFoundError(
                    "Only Spotify podcast episodes can be downloaded — music tracks are DRM-protected"
                )
            classify_ytdlp_error(e)
