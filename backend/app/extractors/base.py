from abc import ABC, abstractmethod
from app.models import MediaInfo
import re


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
