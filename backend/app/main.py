import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.datastructures import MutableHeaders

from app.exceptions import ExtractionError, UnsupportedPlatformError
from app.models import ExtractRequest, ErrorResponse
from app.proxy import is_allowed_domain, stream_proxy, get_upstream_headers
from app.rate_limiter import limiter
from app.router import ExtractorRouter

load_dotenv()

router = ExtractorRouter()

_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]


# ---------------------------------------------------------------------------
# CORS wrapper — pure ASGI, wraps the entire FastAPI app
# ---------------------------------------------------------------------------
class CORSWrapper:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        req_headers = dict(scope.get("headers") or [])
        origin = req_headers.get(b"origin", b"").decode()

        allow = "*" in ALLOWED_ORIGINS or origin in ALLOWED_ORIGINS
        cors_origin = origin if (allow and origin) else "*"

        # Preflight — respond immediately, never reaches FastAPI
        if scope["method"] == "OPTIONS":
            headers = [
                (b"access-control-allow-origin", cors_origin.encode()),
                (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
                (b"access-control-allow-headers", b"Content-Type, Authorization"),
                (b"access-control-max-age", b"86400"),
                (b"content-length", b"0"),
            ]
            await send({"type": "http.response.start", "status": 200, "headers": headers})
            await send({"type": "http.response.body", "body": b""})
            return

        # Normal requests — inject CORS header into the response
        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start" and allow:
                headers = MutableHeaders(scope=message)
                headers.append("access-control-allow-origin", cors_origin)
                headers.append("access-control-expose-headers", "Content-Length")
            await send(message)

        await self.app(scope, receive, send_wrapper)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    print(f"Loaded extractors: {router.supported_platforms}")
    yield


_app = FastAPI(title="Linkloader API", version="1.0.0", lifespan=lifespan)
_app.state.limiter = limiter
_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@_app.exception_handler(ExtractionError)
async def extraction_error_handler(request: Request, exc: ExtractionError):
    body = {"error": exc.error_code, "message": exc.message}
    if isinstance(exc, UnsupportedPlatformError):
        body["supported"] = exc.supported
    return JSONResponse(status_code=exc.status_code, content=body)


@_app.post("/api/extract")
@limiter.limit("15/minute;100/hour")
async def extract(request: Request, body: ExtractRequest):
    url = str(body.url)
    extractor = router.resolve(url)
    if not extractor:
        raise UnsupportedPlatformError(supported=router.supported_platforms)
    result = await extractor.extract(url)
    return result.model_dump()


@_app.get("/api/proxy-download")
@limiter.limit("5/minute")
async def proxy_download(
    request: Request,
    url: str = Query(..., description="Direct download URL to proxy"),
    filename: str = Query("download", description="Suggested filename"),
):
    if not is_allowed_domain(url):
        raise HTTPException(status_code=403, detail="Domain not allowed for proxying")

    upstream_headers = await get_upstream_headers(url)

    response_headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "Content-Length",
    }
    if "Content-Length" in upstream_headers:
        response_headers["Content-Length"] = upstream_headers["Content-Length"]

    return StreamingResponse(
        stream_proxy(url),
        media_type="application/octet-stream",
        headers=response_headers,
    )


@_app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "extractors": router.supported_platforms,
    }


# ---------------------------------------------------------------------------
# Export: uvicorn picks up `app` which is the CORS-wrapped ASGI callable
# ---------------------------------------------------------------------------
app = CORSWrapper(_app)
