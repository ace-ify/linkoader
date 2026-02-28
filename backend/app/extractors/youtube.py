import asyncio
import copy
import json
import re
import httpx
import yt_dlp
from app.extractors.base import BaseExtractor, classify_ytdlp_error, CF_PROXY_URL, CF_PROXY_SECRET
from app.stealth import get_stealth_ytdlp_opts, get_random_headers, stealth_fetch, get_random_ua
from app.models import MediaInfo
from app.exceptions import (
    ContentNotFoundError,
    ExtractionFailedError,
    ExtractionTimeoutError,
    UpstreamError,
    AgeRestrictedError,
    LoginRequiredError,
)

EXTRACTION_TIMEOUT = 20  # Must fit within main.py's 25s limit

# InnerTube API — same endpoint YouTube's own apps hit.
_INNERTUBE_API_URL = "https://www.youtube.com/youtubei/v1/player"
_INNERTUBE_API_KEY = "AIzaSyA8eiZmM1FaDVjRy-df2KTyQ_vz_yYM39w"

# IOS client — works best through CF Worker proxy with visitorData
_IOS_CLIENT = {
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
}

# Fallback clients for direct (non-proxy) InnerTube calls
_INNERTUBE_CLIENTS = [
    {
        "name": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
        "context": {
            "client": {
                "clientName": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
                "clientVersion": "2.0",
                "hl": "en",
            },
            "thirdParty": {"embedUrl": "https://www.google.com"},
        },
        "user_agent": "Mozilla/5.0 (SMART-TV; LINUX; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) 85.0.4183.93/6.5 TV Safari/537.36",
    },
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
    _IOS_CLIENT,
    # WEB client — sometimes works when others don't
    {
        "name": "WEB",
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20250225.01.00",
                "hl": "en",
                "gl": "US",
            },
        },
        "user_agent": None,  # use rotated stealth UA
    },
    # MWEB client — mobile web, another fallback
    {
        "name": "MWEB",
        "context": {
            "client": {
                "clientName": "MWEB",
                "clientVersion": "2.20250225.01.00",
                "hl": "en",
                "gl": "US",
            },
        },
        "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    },
]

_VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?.*v=|shorts/|live/)|youtu\.be/)([\w-]{11})"
)
_VISITOR_DATA_RE = re.compile(r'"visitorData"\s*:\s*"([^"]+)"')
_INITIAL_PLAYER_RE = re.compile(
    r"var\s+ytInitialPlayerResponse\s*=\s*(\{.+?\})\s*;(?:\s*var\s|\s*</script>)",
    re.DOTALL,
)


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

        # Strategy 1: yt-dlp with impersonation (most reliable now)
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(self._extract_ytdlp, url),
                timeout=15,  # Fast fail so we can try other strategies
            )
            return self._info_to_media(info)
        except asyncio.TimeoutError:
            pass  # Try next strategy
        except (ContentNotFoundError, AgeRestrictedError):
            raise
        except Exception:
            pass  # Try next strategy

        # Strategy 2: CF Worker proxy (visitorData + IOS client via Cloudflare's trusted IPs)
        if CF_PROXY_URL and CF_PROXY_SECRET:
            try:
                result = await asyncio.wait_for(
                    self._extract_via_proxy(video_id),
                    timeout=12,
                )
                if result:
                    return result
            except asyncio.TimeoutError:
                raise ExtractionTimeoutError()
            except (ContentNotFoundError, AgeRestrictedError):
                raise
            except Exception:
                pass

        # Strategy 3: Direct stealth InnerTube (curl_cffi TLS impersonation)
        try:
            result = await asyncio.wait_for(
                self._extract_innertube_stealth(video_id),
                timeout=10,
            )
            if result:
                return result
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, AgeRestrictedError, LoginRequiredError):
            raise
        except Exception:
            pass

        raise ExtractionFailedError(
            "Could not extract this YouTube video. It may be restricted or unavailable."
        )

    # ── CF Worker proxy strategy ──────────────────────────────────────

    async def _extract_via_proxy(self, video_id: str) -> MediaInfo | None:
        """Use CF Worker proxy to bypass YouTube's datacenter IP blocking.

        1. Proxy fetches YouTube page → we extract visitorData
        2. Proxy calls InnerTube API with visitorData + IOS client → streams
        """
        proxy_headers = {
            "Content-Type": "application/json",
            "X-Proxy-Secret": CF_PROXY_SECRET,
        }

        async with httpx.AsyncClient(timeout=25) as client:
            # Step 1: Get visitorData from YouTube page via proxy
            visitor_data = ""
            try:
                vd_resp = await client.post(
                    CF_PROXY_URL,
                    headers=proxy_headers,
                    json={
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "headers": get_random_headers({"Accept-Language": "en-US,en;q=0.9"}),
                    },
                )
                if vd_resp.status_code == 200:
                    m = _VISITOR_DATA_RE.search(vd_resp.text)
                    if m:
                        visitor_data = m.group(1)

                    # Also try to get player response from webpage
                    m2 = _INITIAL_PLAYER_RE.search(vd_resp.text)
                    if m2:
                        try:
                            wp_data = json.loads(m2.group(1))
                            result = self._player_response_to_media(wp_data)
                            if result:
                                return result
                        except (json.JSONDecodeError, Exception):
                            pass
            except Exception:
                pass

            if not visitor_data:
                return None

            # Step 2: Call InnerTube API via proxy with visitorData + IOS client
            context = copy.deepcopy(_IOS_CLIENT["context"])
            context["client"]["visitorData"] = visitor_data

            api_resp = await client.post(
                CF_PROXY_URL,
                headers=proxy_headers,
                json={
                    "url": f"{_INNERTUBE_API_URL}?key={_INNERTUBE_API_KEY}&prettyPrint=false",
                    "method": "POST",
                    "headers": {
                        "User-Agent": _IOS_CLIENT["user_agent"],
                        "Content-Type": "application/json",
                        "Origin": "https://www.youtube.com",
                        "X-Goog-Visitor-Id": visitor_data,
                    },
                    "payload": {
                        "videoId": video_id,
                        "context": context,
                        "contentCheckOk": True,
                        "racyCheckOk": True,
                    },
                },
            )

            if api_resp.status_code != 200:
                return None

            data = api_resp.json()
            return self._player_response_to_media(data)

    # ── Direct stealth InnerTube strategy (curl_cffi TLS) ─────────────

    async def _extract_innertube_stealth(self, video_id: str) -> MediaInfo | None:
        """Direct InnerTube via stealth_fetch (curl_cffi TLS impersonation).

        Unlike the old httpx version, this uses curl_cffi so YouTube can't
        detect the Python TLS fingerprint.
        """
        # Step 1: Fetch webpage via stealth to get visitorData
        visitor_data = ""
        try:
            resp = await stealth_fetch(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={"Accept-Language": "en-US,en;q=0.9"},
                timeout=20.0,
            )
            if resp.status_code == 200:
                text = resp.text
                m = _VISITOR_DATA_RE.search(text)
                if m:
                    visitor_data = m.group(1)
                # Try inline player response
                m2 = _INITIAL_PLAYER_RE.search(text)
                if m2:
                    try:
                        wp_data = json.loads(m2.group(1))
                        result = self._player_response_to_media(wp_data)
                        if result:
                            return result
                    except (json.JSONDecodeError, Exception):
                        pass
        except Exception:
            pass

        # Step 2: Try each InnerTube client via stealth_fetch
        for cfg in _INNERTUBE_CLIENTS:
            try:
                context = copy.deepcopy(cfg["context"])
                if visitor_data:
                    context["client"]["visitorData"] = visitor_data

                ua = cfg["user_agent"] or get_random_ua()
                headers = {
                    "User-Agent": ua,
                    "Content-Type": "application/json",
                    "Origin": "https://www.youtube.com",
                    "Referer": "https://www.youtube.com/",
                }
                if visitor_data:
                    headers["X-Goog-Visitor-Id"] = visitor_data

                api_url = f"{_INNERTUBE_API_URL}?key={_INNERTUBE_API_KEY}&prettyPrint=false"
                resp = await stealth_fetch(
                    api_url,
                    method="POST",
                    headers=headers,
                    json_body={
                        "videoId": video_id,
                        "context": context,
                        "contentCheckOk": True,
                        "racyCheckOk": True,
                    },
                    timeout=15.0,
                    rate_limit=False,  # don't delay between client attempts
                )

                if resp.status_code == 200:
                    result = self._player_response_to_media(resp.json())
                    if result:
                        return result
            except (ContentNotFoundError, AgeRestrictedError):
                raise
            except Exception:
                continue

        return None

    # ── Shared helpers ────────────────────────────────────────────────

    def _player_response_to_media(self, data: dict) -> MediaInfo | None:
        """Convert a raw player response dict to MediaInfo."""
        playability = data.get("playabilityStatus", {})
        status = playability.get("status", "")

        if status == "LOGIN_REQUIRED":
            reason = playability.get("reason", "").lower()
            if "age" in reason:
                raise AgeRestrictedError()
            # Don't raise LoginRequiredError here — just return None so
            # we can try the next InnerTube client or yt-dlp
            return None

        if status == "UNPLAYABLE":
            raise ContentNotFoundError(
                playability.get("reason", "Content not available")
            )

        if status == "ERROR":
            reason = playability.get("reason", "")
            if "not found" in reason.lower() or "unavailable" in reason.lower():
                raise ContentNotFoundError(reason)
            return None

        if status != "OK":
            return None

        streaming = data.get("streamingData", {})
        all_formats = streaming.get("formats", []) + streaming.get("adaptiveFormats", [])
        if not all_formats:
            return None

        # Prefer combined (video+audio) formats
        merged = [f for f in streaming.get("formats", []) if f.get("url")]
        if not merged:
            # IOS client returns only adaptive — pick best video stream with URL
            video_streams = [
                f for f in streaming.get("adaptiveFormats", [])
                if f.get("url") and f.get("height")
            ]
            if video_streams:
                merged = video_streams

        if not merged:
            # Last resort: anything with a URL
            merged = [f for f in all_formats if f.get("url")]

        if not merged:
            return None

        merged.sort(key=lambda f: f.get("height", 0), reverse=True)
        best = merged[0]

        details = data.get("videoDetails", {})
        thumbnail = ""
        thumbs = details.get("thumbnail", {}).get("thumbnails", [])
        if thumbs:
            thumbnail = thumbs[-1].get("url", "")

        title = details.get("title", "Untitled")
        if len(title) > 80:
            title = title[:77] + "\u2026"

        return MediaInfo(
            platform="youtube",
            title=title,
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
        """Primary: use yt-dlp with full stealth + multiple client fallback."""
        opts = get_stealth_ytdlp_opts("best[ext=mp4]/best", {
            "extract_flat": False,
            # Try multiple YouTube player clients for best coverage
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "web_creator", "mweb", "tv"],
                },
            },
        })
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
