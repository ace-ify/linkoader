import asyncio
import re
from app.extractors.base import BaseExtractor, proxy_fetch
from app.models import MediaInfo
from app.exceptions import (
    ContentNotFoundError,
    ExtractionFailedError,
    ExtractionTimeoutError,
)

EXTRACTION_TIMEOUT = 30

_SPOTIFY_ID_RE = re.compile(
    r"open\.spotify\.com/(track|episode|show|album|playlist)/([\w-]+)"
)


class SpotifyExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://open\.spotify\.com/track/[\w-]+",
        r"https?://open\.spotify\.com/episode/[\w-]+",
        r"https?://open\.spotify\.com/show/[\w-]+",
        r"https?://open\.spotify\.com/album/[\w-]+",
        r"https?://open\.spotify\.com/playlist/[\w-]+",
    ]

    async def extract(self, url: str) -> MediaInfo:
        m = _SPOTIFY_ID_RE.search(url)
        if not m:
            raise ContentNotFoundError("Could not parse Spotify URL")

        content_type = m.group(1)
        content_id = m.group(2)

        # Music tracks, albums, and playlists are DRM-protected
        if content_type in ("track", "album", "playlist"):
            raise ContentNotFoundError(
                f"Spotify {content_type}s are DRM-protected and cannot be downloaded. "
                "Only podcast episodes are supported."
            )

        # Shows — link to latest episode
        if content_type == "show":
            raise ContentNotFoundError(
                "Please share a specific episode link, not the show page."
            )

        # Episodes — try direct extraction from embed page
        try:
            return await asyncio.wait_for(
                self._extract_episode(content_id, url),
                timeout=EXTRACTION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError()
        except ContentNotFoundError:
            raise
        except Exception:
            raise ExtractionFailedError(
                "Could not extract this podcast episode. "
                "Spotify may have restricted access."
            )

    async def _extract_episode(self, episode_id: str, original_url: str) -> MediaInfo:
        """Extract podcast episode using Spotify's embed endpoint."""
        # Get metadata from oEmbed API (always works, no auth)
        oembed_resp = await proxy_fetch(
            f"https://open.spotify.com/oembed?url={original_url}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; Linkloader/1.0)"},
        )

        if oembed_resp.status_code == 404:
            raise ContentNotFoundError("Spotify episode not found")
        if oembed_resp.status_code != 200:
            raise ExtractionFailedError("Could not fetch episode metadata")

        oembed = oembed_resp.json()

        title = oembed.get("title", "Spotify Episode")
        if len(title) > 80:
            title = title[:77] + "\u2026"
        thumbnail = oembed.get("thumbnail_url", "")

        # Try to get the actual audio stream from the embed page
        embed_url = f"https://open.spotify.com/embed/episode/{episode_id}"
        embed_resp = await proxy_fetch(embed_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        })

        if embed_resp.status_code != 200:
            raise ExtractionFailedError("Could not access episode embed page")

        text = embed_resp.text

        # Spotify embeds contain a JSON blob with episode data
        audio_url = ""

        # Try extracting from __NEXT_DATA__ or similar embedded JSON
        import json
        for pattern in [
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            r'"audioPreview"\s*:\s*\{[^}]*"url"\s*:\s*"([^"]+)"',
            r'"audio_preview_url"\s*:\s*"([^"]+)"',
        ]:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                if "audioPreview" in pattern or "audio_preview" in pattern:
                    audio_url = match.group(1)
                    break
                else:
                    # Parse __NEXT_DATA__
                    try:
                        next_data = json.loads(match.group(1))
                        props = next_data.get("props", {}).get("pageProps", {})
                        state = props.get("state", {})
                        ep_data = state.get("data", {}).get("entity", {})
                        audio_url = ep_data.get("audioPreview", {}).get("url", "")
                        if not audio_url:
                            audio_url = ep_data.get("audio_preview_url", "")
                    except (json.JSONDecodeError, AttributeError):
                        pass

        if not audio_url:
            # As a last resort, check for any mp3/audio URL in the page
            mp3_match = re.search(r'(https://[^"]*\.mp3[^"]*)', text)
            if mp3_match:
                audio_url = mp3_match.group(1)

        if not audio_url:
            raise ContentNotFoundError(
                "Could not extract audio from this podcast episode. "
                "Spotify may require authentication for this content."
            )

        return MediaInfo(
            platform="spotify",
            title=title,
            thumbnail=thumbnail,
            media_type="audio",
            format="mp3",
            quality="preview",
            file_size=0,
            download_url=audio_url,
            duration=None,
            author=oembed.get("provider_name", "Spotify"),
        )
