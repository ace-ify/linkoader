import { useState, useCallback, useRef, useEffect } from "react";
import { getProxyDownloadUrl } from "../lib/api";

type DownloadPhase = "idle" | "connecting" | "downloading" | "saving" | "done" | "error";

interface DownloadButtonProps {
  downloadUrl: string;
  filename: string;
  title: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatSpeed(bytesPerSec: number): string {
  if (bytesPerSec < 1024) return `${bytesPerSec.toFixed(0)} B/s`;
  if (bytesPerSec < 1024 * 1024) return `${(bytesPerSec / 1024).toFixed(1)} KB/s`;
  return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`;
}

export default function DownloadButton({
  downloadUrl,
  filename,
  title,
}: DownloadButtonProps) {
  const [phase, setPhase] = useState<DownloadPhase>("idle");
  const [progress, setProgress] = useState(0);       // 0–100, or -1 = indeterminate
  const [loaded, setLoaded] = useState(0);           // bytes received
  const [total, setTotal] = useState(0);             // bytes total (0 = unknown)
  const [speed, setSpeed] = useState(0);             // bytes/s
  const [errorMsg, setErrorMsg] = useState("");

  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speedRef = useRef({ lastBytes: 0, lastTime: 0 });

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleDownload = useCallback(async () => {
    if (phase !== "idle" && phase !== "error") return;

    // Reset state
    setPhase("connecting");
    setProgress(-1);
    setLoaded(0);
    setTotal(0);
    setSpeed(0);
    setErrorMsg("");
    speedRef.current = { lastBytes: 0, lastTime: performance.now() };

    const abort = new AbortController();
    abortRef.current = abort;
    const proxyUrl = getProxyDownloadUrl(downloadUrl, filename);

    try {
      const response = await fetch(proxyUrl, { signal: abort.signal });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }
      if (!response.body) {
        throw new Error("No response stream available");
      }

      const contentLength = response.headers.get("Content-Length");
      const totalBytes = contentLength ? parseInt(contentLength, 10) : 0;
      setTotal(totalBytes);
      setPhase("downloading");
      setProgress(totalBytes > 0 ? 0 : -1);

      // Stream the body chunk by chunk
      const reader = response.body.getReader();
      const chunks: Uint8Array[] = [];
      let receivedBytes = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (abort.signal.aborted) throw new DOMException("Aborted", "AbortError");

        chunks.push(value);
        receivedBytes += value.byteLength;
        setLoaded(receivedBytes);

        // Progress percentage
        if (totalBytes > 0) {
          setProgress(Math.min(99, (receivedBytes / totalBytes) * 100));
        }

        // Speed calculation (rolling, every ~300ms worth of data)
        const now = performance.now();
        const elapsed = (now - speedRef.current.lastTime) / 1000;
        if (elapsed >= 0.3) {
          const deltaBytes = receivedBytes - speedRef.current.lastBytes;
          setSpeed(deltaBytes / elapsed);
          speedRef.current = { lastBytes: receivedBytes, lastTime: now };
        }
      }

      // Assemble blob and trigger save
      setPhase("saving");
      setProgress(100);

      const blob = new Blob(chunks, { type: "application/octet-stream" });
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Small delay so the "saving" state is visible
      await new Promise((r) => setTimeout(r, 400));
      URL.revokeObjectURL(blobUrl);

      setPhase("done");
      timerRef.current = setTimeout(() => {
        setPhase("idle");
        setProgress(0);
        setLoaded(0);
        setTotal(0);
        setSpeed(0);
      }, 3500);
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setPhase("idle");
        return;
      }
      setPhase("error");
      setErrorMsg((err as Error).message || "Download failed");
      timerRef.current = setTimeout(() => setPhase("idle"), 4000);
    }
  }, [downloadUrl, filename, phase]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    setPhase("idle");
    setProgress(0);
    setLoaded(0);
    setSpeed(0);
  }, []);

  // ─── Derived UI values ──────────────────────────────────────────────────────
  const isActive = phase === "connecting" || phase === "downloading" || phase === "saving";
  const isIndeterminate = progress < 0 || phase === "connecting" || phase === "saving";

  const labelMap: Record<DownloadPhase, string> = {
    idle: "↓  Download",
    connecting: "Connecting…",
    downloading:
      total > 0
        ? `${formatBytes(loaded)} / ${formatBytes(total)}  ·  ${formatSpeed(speed)}`
        : `${formatBytes(loaded)}  ·  ${formatSpeed(speed)}`,
    saving: "Saving file…",
    done: "Saved  ✓",
    error: errorMsg || "Error — retry",
  };

  // Progress bar width for the fill segment
  const barWidth = isIndeterminate ? "100%" : `${progress}%`;

  return (
    <div className="w-full mt-4 space-y-2">
      <button
        onClick={isActive ? handleCancel : handleDownload}
        disabled={phase === "saving" || phase === "done"}
        aria-label={isActive ? `Cancel download of ${title}` : `Download ${title}`}
        className={`
          relative w-full py-3 px-6 rounded-lg text-sm font-semibold overflow-hidden
          transition-all duration-200 cursor-pointer
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20
          disabled:cursor-default
          ${
            phase === "error"
              ? "border border-[rgba(255,68,68,0.4)] text-[rgba(255,100,100,0.9)]"
              : phase === "done"
              ? "border border-border text-primary"
              : "border border-border text-primary hover:bg-surface-hover hover:border-secondary/30"
          }
        `}
      >
        {/* ── Progress fill bar (sits behind text) ─────────────────────── */}
        {isActive && (
          <span
            aria-hidden="true"
            className={`
              absolute inset-0 rounded-lg pointer-events-none
              transition-all duration-300 ease-out
              ${isIndeterminate ? "animate-[indeterminate-slide_1.4s_ease-in-out_infinite]" : ""}
            `}
            style={{
              background: isIndeterminate
                ? "linear-gradient(90deg, transparent 0%, rgba(250,250,250,0.06) 50%, transparent 100%)"
                : `linear-gradient(90deg, rgba(250,250,250,0.07) ${barWidth}, transparent ${barWidth})`,
              width: isIndeterminate ? "200%" : "100%",
            }}
          />
        )}

        {/* ── Button label ──────────────────────────────────────────────── */}
        <span className="relative z-10 flex items-center justify-center gap-2">
          {phase === "downloading" && (
            <span
              className="text-xs font-mono text-secondary"
              style={{ letterSpacing: "0.01em" }}
            >
              {total > 0
                ? `${Math.round(progress)}%`
                : "···"}
            </span>
          )}
          <span>{labelMap[phase]}</span>
          {isActive && phase !== "saving" && (
            <span className="ml-auto text-xs text-secondary opacity-60 hover:opacity-100 transition-opacity">
              ✕
            </span>
          )}
        </span>
      </button>

      {/* ── Thin pixel progress track below button ──────────────────────── */}
      {isActive && (
        <div
          className="w-full h-px rounded-full overflow-hidden"
          style={{ background: "rgba(250,250,250,0.08)" }}
          role="progressbar"
          aria-valuenow={isIndeterminate ? undefined : Math.round(progress)}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full transition-all duration-300 ease-out"
            style={{
              width: isIndeterminate ? "40%" : barWidth,
              background: "rgba(250,250,250,0.55)",
              animation: isIndeterminate
                ? "indeterminate-track 1.4s ease-in-out infinite"
                : undefined,
            }}
          />
        </div>
      )}
    </div>
  );
}
