# Linkloader — Deployment Plan

## Overview

Linkloader is a two-service app:

| Service | Stack | Recommended Host |
|---|---|---|
| **Backend** | FastAPI + uvicorn | Railway / Render / Fly.io |
| **Frontend** | React + Vite (static SPA) | Vercel |

Both services are independent and communicate over HTTP. The frontend calls the backend API and the backend streams downloads through a proxy.

---

## Frontend — Vercel (Recommended)

`vercel.json` is already configured for SPA routing.

### Steps

1. Push the repo to GitHub
2. Go to [vercel.com](https://vercel.com) → **Add New Project** → import the repo
3. Set **Root Directory** to `frontend`
4. Add environment variable:
   ```
   VITE_API_URL=https://your-backend-url.railway.app
   ```
5. Vercel auto-detects Vite — click **Deploy**

### Every subsequent deploy
Push to `main` → Vercel auto-deploys. Zero config needed after initial setup.

---

## Backend — Option A: Railway (Easiest)

Railway auto-detects the `Dockerfile` and `Procfile`.

### Steps

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select the repo, set the **Root Directory** to `backend`
3. Add environment variables in Railway dashboard:
   ```
   PORT=8000
   ALLOWED_ORIGINS=https://your-app.vercel.app
   ```
4. Railway assigns a public URL — paste it into Vercel's `VITE_API_URL`

### Caveat
Railway free tier sleeps after 30 min of inactivity. Upgrade to Hobby ($5/mo) for always-on.

---

## Backend — Option B: Render

1. Go to [render.com](https://render.com) → **New Web Service** → connect GitHub repo
2. Set **Root Directory** to `backend`
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add env vars (same as Railway above)

### Caveat
Free tier spins down after 15 min idle. Starter plan ($7/mo) for always-on.

---

## Backend — Option C: Fly.io

Fly.io is the best option for global low-latency and doesn't sleep.

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

cd backend
fly launch          # follow prompts, set region
fly secrets set ALLOWED_ORIGINS=https://your-app.vercel.app
fly deploy
```

Free allowance covers a small VM 24/7 with no sleep.

---

## Backend — Option D: Self-hosted (Docker)

```bash
cd backend
docker build -t linkloader-backend .
docker run -d \
  -p 8000:8000 \
  -e ALLOWED_ORIGINS=https://yourdomain.com \
  --name linkloader \
  linkloader-backend
```

Use **nginx** as a reverse proxy in front for TLS termination.

---

## CORS Configuration

In production, **always restrict CORS** to your specific frontend domain:

```env
# backend/.env (production)
ALLOWED_ORIGINS=https://your-app.vercel.app
```

During development `*` is fine.

---

## CI/CD — GitHub Actions

Basic workflow to run checks on every push:

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci
      - run: npm run build
```

---

## Environment Variables Reference

### Backend

| Variable | Example | Notes |
|---|---|---|
| `PORT` | `8000` | Port uvicorn listens on |
| `ALLOWED_ORIGINS` | `https://linkloader.vercel.app` | Comma-separated. Use `*` only in dev |
| `RATE_LIMIT_EXTRACT` | `15/minute;100/hour` | SlowAPI format |
| `RATE_LIMIT_PROXY` | `5/minute` | SlowAPI format |

### Frontend

| Variable | Example | Notes |
|---|---|---|
| `VITE_API_URL` | `https://linkloader.railway.app` | Leave empty if same-origin deploy |

---

## Recommended Production Stack (cheapest, reliable)

| | Service | Cost |
|---|---|---|
| Frontend | Vercel Hobby | Free |
| Backend | Fly.io | Free (within allowance) |
| Domain | Cloudflare Registrar | ~$10/yr |
| Total | | **~$10/yr** |
