import re
import asyncio
from bs4 import BeautifulSoup
from app.extractors.base import BaseExtractor, proxy_fetch
from app.stealth import get_random_headers
from app.models import MediaInfo
from app.exceptions import (
    ContentNotFoundError,
    ExtractionFailedError,
    ExtractionTimeoutError,
    UpstreamError,
)

EXTRACTION_TIMEOUT = 20


class PinterestExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?pinterest\.com/pin/[\w-]+",
        r"https?://([\w]+\.)?pinterest\.com/pin/[\w-]+",
        r"https?://pin\.it/[\w-]+",
    ]

    async def extract(self, url: str) -> MediaInfo:
        try:
            return await asyncio.wait_for(
                self._do_extract(url),
                timeout=EXTRACTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, UpstreamError, ExtractionFailedError):
            raise
        except Exception:
            raise ExtractionFailedError()

    async def _do_extract(self, url: str) -> MediaInfo:
        headers = get_random_headers()

        try:
            response = await proxy_fetch(url, headers=headers, timeout=12.0)
        except Exception:
            raise UpstreamError()

        if response.status_code == 404:
            raise ContentNotFoundError()
        if response.status_code != 200:
            raise UpstreamError()

        soup = BeautifulSoup(response.text, "html.parser")

        og_video = soup.find("meta", property="og:video")
        og_image = soup.find("meta", property="og:image")
        og_title = soup.find("meta", property="og:title")

        if og_video and og_video.get("content"):
            download_url = og_video["content"]
            media_type = "video"
            fmt = "mp4"
        elif og_image and og_image.get("content"):
            download_url = og_image["content"]
            download_url = self._get_original_url(download_url)
            media_type = "image"
            fmt = "jpg"
        else:
            raise ContentNotFoundError("Could not find media in this Pinterest pin")

        title = og_title["content"] if og_title and og_title.get("content") else "Pinterest Pin"
        thumbnail = og_image["content"] if og_image and og_image.get("content") else ""

        return MediaInfo(
            platform="pinterest",
            title=title[:80],
            thumbnail=thumbnail,
            media_type=media_type,
            format=fmt,
            quality="original",
            file_size=0,
            download_url=download_url,
        )

    def _get_original_url(self, url: str) -> str:
        """Replace Pinterest image size suffix to get original resolution."""
        return re.sub(r"/\d+x/", "/originals/", url)
