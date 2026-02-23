import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.exceptions import ExtractionError, UnsupportedPlatformError
from app.models import ExtractRequest, ErrorResponse
from app.proxy import is_allowed_domain, stream_proxy, get_upstream_headers
from app.rate_limiter import limiter
from app.router import ExtractorRouter

load_dotenv()

router = ExtractorRouter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Loaded extractors: {router.supported_platforms}")
    yield


app = FastAPI(title="Linkloader API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(ExtractionError)
async def extraction_error_handler(request: Request, exc: ExtractionError):
    body = {"error": exc.error_code, "message": exc.message}
    if isinstance(exc, UnsupportedPlatformError):
        body["supported"] = exc.supported
    return JSONResponse(status_code=exc.status_code, content=body)


@app.post("/api/extract")
@limiter.limit("15/minute;100/hour")
async def extract(request: Request, body: ExtractRequest):
    url = str(body.url)
    extractor = router.resolve(url)
    if not extractor:
        raise UnsupportedPlatformError(supported=router.supported_platforms)
    result = await extractor.extract(url)
    return result.model_dump()


@app.get("/api/proxy-download")
@limiter.limit("5/minute")
async def proxy_download(
    request: Request,
    url: str = Query(..., description="Direct download URL to proxy"),
    filename: str = Query("download", description="Suggested filename"),
):
    if not is_allowed_domain(url):
        raise HTTPException(status_code=403, detail="Domain not allowed for proxying")

    # HEAD the upstream URL so we can forward Content-Length for real progress
    upstream_headers = await get_upstream_headers(url)

    response_headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        # Expose Content-Length so the browser JS can read it cross-origin
        "Access-Control-Expose-Headers": "Content-Length",
    }
    if "Content-Length" in upstream_headers:
        response_headers["Content-Length"] = upstream_headers["Content-Length"]

    return StreamingResponse(
        stream_proxy(url),
        media_type="application/octet-stream",
        headers=response_headers,
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "extractors": router.supported_platforms,
    }
