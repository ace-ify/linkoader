import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.types import ASGIApp, Receive, Scope, Send

from app.exceptions import ExtractionError, UnsupportedPlatformError
from app.models import ExtractRequest, ErrorResponse
from app.proxy import is_allowed_domain, stream_proxy, get_upstream_headers
from app.rate_limiter import limiter
from app.router import ExtractorRouter

load_dotenv()

logger = logging.getLogger("linkloader")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

router = ExtractorRouter()

_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]

# Maximum time we allow an extraction before returning an error.
# Must be LESS than Render/Railway's request timeout (typically 30s).
EXTRACT_TIMEOUT = 25


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
        origin_bytes = cors_origin.encode()

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((b"access-control-allow-origin", origin_bytes))
                headers.append((b"access-control-expose-headers", b"Content-Length"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.stealth import HAS_CURL_CFFI
    logger.info(f"Loaded extractors: {router.supported_platforms}")
    logger.info(f"curl_cffi available: {HAS_CURL_CFFI}")
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
@limiter.limit(os.getenv("RATE_LIMIT_EXTRACT", "15/minute;100/hour"))
async def extract(request: Request, body: ExtractRequest):
    url = str(body.url)
    extractor = router.resolve(url)
    if not extractor:
        raise UnsupportedPlatformError(supported=router.supported_platforms)

    logger.info(f"Extracting [{extractor.platform_name}]: {url}")

    try:
        result = await asyncio.wait_for(
            extractor.extract(url),
            timeout=EXTRACT_TIMEOUT,
        )
        logger.info(f"Success [{extractor.platform_name}]: {result.title[:50]}")
        return result.model_dump()
    except asyncio.TimeoutError:
        logger.warning(f"Timeout [{extractor.platform_name}]: {url} (>{EXTRACT_TIMEOUT}s)")
        return JSONResponse(
            status_code=504,
            content={
                "error": "timeout",
                "message": f"Extraction timed out after {EXTRACT_TIMEOUT}s. "
                           "The platform may be throttling this server. Try again shortly.",
            },
        )
    except ExtractionError:
        raise  # Already handled by extraction_error_handler
    except Exception as e:
        logger.error(f"Unhandled error [{extractor.platform_name}]: {type(e).__name__}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "extraction_failed",
                "message": "Failed to extract media. Try again.",
            },
        )


@_app.get("/api/proxy-download")
@limiter.limit(os.getenv("RATE_LIMIT_PROXY", "5/minute"))
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
