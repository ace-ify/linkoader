from abc import ABC, abstractmethod
from dataclasses import dataclass
from app.models import MediaInfo
import httpx
import os
import re

# Cloudflare Worker proxy config — set these env vars on Render
CF_PROXY_URL = os.environ.get("CF_PROXY_URL", "")
CF_PROXY_SECRET = os.environ.get("CF_PROXY_SECRET", "")


@dataclass
class ProxyResponse:
    """Lightweight response object returned by proxy_fetch."""
    status_code: int
    text: str

    def json(self):
        import json
        return json.loads(self.text)


async def proxy_fetch(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    json_body: dict | None = None,
    timeout: float = 15.0,
) -> ProxyResponse:
    """Fetch a URL, routing through CF Worker proxy if configured.

    Falls back to direct httpx request if proxy is not set up.
    """
    if CF_PROXY_URL and CF_PROXY_SECRET:
        # Route through Cloudflare Worker
        payload: dict = {"url": url, "method": method}
        if headers:
            payload["headers"] = headers
        if json_body and method in ("POST", "PUT", "PATCH"):
            payload["payload"] = json_body

        async with httpx.AsyncClient(timeout=timeout + 10) as client:
            resp = await client.post(
                CF_PROXY_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-Proxy-Secret": CF_PROXY_SECRET,
                },
                json=payload,
            )
            return ProxyResponse(status_code=resp.status_code, text=resp.text)
    else:
        # Direct request
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers or {})
            else:
                resp = await client.request(
                    method, url, headers=headers or {}, json=json_body,
                )
            return ProxyResponse(status_code=resp.status_code, text=resp.text)


class BaseExtractor(ABC):
    """Base class for all platform extractors."""

    SUPPORTED_PATTERNS: list[str] = []

    def matches(self, url: str) -> bool:
        """Check if this extractor handles the given URL."""
        return any(re.match(p, url) for p in self.SUPPORTED_PATTERNS)

    @abstractmethod
    async def extract(self, url: str) -> MediaInfo:
        """Extract media info from the URL.

        Returns MediaInfo on success.
        Raises ExtractionError on failure.
        """
        ...

    @property
    def platform_name(self) -> str:
        """Human-readable platform name."""
        return self.__class__.__name__.replace("Extractor", "").lower()


def classify_ytdlp_error(e: Exception) -> None:
    """Classify a yt-dlp DownloadError into a specific exception type.

    Always raises — never returns normally.
    """
    from app.exceptions import (
        ContentNotFoundError,
        ExtractionFailedError,
        UpstreamError,
        AgeRestrictedError,
        LoginRequiredError,
    )

    error_msg = str(e).lower()

    # Content not available
    if any(kw in error_msg for kw in (
        "not found", "removed", "private", "unavailable",
        "does not exist", "been deleted", "no video", "no media",
        "protected", "suspended",
    )):
        raise ContentNotFoundError()

    # Age / maturity gates
    if any(kw in error_msg for kw in ("age", "mature", "age-restricted")):
        raise AgeRestrictedError()

    # Login required
    if any(kw in error_msg for kw in (
        "login", "sign in", "authentication", "authenticate",
    )):
        raise LoginRequiredError()

    # Network issues
    if any(kw in error_msg for kw in (
        "urlopen error", "timed out", "connection refused",
        "name or service not known", "network is unreachable",
    )):
        raise UpstreamError()

    # Fallback
    raise ExtractionFailedError()
