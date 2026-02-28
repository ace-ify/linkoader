import httpx
from urllib.parse import urlparse
from app.stealth import get_random_headers, HAS_CURL_CFFI

ALLOWED_DOMAINS = {
    # YouTube
    "googlevideo.com",
    "ytimg.com",
    # Instagram
    "cdninstagram.com",
    "instagram.com",
    # Facebook
    "fbcdn.net",
    "scontent.xx.fbcdn.net",
    "video.xx.fbcdn.net",
    # Pinterest
    "pinimg.com",
    # TikTok
    "tiktokcdn.com",
    "tiktokcdn-us.com",
    "musical.ly",
    "tiktokv.com",
    "tiktokcdn-eu.com",
    # Twitter / X
    "twimg.com",
    "video.twimg.com",
    "pbs.twimg.com",
    "ton.twitter.com",
    "abs.twimg.com",
    # Reddit
    "redd.it",
    "redditmedia.com",
    "redgifs.com",
    "preview.redd.it",
    "v.redd.it",
    # Snapchat
    "cf-st.sc",
    "snap-storage-cdn.l.google.com",
    "bolt-gcdn.sc",
    # Threads (shares Instagram CDN)
    "threads.net",
    # Twitch
    "clips-media-assets2.twitch.tv",
    "vod-secure.twitch.tv",
    "production.assets.clips.twitchcdn.net",
    "usher.ttvnw.net",
    # LinkedIn
    "media.licdn.com",
    "dms.licdn.com",
    # Spotify
    "audio-ak-spotify-com.akamaized.net",
    "audio4-ak-spotify-com.akamaized.net",
    "akamaized.net",
    # Dailymotion
    "dailymotion.com",
    "dmcdn.net",
    "proxy-im.dailymotion.com",
}


def is_allowed_domain(url: str) -> bool:
    """Only proxy from known media CDN domains."""
    hostname = urlparse(url).hostname or ""
    return any(hostname.endswith(d) for d in ALLOWED_DOMAINS)


async def stream_proxy(url: str):
    """Generator that streams content from source with stealth headers."""
    headers = get_random_headers()
    # Remove headers not appropriate for media downloads
    for key in ("Sec-Fetch-Dest", "Sec-Fetch-Mode", "Sec-Fetch-Site",
                "Sec-Fetch-User", "Upgrade-Insecure-Requests", "Cache-Control"):
        headers.pop(key, None)

    if HAS_CURL_CFFI:
        # Use curl_cffi for TLS-impersonated streaming
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome131", timeout=60) as s:
                resp = await s.get(url, headers=headers, stream=True)
                async for chunk in resp.aiter_content(65536):
                    yield chunk
                return
        except Exception:
            pass  # Fall back to httpx

    # Fallback: httpx with stealth headers
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        async with client.stream("GET", url, headers=headers) as response:
            async for chunk in response.aiter_bytes(chunk_size=65536):
                yield chunk


async def get_upstream_headers(url: str) -> dict:
    """
    Does a HEAD request to the upstream CDN to grab Content-Length and
    Content-Type before we start streaming — lets the frontend show real
    progress instead of an indeterminate spinner.
    Falls back to an empty dict if the upstream doesn't support HEAD.
    """
    headers = get_random_headers()
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8.0) as client:
            head = await client.head(url, headers=headers)
            result = {}
            if "content-length" in head.headers:
                result["Content-Length"] = head.headers["content-length"]
            if "content-type" in head.headers:
                result["X-Upstream-Content-Type"] = head.headers["content-type"]
            return result
    except Exception:
        return {}
