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
