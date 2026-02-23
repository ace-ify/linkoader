# Linkloader — Product Requirements Document

**Version:** 1.0
**Date:** 2026-02-23
**Status:** Draft
**Author:** BitBuddy

---

## 1. Overview

Linkloader is a web-based utility that lets users paste any URL and instantly download the content behind it — video, audio, image, or document. No accounts, no clutter, no friction. Paste, preview, download.

### 1.1 Problem Statement

Downloading content from platforms like YouTube, Instagram, Pinterest, and Facebook is unnecessarily difficult. Users currently rely on:

- Scattered, ad-ridden third-party tools with poor UX
- Browser extensions that break with platform updates
- CLI tools (yt-dlp) that require technical knowledge
- Multiple different tools for different platforms

There is no single, clean, reliable, and ad-free solution that handles all major platforms with a professional user experience.

### 1.2 Solution

A single-page web app where users paste any supported URL and get a clean preview card with a one-click download button. The app automatically detects the platform, extracts the best available quality, and initiates the download — all within seconds.

### 1.3 Target Users

- **Primary:** Everyday internet users who want to save content for offline use
- **Secondary:** Content creators who need to download reference material
- **Tertiary:** Researchers and archivists preserving online content

---

## 2. Product Goals

| Priority | Goal | Success Metric |
|----------|------|----------------|
| P0 | Users can download content from any supported URL in under 10 seconds | Time-to-download < 10s for 90% of requests |
| P0 | Support YouTube, Instagram, Pinterest, Facebook at launch | All 4 platforms functional with >95% success rate |
| P1 | Zero-friction UX — no signup, no ads, no popups | Single-page flow: paste → preview → download |
| P1 | Professional, minimalist design that builds trust | Monochrome design, clean typography, zero visual noise |
| P2 | Extensible architecture for adding new platforms | New platform integration < 1 day of work |

---

## 3. User Stories

### 3.1 Core Flow

```
As a user,
I want to paste a URL from any supported platform,
So that I can download the content (video, image, audio) directly to my device.
```

**Acceptance Criteria:**
- User lands on a single page with a prominent URL input field
- Pasting a URL immediately triggers extraction (no separate "submit" button beyond the arrow)
- A preview card appears showing: thumbnail, title, file type, quality, file size, source platform
- Clicking "Download" initiates the browser's native download dialog
- The entire flow completes in under 10 seconds for standard content

### 3.2 Error Handling

```
As a user,
I want clear feedback when something goes wrong,
So that I know whether to retry, use a different URL, or wait.
```

**Acceptance Criteria:**
- Invalid URLs show inline validation ("This doesn't look like a supported URL")
- Unsupported platforms show a clear message ("This platform isn't supported yet")
- Network errors show a retry option
- Rate limiting shows a countdown timer
- Content not found (deleted/private) shows an appropriate message

### 3.3 Platform Support

```
As a user,
I want the app to handle URLs from all major content platforms,
So that I don't need a different tool for each platform.
```

**MVP Platforms:**

| Platform | Content Types | Notes |
|----------|--------------|-------|
| YouTube | Video, audio, shorts | Best quality auto-selected. Playlists out of MVP scope |
| Instagram | Posts, reels, stories, profile pictures | Public content only |
| Pinterest | Pins (images and videos) | Original resolution |
| Facebook | Videos, reels, posts | Public content only |

---

## 4. Functional Requirements

### 4.1 URL Extraction

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | System shall accept any URL via a text input field | P0 |
| FR-02 | System shall auto-detect the platform from the URL pattern | P0 |
| FR-03 | System shall extract: title, thumbnail, media type, format, quality, file size, download URL | P0 |
| FR-04 | System shall always extract the highest available quality | P0 |
| FR-05 | System shall return extraction results within 5 seconds | P1 |
| FR-06 | System shall validate URLs before sending to backend | P1 |

### 4.2 Download

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-07 | System shall initiate browser-native download from extracted URL | P0 |
| FR-08 | System shall fall back to server-side proxy if CORS blocks direct download | P0 |
| FR-09 | System shall set appropriate Content-Disposition headers for file naming | P1 |
| FR-10 | System shall show download progress state on the button | P1 |

### 4.3 Rate Limiting

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-11 | System shall limit extractions to 15/minute and 100/hour per IP | P0 |
| FR-12 | System shall limit proxy downloads to 5/minute per IP | P0 |
| FR-13 | System shall return 429 with retry-after time when rate limited | P0 |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | Page load time (LCP) | < 1.5s |
| NFR-02 | Extraction API response time | < 5s (95th percentile) |
| NFR-03 | Frontend bundle size | < 150KB gzipped |
| NFR-04 | Time to Interactive | < 2s |

### 5.2 Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-05 | API uptime | 99.5% |
| NFR-06 | Extraction success rate per platform | > 95% |
| NFR-07 | Graceful degradation when a platform extractor fails | Other platforms unaffected |

### 5.3 Security

| ID | Requirement |
|----|-------------|
| NFR-08 | No user data stored — no cookies, no analytics, no tracking |
| NFR-09 | URL input sanitized against injection attacks |
| NFR-10 | Proxy endpoint restricted to known media domains (no open relay) |
| NFR-11 | Rate limiting prevents abuse and resource exhaustion |
| NFR-12 | HTTPS enforced on all endpoints |

### 5.4 Accessibility

| ID | Requirement |
|----|-------------|
| NFR-13 | WCAG 2.1 AA compliant contrast ratios (monochrome palette passes) |
| NFR-14 | Full keyboard navigation support |
| NFR-15 | Screen reader compatible with proper ARIA labels |
| NFR-16 | Reduced motion support for animations |

---

## 6. Design Requirements

### 6.1 Visual Identity

- **Aesthetic:** Minimalist, monochrome, professional
- **Palette:** Pure black/white/gray — no accent colors
- **Typography:** Inter (UI), JetBrains Mono (technical data)
- **Spacing:** 4px grid, generous whitespace
- **Branding:** "linkloader_" — lowercase, trailing underscore, monospace feel

### 6.2 Key Screens

**6.2.1 Landing State**
- Centered layout, max-width 640px
- Wordmark top-left, GitHub link top-right
- Tagline: "Paste any link. Get the file."
- URL input with arrow submit button
- Supported platform names listed below input
- Footer: "rate limited to fair use · no data stored"

**6.2.2 Preview State**
- URL input moves to top
- Preview card appears below with slide-up animation
- Card contains: thumbnail (left), metadata (right), download button (bottom center)
- Metadata: title, format tag, quality, file size, source domain
- Clear (×) button on input to reset

**6.2.3 Error State**
- Same card layout, red-tinted border (subtle, #FF4444 at 20% opacity)
- Error message in secondary text color
- Retry button where download button would be

**6.2.4 Loading State**
- Thin white progress bar below input, animating left-to-right
- Input disabled during extraction
- No spinners — motion is horizontal only

### 6.3 Responsive Design

- **Desktop (>768px):** Centered, 640px max-width, horizontal preview card
- **Mobile (<768px):** Full-width with 16px padding, vertical preview card (thumbnail stacked above metadata)

---

## 7. Technical Constraints

| Constraint | Detail |
|-----------|--------|
| No server-side storage | Content is never cached or stored on the server |
| Client-side download preferred | Server proxy is fallback only, to minimize bandwidth costs |
| Platform extraction may break | Source platforms change their APIs/structure; extractors need maintenance |
| Legal gray area | Content downloading exists in a legal gray area; app provides the tool, not the content |

---

## 8. Out of Scope (MVP)

| Feature | Reason |
|---------|--------|
| User accounts | Adds complexity without core value |
| Download history | Requires storage, conflicts with no-data-stored principle |
| Playlist/bulk download | Complex UX, high server load |
| Quality/format picker | Simplicity — always best quality |
| Browser extension | Separate product, post-MVP |
| Mobile app | Web-first, post-MVP |
| Audio-only extraction | Post-MVP enhancement for YouTube |
| Private/authenticated content | Requires user credentials, security risk |

---

## 9. Future Roadmap

| Phase | Features |
|-------|----------|
| v1.1 | TikTok, Twitter/X support |
| v1.2 | Quality/format picker toggle |
| v1.3 | Audio extraction mode (YouTube → MP3) |
| v2.0 | Browser extension for in-page download buttons |
| v2.1 | Playlist/batch download |
| v2.2 | Self-hosted Docker option |

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Extraction success rate | > 95% | Server-side logging (no PII) |
| Average time-to-download | < 10s | Client-side performance timing |
| Error rate | < 5% | Server-side error logs |
| Proxy fallback rate | < 20% | Track proxy vs direct downloads |

---

*This document defines what Linkloader is. For how it's built, see the [Technical Design Document](./2026-02-23-linkloader-design.md).*
