export interface MediaInfo {
  platform: string;
  title: string;
  thumbnail: string;
  media_type: "video" | "audio" | "image" | "document";
  format: string;
  quality: string;
  file_size: number;
  download_url: string;
  duration?: number;
  author?: string;
}

export interface ApiError {
  error: string;
  message: string;
  retry_after?: number;
  supported?: string[];
}
