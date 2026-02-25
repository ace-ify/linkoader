import asyncio
import yt_dlp
from bs4 import BeautifulSoup
from app.extractors.base import BaseExtractor, proxy_fetch
from app.models import MediaInfo
from app.exceptions import (
    ContentNotFoundError,
    ExtractionFailedError,
    ExtractionTimeoutError,
    UpstreamError,
    LoginRequiredError,
)

EXTRACTION_TIMEOUT = 30


class InstagramExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?instagram\.com/p/[\w-]+",
        r"https?://(www\.)?instagram\.com/reel/[\w-]+",
        r"https?://(www\.)?instagram\.com/reels/[\w-]+",
        r"https?://(www\.)?instagram\.com/stories/[\w-]+/[\d]+",
    ]

    async def extract(self, url: str) -> MediaInfo:
        # Try yt-dlp first (works for reels and some posts)
        try:
            return await asyncio.wait_for(
                self._extract_with_ytdlp(url),
                timeout=EXTRACTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, LoginRequiredError):
            raise
        except Exception:
            pass

        # Fallback to og:meta scraping for images
        try:
            return await asyncio.wait_for(
                self._extract_with_scraping(url),
                timeout=15,
            )
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, UpstreamError):
            raise
        except Exception:
            raise ExtractionFailedError()

    async def _extract_with_ytdlp(self, url: str) -> MediaInfo:
        info = await asyncio.to_thread(self._ytdlp_sync, url)
        return MediaInfo(
            platform="instagram",
            title=info.get("title", info.get("description", "Instagram Post")[:80]),
            thumbnail=info.get("thumbnail", ""),
            media_type="video" if info.get("ext") in ("mp4", "webm") else "image",
            format=info.get("ext", "mp4"),
            quality=f"{info.get('height', 0)}p" if info.get("height") else "original",
            file_size=info.get("filesize") or info.get("filesize_approx") or 0,
            download_url=info["url"],
            duration=info.get("duration"),
            author=info.get("uploader"),
        )

    def _ytdlp_sync(self, url: str) -> dict:
        ydl_opts = {
            "format": "best",
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 15,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise ContentNotFoundError()
                return info
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e).lower()
            if "login" in error_msg or "authentication" in error_msg:
                raise LoginRequiredError()
            if "not found" in error_msg or "private" in error_msg:
                raise ContentNotFoundError()
            if "urlopen error" in error_msg:
                raise UpstreamError()
            raise ExtractionFailedError()

    async def _extract_with_scraping(self, url: str) -> MediaInfo:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        try:
            response = await proxy_fetch(url, headers=headers)
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
            media_type = "image"
            fmt = "jpg"
        else:
            raise ContentNotFoundError("Could not find media in this Instagram post")

        title = og_title["content"] if og_title and og_title.get("content") else "Instagram Post"
        thumbnail = og_image["content"] if og_image and og_image.get("content") else ""

        return MediaInfo(
            platform="instagram",
            title=title[:80],
            thumbnail=thumbnail,
            media_type=media_type,
            format=fmt,
            quality="original",
            file_size=0,
            download_url=download_url,
        )
