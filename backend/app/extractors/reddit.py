import asyncio
import re
import yt_dlp
from app.extractors.base import BaseExtractor, classify_ytdlp_error, proxy_fetch
from app.models import MediaInfo
from app.exceptions import (
    ContentNotFoundError,
    ExtractionFailedError,
    ExtractionTimeoutError,
    UpstreamError,
    LoginRequiredError,
)

EXTRACTION_TIMEOUT = 30

_REDDIT_POST_RE = re.compile(
    r"https?://(?:www\.|old\.)?reddit\.com/r/\w+/comments/([\w-]+)"
)


class RedditExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?reddit\.com/r/\w+/comments/[\w-]+",
        r"https?://(old\.)?reddit\.com/r/\w+/comments/[\w-]+",
        r"https?://redd\.it/[\w-]+",
        r"https?://(www\.)?reddit\.com/r/\w+/s/[\w-]+",
        r"https?://v\.redd\.it/[\w-]+",
        r"https?://i\.redd\.it/[\w-]+",
    ]

    async def extract(self, url: str) -> MediaInfo:
        # Strategy 1: Direct Reddit JSON API (works on datacenter IPs)
        try:
            result = await asyncio.wait_for(
                self._extract_direct(url),
                timeout=EXTRACTION_TIMEOUT,
            )
            if result:
                return result
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, LoginRequiredError):
            raise
        except Exception:
            pass

        # Strategy 2: yt-dlp fallback
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(self._extract_sync, url),
                timeout=EXTRACTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except (ContentNotFoundError, UpstreamError, ExtractionFailedError,
                LoginRequiredError):
            raise
        except Exception:
            raise ExtractionFailedError()

        ext = info.get("ext", "mp4")
        is_image = ext in ("jpg", "jpeg", "png", "webp", "gif")
        media_type = "image" if is_image else "video"

        title = info.get("title", "Reddit Post")
        if len(title) > 80:
            title = title[:77] + "\u2026"

        return MediaInfo(
            platform="reddit",
            title=title,
            thumbnail=info.get("thumbnail", ""),
            media_type=media_type,
            format=ext,
            quality=f"{info.get('height', 0)}p" if info.get("height") else "original",
            file_size=info.get("filesize") or info.get("filesize_approx") or 0,
            download_url=info["url"],
            duration=info.get("duration"),
            author=info.get("uploader"),
        )

    async def _extract_direct(self, url: str) -> MediaInfo | None:
        """Use Reddit's public JSON API — no auth needed."""
        clean_url = url.split("?")[0].rstrip("/")

        # For short URLs, resolve via proxy_fetch HEAD-like GET
        if "redd.it" in url or "/s/" in url:
            try:
                resp = await proxy_fetch(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; bot)",
                })
                # proxy_fetch follows redirects, check if we got a reddit page
                # We can't get the final URL from proxy_fetch, so try the original
                return None  # fall through to yt-dlp for short URLs
            except Exception:
                return None

        # Fetch JSON for the post
        json_url = clean_url + ".json"
        resp = await proxy_fetch(json_url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; Linkloader/1.0)",
        })

        if resp.status_code == 404:
            raise ContentNotFoundError("Reddit post not found")
        if resp.status_code == 403:
            raise LoginRequiredError()
        if resp.status_code != 200:
            return None

        data = resp.json()

        # Parse the Reddit API response
        if not isinstance(data, list) or len(data) < 1:
            return None

        post_data = data[0].get("data", {}).get("children", [{}])[0].get("data", {})
        if not post_data:
            return None

        title = post_data.get("title", "Reddit Post")
        if len(title) > 80:
            title = title[:77] + "\u2026"
        author = post_data.get("author", "")
        thumbnail = post_data.get("thumbnail", "")
        if thumbnail in ("self", "default", "nsfw", "spoiler", ""):
            thumbnail = ""

        # Check for video (Reddit-hosted)
        if post_data.get("is_video") and post_data.get("media"):
            reddit_video = post_data["media"].get("reddit_video", {})
            video_url = reddit_video.get("fallback_url", "")
            if video_url:
                # Remove the ?source=fallback query param
                video_url = video_url.split("?")[0]
                return MediaInfo(
                    platform="reddit",
                    title=title,
                    thumbnail=thumbnail,
                    media_type="video",
                    format="mp4",
                    quality=f"{reddit_video.get('height', 0)}p",
                    file_size=0,
                    download_url=video_url,
                    duration=reddit_video.get("duration"),
                    author=author,
                )

        # Check for image posts
        url_field = post_data.get("url", "")
        if url_field and any(url_field.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
            fmt = url_field.rsplit(".", 1)[-1]
            return MediaInfo(
                platform="reddit",
                title=title,
                thumbnail=thumbnail,
                media_type="image",
                format=fmt,
                quality="original",
                file_size=0,
                download_url=url_field,
                author=author,
            )

        # Check for i.redd.it images
        if url_field and "i.redd.it" in url_field:
            fmt = url_field.rsplit(".", 1)[-1] if "." in url_field.split("/")[-1] else "jpg"
            return MediaInfo(
                platform="reddit",
                title=title,
                thumbnail=thumbnail,
                media_type="image",
                format=fmt,
                quality="original",
                file_size=0,
                download_url=url_field,
                author=author,
            )

        # Check for gallery posts
        gallery_data = post_data.get("gallery_data", {})
        media_metadata = post_data.get("media_metadata", {})
        if gallery_data and media_metadata:
            items = gallery_data.get("items", [])
            if items:
                first_id = items[0].get("media_id", "")
                meta = media_metadata.get(first_id, {})
                if meta.get("s", {}).get("u"):
                    img_url = meta["s"]["u"].replace("&amp;", "&")
                    fmt = meta.get("m", "image/jpeg").split("/")[-1]
                    return MediaInfo(
                        platform="reddit",
                        title=title,
                        thumbnail=thumbnail,
                        media_type="image",
                        format=fmt,
                        quality="original",
                        file_size=0,
                        download_url=img_url,
                        author=author,
                    )

        # Check for external video links (v.redd.it crosspost, gfycat, etc.)
        crosspost = post_data.get("crosspost_parent_list", [])
        if crosspost:
            cp = crosspost[0]
            if cp.get("is_video") and cp.get("media"):
                reddit_video = cp["media"].get("reddit_video", {})
                video_url = reddit_video.get("fallback_url", "")
                if video_url:
                    video_url = video_url.split("?")[0]
                    return MediaInfo(
                        platform="reddit",
                        title=title,
                        thumbnail=thumbnail,
                        media_type="video",
                        format="mp4",
                        quality=f"{reddit_video.get('height', 0)}p",
                        file_size=0,
                        download_url=video_url,
                        duration=reddit_video.get("duration"),
                        author=author,
                    )

        # No downloadable media found
        raise ContentNotFoundError("This Reddit post doesn't contain downloadable media")

    def _extract_sync(self, url: str) -> dict:
        ydl_opts = {
            "format": "best[ext=mp4]/best",
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
            classify_ytdlp_error(e)
