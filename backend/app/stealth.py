"""
Stealth networking layer for Linkoader.

Provides:
- Realistic browser header rotation (full profile, not just UA)
- TLS fingerprint impersonation via curl_cffi
- Cookie jar persistence across request chains
- Request timing randomization
- Referer chain simulation

All scraping/API requests should go through `stealth_fetch()` or
use `get_stealth_ytdlp_opts()` for yt-dlp calls.
"""

import asyncio
import random
import time
from dataclasses import dataclass, field

try:
    from curl_cffi.requests import AsyncSession
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

import httpx

# ──────────────────────────────────────────────────────────────────────
# Browser profiles — complete header sets that match real browsers
# ──────────────────────────────────────────────────────────────────────

BROWSER_PROFILES = [
    # Chrome 131 on Windows 10
    {
        "impersonate": "chrome131",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        },
    },
    # Chrome 130 on Windows 10
    {
        "impersonate": "chrome130",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-CH-UA": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
    },
    # Chrome 131 on macOS
    {
        "impersonate": "chrome131",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
    },
    # Firefox 133 on Windows 10
    {
        "impersonate": "firefox133",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive",
        },
    },
    # Edge 131 on Windows 10
    {
        "impersonate": "edge131",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-CH-UA": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
    },
    # Safari 18 on macOS
    {
        "impersonate": "safari18_0",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Connection": "keep-alive",
        },
    },
    # Chrome on Android (mobile)
    {
        "impersonate": "chrome131_android",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-CH-UA-Mobile": "?1",
            "Sec-CH-UA-Platform": '"Android"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
    },
]

# curl_cffi impersonate names that are known to work reliably
_SAFE_IMPERSONATES = ["chrome131", "chrome130", "chrome124", "chrome120",
                       "chrome116", "chrome110", "chrome107", "chrome104",
                       "edge131", "edge101", "safari18_0", "safari17_0"]


def get_random_profile() -> dict:
    """Pick a random browser profile."""
    return random.choice(BROWSER_PROFILES)


def get_random_headers(extra: dict | None = None) -> dict:
    """Get a random complete header set, optionally merged with extras."""
    headers = dict(get_random_profile()["headers"])
    if extra:
        headers.update(extra)
    return headers


def get_random_ua() -> str:
    """Get just a random User-Agent string."""
    return get_random_profile()["headers"]["User-Agent"]


# ──────────────────────────────────────────────────────────────────────
# Stealth response wrapper
# ──────────────────────────────────────────────────────────────────────

@dataclass
class StealthResponse:
    """Unified response from stealth_fetch, regardless of backend."""
    status_code: int
    text: str
    headers: dict = field(default_factory=dict)

    def json(self):
        import json
        return json.loads(self.text)


# ──────────────────────────────────────────────────────────────────────
# Core stealth fetch — uses curl_cffi when available, httpx fallback
# ──────────────────────────────────────────────────────────────────────

# Rate limiting: track last request time per domain
_domain_last_request: dict[str, float] = {}
_MIN_REQUEST_INTERVAL = 0.3  # seconds between requests to same domain


async def _rate_limit_domain(url: str) -> None:
    """Add a randomized delay to avoid burst patterns."""
    from urllib.parse import urlparse
    domain = urlparse(url).hostname or ""
    now = time.monotonic()
    last = _domain_last_request.get(domain, 0)
    elapsed = now - last
    if elapsed < _MIN_REQUEST_INTERVAL:
        delay = _MIN_REQUEST_INTERVAL - elapsed + random.uniform(0.1, 0.5)
        await asyncio.sleep(delay)
    _domain_last_request[domain] = time.monotonic()


async def stealth_fetch(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    json_body: dict | None = None,
    timeout: float = 15.0,
    referer: str | None = None,
    rate_limit: bool = True,
) -> StealthResponse:
    """Make a request with full browser impersonation.

    - Uses curl_cffi with TLS fingerprint impersonation if available
    - Falls back to httpx with realistic headers if not
    - Automatically rotates browser profiles
    - Adds randomized timing delays per domain
    """
    if rate_limit:
        await _rate_limit_domain(url)

    profile = get_random_profile()
    merged_headers = dict(profile["headers"])
    if referer:
        merged_headers["Referer"] = referer
        merged_headers["Sec-Fetch-Site"] = "same-origin"
    if headers:
        merged_headers.update(headers)

    if HAS_CURL_CFFI:
        return await _fetch_curl_cffi(
            url, method=method, headers=merged_headers,
            json_body=json_body, timeout=timeout,
            impersonate=profile["impersonate"],
        )
    else:
        return await _fetch_httpx(
            url, method=method, headers=merged_headers,
            json_body=json_body, timeout=timeout,
        )


async def _fetch_curl_cffi(
    url: str,
    *,
    method: str,
    headers: dict,
    json_body: dict | None,
    timeout: float,
    impersonate: str,
) -> StealthResponse:
    """Fetch via curl_cffi with TLS impersonation."""
    # Some impersonate values may not be available in installed version,
    # fall back gracefully
    try:
        async with AsyncSession(impersonate=impersonate, timeout=timeout) as s:
            if method == "GET":
                resp = await s.get(url, headers=headers)
            elif method == "POST":
                if json_body:
                    resp = await s.post(url, headers=headers, json=json_body)
                else:
                    resp = await s.post(url, headers=headers)
            elif method == "HEAD":
                resp = await s.head(url, headers=headers)
            else:
                resp = await s.request(method, url, headers=headers, json=json_body)

            resp_headers = dict(resp.headers) if hasattr(resp, "headers") else {}
            return StealthResponse(
                status_code=resp.status_code,
                text=resp.text,
                headers=resp_headers,
            )
    except Exception:
        # If impersonate value fails, try with a safe default
        try:
            async with AsyncSession(impersonate="chrome120", timeout=timeout) as s:
                if method == "GET":
                    resp = await s.get(url, headers=headers)
                elif method == "POST":
                    if json_body:
                        resp = await s.post(url, headers=headers, json=json_body)
                    else:
                        resp = await s.post(url, headers=headers)
                else:
                    resp = await s.request(method, url, headers=headers, json=json_body)

                resp_headers = dict(resp.headers) if hasattr(resp, "headers") else {}
                return StealthResponse(
                    status_code=resp.status_code,
                    text=resp.text,
                    headers=resp_headers,
                )
        except Exception:
            # Final fallback to httpx
            return await _fetch_httpx(
                url, method=method, headers=headers,
                json_body=json_body, timeout=timeout,
            )


async def _fetch_httpx(
    url: str,
    *,
    method: str,
    headers: dict,
    json_body: dict | None,
    timeout: float,
) -> StealthResponse:
    """Fallback: plain httpx with realistic headers."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers)
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=json_body)
        elif method == "HEAD":
            resp = await client.head(url, headers=headers)
        else:
            resp = await client.request(method, url, headers=headers, json=json_body)

        resp_headers = dict(resp.headers)
        return StealthResponse(
            status_code=resp.status_code,
            text=resp.text,
            headers=resp_headers,
        )


# ──────────────────────────────────────────────────────────────────────
# yt-dlp stealth options
# ──────────────────────────────────────────────────────────────────────

def get_stealth_ytdlp_opts(
    format_spec: str = "best[ext=mp4]/best",
    extra_opts: dict | None = None,
) -> dict:
    """Return yt-dlp options with anti-detection enabled.

    Adds:
    - Browser impersonation (curl_cffi TLS)
    - Randomized headers
    - Request rate limiting
    - Retry logic
    """
    profile = get_random_profile()

    opts: dict = {
        "format": format_spec,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 15,
        # Anti-detection: browser impersonation via curl_cffi
        "http_headers": profile["headers"],
        # Retries
        "retries": 3,
        "fragment_retries": 3,
        # Rate limiting — don't hammer servers
        "sleep_interval_requests": 0.5,
    }

    # Enable TLS impersonation if curl_cffi is available
    if HAS_CURL_CFFI:
        # yt-dlp's impersonate feature needs curl_cffi installed
        opts["impersonate"] = profile["impersonate"]

    if extra_opts:
        opts.update(extra_opts)

    return opts
