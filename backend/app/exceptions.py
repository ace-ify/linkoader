class ExtractionError(Exception):
    """Base exception for extraction failures."""

    def __init__(self, error_code: str, message: str, status_code: int = 500):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InvalidURLError(ExtractionError):
    def __init__(self, message: str = "URL format is invalid"):
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
