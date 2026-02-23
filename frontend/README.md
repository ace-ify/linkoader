# Linkloader — Frontend

React + TypeScript + Vite frontend for [Linkloader](../README.md).

## Dev Setup

```bash
npm install
cp .env.example .env   # set VITE_API_URL to your backend URL
npm run dev            # http://localhost:5173
```

## Build

```bash
npm run build          # output goes to dist/
```

## Deploy

Hosted on **Vercel**. The `vercel.json` at this directory root configures SPA rewrites so React Router works correctly on all paths.

Set `VITE_API_URL` as an environment variable in your Vercel project to point at the backend.
