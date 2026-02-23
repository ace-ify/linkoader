import type { MediaInfo, ApiError } from "../types/media";

const API_BASE = import.meta.env.VITE_API_URL || "";

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
  const response = await fetch(`${API_BASE}/api/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    let errorData: ApiError;
    try {
      errorData = await response.json();
    } catch {
      throw new ApiRequestError("unknown", "An unexpected error occurred");
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
