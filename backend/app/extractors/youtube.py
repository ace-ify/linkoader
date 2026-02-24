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

EXTRACTION_TIMEOUT = 45

# InnerTube API — same endpoint YouTube's own apps hit.
_INNERTUBE_API_URL = "https://www.youtube.com/youtubei/v1/player"
_INNERTUBE_API_KEY = "AIzaSyA8eiZmM1FaDVjRy-df2KTyQ_vz_yYM39w"

# Client configs ordered by datacenter-friendliness.
# android_vr needs no PO token and no JS player — cleanest path.
_INNERTUBE_CLIENTS = [
    {
        "name": "ANDROID_VR",
        "context": {
            "client": {
                "clientName": "ANDROID_VR",
                "clientVersion": "1.71.26",
                "deviceMake": "Oculus",
                "deviceModel": "Quest 3",
                "androidSdkVersion": 32,
                "osName": "Android",
                "osVersion": "12L",
                "hl": "en",
            },
        },
        "user_agent": "com.google.android.apps.youtube.vr.oculus/1.71.26 (Linux; U; Android 12L; eureka-user Build/SQ3A.220605.009.A1) gzip",
    },
    {
        "name": "ANDROID",
        "context": {
            "client": {
                "clientName": "ANDROID",
                "clientVersion": "21.02.35",
                "androidSdkVersion": 30,
                "osName": "Android",
                "osVersion": "11",
                "hl": "en",
            },
        },
        "user_agent": "com.google.android.youtube/21.02.35 (Linux; U; Android 11) gzip",
    },
    {
        "name": "IOS",
        "context": {
            "client": {
                "clientName": "IOS",
                "clientVersion": "21.02.3",
                "deviceMake": "Apple",
                "deviceModel": "iPhone16,2",
                "osName": "iPhone",
                "osVersion": "18.3.2.22D82",
                "hl": "en",
            },
        },
        "user_agent": "com.google.ios.youtube/21.02.3 (iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)",
    },
]

_VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?.*v=|shorts/|live/)|youtu\.be/)([\w-]{11})"
)
_VISITOR_DATA_RE = re.compile(r'"visitorData"\s*:\s*"([^"]+)"')


class YouTubeExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?youtube\.com/watch\?v=[\w-]+",
        r"https?://(www\.)?youtube\.com/shorts/[\w-]+",
        r"https?://youtu\.be/[\w-]+",
        r"https?://(www\.)?youtube\.com/watch\?.*v=[\w-]+",
        r"https?://(www\.)?youtube\.com/live/[\w-]+",
    ]

    async def extract(self, url: str) -> MediaInfo:
        video_id = self._parse_video_id(url)
        if not video_id:
            raise ContentNotFoundError("Could not parse video ID from URL")

        # Strategy 1: Direct InnerTube API (works on datacenter IPs with visitorData)
        try:
            return await asyncio.wait_for(
                self._extract_innertube(video_id),
                timeout=EXTRACTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, AgeRestrictedError, LoginRequiredError):
            raise
        except Exception:
            pass

        # Strategy 2: yt-dlp fallback (better format selection, works on residential IPs)
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(self._extract_ytdlp, url),
                timeout=EXTRACTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, ExtractionFailedError, UpstreamError,
                AgeRestrictedError, LoginRequiredError):
            raise
        except Exception:
            raise ExtractionFailedError()

        return self._info_to_media(info)

    async def _fetch_visitor_data(self, client: httpx.AsyncClient, video_id: str) -> str:
        """Fetch visitorData token from YouTube webpage — required for InnerTube API on datacenter IPs."""
        try:
            resp = await client.get(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                follow_redirects=True,
            )
            if resp.status_code == 200:
                m = _VISITOR_DATA_RE.search(resp.text)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return ""

    async def _extract_innertube(self, video_id: str) -> MediaInfo:
        """Call YouTube's InnerTube API directly — bypasses bot detection."""
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=20) as client:
            # Step 1: Get visitorData from webpage (critical for datacenter IPs)
            visitor_data = await self._fetch_visitor_data(client, video_id)

            # Step 2: Try each InnerTube client with visitorData
            for cfg in _INNERTUBE_CLIENTS:
                try:
                    result = await self._try_innertube_client(client, video_id, cfg, visitor_data)
                    if result:
                        return result
                except (ContentNotFoundError, AgeRestrictedError):
                    raise
                except Exception as e:
                    last_error = e
                    continue

        if last_error:
            raise last_error
        raise ExtractionFailedError("All InnerTube clients failed")

    async def _try_innertube_client(
        self, client: httpx.AsyncClient, video_id: str, cfg: dict, visitor_data: str
    ) -> MediaInfo | None:
        context = cfg["context"].copy()
        context["client"] = cfg["context"]["client"].copy()

        # Inject visitorData into context if available
        if visitor_data:
            context["client"]["visitorData"] = visitor_data

        body = {
            "videoId": video_id,
            "context": context,
            "playbackContext": {
                "contentPlaybackContext": {
                    "html5Preference": "HTML5_PREF_WANTS",
                },
            },
            "contentCheckOk": True,
            "racyCheckOk": True,
        }

        headers = {
            "User-Agent": cfg["user_agent"],
            "X-YouTube-Client-Name": cfg["context"]["client"]["clientName"],
            "X-YouTube-Client-Version": cfg["context"]["client"]["clientVersion"],
            "Origin": "https://www.youtube.com",
            "Content-Type": "application/json",
        }

        # Add visitorData as header too (how yt-dlp does it)
        if visitor_data:
            headers["X-Goog-Visitor-Id"] = visitor_data

        resp = await client.post(
            _INNERTUBE_API_URL,
            params={"key": _INNERTUBE_API_KEY, "prettyPrint": "false"},
            json=body,
            headers=headers,
        )

        if resp.status_code != 200:
            return None

        data = resp.json()

        # Check playability
        playability = data.get("playabilityStatus", {})
        status = playability.get("status", "")

        if status == "LOGIN_REQUIRED":
            reason = playability.get("reason", "").lower()
            if "bot" in reason or "confirm" in reason:
                return None  # Try next client
            if "age" in reason:
                raise AgeRestrictedError()
            return None  # Try next client instead of hard fail

        if status == "UNPLAYABLE":
            raise ContentNotFoundError(
                playability.get("reason", "Content not available")
            )

        if status == "ERROR":
            reason = playability.get("reason", "")
            if "not found" in reason.lower() or "unavailable" in reason.lower():
                raise ContentNotFoundError(reason)
            return None  # Try next client

        if status != "OK":
            return None

        # Extract streaming data
        streaming = data.get("streamingData", {})
        formats = streaming.get("formats", []) + streaming.get("adaptiveFormats", [])

        if not formats:
            return None

        # Pick best pre-merged format (has both video+audio)
        merged = [f for f in streaming.get("formats", []) if f.get("url")]
        if not merged:
            # Fall back to any format with a URL
            merged = [f for f in formats if f.get("url")]

        if not merged:
            return None

        # Sort by quality (height descending)
        merged.sort(key=lambda f: f.get("height", 0), reverse=True)
        best = merged[0]

        # Video details
        details = data.get("videoDetails", {})
        thumbnail = ""
        thumbs = details.get("thumbnail", {}).get("thumbnails", [])
        if thumbs:
            thumbnail = thumbs[-1].get("url", "")

        return MediaInfo(
            platform="youtube",
            title=details.get("title", "Untitled"),
            thumbnail=thumbnail,
            media_type="video",
            format=best.get("mimeType", "video/mp4").split(";")[0].split("/")[-1],
            quality=f"{best.get('height', 0)}p",
            file_size=int(best.get("contentLength", 0)),
            download_url=best["url"],
            duration=int(details.get("lengthSeconds", 0)),
            author=details.get("author", ""),
        )

    def _extract_ytdlp(self, url: str) -> dict:
        """Fallback: use yt-dlp (works better on residential IPs)."""
        opts = {
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "socket_timeout": 15,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise ContentNotFoundError()
                return info
        except yt_dlp.utils.DownloadError as e:
            classify_ytdlp_error(e)

    @staticmethod
    def _info_to_media(info: dict) -> MediaInfo:
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

    @staticmethod
    def _parse_video_id(url: str) -> str | None:
        m = _VIDEO_ID_RE.search(url)
        return m.group(1) if m else None
