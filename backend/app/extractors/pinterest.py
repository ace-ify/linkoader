import httpx
from bs4 import BeautifulSoup
from app.extractors.base import BaseExtractor
from app.models import MediaInfo
from app.exceptions import ContentNotFoundError, ExtractionFailedError, UpstreamError


class PinterestExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?pinterest\.com/pin/[\w-]+",
        r"https?://([\w]+\.)?pinterest\.com/pin/[\w-]+",
        r"https?://pin\.it/[\w-]+",
    ]

    async def extract(self, url: str) -> MediaInfo:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()
            except httpx.TimeoutException:
                raise UpstreamError()
            except httpx.HTTPStatusError:
                raise ContentNotFoundError()

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
            # Try to get original resolution by replacing size suffix
            download_url = self._get_original_url(download_url)
            media_type = "image"
            fmt = "jpg"
        else:
            raise ContentNotFoundError()

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
        # Pinterest URLs like: https://i.pinimg.com/736x/xx/xx/xx.jpg
        # Replace 736x, 564x, 474x, 236x, 170x with originals
        import re
        return re.sub(r"/\d+x/", "/originals/", url)
