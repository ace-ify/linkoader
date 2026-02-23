import type { MediaInfo, ApiError } from "../types/media";

const API_BASE = import.meta.env.VITE_API_URL || "";
const EXTRACT_TIMEOUT = 35_000; // 35s — slightly above backend's 30s timeout

export class ApiRequestError extends Error {
  error: string;
  retryAfter?: number;
  supported?: string[];

  constructor(
    error: string,
    message: string,
    retryAfter?: number,
    supported?: string[]
  ) {
    super(message);
    this.error = error;
    this.retryAfter = retryAfter;
    this.supported = supported;
  }
}

export async function extractMedia(url: string): Promise<MediaInfo> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), EXTRACT_TIMEOUT);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if ((err as Error).name === "AbortError") {
      throw new ApiRequestError("timeout", "Request timed out — try again.");
    }
    throw new ApiRequestError("network", "Network error. Check your connection.");
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    let errorData: ApiError;
    try {
      errorData = await response.json();
    } catch {
      throw new ApiRequestError("unknown", "An unexpected error occurred");
    }

    // Handle Pydantic 422 validation errors
    if (response.status === 422) {
      throw new ApiRequestError("invalid_url", "That doesn't look like a valid URL.");
    }

    throw new ApiRequestError(
      errorData.error,
      errorData.message,
      errorData.retry_after,
      errorData.supported
    );
  }

  return response.json();
}

export function getProxyDownloadUrl(
  url: string,
  filename?: string
): string {
  const params = new URLSearchParams({ url });
  if (filename) params.set("filename", filename);
  return `${API_BASE}/api/proxy-download?${params.toString()}`;
}
