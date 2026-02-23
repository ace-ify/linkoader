# Linkloader — Implementation Plan

**Date:** 2026-02-23
**Prerequisites:** [PRD](./2026-02-23-linkloader-prd.md) | [Design Doc](./2026-02-23-linkloader-design.md)

---

## How to Use This Plan

This is an ordered, step-by-step implementation plan. Each phase builds on the previous one. Within each phase, steps are numbered and should be executed in order. Each step specifies the exact files to create/modify, commands to run, and acceptance criteria.

**Reference the Design Doc for all code patterns, interfaces, and architecture details.**

---

## Phase 1: Project Scaffolding

### Step 1.1 — Initialize Git Repository

```bash
cd S:/BitBuddy/Projects/linkoader
git init
```

### Step 1.2 — Create .gitignore

Create `.gitignore` in project root with entries for:
- Python: `__pycache__/`, `*.pyc`, `.venv/`, `*.egg-info/`
- Node: `node_modules/`, `dist/`, `.env`, `.env.local`
- IDE: `.vscode/`, `.idea/`
- OS: `.DS_Store`, `Thumbs.db`
- Project: `backend/*.log`

### Step 1.3 — Create directory structure

```
mkdir -p backend/app/extractors
mkdir -p backend/tests
mkdir -p frontend/src/components
mkdir -p frontend/src/hooks
mkdir -p frontend/src/lib
mkdir -p frontend/src/types
mkdir -p frontend/public
```

### Step 1.4 — Initial commit

Commit the docs/plans directory and .gitignore.

**Acceptance:** `git log` shows initial commit. Directory structure exists.

---

## Phase 2: Backend Core

### Step 2.1 — Python environment and dependencies

Create `backend/requirements.txt`:
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
yt-dlp>=2024.12.0
httpx==0.28.1
slowapi==0.1.9
pydantic==2.10.0
python-dotenv==1.0.1
beautifulsoup4==4.12.3
```

Commands:
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
```

### Step 2.2 — Pydantic models

Create `backend/app/models.py` — implement `ExtractRequest`, `MediaInfo`, and `ErrorResponse` exactly as specified in Design Doc section 3.4.

### Step 2.3 — Custom exceptions

Create `backend/app/exceptions.py`:

```python
class ExtractionError(Exception):
    """Base exception for extraction failures."""
    def __init__(self, error_code: str, message: str, status_code: int = 500):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code

class InvalidURLError(ExtractionError):
    def __init__(self, message="URL format is invalid"):
        super().__init__("invalid_url", message, 400)

class UnsupportedPlatformError(ExtractionError):
    def __init__(self, supported: list[str] | None = None):
        super().__init__("unsupported_platform", "This platform is not supported", 400)
        self.supported = supported or []

class ContentNotFoundError(ExtractionError):
    def __init__(self):
        super().__init__("not_found", "Content not found or is private", 404)

class UpstreamError(ExtractionError):
    def __init__(self):
        super().__init__("upstream_error", "Could not reach the platform", 502)

class ExtractionFailedError(ExtractionError):
    def __init__(self):
        super().__init__("extraction_failed", "Failed to extract content", 503)
```

### Step 2.4 — Base extractor interface

Create `backend/app/extractors/__init__.py` (empty).
Create `backend/app/extractors/base.py` — implement `BaseExtractor` ABC exactly as specified in Design Doc section 3.3.

### Step 2.5 — Extractor router

Create `backend/app/router.py` — implement `ExtractorRouter` with auto-discovery exactly as specified in Design Doc section 3.3.

### Step 2.6 — Rate limiter

Create `backend/app/rate_limiter.py` — implement slowapi limiter as specified in Design Doc section 3.5.

### Step 2.7 — CORS proxy

Create `backend/app/proxy.py` — implement `is_allowed_domain()` and `stream_proxy()` as specified in Design Doc section 3.6.

### Step 2.8 — `__init__.py` files

Create `backend/app/__init__.py` (empty).

**Acceptance:** All modules importable. `python -c "from app.models import MediaInfo"` succeeds from `backend/` directory.

---

## Phase 3: Platform Extractors

### Step 3.1 — YouTube extractor

Create `backend/app/extractors/youtube.py`.

Implementation details:
- Use yt-dlp with `extract_info(url, download=False)`
- Format: `best[ext=mp4]/best`
- URL patterns: `youtube.com/watch`, `youtube.com/shorts/`, `youtu.be/`
- Map yt-dlp info dict fields to `MediaInfo`
- Wrap yt-dlp exceptions → `ContentNotFoundError` or `ExtractionFailedError`
- Run yt-dlp extraction in a thread executor (`asyncio.to_thread`) since yt-dlp is synchronous

Reference: Design Doc section 3.3 (YouTube Extractor example) and section 11.

### Step 3.2 — Instagram extractor

Create `backend/app/extractors/instagram.py`.

Implementation details:
- Try yt-dlp first (it has Instagram support)
- URL patterns: `instagram.com/p/`, `instagram.com/reel/`, `instagram.com/stories/`
- For posts with images, yt-dlp may not work — fallback to parsing `og:image` meta tags via httpx + BeautifulSoup
- media_type: `"video"` for reels, `"image"` for photo posts
- Wrap errors appropriately

Reference: Design Doc section 11 (Instagram notes).

### Step 3.3 — Pinterest extractor

Create `backend/app/extractors/pinterest.py`.

Implementation details:
- Custom extractor using httpx (yt-dlp Pinterest support is limited)
- URL patterns: `pinterest.com/pin/`, `pin.it/`
- Fetch pin page HTML, parse `og:image` and `og:video` meta tags with BeautifulSoup
- For images: extract original resolution URL (replace size suffix in URL)
- For videos: extract video source from page data
- Follow redirects for short URLs (`pin.it/`)
- media_type: `"image"` or `"video"` based on `og:video` presence

Reference: Design Doc section 11 (Pinterest notes).

### Step 3.4 — Facebook extractor

Create `backend/app/extractors/facebook.py`.

Implementation details:
- Use yt-dlp (has Facebook support)
- URL patterns: `facebook.com/watch`, `facebook.com/reel/`, `facebook.com/*/videos/`, `fb.watch/`
- Format: `best[ext=mp4]/best`
- Only works with public content
- Wrap yt-dlp exceptions

Reference: Design Doc section 11 (Facebook notes).

**Acceptance:** Each extractor can be instantiated and `matches()` returns True for valid URLs. YouTube extractor tested with a real public video URL.

---

## Phase 4: FastAPI Application

### Step 4.1 — Main application

Create `backend/app/main.py`.

Implementation:
- FastAPI app with lifespan context manager
- CORS middleware (configurable origins via env var, default `*`)
- Exception handler for `ExtractionError` → JSON error responses
- Rate limit error handler for slowapi

Endpoints:

**POST `/api/extract`:**
- Rate limited: `15/minute;100/hour`
- Accept `ExtractRequest` body
- Resolve extractor via `ExtractorRouter`
- If no match → raise `UnsupportedPlatformError` with supported list
- Call `extractor.extract(url)`
- Return `MediaInfo` as JSON

**GET `/api/proxy-download`:**
- Rate limited: `5/minute`
- Query params: `url` (required), `filename` (optional)
- Validate domain against whitelist via `is_allowed_domain()`
- If not allowed → 403
- Return `StreamingResponse` from `stream_proxy()`
- Set `Content-Disposition: attachment` header

**GET `/api/health`:**
- No rate limit
- Return status, version, and list of supported extractors

Reference: Design Doc sections 3.2 and 3.7.

### Step 4.2 — Environment configuration

Create `backend/.env.example`:
```
PORT=8000
ALLOWED_ORIGINS=*
RATE_LIMIT_EXTRACT=15/minute;100/hour
RATE_LIMIT_PROXY=5/minute
```

Load env vars with `python-dotenv` in `main.py`.

### Step 4.3 — Run and verify

```bash
cd backend
source .venv/Scripts/activate
uvicorn app.main:app --reload --port 8000
```

Verify:
- `GET /api/health` → 200 with extractors list
- `POST /api/extract` with YouTube URL → 200 with MediaInfo
- `GET /docs` → Swagger UI works
- `POST /api/extract` with invalid URL → 400

**Acceptance:** All 3 endpoints respond correctly. YouTube extraction returns valid MediaInfo.

---

## Phase 5: Backend Tests

### Step 5.1 — Test dependencies

Add to `backend/requirements.txt`:
```
pytest==8.3.4
pytest-asyncio==0.25.0
httpx==0.28.1
```

### Step 5.2 — Router tests

Create `backend/tests/test_router.py`:
- Test URL pattern matching for each extractor
- Test unknown URLs return None
- Test supported_platforms property lists all extractors

### Step 5.3 — Proxy tests

Create `backend/tests/test_proxy.py`:
- Test `is_allowed_domain()` accepts whitelisted domains
- Test `is_allowed_domain()` rejects unknown domains
- Test subdomain matching works (e.g., `rr1---sn.googlevideo.com`)

### Step 5.4 — Extractor tests

Create `backend/tests/test_extractors.py`:
- Test each extractor's `matches()` with valid and invalid URLs
- Integration tests for YouTube extraction with a known public video (mark with `@pytest.mark.integration`)

### Step 5.5 — API endpoint tests

Create `backend/tests/test_api.py`:
- Use `httpx.AsyncClient` with FastAPI `TestClient`
- Test `/api/health` returns 200
- Test `/api/extract` with valid YouTube URL returns MediaInfo
- Test `/api/extract` with unsupported URL returns 400
- Test `/api/extract` with invalid URL format returns 400
- Test `/api/proxy-download` with non-whitelisted domain returns 403

**Acceptance:** `pytest backend/tests/ -v` passes. Unit tests pass without network. Integration tests pass with network.

---

## Phase 6: Frontend Setup

### Step 6.1 — Initialize Vite + React + TypeScript project

```bash
cd S:/BitBuddy/Projects/linkoader
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

### Step 6.2 — Install Tailwind CSS v4

```bash
cd frontend
npm install tailwindcss @tailwindcss/vite
```

Configure Vite plugin in `vite.config.ts`:
```typescript
import tailwindcss from "@tailwindcss/vite";
// Add to plugins array
```

Replace `src/index.css` content with:
```css
@import "tailwindcss";
```

### Step 6.3 — Configure Tailwind theme

In `src/index.css`, add theme configuration using Tailwind v4's CSS-based config:

```css
@import "tailwindcss";

@theme {
  --color-surface: #0A0A0A;
  --color-surface-hover: #141414;
  --color-border: #1F1F1F;
  --color-primary: #FAFAFA;
  --color-secondary: #A0A0A0;
  --color-muted: #525252;
  --color-error: rgba(255, 68, 68, 0.2);

  --font-sans: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", monospace;

  --tracking-tighter: -0.02em;
  --max-width-content: 640px;
}
```

### Step 6.4 — Add Inter and JetBrains Mono fonts

In `index.html`, add Google Fonts links for Inter (400, 600) and JetBrains Mono (400).

### Step 6.5 — Configure Vite proxy for development

In `vite.config.ts`, add dev server proxy:
```typescript
server: {
  proxy: {
    "/api": "http://localhost:8000",
  },
}
```

### Step 6.6 — Add environment variable

Create `frontend/.env`:
```
VITE_API_URL=http://localhost:8000
```

### Step 6.7 — Clean up Vite defaults

- Remove `src/App.css`
- Remove Vite logo assets
- Clear `App.tsx` to a blank component
- Set `<html>` bg to black in `index.html`

### Step 6.8 — Verify

```bash
cd frontend
npm run dev
```

**Acceptance:** Vite dev server starts. Page loads with black background. No console errors. Tailwind classes work.

---

## Phase 7: Frontend Types and Utilities

### Step 7.1 — TypeScript types

Create `frontend/src/types/media.ts`:

```typescript
export interface MediaInfo {
  platform: string;
  title: string;
  thumbnail: string;
  media_type: "video" | "audio" | "image" | "document";
  format: string;
  quality: string;
  file_size: number;
  download_url: string;
  duration?: number;
  author?: string;
}

export interface ApiError {
  error: string;
  message: string;
  retry_after?: number;
  supported?: string[];
}
```

### Step 7.2 — API client

Create `frontend/src/lib/api.ts`:

- `extractMedia(url: string): Promise<MediaInfo>` — POST to `/api/extract`
- `getProxyDownloadUrl(url: string, filename?: string): string` — constructs proxy URL
- Proper error handling: parse JSON error body, throw typed errors
- Use `VITE_API_URL` env var as base URL (empty string for same-origin in production with proxy)

### Step 7.3 — Formatters

Create `frontend/src/lib/format.ts`:

- `formatFileSize(bytes: number): string` — "48.2 MB", "1.3 GB", "256 KB"
- `formatDuration(seconds: number): string` — "3:42", "1:02:15"

### Step 7.4 — URL validation

Create `frontend/src/lib/validate.ts`:

- `isValidUrl(input: string): boolean` — checks URL format
- `getSupportedPlatforms(): string[]` — returns list of platform names

**Acceptance:** Types compile. Formatters produce correct output. `formatFileSize(50531584)` returns `"48.2 MB"`.

---

## Phase 8: Frontend Components

Build components bottom-up. Each component should be self-contained, using Tailwind for styling. Reference Design Doc section 2 for all specs.

### Step 8.1 — Header

Create `frontend/src/components/Header.tsx`:
- Wordmark "linkloader_" in monospace, top-left
- GitHub icon link, top-right
- Flex row with justify-between, padding 24px

### Step 8.2 — Footer

Create `frontend/src/components/Footer.tsx`:
- Text: "rate limited to fair use · no data stored"
- Centered, muted color, small text
- Positioned at bottom of page

### Step 8.3 — PlatformList

Create `frontend/src/components/PlatformList.tsx`:
- Displays: "YouTube · Instagram · Pinterest · Facebook"
- Muted secondary text, centered
- Accepts `visible: boolean` prop (hidden when preview is showing)

### Step 8.4 — LoadingBar

Create `frontend/src/components/LoadingBar.tsx`:
- Thin (2px) white bar
- CSS animation: `translateX(-100%)` → `translateX(100%)` infinitely
- Accepts `visible: boolean` prop
- Respects `prefers-reduced-motion`

### Step 8.5 — DownloadButton

Create `frontend/src/components/DownloadButton.tsx`:
- Three states: `idle`, `downloading`, `done`
- idle: bordered button with "↓ Download"
- downloading: "Downloading..." with pulse
- done: "Done ✓" — auto-resets after 3s
- Props: `downloadUrl: string`, `filename: string`, `proxyFallbackUrl: string`
- On click: create hidden `<a>` element with `download` attribute, click it
- If direct download fails (detect via error event or CORS), fall back to proxy URL

### Step 8.6 — MediaPreview

Create `frontend/src/components/MediaPreview.tsx`:
- Accepts `MediaInfo` prop
- Card with `bg-surface` background, `border` color border, rounded corners
- Layout: thumbnail (left/top on mobile) + metadata (right/bottom on mobile)
- Thumbnail: `object-cover`, blur-to-sharp load transition using `onLoad`
- Metadata: title (primary, 600 weight), format badge, quality, file size (mono), source domain
- DownloadButton at card bottom center
- Entrance animation: `translateY(8px)` + fade in

### Step 8.7 — ErrorCard

Create `frontend/src/components/ErrorCard.tsx`:
- Same card layout as MediaPreview
- Red-tinted border (`border-error`)
- Error message in secondary color
- Retry button in place of download button
- Props: `message: string`, `onRetry: () => void`

### Step 8.8 — Toast

Create `frontend/src/components/Toast.tsx`:
- Fixed position bottom-center
- Slide-up animation
- Auto-dismisses after 5s
- Props: `message: string`, `visible: boolean`
- Used for rate limit messages

### Step 8.9 — URLInput

Create `frontend/src/components/URLInput.tsx`:
- Full-width input with `bg-surface` background
- Placeholder: "https://"
- Submit arrow button (→) on the right side inside the input
- Clear button (×) appears when input has value
- Auto-focus on mount
- Paste event auto-triggers submit (debounced 300ms)
- Enter key triggers submit
- Props: `onSubmit`, `onClear`, `disabled`, `value`, `onChange`

**Acceptance:** Each component renders in isolation. No TypeScript errors. Tailwind classes produce correct visual output.

---

## Phase 9: Custom Hook and App Integration

### Step 9.1 — useExtract hook

Create `frontend/src/hooks/useExtract.ts`:

```typescript
export function useExtract() {
  // State: data, loading, error
  // extract(url): calls API, sets loading/data/error
  // reset(): clears all state
  // Maps API errors to user-friendly messages using ERROR_MESSAGES map
  return { extract, data, loading, error, reset };
}
```

Error message mapping (from Design Doc section 6.2):
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

### Step 9.2 — App.tsx composition

Compose all components in `frontend/src/App.tsx`:

```
<div className="bg-black min-h-screen text-primary">
  <Header />
  <main className="max-w-content mx-auto px-4">
    {!data && !loading && <Tagline />}
    <URLInput ... />
    <LoadingBar visible={loading} />
    {data && <MediaPreview media={data} />}
    {error && <ErrorCard message={error} onRetry={retry} />}
    {!data && !error && <PlatformList />}
  </main>
  <Toast ... />
  <Footer />
</div>
```

State management:
- `url` state for controlled input
- `useExtract()` hook for extraction lifecycle
- URL submission → `extract(url)`
- Clear → `reset()` + clear URL
- Rate limit error → show Toast with countdown

### Step 9.3 — Global styles

Update `frontend/src/index.css` with:
- Base body styles: `bg-black`, `text-primary`, `font-sans`
- Custom animation keyframes for loading bar, card entrance, toast slide
- `prefers-reduced-motion` media query overrides
- Scrollbar styling (thin, monochrome)
- Selection color styling

**Acceptance:** Full flow works end-to-end locally. Paste YouTube URL → loading bar → preview card → download button. Errors show ErrorCard. Invalid URLs show inline feedback.

---

## Phase 10: Responsive Design and Polish

### Step 10.1 — Mobile responsive layout

- URLInput: full width on all screens
- MediaPreview: horizontal (thumbnail left) on desktop, vertical (thumbnail top) on mobile at `md:` breakpoint (768px)
- Reduce padding on mobile: `px-4` vs `px-6`
- Test on 375px width (iPhone SE)

### Step 10.2 — Keyboard accessibility

- Tab order: input → submit → download
- Focus ring styles: `focus-visible:ring-2 ring-white/20`
- Escape key clears input and resets state
- All interactive elements have `aria-label` attributes

### Step 10.3 — Favicon

Create `frontend/public/favicon.svg` — a minimal monochrome "L" or down-arrow icon.

### Step 10.4 — HTML meta tags

Update `frontend/index.html`:
- Title: "linkloader_ — paste any link, get the file"
- Meta description
- Open Graph tags (title, description)
- Theme color: `#000000`
- Viewport meta tag

**Acceptance:** App is fully usable on mobile. Keyboard navigation works. All interactive elements accessible.

---

## Phase 11: Environment Configuration

### Step 11.1 — Backend Dockerfile

Create `backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 11.2 — Frontend build config

Ensure `vite.config.ts` produces correct build output:
```bash
cd frontend
npm run build
# Output in dist/ — ready for Vercel
```

### Step 11.3 — Environment variable documentation

Create `backend/.env.example` and `frontend/.env.example` with all required env vars documented.

### Step 11.4 — Vercel config

Create `frontend/vercel.json`:
```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

### Step 11.5 — Railway config

Create `backend/railway.toml` or `Procfile`:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Acceptance:** `npm run build` succeeds. Docker builds and runs. Both deployment configs present.

---

## Phase 12: Final Integration Testing

### Step 12.1 — Manual E2E testing checklist

Run both backend and frontend locally. Test each scenario:

- [ ] Paste YouTube video URL → preview shows → download works
- [ ] Paste YouTube Shorts URL → works
- [ ] Paste Instagram Reel URL → works
- [ ] Paste Instagram post URL → works
- [ ] Paste Pinterest pin URL → works
- [ ] Paste Facebook video URL → works
- [ ] Paste invalid URL → inline error message
- [ ] Paste unsupported platform URL → error card
- [ ] Paste private/deleted content URL → "not found" error
- [ ] Rapid-fire 16 requests → rate limit toast
- [ ] Mobile viewport → responsive layout
- [ ] Keyboard-only navigation → all flows work
- [ ] Clear button resets to landing state
- [ ] Refresh page → clean state

### Step 12.2 — Performance check

```bash
cd frontend
npm run build
npx serve dist
# Open Chrome DevTools → Lighthouse → Performance
# Target: > 95 score
```

### Step 12.3 — Bundle size check

```bash
cd frontend
npx vite-bundle-visualizer
# Verify < 150KB gzipped total
```

**Acceptance:** All checklist items pass. Lighthouse > 95. Bundle < 150KB gzipped.

---

## Implementation Order Summary

| Order | Phase | Est. Complexity | Dependencies |
|-------|-------|----------------|--------------|
| 1 | Project Scaffolding | Low | None |
| 2 | Backend Core | Medium | Phase 1 |
| 3 | Platform Extractors | High | Phase 2 |
| 4 | FastAPI Application | Medium | Phase 2, 3 |
| 5 | Backend Tests | Medium | Phase 4 |
| 6 | Frontend Setup | Low | Phase 1 |
| 7 | Frontend Types & Utils | Low | Phase 6 |
| 8 | Frontend Components | High | Phase 7 |
| 9 | Hook & App Integration | Medium | Phase 8 |
| 10 | Responsive & Polish | Medium | Phase 9 |
| 11 | Environment Config | Low | Phase 4, 9 |
| 12 | Integration Testing | Medium | Phase 11 |

**Note:** Phases 2-5 (backend) and Phases 6-10 (frontend) can be developed in parallel by separate developers. Phase 11 requires both to be complete. Phase 12 is the final gate.

---

## CLAUDE.md Instructions

When implementing this project, create a `CLAUDE.md` at the project root with:

```markdown
# Linkloader

## Quick Start
- Backend: `cd backend && source .venv/Scripts/activate && uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && npm run dev`

## Architecture
- Plugin-based monolith: React (Vite) frontend + FastAPI backend
- Each platform = one extractor file in `backend/app/extractors/`
- Auto-discovery: drop a new extractor file, it's registered automatically

## Adding a New Platform
1. Create `backend/app/extractors/newplatform.py`
2. Implement `BaseExtractor` interface (see `base.py`)
3. Define `SUPPORTED_PATTERNS` with URL regexes
4. Implement `async def extract(url) -> MediaInfo`
5. Restart server — auto-discovered

## Key Files
- PRD: `docs/plans/2026-02-23-linkloader-prd.md`
- Design: `docs/plans/2026-02-23-linkloader-design.md`
- Implementation: `docs/plans/2026-02-23-linkloader-implementation.md`

## Conventions
- Monochrome UI only — no accent colors
- Inter font for UI, JetBrains Mono for technical data
- All animations respect prefers-reduced-motion
- No user data stored, no cookies, no tracking
```

---

*This plan implements the architecture defined in the [Design Doc](./2026-02-23-linkloader-design.md) to fulfill the requirements in the [PRD](./2026-02-23-linkloader-prd.md).*
