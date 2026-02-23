# Linkloader — Technical Design Document

**Version:** 1.0
**Date:** 2026-02-23
**Status:** Approved
**Author:** BitBuddy

---

## 1. System Architecture

### 1.1 High-Level Overview

Linkloader is a two-tier web application: a React single-page frontend and a Python FastAPI backend. The backend uses a plugin-based extractor architecture — each supported platform is an independent module implementing a common interface.

```
                        ┌─────────────────┐
                        │     Browser     │
                        │   (React SPA)   │
                        └────────┬────────┘
                                 │
                    HTTPS REST API calls
                                 │
                        ┌────────▼────────┐
                        │    FastAPI       │
                        │    Backend       │
                        │                 │
                        │  ┌───────────┐  │
                        │  │ Extractor │  │
                        │  │  Router   │  │
                        │  └─────┬─────┘  │
                        │        │        │
                        │  ┌─────▼─────┐  │
                        │  │ Platform  │  │
                        │  │Extractors │  │
                        │  └─────┬─────┘  │
                        │        │        │
                        │  Rate Limiter   │
                        │  CORS Proxy     │
                        └────────┬────────┘
                                 │
                     Upstream platform APIs
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
               YouTube     Instagram    Pinterest
                                              Facebook
```

### 1.2 Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Plugin-based monolith | Extensible without microservice complexity |
| Frontend framework | React + Vite | Fast builds, lightweight, strong ecosystem |
| Styling | Tailwind CSS | Utility-first, pairs well with monochrome design system |
| Backend framework | FastAPI | Async-native, auto-docs, excellent Python ecosystem |
| Primary extractor | yt-dlp | Battle-tested, supports 1000+ sites, active maintenance |
| Rate limiting | slowapi (in-memory) | Simple, no Redis dependency for MVP |
| Deployment | Vercel (frontend) + Railway (backend) | Managed hosting, free/cheap tiers, easy CI/CD |

---

## 2. Frontend Architecture

### 2.1 Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | React | 19.x |
| Build tool | Vite | 6.x |
| Styling | Tailwind CSS | 4.x |
| HTTP client | Native fetch | — |
| TypeScript | TypeScript | 5.x |

### 2.2 Component Tree

```
App
├── Header
│   ├── Wordmark ("linkloader_")
│   └── GitHubLink
├── Main
│   ├── Tagline (hidden when preview is active)
│   ├── URLInput
│   │   ├── <input> field
│   │   ├── SubmitArrow button
│   │   └── ClearButton (× when URL present)
│   ├── LoadingBar (thin animated bar)
│   ├── MediaPreview
│   │   ├── Thumbnail
│   │   ├── MediaMeta (title, format, quality, size, source)
│   │   └── DownloadButton
│   ├── ErrorCard
│   │   ├── ErrorMessage
│   │   └── RetryButton
│   └── PlatformList ("YouTube · Instagram · ...")
├── Toast (rate limit / transient messages)
└── Footer ("rate limited to fair use · no data stored")
```

### 2.3 Component Specifications

#### URLInput

```typescript
interface URLInputProps {
  onSubmit: (url: string) => void;
  onClear: () => void;
  disabled: boolean;
  value: string;
}
```

- Auto-focuses on page load
- Triggers `onSubmit` on Enter key or arrow click
- Validates URL format client-side before submission
- Pastes auto-trigger submission (debounced 300ms)

#### MediaPreview

```typescript
interface MediaInfo {
  platform: string;
  title: string;
  thumbnail: string;
  media_type: "video" | "audio" | "image" | "document";
  format: string;
  quality: string;
  file_size: number; // bytes
  download_url: string;
  duration?: number; // seconds, for video/audio
  author?: string;
}
```

- Renders a card with thumbnail and metadata
- Thumbnail loads with CSS `blur(20px)` → `blur(0)` transition
- File size formatted: bytes → KB/MB/GB
- Duration formatted: seconds → MM:SS or HH:MM:SS

#### DownloadButton

- Three states: `idle` → `downloading` → `done`
- `idle`: "↓ Download" — white text on transparent border
- `downloading`: "Downloading..." — subtle pulse animation
- `done`: "Done ✓" — resets to `idle` after 3 seconds
- Attempts direct download via `<a href download>` first
- Falls back to `/api/proxy-download` if direct fails

### 2.4 Custom Hook: useExtract

```typescript
function useExtract() {
  return {
    extract: (url: string) => Promise<void>,
    data: MediaInfo | null,
    loading: boolean,
    error: string | null,
    reset: () => void,
  };
}
```

- Manages the extraction lifecycle
- Handles API errors and maps to user-friendly messages
- Stores no persistent state — resets on page refresh

### 2.5 Design Tokens (Tailwind Config)

```typescript
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0A0A0A",
          hover: "#141414",
        },
        border: "#1F1F1F",
        primary: "#FAFAFA",
        secondary: "#A0A0A0",
        muted: "#525252",
        error: "rgba(255, 68, 68, 0.2)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      letterSpacing: {
        tighter: "-0.02em",
      },
      maxWidth: {
        content: "640px",
      },
    },
  },
};
```

### 2.6 Animations

All animations respect `prefers-reduced-motion`:

| Animation | Implementation | Duration |
|-----------|---------------|----------|
| Preview card entrance | `translateY(8px)` + `opacity(0)` → default | 200ms ease-out |
| Thumbnail blur | `filter: blur(20px)` → `blur(0)` on load | 300ms ease-out |
| Loading bar | `translateX(-100%)` → `translateX(100%)` loop | 1.5s linear infinite |
| Toast entrance | `translateY(100%)` → `translateY(0)` | 200ms ease-out |
| Download button state | Text crossfade | 150ms |

---

## 3. Backend Architecture

### 3.1 Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | FastAPI | 0.115.x |
| Python | Python | 3.12+ |
| Primary extractor | yt-dlp | Latest |
| HTTP client | httpx | 0.28.x |
| Rate limiting | slowapi | 0.1.x |
| Validation | Pydantic v2 | 2.x |
| ASGI server | Uvicorn | 0.34.x |

### 3.2 API Endpoints

#### POST /api/extract

Extracts media metadata and download URL from a given URL.

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response (200):**
```json
{
  "platform": "youtube",
  "title": "Rick Astley - Never Gonna Give You Up",
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "media_type": "video",
  "format": "mp4",
  "quality": "1080p",
  "file_size": 50531584,
  "download_url": "https://rr1---sn-...",
  "duration": 212,
  "author": "Rick Astley"
}
```

**Error Responses:**

| Status | Body | When |
|--------|------|------|
| 400 | `{"error": "invalid_url", "message": "URL format is invalid"}` | Malformed URL |
| 400 | `{"error": "unsupported_platform", "message": "This platform is not supported", "supported": [...]}` | Unknown platform |
| 404 | `{"error": "not_found", "message": "Content not found or is private"}` | Deleted/private content |
| 429 | `{"error": "rate_limited", "message": "Too many requests", "retry_after": 45}` | Rate limit exceeded |
| 502 | `{"error": "upstream_error", "message": "Could not reach the platform"}` | Platform unreachable |
| 503 | `{"error": "extraction_failed", "message": "Failed to extract content"}` | Extractor broken |

#### GET /api/proxy-download

Streams content through the server when CORS blocks direct browser downloads.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | URL-encoded direct download URL |
| `filename` | string | No | Suggested filename for Content-Disposition |

**Response:** Binary stream with headers:
```
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="video.mp4"
Transfer-Encoding: chunked
```

**Security:** Only allows proxying from whitelisted domains (youtube.com, instagram.com, pinterest.com, facebook.com, fbcdn.net, cdninstagram.com, pinimg.com, googlevideo.com, ytimg.com).

#### GET /api/health

**Response (200):**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "extractors": ["youtube", "instagram", "pinterest", "facebook"]
}
```

### 3.3 Extractor Architecture

#### Base Interface

```python
# backend/app/extractors/base.py

from abc import ABC, abstractmethod
from app.models import MediaInfo
import re

class BaseExtractor(ABC):
    """Base class for all platform extractors."""

    # Subclasses define URL patterns they handle
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
```

#### Extractor Router (Auto-Discovery)

```python
# backend/app/router.py

import importlib
import pkgutil
from app.extractors.base import BaseExtractor
from app.extractors import __path__ as extractors_path

class ExtractorRouter:
    def __init__(self):
        self._extractors: list[BaseExtractor] = []
        self._discover()

    def _discover(self):
        """Auto-discover all extractor modules."""
        for _, name, _ in pkgutil.iter_modules(extractors_path):
            if name == "base":
                continue
            module = importlib.import_module(f"app.extractors.{name}")
            for attr in dir(module):
                cls = getattr(module, attr)
                if (isinstance(cls, type)
                    and issubclass(cls, BaseExtractor)
                    and cls is not BaseExtractor):
                    self._extractors.append(cls())

    def resolve(self, url: str) -> BaseExtractor | None:
        """Find the extractor that handles this URL."""
        for extractor in self._extractors:
            if extractor.matches(url):
                return extractor
        return None

    @property
    def supported_platforms(self) -> list[str]:
        return [e.platform_name for e in self._extractors]
```

#### YouTube Extractor (Example)

```python
# backend/app/extractors/youtube.py

import yt_dlp
from app.extractors.base import BaseExtractor
from app.models import MediaInfo

class YouTubeExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?youtube\.com/watch\?v=[\w-]+",
        r"https?://(www\.)?youtube\.com/shorts/[\w-]+",
        r"https?://youtu\.be/[\w-]+",
    ]

    async def extract(self, url: str) -> MediaInfo:
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return MediaInfo(
            platform="youtube",
            title=info.get("title", "Untitled"),
            thumbnail=info.get("thumbnail", ""),
            media_type="video",
            format=info.get("ext", "mp4"),
            quality=f"{info.get('height', 0)}p",
            file_size=info.get("filesize") or info.get("filesize_approx") or 0,
            download_url=info["url"],
            duration=info.get("duration"),
            author=info.get("uploader"),
        )
```

### 3.4 Pydantic Models

```python
# backend/app/models.py

from pydantic import BaseModel, HttpUrl
from typing import Literal, Optional

class ExtractRequest(BaseModel):
    url: HttpUrl

class MediaInfo(BaseModel):
    platform: str
    title: str
    thumbnail: str
    media_type: Literal["video", "audio", "image", "document"]
    format: str
    quality: str
    file_size: int  # bytes
    download_url: str
    duration: Optional[int] = None  # seconds
    author: Optional[str] = None

class ErrorResponse(BaseModel):
    error: str
    message: str
    retry_after: Optional[int] = None
    supported: Optional[list[str]] = None
```

### 3.5 Rate Limiting

```python
# backend/app/rate_limiter.py

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Applied as decorators on endpoints:
# @limiter.limit("15/minute;100/hour")  → /api/extract
# @limiter.limit("5/minute")            → /api/proxy-download
```

### 3.6 CORS Proxy (Fallback)

```python
# backend/app/proxy.py

import httpx
from urllib.parse import urlparse

ALLOWED_DOMAINS = {
    "googlevideo.com",
    "ytimg.com",
    "cdninstagram.com",
    "fbcdn.net",
    "pinimg.com",
    "scontent.xx.fbcdn.net",
}

def is_allowed_domain(url: str) -> bool:
    """Only proxy from known media CDN domains."""
    hostname = urlparse(url).hostname or ""
    return any(hostname.endswith(d) for d in ALLOWED_DOMAINS)

async def stream_proxy(url: str):
    """Generator that streams content from source."""
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", url) as response:
            async for chunk in response.aiter_bytes(chunk_size=65536):
                yield chunk
```

### 3.7 FastAPI Application

```python
# backend/app/main.py

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from app.router import ExtractorRouter
from app.models import ExtractRequest, MediaInfo, ErrorResponse
from app.rate_limiter import limiter
from app.proxy import stream_proxy, is_allowed_domain

router = ExtractorRouter()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify extractors loaded
    print(f"Loaded extractors: {router.supported_platforms}")
    yield

app = FastAPI(title="Linkloader API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## 4. Project Structure

```
linkloader/
│
├── frontend/
│   ├── public/
│   │   └── favicon.svg
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── URLInput.tsx
│   │   │   ├── LoadingBar.tsx
│   │   │   ├── MediaPreview.tsx
│   │   │   ├── DownloadButton.tsx
│   │   │   ├── ErrorCard.tsx
│   │   │   ├── PlatformList.tsx
│   │   │   ├── Toast.tsx
│   │   │   └── Footer.tsx
│   │   ├── hooks/
│   │   │   └── useExtract.ts
│   │   ├── lib/
│   │   │   ├── api.ts          # API client
│   │   │   ├── format.ts       # File size, duration formatters
│   │   │   └── validate.ts     # URL validation
│   │   ├── types/
│   │   │   └── media.ts        # MediaInfo type
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css           # Tailwind directives + custom styles
│   ├── index.html
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── router.py           # Extractor auto-discovery + routing
│   │   ├── models.py           # Pydantic schemas
│   │   ├── rate_limiter.py     # slowapi configuration
│   │   ├── proxy.py            # CORS fallback proxy
│   │   ├── exceptions.py       # Custom exception classes
│   │   └── extractors/
│   │       ├── __init__.py
│   │       ├── base.py         # BaseExtractor ABC
│   │       ├── youtube.py
│   │       ├── instagram.py
│   │       ├── pinterest.py
│   │       └── facebook.py
│   ├── tests/
│   │   ├── test_router.py
│   │   ├── test_extractors.py
│   │   └── test_proxy.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── docs/
│   └── plans/
│       ├── 2026-02-23-linkloader-prd.md
│       └── 2026-02-23-linkloader-design.md
│
├── .gitignore
└── README.md
```

---

## 5. Data Flow

### 5.1 Extraction Flow (Happy Path)

```
User                Frontend              Backend              Platform
 │                    │                      │                    │
 │  paste URL         │                      │                    │
 │───────────────────>│                      │                    │
 │                    │  POST /api/extract   │                    │
 │                    │─────────────────────>│                    │
 │                    │                      │  resolve extractor │
 │                    │                      │──┐                 │
 │                    │                      │<─┘                 │
 │                    │                      │  extract info      │
 │                    │                      │───────────────────>│
 │                    │                      │  media metadata    │
 │                    │                      │<───────────────────│
 │                    │  MediaInfo JSON      │                    │
 │                    │<─────────────────────│                    │
 │  show preview      │                      │                    │
 │<───────────────────│                      │                    │
 │                    │                      │                    │
 │  click download    │                      │                    │
 │───────────────────>│                      │                    │
 │                    │  <a href download>   │                    │
 │                    │─────────────────────────────────────────>│
 │                    │                      │    binary stream   │
 │<──────────────────────────────────────────────────────────────│
 │  file saved        │                      │                    │
```

### 5.2 CORS Fallback Flow

```
User                Frontend              Backend              Platform
 │                    │                      │                    │
 │  click download    │                      │                    │
 │───────────────────>│                      │                    │
 │                    │  direct download     │                    │
 │                    │─────────────────────────────────(CORS)──>│
 │                    │  BLOCKED             │                    │
 │                    │<────────────────────────────────(CORS)───│
 │                    │                      │                    │
 │                    │  GET /api/proxy-download                 │
 │                    │─────────────────────>│                    │
 │                    │                      │  stream from CDN   │
 │                    │                      │───────────────────>│
 │                    │                      │<───────────────────│
 │                    │  chunked stream      │                    │
 │                    │<─────────────────────│                    │
 │  file saved        │                      │                    │
 │<───────────────────│                      │                    │
```

---

## 6. Error Handling Strategy

### 6.1 Backend Errors

| Layer | Error Type | Handling |
|-------|-----------|----------|
| URL validation | Invalid format | 400 with `invalid_url` |
| Router | No extractor match | 400 with `unsupported_platform` |
| Extractor | Content not found | 404 with `not_found` |
| Extractor | Platform API changed | 503 with `extraction_failed` |
| Network | Platform unreachable | 502 with `upstream_error` |
| Rate limiter | Limit exceeded | 429 with `retry_after` |
| Proxy | Domain not whitelisted | 403 with `proxy_denied` |

### 6.2 Frontend Error Mapping

```typescript
const ERROR_MESSAGES: Record<string, string> = {
  invalid_url: "That doesn't look like a valid URL.",
  unsupported_platform: "This platform isn't supported yet.",
  not_found: "Content not found — it may be private or deleted.",
  upstream_error: "Couldn't reach the platform. Try again.",
  extraction_failed: "Something went wrong extracting this content.",
  rate_limited: "Too many requests.",
  proxy_denied: "Download blocked for security reasons.",
};
```

---

## 7. Security Considerations

| Threat | Mitigation |
|--------|-----------|
| SSRF via URL input | Validate URL scheme (http/https only), reject private IPs, extractor patterns restrict to known domains |
| Open proxy abuse | Whitelist CDN domains in proxy endpoint, rate limit aggressively |
| Injection via URL | Pydantic `HttpUrl` validation, no shell execution with user input |
| DDoS | Rate limiting per IP, cloud provider DDoS protection |
| Data exposure | No storage, no logging of URLs or content, no cookies |

---

## 8. Deployment Architecture

```
┌──────────────────────────────────┐
│           Vercel                 │
│  ┌────────────────────────────┐  │
│  │   React SPA (Static)      │  │
│  │   CDN-served, edge-cached │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
                │
          API requests
                │
┌──────────────────────────────────┐
│          Railway                 │
│  ┌────────────────────────────┐  │
│  │   FastAPI (Uvicorn)        │  │
│  │   Auto-scaling             │  │
│  │   Health check: /api/health│  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

### 8.1 Environment Variables

**Backend (Railway):**
```
PORT=8000
ALLOWED_ORIGINS=https://linkloader.vercel.app
RATE_LIMIT_EXTRACT=15/minute;100/hour
RATE_LIMIT_PROXY=5/minute
```

**Frontend (Vercel):**
```
VITE_API_URL=https://linkloader-api.up.railway.app
```

### 8.2 CI/CD

- **Frontend:** Vercel auto-deploys on push to `main`
- **Backend:** Railway auto-deploys on push to `main`
- **Branch previews:** Both Vercel and Railway support preview deployments

---

## 9. Testing Strategy

| Level | Tool | Scope |
|-------|------|-------|
| Backend unit | pytest | Extractor logic, URL matching, model validation |
| Backend integration | pytest + httpx | API endpoints, rate limiting, proxy |
| Frontend unit | Vitest | Hooks, utilities, formatters |
| Frontend component | Vitest + Testing Library | Component rendering, state transitions |
| E2E | Playwright | Full paste → preview → download flow |

### 9.1 Key Test Cases

| Test | Type | Description |
|------|------|-------------|
| URL routing | Unit | Each extractor correctly matches its URL patterns |
| YouTube extraction | Integration | Extract metadata from a known YouTube video |
| Invalid URL rejection | Unit | Malformed URLs return 400 |
| Rate limiting | Integration | 16th request in a minute returns 429 |
| Proxy domain whitelist | Unit | Non-whitelisted domains are rejected |
| Preview card rendering | Component | MediaInfo renders all fields correctly |
| Error state rendering | Component | Each error type shows correct message |
| Download fallback | E2E | CORS-blocked download falls back to proxy |

---

## 10. Performance Budget

| Metric | Target |
|--------|--------|
| Frontend bundle (gzipped) | < 150 KB |
| First Contentful Paint | < 1.0s |
| Largest Contentful Paint | < 1.5s |
| Time to Interactive | < 2.0s |
| API response (extraction) | < 5s p95 |
| Lighthouse Performance score | > 95 |

---

## 11. Extractor Implementation Notes

### YouTube
- **Library:** yt-dlp
- **Method:** `extract_info(url, download=False)`
- **Format selection:** `best[ext=mp4]/best`
- **Known issues:** Download URLs expire after ~6 hours; generate fresh on each request

### Instagram
- **Library:** yt-dlp (has Instagram support) or custom via `httpx`
- **Method:** Parse `?__a=1&__d=dis` API endpoint or use yt-dlp
- **Content types:** Posts (images/carousels), Reels (video), Stories (requires login — out of MVP scope for stories)
- **Known issues:** Instagram aggressively blocks scrapers; may need rotating user agents

### Pinterest
- **Library:** Custom extractor via `httpx`
- **Method:** Parse pin page HTML for `og:image` / `og:video` meta tags
- **Content types:** Images (original resolution), videos
- **Known issues:** Pin URLs may redirect; follow redirects to get canonical URL

### Facebook
- **Library:** yt-dlp (has Facebook support)
- **Method:** `extract_info` with Facebook URL
- **Content types:** Videos, Reels
- **Known issues:** Many videos are private/friends-only; only public content works

---

## 12. Future Extension Points

| Extension | How |
|-----------|-----|
| New platform | Add `extractors/platform.py` implementing `BaseExtractor` |
| Quality picker | Add `qualities` field to `MediaInfo`, frontend renders dropdown |
| Audio extraction | Add `format` parameter to `/api/extract` (e.g., `mp3`) |
| Batch download | New endpoint `/api/extract-batch` accepting URL array |
| WebSocket progress | Replace polling with WS for real-time extraction status |

---

*This document defines how Linkloader is built. For what it is, see the [Product Requirements Document](./2026-02-23-linkloader-prd.md).*
