import httpx
from urllib.parse import urlparse

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
}


def is_allowed_domain(url: str) -> bool:
    """Only proxy from known media CDN domains."""
    hostname = urlparse(url).hostname or ""
    return any(hostname.endswith(d) for d in ALLOWED_DOMAINS)


async def stream_proxy(url: str):
    """Generator that streams content from source."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            async for chunk in response.aiter_bytes(chunk_size=65536):
                yield chunk


async def get_upstream_headers(url: str) -> dict:
    """
    Does a HEAD request to the upstream CDN to grab Content-Length and
    Content-Type before we start streaming — lets the frontend show real
    progress instead of an indeterminate spinner.
    Falls back to an empty dict if the upstream doesn't support HEAD.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8.0) as client:
            head = await client.head(url)
            headers = {}
            if "content-length" in head.headers:
                headers["Content-Length"] = head.headers["content-length"]
            if "content-type" in head.headers:
                headers["X-Upstream-Content-Type"] = head.headers["content-type"]
            return headers
    except Exception:
        return {}
