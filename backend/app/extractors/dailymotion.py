import asyncio
import re
import httpx
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

_DM_VIDEO_ID_RE = re.compile(
    r"(?:dailymotion\.com/(?:video|embed/video)/|dai\.ly/)([\w]+)"
)


class DailymotionExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?dailymotion\.com/video/[\w-]+",
        r"https?://dai\.ly/[\w-]+",
        r"https?://(www\.)?dailymotion\.com/embed/video/[\w-]+",
    ]

    async def extract(self, url: str) -> MediaInfo:
        # Strategy 1: Direct Dailymotion API (works on datacenter IPs)
        try:
            result = await asyncio.wait_for(
                self._extract_direct(url),
                timeout=EXTRACTION_TIMEOUT,
            )
            if result:
                return result
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, AgeRestrictedError, LoginRequiredError):
            raise
        except Exception:
            pass

        # Strategy 2: yt-dlp fallback
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

        title = info.get("title", "Dailymotion Video")
        if len(title) > 80:
            title = title[:77] + "\u2026"

        return MediaInfo(
            platform="dailymotion",
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

    async def _extract_direct(self, url: str) -> MediaInfo | None:
        """Use Dailymotion's player metadata API — works on datacenter IPs."""
        video_id = self._parse_video_id(url)
        if not video_id:
            return None

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            # Dailymotion player metadata endpoint
            metadata_url = f"https://www.dailymotion.com/player/metadata/video/{video_id}"
            resp = await client.get(metadata_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": f"https://www.dailymotion.com/video/{video_id}",
            })

            if resp.status_code == 404:
                raise ContentNotFoundError("Dailymotion video not found")
            if resp.status_code != 200:
                return None

            data = resp.json()

        # Check for errors
        error = data.get("error")
        if error:
            err_title = error.get("title", "").lower()
            if "not found" in err_title or "deleted" in err_title:
                raise ContentNotFoundError("Video not found or deleted")
            if "age" in err_title or "explicit" in err_title:
                raise AgeRestrictedError()
            if "private" in err_title or "password" in err_title:
                raise LoginRequiredError()
            return None

        title = data.get("title", "Dailymotion Video")
        if len(title) > 80:
            title = title[:77] + "\u2026"

        thumbnail = ""
        poster = data.get("posters", {})
        # Get highest quality poster
        for size in ("1080", "720", "480", "240", "60"):
            if poster.get(size):
                thumbnail = poster[size]
                break

        duration = data.get("duration")
        author = data.get("owner", {}).get("screenname", "")

        # Get video qualities from the qualities object
        qualities = data.get("qualities", {})
        if not qualities:
            return None

        # Try to get the best auto quality or progressive download
        best_url = None
        best_height = 0

        # Dailymotion provides qualities as {"auto": [...], "1080": [...], "720": [...], etc.}
        for quality_key in ("1080", "720", "480", "380", "240", "auto"):
            streams = qualities.get(quality_key, [])
            for stream in streams:
                stream_type = stream.get("type", "")
                stream_url = stream.get("url", "")
                if not stream_url:
                    continue
                # Prefer mp4 progressive downloads, then HLS
                if "video/mp4" in stream_type:
                    try:
                        height = int(quality_key)
                    except ValueError:
                        height = 0
                    if height > best_height or not best_url:
                        best_url = stream_url
                        best_height = height

        # If no mp4 found, try HLS manifest (m3u8)
        if not best_url:
            for quality_key in ("auto",):
                streams = qualities.get(quality_key, [])
                for stream in streams:
                    if "mpegURL" in stream.get("type", "") or "m3u8" in stream.get("url", ""):
                        best_url = stream.get("url", "")
                        best_height = 0
                        break

        if not best_url:
            return None

        return MediaInfo(
            platform="dailymotion",
            title=title,
            thumbnail=thumbnail,
            media_type="video",
            format="mp4",
            quality=f"{best_height}p" if best_height else "best",
            file_size=0,
            download_url=best_url,
            duration=duration,
            author=author,
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

    @staticmethod
    def _parse_video_id(url: str) -> str | None:
        m = _DM_VIDEO_ID_RE.search(url)
        return m.group(1) if m else None
