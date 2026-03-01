<a name="top"></a>

<h1 align="center">Linkloader</h1>
<p align="center"><strong>The stealthy, self-hosted universal media extractor.</strong></p>
<p align="center">
  <a href="#the-architecture-bypassing-anti-bot-defenses">The Architecture</a> ·
  <a href="#supported-platforms">Supported Platforms</a> ·
  <a href="#quick-start-self-hosting">Self-Hosting</a> ·
  <a href="#how-it-works">How it Works</a>
</p>

---

**Linkloader** is a minimal, privacy-respecting media downloader. Paste a URL from a supported social platform and get a direct file download (video, audio, or image) at maximum quality. 

Built as **Project 1 of my [#SudoShipIt Challenge](https://www.linkedin.com/hashtag/sudoshipit/)** (6 projects in 6 weeks).

## The Architecture: Bypassing Anti-Bot Defenses

Modern social platforms (YouTube, Pinterest, Instagram) employ aggressive anti-bot protections. Generic cloud deployments (like Render, AWS, or Fly.io) use known datacenter IP ranges, which are instantly flagged and shadowbanned when attempting to extract media.

**The Solution: Self-Hosting & Residential IPs**

Linkloader bypasses these restrictions by running the extraction engine locally on your personal machine (using your residential IP), while serving the frontend cleanly on the web. 

1. **Frontend:** Hosted on Vercel.
2. **Backend:** Runs locally via Python FastAPI.
3. **The Bridge:** We use `ngrok` to securely tunnel the local backend to a permanent public URL, which the frontend communicates with.

By using residential IPs combined with TLS fingerprint spoofing (`curl_cffi`), the platforms see standard user traffic, allowing fast and reliable extractions without the need for expensive rotating proxy pools.

## Supported Platforms

| Platform | Videos | Images | Reels/Shorts | Supported Extractors |
|---|---|---|---|---|
| **YouTube** | ✅ | — | ✅ | `yt-dlp`, Direct InnerTube API |
| **Instagram** | ✅ | ✅ | ✅ | Private API, GraphQL |
| **Pinterest** | ✅ | ✅ | — | DOM Parsing, API extraction |
| **Facebook** | ✅ | — | ✅ | Mobile API |

*Linkloader uses an auto-discovering plugin system. Dropping a new `platform.py` in the `extractors/` folder automatically adds support for it.*

## Quick Start (Self-Hosting)

Because Linkloader requires a residential IP to work reliably, you run the backend on your own machine. 

### Prerequisites
- Windows OS (for the automated startup script)
- Python 3.12+
- Node.js 20+ (if running the frontend locally)
- [ngrok](https://ngrok.com/) installed (`winget install ngrok.ngrok` from the MS Store)

### 1. Backend Setup (One-Click)
1. Clone the repository.
2. Go to `backend/` and copy `.env.example` to `.env`.
3. Add your `NGROK_AUTHTOKEN` and an optional static `NGROK_DOMAIN` to the `.env` file.
4. Double-click **`start-selfhost.bat`**.

That's it! The batch script automatically activates the virtual environment, starts the FastAPI server, and launches the ngrok tunnel. 

### 2. Frontend Setup
1. Go to `frontend/`.
2. Run `npm install`.
3. Copy `.env.example` to `.env` and set `VITE_API_URL` to your new ngrok domain (e.g., `https://your-domain.ngrok-free.app`).
4. Run `npm run dev`.

Open `http://localhost:5173` and start extracting!

## Privacy & Design Principles

- **Zero Data Stored:** No accounts, no tracking, no databases. Extractions happen in memory and stream directly to the client.
- **Real-time downloads:** Uses `ReadableStream` to proxy downloads directly from the platform to the user, bypassing cors limitations while showing live progress.
- **Minimalist UI:** Built with React, Tailwind v4, and Lucide icons. Respects OS-level reduced motion preferences.

## License

[MIT](LICENSE) © Ace
