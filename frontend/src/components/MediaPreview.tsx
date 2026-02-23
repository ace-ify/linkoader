import { useState } from "react";
import type { MediaInfo } from "../types/media";
import { formatFileSize, formatDuration } from "../lib/format";
import DownloadButton from "./DownloadButton";

interface MediaPreviewProps {
  media: MediaInfo;
}

export default function MediaPreview({ media }: MediaPreviewProps) {
  const [imgLoaded, setImgLoaded] = useState(false);

  const filename = `${media.title.replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-")}.${media.format}`;

  return (
    <div
      className="mt-6 bg-surface border border-border rounded-xl overflow-hidden"
      style={{ animation: "slide-up 200ms ease-out" }}
    >
      <div className="flex flex-col md:flex-row">
        {/* Thumbnail */}
        {media.thumbnail && (
          <div className="md:w-48 md:h-36 w-full h-48 flex-shrink-0 overflow-hidden bg-border">
            <img
              src={media.thumbnail}
              alt={media.title}
              className={`w-full h-full object-cover transition-all duration-300 ${
                imgLoaded ? "blur-0 opacity-100" : "blur-lg opacity-50"
              }`}
              onLoad={() => setImgLoaded(true)}
            />
          </div>
        )}

        {/* Metadata */}
        <div className="flex-1 p-4 flex flex-col justify-center min-w-0">
          <h2 className="text-primary text-sm font-semibold tracking-tighter leading-snug truncate">
            {media.title}
          </h2>

          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <span className="text-xs font-mono text-secondary bg-border px-2 py-0.5 rounded uppercase">
              {media.format}
            </span>
            {media.quality && media.quality !== "0p" && (
              <span className="text-xs font-mono text-secondary">
                {media.quality}
              </span>
            )}
            <span className="text-xs font-mono text-muted">
              {formatFileSize(media.file_size)}
            </span>
            {media.duration && media.duration > 0 && (
              <span className="text-xs font-mono text-muted">
                {formatDuration(media.duration)}
              </span>
            )}
          </div>

          {media.author && (
            <p className="text-xs text-muted mt-1 truncate">{media.author}</p>
          )}

          <p className="text-xs text-muted mt-0.5">{media.platform}</p>
        </div>
      </div>

      <div className="px-4 pb-4">
        <DownloadButton
          downloadUrl={media.download_url}
          filename={filename}
          title={media.title}
        />
      </div>
    </div>
  );
}
