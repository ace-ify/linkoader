<a name="top"></a>

<h1 align="center">Linkloader</h1>
<p align="center"><strong>The stealthy, self-hosted universal media extractor.</strong></p>

<p align="center">
  <img alt="GitHub License" src="https://img.shields.io/github/license/ace-ify/linkoader?style=flat-square&color=blue">
  <img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/ace-ify/linkoader?style=flat-square&color=yellow">
  <img alt="Python Version" src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square&logo=python">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi">
  <img alt="React" src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB">
</p>

<p align="center">
  <a href="#✨-features">Features</a> ·
  <a href="#🛡️-the-architecture-bypassing-anti-bot-defenses">Architecture</a> ·
  <a href="#📥-supported-platforms">Platforms</a> ·
  <a href="#🚀-quick-start-self-hosting">Self-Hosting</a> ·
  <a href="#🤝-contributing">Contributing</a>
</p>

---

**Linkloader** is a minimal, privacy-respecting media downloader. Paste a URL from a supported social platform and get a direct file download (video, audio, or image) at maximum quality—no accounts, no tracking, no databases.

*Built as **Project 1 of my [#SudoShipIt Challenge](https://www.linkedin.com/hashtag/sudoshipit/)** (6 projects in 6 weeks).*

<p align="center">
  <img src=".\docs\Screenshot 2026-03-01 190825.png" alt="Linkloader Application Interface" width="600" />
</p>

---

## ✨ Features

- **🚀 Universal Extraction:** One input box handles YouTube, Instagram, Pinterest, and more.
- **🕵️‍♂️ Stealth Mode Routing:** Uses your residential IP and TLS fingerprint spoofing (`curl_cffi`) to completely bypass datacenter bot-blocks. 
- **⚡ Real-time Stream Proxying:** Large files aren't saved to a server. They are piped in real-time from the source straight to the client via `ReadableStream`.
- **🔌 Plug-and-Play Architecture:** Adding a new platform is as easy as dropping a `.py` file into the `extractors/` folder. Auto-discovery handles the rest.
- **🎨 Modern Aesthetic:** Built with React, Tailwind v4, and Lucide icons in a sleek monochrome design that respects OS reduced-motion preferences.

## 🛡️ The Architecture: Bypassing Anti-Bot Defenses

Modern social platforms (YouTube, Pinterest, Instagram) employ aggressive anti-bot protections. Generic cloud deployments (like Render, AWS, or Fly.io) use known datacenter IP ranges, which are instantly flagged and shadowbanned when attempting to extract media.

**The Solution: Self-Hosting & Residential IPs**

Linkloader bypasses these restrictions by running the extraction engine locally on your personal machine (using your residential IP), while serving the frontend cleanly on the web. 

1. **Frontend:** Hosted statitcally on Vercel.
2. **Backend:** Runs locally via Python FastAPI.
3. **The Bridge:** We use `ngrok` to securely tunnel the local backend to a permanent public URL, which the frontend communicates with.

By using residential IPs combined with TLS fingerprint spoofing (`curl_cffi`), the platforms see standard user traffic, allowing fast and reliable extractions without the need for expensive rotating proxy pools.

## 📥 Supported Platforms

| Platform | Videos | Images | Audio/Music | Supported Extractors |
|---|:---:|:---:|:---:|---|
| **YouTube** | ✅ | — | ✅ | `yt-dlp`, Direct InnerTube API |
| **Instagram** | ✅ | ✅ | — | Private API, GraphQL |
| **Pinterest** | ✅ | ✅ | — | DOM Parsing, Web API |
| **TikTok** | ✅ | ✅ | ✅ | Web API, Regex Extraction |
| **Twitter / X** | ✅ | ✅ | — | Guest API |
| **Reddit** | ✅ | ✅ | — | JSON API |
| **Facebook** | ✅ | — | — | Mobile API |
| **Snapchat** | ✅ | ✅ | — | Web API |
| **Threads** | ✅ | ✅ | — | GraphQL API |
| **Twitch** | ✅ | — | ✅ | GQL API |
| **Spotify** | — | — | ✅ | Web API |
| **LinkedIn** | ✅ | ✅ | — | Web API |
| **Dailymotion** | ✅ | — | — | GraphQL API |

*Linkloader uses an auto-discovering plugin system. Dropping a new `platform.py` in the `extractors/` folder automatically adds support for it.*

## 🚀 Quick Start (Self-Hosting)

Because Linkloader requires a residential IP to work reliably, you must run the backend on your own machine. 

### Prerequisites
- Windows OS (for the automated startup script)
- Python 3.12+
- Node.js 20+ (if running the frontend locally)
- [ngrok](https://ngrok.com/) installed (`winget install ngrok.ngrok` from the MS Store)

### 1. Backend Setup (One-Click)
1. Clone the repository: `git clone https://github.com/ace-ify/linkoader.git`
2. Go to `backend/` and copy `.env.example` to `.env`.
3. Add your `NGROK_AUTHTOKEN` and an optional static `NGROK_DOMAIN` to the `.env` file.
4. Double-click **`start-selfhost.bat`**.

That's it! The batch script automatically creates the virtual environment, installs dependencies, starts the FastAPI server, and launches the ngrok tunnel. 

### 2. Frontend Setup
1. Go to `frontend/`.
2. Run `npm install`.
3. Copy `.env.example` to `.env` and set `VITE_API_URL` to your new ngrok domain (e.g., `https://your-domain.ngrok-free.app`).
4. Run `npm run dev`.

Open `http://localhost:5173` and start extracting!

## 🤝 Contributing

Contributions are completely welcome! If you want to add a new platform extractor or improve the UI:
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

**How to add an extractor:** Create a file in `backend/app/extractors/` that inherits from `BaseExtractor` and provides a Regex pattern. The app will auto-import it.

## 📜 License

Distributed under the [MIT](LICENSE) License. © Ace

---
<p align="center"><a href="#top">Back to top</a></p>
