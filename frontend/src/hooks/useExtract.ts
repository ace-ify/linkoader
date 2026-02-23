import { useState, useCallback } from "react";
import type { MediaInfo } from "../types/media";
import { extractMedia, ApiRequestError } from "../lib/api";

const ERROR_MESSAGES: Record<string, string> = {
  invalid_url: "That doesn't look like a valid URL.",
  unsupported_platform: "This platform isn't supported yet.",
  not_found: "Content not found — it may be private or deleted.",
  upstream_error: "Couldn't reach the platform. Try again.",
  extraction_failed: "Something went wrong extracting this content.",
  rate_limited: "Too many requests.",
  proxy_denied: "Download blocked for security reasons.",
};

export function useExtract() {
  const [data, setData] = useState<MediaInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryAfter, setRetryAfter] = useState<number | undefined>();

  const extract = useCallback(async (url: string) => {
    setLoading(true);
    setError(null);
    setData(null);
    setRetryAfter(undefined);

    try {
      const result = await extractMedia(url);
      setData(result);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(ERROR_MESSAGES[err.error] || err.message);
        setRetryAfter(err.retryAfter);
      } else {
        setError("Network error. Check your connection and try again.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
    setRetryAfter(undefined);
  }, []);

  return { data, loading, error, retryAfter, extract, reset };
}
