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

EXTRACTION_TIMEOUT = 45

# Player client strategies, ordered by reliability on datacenter IPs.
# Each entry is passed via extractor_args to yt-dlp.
_CLIENT_STRATEGIES = [
    "mweb",
    "android",
    "ios",
    "tv",
]


class YouTubeExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?youtube\.com/watch\?v=[\w-]+",
        r"https?://(www\.)?youtube\.com/shorts/[\w-]+",
        r"https?://youtu\.be/[\w-]+",
        r"https?://(www\.)?youtube\.com/watch\?.*v=[\w-]+",
        r"https?://(www\.)?youtube\.com/live/[\w-]+",
    ]

    async def extract(self, url: str) -> MediaInfo:
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(self._extract_sync, url),
                timeout=EXTRACTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, ExtractionFailedError, UpstreamError,
                AgeRestrictedError, LoginRequiredError):
            raise
        except Exception:
            raise ExtractionFailedError()

        return MediaInfo(
            platform="youtube",
            title=info.get("title", "Untitled"),
            thumbnail=info.get("thumbnail", ""),
            media_type="video",
            format=info.get("ext", "mp4"),
            quality=f"{info.get('height', 0)}p",
            file_size=info.get("filesize") or info.get("filesize_approx") or 0,
            download_url=info["url"],
            duration=info.get("duration"),
            author=info.get("uploader"),
        )

    def _extract_sync(self, url: str) -> dict:
        # Try the default client first (no override), then rotate through
        # alternative player clients that are less likely to trigger
        # YouTube's bot/login gate on datacenter IPs.
        last_err: Exception | None = None

        for client in [None, *_CLIENT_STRATEGIES]:
            opts = self._build_opts(client)
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info is None:
                        raise ContentNotFoundError()
                    return info
            except yt_dlp.utils.DownloadError as e:
                err_msg = str(e).lower()
                # Only retry on login/auth/bot errors — everything else
                # (not found, age-restricted, network) won't improve.
                if any(kw in err_msg for kw in (
                    "login", "sign in", "authenticate", "bot",
                    "confirm your age", "cookies",
                )):
                    last_err = e
                    continue
                classify_ytdlp_error(e)

        # All strategies exhausted
        if last_err is not None:
            classify_ytdlp_error(last_err)
        raise ExtractionFailedError()

    @staticmethod
    def _build_opts(player_client: str | None) -> dict:
        opts: dict = {
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "socket_timeout": 15,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            },
        }
        if player_client:
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": [player_client],
                    "player_skip": ["webpage", "configs"],
                },
            }
        return opts
