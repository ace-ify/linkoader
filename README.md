<a name="top"></a>

<h1 align="center">Linkloader</h1>
<p align="center">Paste any link. Get the file.</p>
<p align="center">
  <a href="#supported-platforms">Platforms</a> ·
  <a href="#local-setup">Local Setup</a> ·
  <a href="#environment-variables">Env Vars</a> ·
  <a href="#adding-a-platform">Extend It</a> ·
  <a href="#deployment">Deployment</a>
</p>

---

Linkloader is a minimal, privacy-respecting media downloader. Users paste a URL from a supported platform and get a direct file download — video, audio, image, or document. No accounts, no tracking, no data stored.

## Supported Platforms

| Platform | Videos | Images | Reels/Shorts |
|---|---|---|---|
| YouTube | ✅ | — | ✅ Shorts |
| Instagram | ✅ | ✅ | ✅ Reels |
| Facebook | ✅ | — | ✅ Reels |
| Pinterest | ✅ | ✅ | — |

More platforms via the extractor plugin system — see [Adding a Platform](#adding-a-platform).

## Architecture

```
linkoader/
├── backend/          # FastAPI — extraction + proxy streaming
│   ├── app/
│   │   ├── extractors/   # One file per platform (auto-discovered)
│   │   ├── main.py       # API routes
│   │   ├── proxy.py      # Streaming proxy with Content-Length forwarding
│   │   ├── router.py     # Auto-discovery of extractors
│   │   ├── models.py     # Pydantic schemas
│   │   └── exceptions.py
│   ├── Dockerfile
│   ├── Procfile
│   └── requirements.txt
└── frontend/         # React + Vite + TypeScript + Tailwind v4
    └── src/
        ├── components/   # DownloadButton (streaming progress), URLInput, etc.
        ├── hooks/        # useExtract
        └── lib/          # api.ts, validate.ts
```

## Local Setup

### Prerequisites
- Python 3.12+
- Node.js 20+

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env          # set VITE_API_URL=http://localhost:8000
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | Server port |
| `ALLOWED_ORIGINS` | `*` | Comma-separated list of allowed CORS origins |
| `RATE_LIMIT_EXTRACT` | `15/minute;100/hour` | Rate limit for `/api/extract` |
| `RATE_LIMIT_PROXY` | `5/minute` | Rate limit for `/api/proxy-download` |

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `` (empty = same origin) | Backend API base URL |

## Adding a Platform

1. Create `backend/app/extractors/yourplatform.py`
2. Implement the `BaseExtractor` interface:

```python
from app.extractors.base import BaseExtractor
from app.models import MediaInfo

class YourPlatformExtractor(BaseExtractor):
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?yourplatform\.com/...",
    ]

    async def extract(self, url: str) -> MediaInfo:
        # fetch, parse, return MediaInfo(...)
        ...
```

3. Restart the backend — it auto-discovers the new extractor. No registration needed.

## Deployment

See [`docs/deployment-plan.md`](docs/deployment-plan.md) for detailed hosting options (Railway, Render, Fly.io, Vercel + backend PaaS, self-hosted Docker).

**Short version:**
- **Frontend** → Vercel (zero-config, `vercel.json` included)
- **Backend** → Railway / Render / Fly.io (Dockerfile + Procfile included)

## Design Principles

- **Monochrome UI** — Inter for text, JetBrains Mono for technical data
- **Privacy first** — no user data stored, no cookies, no analytics
- **Real-time downloads** — fetch + ReadableStream with live progress, speed, and cancel
- **Plugin architecture** — drop a new `.py` file to support a new platform
- **Respects reduced motion** — all animations disabled when OS preference is set

## License

[MIT](LICENSE) © Ace
